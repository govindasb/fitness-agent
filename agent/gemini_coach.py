import json

from google import genai
from google.genai import types
from pydantic import ValidationError

from agent.gemini_schema import sanitize_schema_for_gemini
from config.gemini import get_gemini_api_key, get_gemini_model
from models.coaching_response import CoachingResponse


COACHING_INSTRUCTIONS = """You are an evidence-aware fitness coach and structured
extractor of coaching output. Use only facts in the supplied CoachingContext.
Treat targets as configured targets, not medical prescriptions. Respect every
constraint: missing data is not zero, absence of a log is not proof behavior did
not occur, and sparse data must not be extrapolated. Never invent fitness
values, adherence, or medical conclusions. Do not upgrade limited or
insufficient evidence.

STRUCTURED DECISION RULES:
- GENERAL GUIDANCE: basis="general_guidance", requires_adherence_evidence=false,
  adherence_metric=null. Logging-consistency and routine-tracking advice is
  general guidance even when the domain has a configured target.
- ADHERENCE-DEPENDENT ADVICE: set requires_adherence_evidence=true only when
  the recommendation depends on concluding that a configured target was met,
  missed, exceeded, or otherwise adhered to. Then adherence_metric is required
  (calories, protein, steps, or training) and its can_assess_* permission must
  be true. If permission is false, do not make that recommendation.
- INSUFFICIENT EVIDENCE: use limited/insufficient observations and/or a data_gap;
  general guidance remains allowed. Never turn insufficient evidence into a
  target conclusion.

Nutrition distinctions matter: no food logs, food logs with unavailable
calories/protein, and complete calorie/protein coverage are different states.
Food presence does not make nutrient adherence assessable. Training counts are
logged observations, not proof of complete real-world training; when training
permission is false, do not extrapolate or claim a target was met/missed.
Likewise, sparse step data describes recorded days only and must not be treated
as representative of the week. Prefer a small number of useful
recommendations. When deterministic context explicitly establishes missing or
incomplete data for a supported domain, and that missingness is relevant to the
summary, observations, or recommendations, represent it consistently in
data_gaps. Do not omit an explicitly established missing domain merely because
other gaps are listed; do not create a gap unless the context establishes it.
The deterministic grounding validator, not this instruction, is the final
authority."""


class GeminiCoachingError(RuntimeError):
    pass


class GeminiFitnessCoach:
    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self.model = model or get_gemini_model()
        self.last_usage: dict[str, int | None] | None = None

    def _client_or_create(self):
        if self._client is None:
            self._client = genai.Client(api_key=get_gemini_api_key())
        return self._client

    @staticmethod
    def _payload(context: dict) -> dict:
        # Keep the adapter from forwarding accidental raw-event data.
        return {key: value for key, value in context.items() if key != "raw_events"}

    def coach(self, context: dict) -> CoachingResponse:
        self.last_usage = None
        payload = self._payload(context)
        schema = sanitize_schema_for_gemini(CoachingResponse.model_json_schema())
        try:
            response = self._client_or_create().models.generate_content(
                model=self.model,
                contents=json.dumps(payload, sort_keys=True, separators=(",", ":")),
                config=types.GenerateContentConfig(
                    system_instruction=COACHING_INSTRUCTIONS,
                    response_mime_type="application/json",
                    response_json_schema=schema,
                    temperature=0.2,
                ),
            )
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                self.last_usage = {
                    "input_tokens": getattr(usage, "prompt_token_count", None),
                    "output_tokens": getattr(usage, "candidates_token_count", None),
                    "total_tokens": getattr(usage, "total_token_count", None),
                }
            parsed = getattr(response, "parsed", None)
            if parsed is None and getattr(response, "text", None):
                parsed = json.loads(response.text)
            if parsed is None:
                raise GeminiCoachingError("Gemini returned no structured coaching response")
            return CoachingResponse.model_validate(parsed)
        except GeminiCoachingError:
            raise
        except (ValidationError, json.JSONDecodeError) as exc:
            raise GeminiCoachingError(f"Gemini coaching output was invalid: {exc}") from exc
        except Exception as exc:
            raise GeminiCoachingError(f"Gemini coaching failed: {exc}") from exc

from datetime import datetime
import json

from google import genai
from google.genai import types

from agent.interpreter import (
    InterpretationResult,
    RelativeTimeResolver,
    normalize_interpretation_result,
)
from config.gemini import get_gemini_api_key, get_gemini_model
from agent.gemini_schema import (
    GEMINI_UNSUPPORTED_SCHEMA_KEYS,
    sanitize_schema_for_gemini,
)
from database.timezone import (
    APPLICATION_TIMEZONE,
    require_aware,
    to_application_timezone,
    utc_now,
)


EXTRACTION_INSTRUCTIONS = """You extract fitness facts from one user message.
You are an information extractor, not a coach. Extract only supported facts
into body_metrics, food_entries, activities, sleep_entries, workouts, and
workout sets. Unknown values must be null. Never give advice, estimate
nutrition, calculate targets, invent measurements, infer unstated
sets/reps/weights, or add facts not supported by the message. When an exact
repeated set count is stated with shared reps/load, emit one ordered
exercise-set record per stated set.

For the exact phrases today, yesterday, this morning, tonight, and last night,
set the record's time_expression to that exact label and leave its concrete
timestamp fields null. Application code resolves those labels. Do not choose
calendar timestamps for relative phrases. Preserve unclear substantial content
in unparsed_fragments and describe interpretation concerns in warnings.
If the message supplies a temporal expression outside those supported labels,
set the affected record's time_status to "unsupported", leave its timestamp
and time_expression null, and preserve the complete relevant fitness clause in
unparsed_fragments. If no time is supplied, leave time_status null.

Do not convert units unless the destination field directly represents the
stated unit. In particular, do not place pounds into a kilogram field.
"""


class GeminiInterpretationError(RuntimeError):
    pass


class GeminiFitnessInterpreter:
    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self.model = model or get_gemini_model()
        self.last_usage: dict[str, int | None] | None = None

    def _client_or_create(self):
        if self._client is None:
            self._client = genai.Client(api_key=get_gemini_api_key())
        return self._client

    def interpret(
        self,
        raw_text: str,
        reference: datetime | None = None,
    ) -> InterpretationResult:
        fixed_reference = reference or utc_now()
        require_aware(fixed_reference)
        self.last_usage = None
        local_reference = to_application_timezone(fixed_reference)
        instructions = (
            f"{EXTRACTION_INSTRUCTIONS}\n"
            f"Reference timestamp: {local_reference.isoformat()}\n"
            f"Application timezone: {APPLICATION_TIMEZONE}\n"
            "Apply the documented relative-time labels exactly; application "
            "code will resolve them against this reference."
        )
        provider_schema = sanitize_schema_for_gemini(
            InterpretationResult.model_json_schema()
        )

        try:
            response = self._client_or_create().models.generate_content(
                model=self.model,
                contents=raw_text,
                config=types.GenerateContentConfig(
                    system_instruction=instructions,
                    response_mime_type="application/json",
                    response_json_schema=provider_schema,
                    temperature=0,
                ),
            )
            self.last_usage = self._map_usage(
                getattr(response, "usage_metadata", None)
            )
            parsed = getattr(response, "parsed", None)
            if parsed is None and getattr(response, "text", None):
                parsed = json.loads(response.text)
            if parsed is None:
                raise GeminiInterpretationError(
                    "Gemini returned no structured interpretation; the "
                    "response may have been blocked or incomplete."
                )
            validated = InterpretationResult.model_validate(parsed)
            return self._resolve_relative_times(validated, fixed_reference)
        except GeminiInterpretationError:
            raise
        except Exception as exc:
            raise GeminiInterpretationError(
                f"Gemini interpretation failed: {exc}"
            ) from exc

    @staticmethod
    def _map_usage(usage) -> dict[str, int | None] | None:
        if usage is None:
            return None
        return {
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        }

    @staticmethod
    def _resolve_relative_times(
        result: InterpretationResult,
        reference: datetime,
    ) -> InterpretationResult:
        result = InterpretationResult.model_validate(result.model_dump())
        resolver = RelativeTimeResolver(reference)

        for item in result.parsed_input.body_metrics:
            if item.measured_at is not None:
                require_aware(item.measured_at)
            if item.time_expression:
                resolved = resolver.resolve(item.time_expression)
                if resolved and resolved.timestamp:
                    item.measured_at = resolved.timestamp

        for entry in result.parsed_input.food_entries:
            if entry.consumed_at is not None:
                require_aware(entry.consumed_at)
            if entry.time_expression:
                resolved = resolver.resolve(entry.time_expression)
                if resolved and resolved.timestamp:
                    entry.consumed_at = resolved.timestamp

        for item in result.parsed_input.activities:
            if item.recorded_at is not None:
                require_aware(item.recorded_at)
            if item.time_expression:
                resolved = resolver.resolve(item.time_expression)
                if resolved and resolved.timestamp:
                    item.recorded_at = resolved.timestamp

        for entry in result.parsed_input.workouts:
            if entry.started_at is not None:
                require_aware(entry.started_at)
            if entry.time_expression:
                resolved = resolver.resolve(entry.time_expression)
                if resolved and resolved.timestamp:
                    entry.started_at = resolved.timestamp

        for item in result.parsed_input.sleep_entries:
            if item.sleep_start is not None:
                require_aware(item.sleep_start)
            if item.sleep_end is not None:
                require_aware(item.sleep_end)
            if item.time_expression:
                resolved = resolver.resolve(item.time_expression)
                if resolved:
                    if resolved.sleep_start:
                        item.sleep_start = resolved.sleep_start
                    if resolved.sleep_end:
                        item.sleep_end = resolved.sleep_end

        return normalize_interpretation_result(result)

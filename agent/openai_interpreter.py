from datetime import datetime

from openai import OpenAI

from agent.interpreter import (
    InterpretationResult,
    RelativeTimeResolver,
    normalize_interpretation_result,
)
from config.openai import get_openai_api_key, get_openai_model
from database.timezone import (
    APPLICATION_TIMEZONE,
    require_aware,
    to_application_timezone,
    utc_now,
)


EXTRACTION_INSTRUCTIONS = """You extract fitness facts from one user message. Return only the structured
InterpretationResult requested by the response schema.

Extract only supported facts into body_metrics, food_entries, activities,
sleep_entries, workouts, and workout sets. Unknown values must be null. Never
give advice, estimate nutrition, calculate targets, invent measurements, infer
unstated sets/reps/weights, or add facts not supported by the message.
When an exact repeated set count is stated with shared reps/load, emit one
ordered exercise-set record per stated set.

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


class OpenAIInterpretationError(RuntimeError):
    pass


class OpenAIFitnessInterpreter:
    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self.model = model or get_openai_model()
        self.last_usage: dict[str, int] | None = None

    def _client_or_create(self):
        if self._client is None:
            self._client = OpenAI(api_key=get_openai_api_key())
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

        try:
            response = self._client_or_create().responses.parse(
                model=self.model,
                instructions=instructions,
                input=raw_text,
                text_format=InterpretationResult,
                store=False,
            )
            if getattr(response, "status", None) != "completed":
                raise OpenAIInterpretationError(
                    "OpenAI returned an incomplete interpretation response."
                )
            if response.output_parsed is None:
                raise OpenAIInterpretationError(
                    "OpenAI returned no structured interpretation."
                )
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.last_usage = {
                    name: int(getattr(usage, name, 0) or 0)
                    for name in (
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                    )
                }
            parsed = InterpretationResult.model_validate(
                response.output_parsed,
            )
            return self._resolve_relative_times(parsed, fixed_reference)
        except OpenAIInterpretationError:
            raise
        except Exception as exc:
            raise OpenAIInterpretationError(
                f"OpenAI interpretation failed: {exc}"
            ) from exc

    @staticmethod
    def _resolve_relative_times(
        result: InterpretationResult,
        reference: datetime,
    ) -> InterpretationResult:
        result = InterpretationResult.model_validate(
            result.model_dump(),
        )
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

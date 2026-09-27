from datetime import date, datetime, time, timedelta
import json
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from database.timezone import APPLICATION_TIMEZONE, to_application_timezone
from models.parsed_input import ParsedInput


class InterpretationResult(BaseModel):
    parsed_input: ParsedInput
    warnings: list[str] = Field(default_factory=list)
    unparsed_fragments: list[str] = Field(default_factory=list)


WORKOUT_LABEL_ALIASES = {
    "run": "running",
}


def normalize_fitness_label(value: str | None) -> str | None:
    """Normalize a controlled categorical fitness label without fuzzy matching."""
    if value is None:
        return None
    normalized = value.strip().lower()
    return WORKOUT_LABEL_ALIASES.get(normalized, normalized)


def _meaningful(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _keep_record(record, values) -> bool:
    """Keep facts unless an explicitly unsupported time makes them unsafe."""
    time_values = values["time"]
    if (
        record.time_status == "unsupported"
        and not any(_meaningful(value) for value in time_values)
    ):
        return False
    return any(_meaningful(value) for value in values["data"] + time_values)


def normalize_interpretation_result(
    result: InterpretationResult,
) -> InterpretationResult:
    """Remove domain records with no extracted facts, preserving metadata."""
    normalized = InterpretationResult.model_validate(result.model_dump())
    parsed = normalized.parsed_input
    for entry in parsed.food_entries:
        entry.meal_type = normalize_fitness_label(entry.meal_type)
    for entry in parsed.workouts:
        entry.workout_type = normalize_fitness_label(entry.workout_type)
        for exercise_set in entry.sets:
            exercise_set.exercise_name = normalize_fitness_label(
                exercise_set.exercise_name
            ) or ""
    parsed.body_metrics = [
        item
        for item in parsed.body_metrics
        if _keep_record(
            item,
            {
                "data": [
                    item.weight_kg,
                    item.waist_cm,
                    item.body_fat_percent,
                    item.resting_heart_rate,
                ],
                "time": [item.measured_at, item.time_expression],
            },
        )
    ]
    parsed.activities = [
        item
        for item in parsed.activities
        if _keep_record(
            item,
            {
                "data": [
                    item.steps,
                    item.distance_km,
                    item.active_minutes,
                    item.calories_burned,
                ],
                "time": [item.recorded_at, item.time_expression],
            },
        )
    ]
    parsed.food_entries = [
        entry
        for entry in parsed.food_entries
        if _keep_record(
            entry,
            {
                "data": [entry.meal_type, entry.items],
                "time": [entry.consumed_at, entry.time_expression],
            },
        )
    ]
    parsed.workouts = [
        entry
        for entry in parsed.workouts
        if _keep_record(
            entry,
            {
                "data": [
                    entry.workout_type,
                    entry.duration_minutes,
                    entry.notes,
                    entry.sets,
                ],
                "time": [entry.started_at, entry.time_expression],
            },
        )
    ]
    parsed.sleep_entries = [
        entry
        for entry in parsed.sleep_entries
        if _keep_record(
            entry,
            {
                "data": [entry.duration_minutes, entry.quality_rating, entry.notes],
                "time": [
                    entry.sleep_start,
                    entry.sleep_end,
                    entry.time_expression,
                ],
            },
        )
    ]
    return normalized


@runtime_checkable
class FitnessInterpreter(Protocol):
    def interpret(
        self,
        raw_text: str,
        reference: datetime | None = None,
    ) -> InterpretationResult | ParsedInput | dict:
        ...


class StaticInterpreter:
    """Deterministic interpreter for tests and explicitly structured demos."""

    def __init__(self, result):
        self.result = result

    def interpret(self, raw_text: str, reference: datetime | None = None):
        return self.result


class JsonInterpreter:
    """Parse explicitly supplied JSON after raw-event preservation."""

    def __init__(self, payload: str):
        self.payload = payload

    def interpret(self, raw_text: str, reference: datetime | None = None):
        return json.loads(self.payload)


class ResolvedTime(BaseModel):
    timestamp: datetime | None = None
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None


class RelativeTimeResolver:
    def __init__(self, reference: datetime):
        self.reference = to_application_timezone(reference)

    @staticmethod
    def _at(local_date: date, hour: int) -> datetime:
        return datetime.combine(
            local_date,
            time(hour=hour),
            tzinfo=APPLICATION_TIMEZONE,
        )

    def resolve(self, expression: str) -> ResolvedTime | None:
        normalized = expression.strip().lower()
        today = self.reference.date()

        if normalized == "today":
            return ResolvedTime(timestamp=self.reference)
        if normalized == "yesterday":
            return ResolvedTime(
                timestamp=self.reference - timedelta(days=1)
            )
        if normalized == "this morning":
            return ResolvedTime(timestamp=self._at(today, 8))
        if normalized == "tonight":
            return ResolvedTime(timestamp=self._at(today, 20))
        if normalized == "last night":
            return ResolvedTime(
                sleep_start=self._at(today - timedelta(days=1), 22),
                sleep_end=self._at(today, 7),
            )
        return None

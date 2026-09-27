from datetime import datetime

from pydantic import BaseModel, Field

from models.time_expression import RelativeTimeExpression, TimeResolutionStatus


class ParsedExerciseSet(BaseModel):
    exercise_name: str
    set_number: int | None = Field(default=None, ge=1)

    weight_kg: float | None = Field(default=None, ge=0)
    reps: int | None = Field(default=None, ge=0)

    duration_seconds: int | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)

    rpe: float | None = Field(default=None, ge=0, le=10)


class ParsedWorkout(BaseModel):
    workout_type: str | None = None
    started_at: datetime | None = None
    time_expression: RelativeTimeExpression | None = None
    time_status: TimeResolutionStatus | None = None

    duration_minutes: int | None = Field(default=None, ge=0, le=1440)

    notes: str | None = None
    sets: list[ParsedExerciseSet]

from datetime import datetime

from pydantic import BaseModel, Field

from models.time_expression import RelativeTimeExpression, TimeResolutionStatus


class ParsedActivity(BaseModel):
    recorded_at: datetime | None = None
    time_expression: RelativeTimeExpression | None = None
    time_status: TimeResolutionStatus | None = None

    steps: int | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    active_minutes: int | None = Field(default=None, ge=0)
    calories_burned: float | None = Field(default=None, ge=0)

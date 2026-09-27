from datetime import datetime

from pydantic import BaseModel, Field

from models.time_expression import RelativeTimeExpression, TimeResolutionStatus


class ParsedSleep(BaseModel):
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    time_expression: RelativeTimeExpression | None = None
    time_status: TimeResolutionStatus | None = None

    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    quality_rating: int | None = Field(default=None, ge=1, le=10)

    notes: str | None = None

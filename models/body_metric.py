from datetime import datetime

from pydantic import BaseModel, Field

from models.time_expression import RelativeTimeExpression, TimeResolutionStatus


class ParsedBodyMetric(BaseModel):
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    waist_cm: float | None = Field(default=None, gt=0, le=300)
    body_fat_percent: float | None = Field(default=None, ge=0, le=100)
    resting_heart_rate: int | None = Field(default=None, ge=20, le=250)
    measured_at: datetime | None = None
    time_expression: RelativeTimeExpression | None = None
    time_status: TimeResolutionStatus | None = None

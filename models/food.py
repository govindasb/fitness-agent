from datetime import datetime

from pydantic import BaseModel, Field

from models.time_expression import RelativeTimeExpression, TimeResolutionStatus


class ParsedFoodItem(BaseModel):
    food_name: str

    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None

    estimated_calories: float | None = Field(default=None, ge=0)
    protein_g: float | None = Field(default=None, ge=0)
    carbs_g: float | None = Field(default=None, ge=0)
    fat_g: float | None = Field(default=None, ge=0)
    fiber_g: float | None = Field(default=None, ge=0)

    is_estimated: bool = True


class ParsedFoodEntry(BaseModel):
    meal_type: str | None = None
    consumed_at: datetime | None = None
    time_expression: RelativeTimeExpression | None = None
    time_status: TimeResolutionStatus | None = None
    items: list[ParsedFoodItem]

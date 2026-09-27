from pydantic import BaseModel, Field


class CoachingTargets(BaseModel):
    """Current behavioral targets used by future coaching analytics.

    These targets are intentionally separate from the user's profile: targets
    can change without changing identity or baseline information.
    """

    daily_calories: int = Field(gt=0)
    daily_protein_g: float = Field(gt=0)
    daily_steps: int = Field(ge=0)
    strength_sessions_per_week: int = Field(ge=0)
    cardio_sessions_per_week: int = Field(ge=0)

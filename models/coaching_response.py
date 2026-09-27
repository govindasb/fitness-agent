from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoachingDomain(StrEnum):
    WEIGHT = "weight"
    NUTRITION = "nutrition"
    ACTIVITY = "activity"
    SLEEP = "sleep"
    TRAINING = "training"
    RECOVERY = "recovery"
    GENERAL = "general"


class EvidenceStatus(StrEnum):
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class RecommendationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationBasis(StrEnum):
    OBSERVED_DATA = "observed_data"
    CONFIGURED_TARGET = "configured_target"
    GENERAL_GUIDANCE = "general_guidance"


class AdherenceMetric(StrEnum):
    CALORIES = "calories"
    PROTEIN = "protein"
    STEPS = "steps"
    TRAINING = "training"


class _StrictTextModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "message",
        "action",
        "missing_information",
        "metric",
        "suggested_logging_action",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class CoachingObservation(_StrictTextModel):
    domain: CoachingDomain
    message: str = Field(min_length=1, max_length=300)
    evidence_status: EvidenceStatus
    metric: str | None = Field(default=None, min_length=1, max_length=80)
    adherence_metric: AdherenceMetric | None = None


class CoachingRecommendation(_StrictTextModel):
    domain: CoachingDomain
    action: str = Field(min_length=1, max_length=300)
    priority: RecommendationPriority
    basis: RecommendationBasis
    requires_adherence_evidence: bool
    adherence_metric: AdherenceMetric | None = None


class CoachingDataGap(_StrictTextModel):
    domain: CoachingDomain
    missing_information: str = Field(min_length=1, max_length=300)
    suggested_logging_action: str | None = Field(default=None, min_length=1, max_length=300)
    adherence_metric: AdherenceMetric | None = None


class CoachingSafety(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medical_escalation_needed: bool = False
    reason: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class CoachingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=500)
    observations: list[CoachingObservation] = Field(default_factory=list, max_length=8)
    recommendations: list[CoachingRecommendation] = Field(default_factory=list, max_length=6)
    data_gaps: list[CoachingDataGap] = Field(default_factory=list, max_length=6)
    safety: CoachingSafety = Field(default_factory=CoachingSafety)

    @field_validator("summary", mode="before")
    @classmethod
    def trim_summary(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

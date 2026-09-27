from dataclasses import dataclass

from models.coaching_response import (
    AdherenceMetric,
    CoachingResponse,
    EvidenceStatus,
    RecommendationBasis,
)


@dataclass(frozen=True)
class GroundingViolation:
    section: str
    code: str
    message: str
    domain: str | None = None
    metric: str | None = None
    index: int | None = None


class CoachingGroundingError(ValueError):
    def __init__(self, violations: list[GroundingViolation]):
        self.violations = tuple(violations)
        super().__init__("Coaching response failed deterministic grounding")


def _permission(context: dict, metric: AdherenceMetric) -> bool:
    return bool(context.get("constraints", {}).get({
        AdherenceMetric.CALORIES: "can_assess_calorie_adherence",
        AdherenceMetric.PROTEIN: "can_assess_protein_adherence",
        AdherenceMetric.STEPS: "can_assess_step_adherence",
        AdherenceMetric.TRAINING: "can_assess_training_adherence",
    }[metric], False))


def _has_observations(context: dict, domain: str) -> bool:
    state = context.get("current_state", {})
    keys = {
        "weight": ("weight", "days_with_weight"),
        "nutrition": ("nutrition", "days_with_food"),
        "activity": ("activity", "days_with_data"),
        "sleep": ("sleep", "days_with_sleep"),
        "training": ("training", "workout_count"),
    }
    section, field = keys.get(domain, (None, None))
    return bool(section and state.get(section, {}).get(field, 0) > 0)


def _target_exists(context: dict, metric: AdherenceMetric) -> bool:
    targets = context.get("targets", {})
    return {
        AdherenceMetric.CALORIES: "daily_calories",
        AdherenceMetric.PROTEIN: "daily_protein_g",
        AdherenceMetric.STEPS: "daily_steps",
        AdherenceMetric.TRAINING: "strength_sessions_per_week",
    }[metric] in targets


def _gap_is_valid(context: dict, domain: str, metric: AdherenceMetric | None) -> bool:
    coverage = context.get("coverage", {})
    constraints = context.get("constraints", {})
    if domain == "nutrition":
        if metric == AdherenceMetric.CALORIES:
            return coverage.get("calorie_days_available", 0) < coverage.get("nutrition_days_requested", 0)
        if metric == AdherenceMetric.PROTEIN:
            return coverage.get("protein_days_available", 0) < coverage.get("nutrition_days_requested", 0)
        return coverage.get("nutrition_days_logged", 0) < coverage.get("nutrition_days_requested", 0)
    if domain == "activity":
        return coverage.get("steps_days_available", 0) < coverage.get("activity_days_requested", 0)
    if domain == "sleep":
        return not _has_observations(context, "sleep")
    if domain == "training":
        return (
            not constraints.get("can_assess_training_adherence", False)
            or coverage.get("training_sessions_unclassified", 0) > 0
        )
    if domain == "weight":
        logged = coverage.get("weight_days_logged")
        requested = coverage.get("weight_days_requested")
        if logged is not None and requested is not None:
            return logged < requested
        return not _has_observations(context, "weight")
    return True


def validate_coaching_response(context: dict, response: CoachingResponse) -> CoachingResponse:
    violations: list[GroundingViolation] = []
    for index, observation in enumerate(response.observations):
        if observation.adherence_metric is not None and observation.evidence_status == EvidenceStatus.SUFFICIENT:
            metric = observation.adherence_metric
            if not _permission(context, metric):
                violations.append(GroundingViolation(
                    "observations", "adherence_permission_denied",
                    "Sufficient adherence observation is not permitted by context",
                    observation.domain.value, metric.value, index,
                ))

    for index, recommendation in enumerate(response.recommendations):
        metric = recommendation.adherence_metric
        if recommendation.basis == RecommendationBasis.GENERAL_GUIDANCE:
            if recommendation.requires_adherence_evidence or metric is not None:
                violations.append(GroundingViolation(
                    "recommendations", "general_guidance_requires_no_adherence",
                    "General guidance cannot require adherence evidence",
                    recommendation.domain.value, metric.value if metric else None, index,
                ))
        elif recommendation.requires_adherence_evidence:
            if metric is None:
                violations.append(GroundingViolation(
                    "recommendations", "adherence_metric_required",
                    "Adherence-dependent recommendation must identify a metric",
                    recommendation.domain.value, index=index,
                ))
            elif not _permission(context, metric):
                violations.append(GroundingViolation(
                    "recommendations", "adherence_permission_denied",
                    "Recommendation requires unavailable adherence evidence",
                    recommendation.domain.value, metric.value, index,
                ))
        if recommendation.basis == RecommendationBasis.CONFIGURED_TARGET:
            if metric is None:
                violations.append(GroundingViolation(
                    "recommendations", "adherence_metric_required",
                    "Target-based recommendation must identify a metric",
                    recommendation.domain.value, index=index,
                ))
            elif not _target_exists(context, metric):
                violations.append(GroundingViolation(
                    "recommendations", "configured_target_unavailable",
                    "Configured target is unavailable for the requested metric",
                    recommendation.domain.value, metric.value, index,
                ))
        if recommendation.basis == RecommendationBasis.OBSERVED_DATA and not _has_observations(context, recommendation.domain.value):
            violations.append(GroundingViolation(
                "recommendations", "observed_data_unavailable",
                "Observed-data basis has no deterministic observations",
                recommendation.domain.value, index=index,
            ))

    for index, gap in enumerate(response.data_gaps):
        if not _gap_is_valid(context, gap.domain.value, gap.adherence_metric):
            violations.append(GroundingViolation(
                "data_gaps", "data_gap_not_supported",
                "Data gap is not supported by deterministic coverage",
                gap.domain.value, gap.adherence_metric.value if gap.adherence_metric else None, index,
            ))

    if response.safety.medical_escalation_needed and not response.safety.reason:
        violations.append(GroundingViolation("safety", "safety_reason_required", "Safety escalation requires a reason"))
    if violations:
        raise CoachingGroundingError(violations)
    return response

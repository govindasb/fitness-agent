from datetime import date, datetime
from math import ceil

from sqlalchemy.orm import Session

from agent.context_builder import build_fitness_context
from analytics.adherence import get_target_adherence
from config.coaching_targets import load_coaching_targets
from config.profile import load_profile
from database.timezone import utc_now


def _window_reference(reference: date | datetime | None) -> date | datetime:
    return reference if reference is not None else utc_now()


def _compact_summary(summary: dict) -> dict:
    return {key: value for key, value in summary.items() if key != "daily"}


def _training_assessment_permission() -> tuple[bool, str]:
    """Training log completeness is not yet deterministically observable."""
    return False, "workout_log_completeness_unknown"


def get_coaching_context(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> dict:
    """Build compact deterministic input for a future AI fitness coach."""
    if days < 1:
        raise ValueError("days must be at least 1")
    resolved_reference = _window_reference(reference)
    production = build_fitness_context(
        db, load_profile(), reference=resolved_reference
    )
    adherence = get_target_adherence(
        db, days=days, reference=resolved_reference
    )
    targets = load_coaching_targets().model_dump()
    coverage = adherence["coverage"]
    coverage = {
        **coverage,
        "weight_days_logged": production["weight"]["days_with_weight"],
        "weight_days_requested": production["weight"]["window_days"],
    }
    threshold = ceil(days / 2)
    can_assess_training, training_reason = _training_assessment_permission()

    return {
        "generated_at": production["generated_at"],
        "timezone": production["timezone"],
        "goal": {
            key: production["profile"].get(key)
            for key in (
                "goal",
                "target_weight_kg",
                "starting_weight_kg",
                "secondary_goals",
            )
        },
        "targets": targets,
        "current_state": {
            "weight": _compact_summary(production["weight"]),
            "nutrition": _compact_summary(production["nutrition"]),
            "activity": _compact_summary(production["activity"]),
            "sleep": _compact_summary(production["sleep"]),
            "training": _compact_summary(production["training"]),
        },
        "adherence": {
            "nutrition": adherence["nutrition"],
            "activity": adherence["activity"],
            "training": adherence["training"],
        },
        "coverage": coverage,
        "constraints": {
            "missing_data_is_not_zero": True,
            "absence_of_log_is_not_proof_of_behavior": True,
            "do_not_invent_nutrition": True,
            "do_not_invent_measurements": True,
            "do_not_extrapolate_sparse_data": True,
            "minimum_metric_days_for_adherence": threshold,
            "can_assess_calorie_adherence": coverage["calorie_days_available"] >= threshold,
            "can_assess_protein_adherence": coverage["protein_days_available"] >= threshold,
            "can_assess_step_adherence": coverage["steps_days_available"] >= threshold,
            "can_assess_training_adherence": can_assess_training,
            "training_adherence_assessment_reason": training_reason,
        },
    }

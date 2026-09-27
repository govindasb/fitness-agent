import pytest

from agent.coaching_grounding import CoachingGroundingError, validate_coaching_response
from models.coaching_response import CoachingResponse


def context(**overrides):
    value = {
        "constraints": {
            "can_assess_calorie_adherence": False,
            "can_assess_protein_adherence": False,
            "can_assess_step_adherence": False,
            "can_assess_training_adherence": False,
        },
        "targets": {
            "daily_calories": 2450,
            "daily_protein_g": 170,
            "daily_steps": 10000,
            "strength_sessions_per_week": 4,
            "cardio_sessions_per_week": 3,
        },
        "current_state": {
            "weight": {"days_with_weight": 1},
            "nutrition": {"days_with_food": 1},
            "activity": {"days_with_data": 1},
            "sleep": {"days_with_sleep": 1},
            "training": {"workout_count": 1},
        },
        "coverage": {
            "nutrition_days_logged": 1, "nutrition_days_requested": 7,
            "calorie_days_available": 0, "protein_days_available": 0,
            "activity_days_logged": 1, "activity_days_requested": 7,
            "steps_days_available": 1, "training_sessions_unclassified": 0,
        },
    }
    for key, value_override in overrides.items():
        value[key].update(value_override)
    return value


def response(**kwargs):
    return CoachingResponse(summary="Data review.", **kwargs)


def test_sufficient_observation_requires_permission_but_limited_is_allowed():
    with pytest.raises(CoachingGroundingError) as error:
        validate_coaching_response(context(), response(observations=[{
            "domain": "nutrition", "message": "x", "evidence_status": "sufficient",
            "adherence_metric": "calories",
        }]))
    assert error.value.violations[0].code == "adherence_permission_denied"
    validate_coaching_response(context(), response(observations=[{
        "domain": "nutrition", "message": "x", "evidence_status": "limited",
        "adherence_metric": "calories",
    }]))


def test_recommendation_requires_metric_and_permission():
    item = {
        "domain": "nutrition", "action": "x", "priority": "high",
        "basis": "observed_data", "requires_adherence_evidence": True,
        "adherence_metric": "calories",
    }
    with pytest.raises(CoachingGroundingError):
        validate_coaching_response(context(), response(recommendations=[item]))
    item["requires_adherence_evidence"] = False
    item["basis"] = "general_guidance"
    item["adherence_metric"] = None
    validate_coaching_response(context(), response(recommendations=[item]))


def test_observed_data_and_configured_target_require_structured_evidence():
    with pytest.raises(CoachingGroundingError):
        validate_coaching_response(context(**{"current_state": {"weight": {"days_with_weight": 0}}}), response(recommendations=[{
            "domain": "weight", "action": "x", "priority": "low",
            "basis": "observed_data", "requires_adherence_evidence": False,
        }]))
    validate_coaching_response(context(), response(recommendations=[{
        "domain": "nutrition", "action": "x", "priority": "low",
        "basis": "configured_target", "requires_adherence_evidence": False,
        "adherence_metric": "calories",
    }]))


def test_data_gaps_and_safety_are_validated():
    validate_coaching_response(context(), response(data_gaps=[{
        "domain": "nutrition", "missing_information": "x", "adherence_metric": "calories",
    }], safety={"medical_escalation_needed": True, "reason": "Review needed"}))
    with pytest.raises(CoachingGroundingError):
        validate_coaching_response(context(**{"coverage": {"nutrition_days_logged": 7, "nutrition_days_requested": 7, "calorie_days_available": 7}}), response(data_gaps=[{
            "domain": "nutrition", "missing_information": "x", "adherence_metric": "calories",
        }]))


@pytest.mark.parametrize("logged, requested, allowed", [(0, 14, True), (1, 14, True), (14, 14, False)])
def test_weight_data_gap_uses_explicit_coverage(logged, requested, allowed):
    value = context(**{"coverage": {"weight_days_logged": logged, "weight_days_requested": requested}})
    gap = response(data_gaps=[{
        "domain": "weight", "missing_information": "More weight observations are needed.",
    }])
    if allowed:
        validate_coaching_response(value, gap)
    else:
        with pytest.raises(CoachingGroundingError):
            validate_coaching_response(value, gap)


def test_multiple_violations_are_reported_without_mutation():
    value = response(observations=[{
        "domain": "activity", "message": "x", "evidence_status": "sufficient", "adherence_metric": "steps",
    }], recommendations=[{
        "domain": "training", "action": "x", "priority": "high", "basis": "observed_data",
        "requires_adherence_evidence": True, "adherence_metric": "training",
    }])
    before = value.model_dump()
    with pytest.raises(CoachingGroundingError) as error:
        validate_coaching_response(context(), value)
    assert len(error.value.violations) == 2
    assert value.model_dump() == before

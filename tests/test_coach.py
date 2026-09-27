import copy

import pytest

from agent.coach import (
    CoachingStructureError,
    StaticCoach,
    generate_grounded_coaching,
)
from agent.coaching_grounding import CoachingGroundingError
from models.coaching_response import CoachingResponse


def context():
    return {
        "constraints": {
            "can_assess_calorie_adherence": False,
            "can_assess_protein_adherence": False,
            "can_assess_step_adherence": False,
            "can_assess_training_adherence": False,
        },
        "targets": {"daily_calories": 2450},
        "current_state": {"nutrition": {"days_with_food": 1}},
        "coverage": {
            "nutrition_days_logged": 1,
            "nutrition_days_requested": 7,
            "calorie_days_available": 0,
            "protein_days_available": 0,
        },
    }


def test_static_coach_returns_valid_response_and_pipeline_returns_type():
    response = CoachingResponse(summary="Keep logging consistently.")
    coach = StaticCoach(response)

    assert coach.coach(context()) is response
    approved = generate_grounded_coaching(context(), coach)

    assert isinstance(approved, CoachingResponse)
    assert approved.summary == response.summary


def test_grounding_rejects_unsupported_adherence_response():
    response = CoachingResponse(summary="Review.", observations=[{
        "domain": "nutrition",
        "message": "Calories met target.",
        "evidence_status": "sufficient",
        "adherence_metric": "calories",
    }])

    with pytest.raises(CoachingGroundingError):
        generate_grounded_coaching(context(), StaticCoach(response))


def test_general_guidance_and_data_gap_pass():
    response = CoachingResponse(
        summary="Logging support.",
        recommendations=[{
            "domain": "nutrition", "action": "Log meals consistently.",
            "priority": "low", "basis": "general_guidance",
            "requires_adherence_evidence": False,
        }],
        data_gaps=[{
            "domain": "nutrition", "missing_information": "Calories are unavailable.",
            "adherence_metric": "calories",
        }],
    )

    assert generate_grounded_coaching(context(), StaticCoach(response)) == response


def test_structural_failure_is_distinct_and_not_approved():
    class InvalidCoach:
        def coach(self, context):
            return {"summary": "   "}

    with pytest.raises(CoachingStructureError):
        generate_grounded_coaching(context(), InvalidCoach())


def test_context_and_response_are_not_mutated():
    original_context = context()
    response = CoachingResponse(summary="Keep logging.")
    context_before = copy.deepcopy(original_context)
    response_before = response.model_dump()

    approved = generate_grounded_coaching(original_context, StaticCoach(response))

    assert original_context == context_before
    assert response.model_dump() == response_before
    assert approved is response

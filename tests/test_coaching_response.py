import json

import pytest
from pydantic import ValidationError

from models.coaching_response import (
    CoachingResponse,
    CoachingSafety,
)


def test_minimal_response_and_safety_default():
    response = CoachingResponse(summary="  Keep logging consistently. ")

    assert response.summary == "Keep logging consistently."
    assert response.observations == []
    assert response.safety == CoachingSafety()


def test_full_response_round_trips_as_json():
    response = CoachingResponse.model_validate(
        {
            "summary": "Recent data provides a limited baseline.",
            "observations": [
                {
                    "domain": "nutrition",
                    "message": "Protein data is available on several days.",
                    "evidence_status": "limited",
                    "metric": "protein_g",
                }
            ],
            "recommendations": [
                {
                    "domain": "nutrition",
                    "action": "Continue logging meals.",
                    "priority": "medium",
                    "basis": "general_guidance",
                    "requires_adherence_evidence": False,
                }
            ],
            "data_gaps": [
                {
                    "domain": "activity",
                    "missing_information": "Steps are not available every day.",
                    "suggested_logging_action": "Log daily steps.",
                }
            ],
            "safety": {"medical_escalation_needed": True, "reason": "Needs review."},
        }
    )
    encoded = response.model_dump_json()
    restored = CoachingResponse.model_validate_json(encoded)

    assert restored == response
    json.dumps(response.model_dump(mode="json"))


@pytest.mark.parametrize(
    "payload",
    [
        {"summary": "ok", "unknown": True},
        {"summary": "ok", "safety": {"extra": 1}},
        {"summary": "ok", "observations": [{"domain": "bogus", "message": "x", "evidence_status": "limited"}]},
    ],
)
def test_controlled_values_and_extra_fields_are_rejected(payload):
    with pytest.raises(ValidationError):
        CoachingResponse.model_validate(payload)


@pytest.mark.parametrize("field", ["summary"])
def test_blank_summary_rejected(field):
    with pytest.raises(ValidationError):
        CoachingResponse.model_validate({field: "   "})


@pytest.mark.parametrize(
    "item",
    [
        {"domain": "weight", "message": " ", "evidence_status": "sufficient"},
        {"domain": "weight", "message": "ok", "evidence_status": "sufficient", "extra": 1},
    ],
)
def test_invalid_observation_rejected(item):
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", observations=[item])


def test_blank_recommendation_and_data_gap_text_rejected():
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", recommendations=[{
            "domain": "general", "action": " ", "priority": "low",
            "basis": "general_guidance", "requires_adherence_evidence": False,
        }])
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", data_gaps=[{
            "domain": "general", "missing_information": " ",
        }])


def test_list_limits_are_enforced():
    observation = {"domain": "general", "message": "ok", "evidence_status": "limited"}
    recommendation = {
        "domain": "general", "action": "ok", "priority": "low",
        "basis": "general_guidance", "requires_adherence_evidence": False,
    }
    gap = {"domain": "general", "missing_information": "ok"}
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", observations=[observation] * 9)
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", recommendations=[recommendation] * 7)
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", data_gaps=[gap] * 7)


def test_adherence_requirement_is_preserved_and_text_is_trimmed():
    response = CoachingResponse(summary="ok", recommendations=[{
        "domain": "training", "action": "  Log sessions. ", "priority": "high",
        "basis": "configured_target", "requires_adherence_evidence": True,
    }])
    assert response.recommendations[0].action == "Log sessions."
    assert response.recommendations[0].requires_adherence_evidence is True


def test_text_length_limits_are_enforced():
    with pytest.raises(ValidationError):
        CoachingResponse(summary="x" * 501)
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", observations=[{
            "domain": "general", "message": "x" * 301,
            "evidence_status": "limited",
        }])
    with pytest.raises(ValidationError):
        CoachingResponse(summary="ok", safety={"reason": "x" * 301})

import json
from types import SimpleNamespace

import pytest

from agent.coach import generate_grounded_coaching
from agent.coaching_grounding import CoachingGroundingError
from agent.gemini_coach import GeminiCoachingError, GeminiFitnessCoach
from models.coaching_response import CoachingResponse


CONTEXT = {
    "timezone": "America/New_York",
    "targets": {"daily_calories": 2450},
    "constraints": {"can_assess_calorie_adherence": False},
    "current_state": {"nutrition": {"days_with_food": 1}},
    "coverage": {"nutrition_days_logged": 1},
}


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.call = None

    def generate_content(self, **kwargs):
        self.call = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, models):
        self.models = models


def provider_response(payload):
    return SimpleNamespace(text=json.dumps(payload), usage_metadata=None)


def test_valid_structured_response_and_context_serialization():
    models = FakeModels(provider_response({"summary": "Log consistently."}))
    coach = GeminiFitnessCoach(client=FakeClient(models), model="test-model")
    result = coach.coach(CONTEXT)

    assert isinstance(result, CoachingResponse)
    assert models.call["model"] == "test-model"
    assert json.loads(models.call["contents"]) == CONTEXT
    config = models.call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is None
    assert config.response_json_schema is not None
    assert config.temperature == 0.2
    assert "missing data" in config.system_instruction.lower()
    instruction = config.system_instruction.lower()
    assert 'basis="general_guidance"' in instruction
    assert "requires_adherence_evidence=false" in instruction
    assert "adherence_metric=null" in instruction
    assert "food presence does not" in instruction
    assert "logged observations" in instruction
    assert "sparse step data" in instruction
    assert "represent it consistently in" in instruction
    assert "explicitly established missing domain" in instruction
    assert "do not create a gap unless the context establishes it" in instruction


def test_raw_events_are_not_forwarded_and_provider_output_is_not_grounded():
    models = FakeModels(provider_response({
        "summary": "Review.",
        "observations": [{
            "domain": "nutrition", "message": "Calories met target.",
            "evidence_status": "sufficient", "adherence_metric": "calories",
        }],
    }))
    context = {**CONTEXT, "raw_events": [{"raw_text": "secret"}]}
    coach = GeminiFitnessCoach(client=FakeClient(models))
    coach.coach(context)
    assert "raw_events" not in json.loads(models.call["contents"])
    with pytest.raises(CoachingGroundingError):
        generate_grounded_coaching(CONTEXT, coach)


def test_corrected_general_guidance_encoding_passes_grounding():
    models = FakeModels(provider_response({
        "summary": "Logging support.",
        "recommendations": [{
            "domain": "training", "action": "Log sessions consistently.",
            "priority": "low", "basis": "general_guidance",
            "requires_adherence_evidence": False, "adherence_metric": None,
        }],
    }))
    coach = GeminiFitnessCoach(client=FakeClient(models))
    approved = generate_grounded_coaching(CONTEXT, coach)
    assert approved.recommendations[0].basis.value == "general_guidance"
    assert approved.recommendations[0].requires_adherence_evidence is False
    assert approved.recommendations[0].adherence_metric is None


@pytest.mark.parametrize("payload", [{"summary": "bad", "extra": 1}, {"summary": "bad", "observations": [{"domain": "invalid", "message": "x", "evidence_status": "limited"}]}])
def test_malformed_or_uncontrolled_output_fails(payload):
    coach = GeminiFitnessCoach(client=FakeClient(FakeModels(provider_response(payload))))
    with pytest.raises(GeminiCoachingError):
        coach.coach(CONTEXT)


def test_provider_exception_is_wrapped_and_context_is_not_mutated():
    context = dict(CONTEXT)
    coach = GeminiFitnessCoach(client=FakeClient(FakeModels(error=RuntimeError("boom"))))
    with pytest.raises(GeminiCoachingError):
        coach.coach(context)
    assert context == CONTEXT


def test_missing_structured_response_fails():
    coach = GeminiFitnessCoach(client=FakeClient(FakeModels(SimpleNamespace(text=None))))
    with pytest.raises(GeminiCoachingError):
        coach.coach(CONTEXT)

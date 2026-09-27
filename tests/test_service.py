from datetime import date

import pytest

from agent.coach import CoachingStructureError
from agent.coaching_grounding import CoachingGroundingError
from agent.service import FitnessAgentService
from models.coaching_response import CoachingResponse


class FakeSession:
    def __init__(self, error=None):
        self.closed = False
        self.error = error

    def close(self):
        self.closed = True


class FakeCoach:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.context = None

    def coach(self, context):
        self.context = context
        if self.error:
            raise self.error
        return self.response


class FakeInterpreter:
    pass


def test_log_delegates_without_triggering_coach(monkeypatch):
    calls = {}

    def fake_ingest(raw_text, interpreter, reference=None):
        calls.update(raw_text=raw_text, interpreter=interpreter, reference=reference)
        return {"status": "processed"}

    monkeypatch.setattr("agent.service.ingest_fitness_message", fake_ingest)
    coach = FakeCoach(CoachingResponse(summary="unused"))
    interpreter = FakeInterpreter()
    service = FitnessAgentService(interpreter, coach)
    result = service.log("walked today", reference="ref")

    assert result == {"status": "processed"}
    assert calls == {"raw_text": "walked today", "interpreter": interpreter, "reference": "ref"}
    assert coach.context is None


def test_get_context_delegates_and_closes_session(monkeypatch):
    session = FakeSession()
    calls = {}

    def fake_context(db, days, reference):
        calls.update(db=db, days=days, reference=reference)
        return {"timezone": "America/New_York"}

    monkeypatch.setattr("agent.service.get_coaching_context", fake_context)
    service = FitnessAgentService(FakeInterpreter(), FakeCoach(), session_factory=lambda: session)
    result = service.get_context(days=14, reference=date(2026, 7, 3))

    assert result == {"timezone": "America/New_York"}
    assert calls["db"] is session
    assert session.closed is True


def test_get_context_closes_session_when_context_fails(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("agent.service.get_coaching_context", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("context")))
    service = FitnessAgentService(FakeInterpreter(), FakeCoach(), session_factory=lambda: session)

    with pytest.raises(RuntimeError):
        service.get_context()
    assert session.closed is True


def test_get_coaching_passes_context_and_returns_approved_response(monkeypatch):
    context = {"constraints": {}}
    response = CoachingResponse(summary="Keep logging.")
    coach = FakeCoach(response)
    service = FitnessAgentService(FakeInterpreter(), coach)
    monkeypatch.setattr(service, "get_context", lambda days, reference: context)
    monkeypatch.setattr("agent.service.generate_grounded_coaching", lambda actual, injected: response)

    assert service.get_coaching(7, date(2026, 7, 3)) is response


@pytest.mark.parametrize("error", [CoachingGroundingError([]), CoachingStructureError.__new__(CoachingStructureError)])
def test_coaching_failures_propagate(monkeypatch, error):
    service = FitnessAgentService(FakeInterpreter(), FakeCoach())
    monkeypatch.setattr(service, "get_context", lambda **kwargs: {})
    monkeypatch.setattr("agent.service.generate_grounded_coaching", lambda *args: (_ for _ in ()).throw(error))

    with pytest.raises(type(error)):
        service.get_coaching()


def test_provider_failure_propagates(monkeypatch):
    service = FitnessAgentService(FakeInterpreter(), FakeCoach())
    monkeypatch.setattr(service, "get_context", lambda **kwargs: {})
    monkeypatch.setattr("agent.service.generate_grounded_coaching", lambda *args: (_ for _ in ()).throw(RuntimeError("provider")))

    with pytest.raises(RuntimeError, match="provider"):
        service.get_coaching()

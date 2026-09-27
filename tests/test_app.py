from agent.coaching_grounding import CoachingGroundingError
from agent.coach import CoachingStructureError
from agent.gemini_coach import GeminiCoachingError
from models.coaching_response import CoachingResponse
from app import run_cli


class FakeService:
    def __init__(self, log_result=None, coaching_result=None, coaching_error=None):
        self.log_result = log_result or {"status": "processed", "raw_event_id": 1, "stored": {"activities": [{"id": 1}]}}
        self.coaching_result = coaching_result or CoachingResponse(summary="Keep logging.")
        self.coaching_error = coaching_error
        self.logged = []
        self.coaching_calls = 0

    def log(self, text):
        self.logged.append(text)
        return self.log_result

    def get_coaching(self):
        self.coaching_calls += 1
        if self.coaching_error:
            raise self.coaching_error
        return self.coaching_result


def run(service, inputs):
    output = []
    values = iter(inputs)
    run_cli(service, input_fn=lambda _: next(values), output_fn=output.append)
    return output


def test_normal_input_logs_without_coaching():
    service = FakeService()
    output = run(service, ["8000 steps today", "exit"])
    assert service.logged == ["8000 steps today"]
    assert service.coaching_calls == 0
    assert any("Raw event: 1" in line for line in output)


def test_coach_command_is_not_logged_and_renders_response():
    service = FakeService(coaching_result=CoachingResponse(
        summary="Summary.", recommendations=[{
            "domain": "general", "action": "Keep logging.", "priority": "low",
            "basis": "general_guidance", "requires_adherence_evidence": False,
        }]))
    output = run(service, [" coach ", "exit"])
    assert service.logged == []
    assert service.coaching_calls == 1
    assert "Summary." in output
    assert any("Keep logging." in line for line in output)


def test_exit_does_not_call_service():
    service = FakeService()
    run(service, ["exit"])
    assert service.logged == []
    assert service.coaching_calls == 0


def test_failed_ingestion_keeps_cli_usable():
    service = FakeService(log_result={"status": "failed", "raw_event_id": 2, "error": "bad input", "stored": {}})
    output = run(service, ["bad", "coach", "exit"])
    assert any("Failure: bad input" in line for line in output)
    assert service.coaching_calls == 1


def test_coaching_failures_are_rendered_and_loop_continues():
    for error, label in ((GeminiCoachingError("provider"), "Provider failure"), (CoachingGroundingError([]), "Grounding failure")):
        service = FakeService(coaching_error=error)
        output = run(service, ["coach", "exit"])
        assert any(label in line for line in output)


def test_structural_coaching_failure_is_rendered():
    error = CoachingStructureError.__new__(CoachingStructureError)
    Exception.__init__(error, "invalid structure")
    service = FakeService(coaching_error=error)
    output = run(service, ["coach", "exit"])
    assert any("Structural validation failure" in line for line in output)


def test_warnings_and_unparsed_fragments_render():
    service = FakeService(log_result={"status": "processed", "raw_event_id": 3, "stored": {}, "warnings": ["unclear"], "unparsed_fragments": ["other text"]})
    output = run(service, ["message", "exit"])
    assert any("Warnings: unclear" in line for line in output)
    assert any("Unparsed: other text" in line for line in output)

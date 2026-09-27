from agent.gemini_interpreter import GeminiFitnessInterpreter
from agent.interpreter import InterpretationResult
from agent.openai_interpreter import OpenAIFitnessInterpreter
from evals.comparator import compare_case
from evals.run_interpreter_eval import (
    default_delay_seconds,
    create_interpreter,
    load_cases,
    run_case,
    run_cases,
)


class FakeInterpreter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.last_usage = None

    def interpret(self, raw_text, reference=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def matching_case():
    case = load_cases()[0]
    return case


def matching_result():
    return InterpretationResult(parsed_input={"body_metrics": [{"weight_kg": 96.2}]})


def test_evaluator_selects_openai_provider():
    interpreter = create_interpreter("openai", "openai-test")

    assert isinstance(interpreter, OpenAIFitnessInterpreter)
    assert interpreter.model == "openai-test"


def test_evaluator_selects_gemini_provider():
    interpreter = create_interpreter("gemini", "gemini-test")

    assert isinstance(interpreter, GeminiFitnessInterpreter)
    assert interpreter.model == "gemini-test"


def test_both_providers_share_dataset_and_comparator():
    case = load_cases()[0]
    actual = InterpretationResult(
        parsed_input={"body_metrics": [{"weight_kg": 96.2}]}
    )

    first = compare_case(case, actual)
    second = compare_case(case, actual)

    assert len(load_cases()) == 34
    assert first == second
    assert first["passed"] is True


def test_provider_defaults_only_gemini_to_conservative_pacing():
    assert default_delay_seconds("gemini") == 5.0
    assert default_delay_seconds("openai") == 0.0


def test_run_cases_does_not_sleep_before_first_case_and_paces_between_cases():
    sleeps = []
    interpreter = FakeInterpreter([matching_result(), matching_result()])

    results = run_cases(
        [matching_case(), matching_case()],
        interpreter,
        delay_seconds=5.0,
        sleep_fn=sleeps.append,
    )

    assert len(results) == 2
    assert sleeps == [5.0]
    assert interpreter.calls == 2


def test_explicit_delay_is_used_without_real_sleep():
    sleeps = []
    interpreter = FakeInterpreter([matching_result(), matching_result()])

    run_cases(
        [matching_case(), matching_case()],
        interpreter,
        delay_seconds=0.25,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [0.25]


class RetryAfterError(RuntimeError):
    status_code = 429
    retry_after = 7


def test_rate_limit_retries_and_honors_retry_after():
    sleeps = []
    interpreter = FakeInterpreter([RetryAfterError("429"), matching_result()])

    result = run_case(
        matching_case(),
        interpreter,
        sleep_fn=sleeps.append,
    )

    assert result["status"] == "passed"
    assert result["retry_count"] == 1
    assert sleeps == [7.0]
    assert interpreter.calls == 2


def test_rate_limit_uses_bounded_fallback_backoff():
    sleeps = []
    interpreter = FakeInterpreter(
        [RuntimeError("429 RESOURCE_EXHAUSTED"), RuntimeError("429"), matching_result()]
    )

    result = run_case(
        matching_case(),
        interpreter,
        sleep_fn=sleeps.append,
    )

    assert result["status"] == "passed"
    assert result["retry_count"] == 2
    assert sleeps == [2.0, 4.0]


def test_exhausted_rate_limit_retries_is_api_error():
    sleeps = []
    interpreter = FakeInterpreter(
        [RuntimeError("429") for _ in range(3)]
    )

    result = run_case(matching_case(), interpreter, sleep_fn=sleeps.append)

    assert result["status"] == "api_error"
    assert result["retry_count"] == 2
    assert sleeps == [2.0, 4.0]
    assert interpreter.calls == 3


def test_non_rate_limit_provider_error_is_not_retried():
    sleeps = []
    interpreter = FakeInterpreter([RuntimeError("authentication failed")])

    result = run_case(matching_case(), interpreter, sleep_fn=sleeps.append)

    assert result["status"] == "api_error"
    assert result["retry_count"] == 0
    assert sleeps == []


def test_semantic_failure_is_not_retried():
    sleeps = []
    interpreter = FakeInterpreter(
        [InterpretationResult(parsed_input={"body_metrics": [{"weight_kg": 90}]})]
    )

    result = run_case(matching_case(), interpreter, sleep_fn=sleeps.append)

    assert result["status"] == "semantic_failure"
    assert result["retry_count"] == 0
    assert sleeps == []

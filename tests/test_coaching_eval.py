from evals.run_coaching_eval import evaluate_case, load_cases, summarize
from models.coaching_response import CoachingResponse


def case(expectations=None):
    return {
        "id": "test",
        "context": {
            "constraints": {"can_assess_calorie_adherence": False},
            "coverage": {"nutrition_days_logged": 1, "nutrition_days_requested": 7, "calorie_days_available": 0},
            "current_state": {"nutrition": {"days_with_food": 1}},
        },
        "expectations": expectations or {},
    }


class FakeCoach:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def coach(self, context):
        self.context = context
        if self.error:
            raise self.error
        return self.result


def test_passing_general_guidance_case():
    result = evaluate_case(case(), FakeCoach(CoachingResponse(summary="Log consistently.")))
    assert result["passed"] is True
    assert result["status"] == "passed"


def test_grounding_failure_is_classified():
    response = CoachingResponse(summary="Review.", observations=[{
        "domain": "nutrition", "message": "Target met", "evidence_status": "sufficient", "adherence_metric": "calories",
    }])
    result = evaluate_case(case(), FakeCoach(response))
    assert result["status"] == "grounding_failure"
    assert "response" in result
    assert result["violations"]
    assert result["expectations"] == {}


def test_semantic_sparse_weight_failure_and_correction():
    sparse = case({"weight_sufficient_forbidden": True})
    response = CoachingResponse(summary="Review.", observations=[{
        "domain": "weight", "message": "Trend is clear", "evidence_status": "sufficient",
    }])
    assert evaluate_case(sparse, FakeCoach(response))["status"] == "semantic_failure"
    response = CoachingResponse(summary="Review.", observations=[{
        "domain": "weight",
        "message": "Recorded weight changed by 1.0 kg between available measurements.",
        "evidence_status": "limited",
    }])
    assert evaluate_case(sparse, FakeCoach(response))["passed"] is True


def test_sparse_weight_fixture_is_coherent_and_only_tests_weight_quality():
    fixture = next(item for item in load_cases() if item["id"] == "sparse_weight")
    assert fixture["context"]["current_state"]["weight"]["days_with_weight"] == 1
    assert fixture["context"]["coverage"]["nutrition_days_requested"] == 7
    assert fixture["context"]["coverage"]["activity_days_requested"] == 7
    assert "required_data_gap_domains" not in fixture["expectations"]

    limited = CoachingResponse(summary="Review.", observations=[{
        "domain": "weight", "message": "One weight day is recorded.",
        "evidence_status": "limited",
    }])
    result = evaluate_case(fixture, FakeCoach(limited))
    assert result["passed"] is True
    assert result["status"] == "passed"


def test_sparse_weight_is_loaded_from_disk_and_passed_directly_to_coach():
    fixture = next(item for item in load_cases() if item["id"] == "sparse_weight")
    coach = FakeCoach(CoachingResponse(summary="One weight day is recorded."))
    evaluate_case(fixture, coach)

    assert coach.context is fixture["context"]
    assert coach.context["current_state"]["weight"]["days_with_weight"] == 1
    assert coach.context["coverage"]["nutrition_days_requested"] == 7
    assert coach.context["coverage"]["activity_days_requested"] == 7
    assert coach.context["coverage"]["training_sessions_total"] == 3


def test_sparse_weight_gemini_style_weight_gap_is_grounded():
    fixture = next(item for item in load_cases() if item["id"] == "sparse_weight")
    response = CoachingResponse(
        summary="Weight coverage is limited.",
        observations=[{
            "domain": "weight", "message": "Weight was logged for 1 day.",
            "evidence_status": "limited",
        }],
        data_gaps=[{
            "domain": "weight",
            "missing_information": "Additional entries are needed to establish a trend.",
        }],
    )
    result = evaluate_case(fixture, FakeCoach(response))
    assert result["passed"] is True


def test_sparse_all_required_domains_have_explicit_disk_context_evidence():
    fixture = next(item for item in load_cases() if item["id"] == "sparse_all")
    context = fixture["context"]
    required = fixture["expectations"]["required_data_gap_domains"]
    coverage = context["coverage"]
    current_state = context["current_state"]
    evidence = {
        "nutrition": "nutrition_days_logged" in coverage,
        "activity": "activity_days_logged" in coverage,
        "sleep": (
            "sleep" in current_state
            and "days_with_sleep" in current_state["sleep"]
            and "window_days" in current_state["sleep"]
        ),
    }
    assert all(evidence[domain] for domain in required)
    assert "training" not in required


def test_provider_error_and_summary():
    result = evaluate_case(case(), FakeCoach(error=RuntimeError("offline")))
    assert result["status"] == "provider_error"
    metrics = summarize([result])
    assert metrics["provider_error"] == 1


def test_evaluator_does_not_mutate_context():
    current = case()
    before = current["context"].copy()
    evaluate_case(current, FakeCoach(CoachingResponse(summary="ok")))
    assert current["context"] == before


def test_summary_reports_grounding_and_semantic_metrics():
    metrics = summarize([
        {"status": "grounding_failure", "passed": False, "violations": [{"code": "adherence_permission_denied"}], "latency_seconds": 0.1},
        {"status": "semantic_failure", "passed": False, "failures": [{"code": "unexpected_safety_escalation"}], "latency_seconds": 0.3},
    ])
    assert metrics["adherence_permission_violations"] == 1
    assert metrics["unsupported_safety_escalations"] == 1
    assert metrics["average_latency_seconds"] == 0.2

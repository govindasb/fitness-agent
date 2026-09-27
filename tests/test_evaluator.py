from agent.interpreter import InterpretationResult
from evals.comparator import aggregate_results, compare_case, values_equal


def case(expected, case_id="case", tags=None):
    return {
        "id": case_id,
        "tags": tags or ["activity"],
        "expected": expected,
    }


def result(parsed_input):
    return InterpretationResult(parsed_input=parsed_input)


def test_exact_partial_match_passes():
    evaluation = compare_case(
        case({"parsed_input": {"activities": [{"steps": 9000}]}}),
        result({"activities": [{"steps": 9000}]}),
    )

    assert evaluation["passed"] is True
    assert evaluation["exact_fields"] == 1
    assert evaluation["matched_fields"] == 1


def test_null_required_detects_hallucinated_field():
    evaluation = compare_case(
        case(
            {
                "parsed_input": {"food_entries": [{"items": [{"food_name": "rice"}]}]},
                "null_required": ["food_entries[0].items[0].estimated_calories"],
            }
        ),
        result(
            {
                "food_entries": [
                    {"items": [{"food_name": "rice", "estimated_calories": 200}]}
                ]
            }
        ),
    )

    assert evaluation["passed"] is False
    assert evaluation["hallucinated"][0]["path"].endswith("estimated_calories")


def test_missing_field_and_domain_are_detected():
    evaluation = compare_case(
        case({"parsed_input": {"activities": [{"steps": 9000}]}}),
        result({}),
    )

    assert evaluation["missing_domains"] == ["activities"]
    assert evaluation["missed"][0]["path"] == "parsed_input.activities[0].steps"


def test_incorrect_value_is_detected():
    evaluation = compare_case(
        case({"parsed_input": {"activities": [{"steps": 9000}]}}),
        result({"activities": [{"steps": 8000}]}),
    )

    assert evaluation["incorrect"] == [
        {
            "path": "parsed_input.activities[0].steps",
            "expected": 9000,
            "actual": 8000,
        }
    ]


def test_unexpected_domain_fields_count_as_hallucinations():
    evaluation = compare_case(
        case({"parsed_input": {"activities": [{"steps": 9000}]}}),
        result(
            {
                "activities": [{"steps": 9000}],
                "body_metrics": [{"weight_kg": 96.2}],
            }
        ),
    )

    assert evaluation["unexpected_domains"] == ["body_metrics"]
    assert evaluation["hallucinated"] == [
        {
            "path": "parsed_input.body_metrics[0].weight_kg",
            "expected": None,
            "actual": 96.2,
        }
    ]


def test_timezone_aware_timestamps_compare_as_instants():
    assert values_equal(
        "2026-07-08T08:00:00-04:00",
        "2026-07-08T12:00:00+00:00",
    )


def test_warning_presence_and_normalized_fragment_containment():
    evaluation = compare_case(
        case(
            {
                "parsed_input": {},
                "warning_required": True,
                "unparsed_contains": ["buy detergent"],
            }
        ),
        InterpretationResult(
            parsed_input={},
            warnings=["Non-fitness request was preserved."],
            unparsed_fragments=["Remember to buy detergent!"],
        ),
    )

    assert evaluation["passed"] is True


def test_ordered_lists_and_extra_sets_are_checked():
    evaluation = compare_case(
        case(
            {
                "parsed_input": {
                    "workouts": [
                        {
                            "sets": [
                                {"exercise_name": "bench", "reps": 8},
                                {"exercise_name": "row", "reps": 10},
                            ]
                        }
                    ]
                }
            }
        ),
        result(
            {
                "workouts": [
                    {
                        "sets": [
                            {"exercise_name": "row", "reps": 10},
                            {"exercise_name": "bench", "reps": 8},
                            {"exercise_name": "curl", "reps": 12},
                        ]
                    }
                ]
            }
        ),
    )

    assert len(evaluation["incorrect"]) == 4
    assert any("sets[2]" in item["path"] for item in evaluation["hallucinated"])


def test_aggregate_metrics_and_tags_separate_api_errors():
    cases = [
        case({}, "passed", ["activity"]),
        case({}, "failed", ["activity", "safety"]),
        case({}, "api", ["body"]),
    ]
    results = [
        {
            "id": "passed",
            "passed": True,
            "exact_fields": 2,
            "matched_fields": 2,
            "hallucinated": [],
            "missed": [],
            "incorrect": [],
            "unexpected_domains": [],
            "missing_domains": [],
        },
        {
            "id": "failed",
            "passed": False,
            "exact_fields": 2,
            "matched_fields": 1,
            "hallucinated": [{"path": "x"}],
            "missed": [{"path": "y"}],
            "incorrect": [{"path": "z"}],
            "unexpected_domains": ["food_entries"],
            "missing_domains": ["activities"],
        },
        {"id": "api", "passed": False, "status": "api_error"},
    ]

    metrics = aggregate_results(cases, results)

    assert metrics["total_cases"] == 3
    assert metrics["passed_cases"] == 1
    assert metrics["api_error_count"] == 1
    assert metrics["failed_case_ids"] == ["failed", "api"]
    assert metrics["exact_structured_field_accuracy"] == 0.75
    assert metrics["hallucinated_field_count"] == 1
    assert metrics["missed_field_count"] == 1
    assert metrics["incorrect_value_count"] == 1
    assert metrics["unexpected_domain_count"] == 1
    assert metrics["missing_domain_count"] == 1
    assert metrics["by_tag"]["activity"]["passed"] == 1

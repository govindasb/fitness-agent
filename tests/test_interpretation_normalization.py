from agent.interpreter import (
    InterpretationResult,
    normalize_fitness_label,
    normalize_interpretation_result,
)


def test_pounds_case_removes_empty_body_record_and_preserves_metadata():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "body_metrics": [
                    {
                        "weight_kg": None,
                        "waist_cm": None,
                        "body_fat_percent": None,
                        "resting_heart_rate": None,
                        "measured_at": None,
                        "time_expression": None,
                    }
                ]
            },
            warnings=["Weight was provided in pounds; conversion was skipped."],
            unparsed_fragments=["I weigh 216 lb."],
        )
    )

    assert result.parsed_input.body_metrics == []
    assert result.warnings == ["Weight was provided in pounds; conversion was skipped."]
    assert result.unparsed_fragments == ["I weigh 216 lb."]


def test_partially_populated_records_remain():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "body_metrics": [{"weight_kg": 96.2}],
                "activities": [{"steps": 9000}],
                "food_entries": [{"items": [{"food_name": "rice"}]}],
                "workouts": [
                    {
                        "sets": [
                            {"exercise_name": "bench press", "reps": 8}
                        ]
                    }
                ],
                "sleep_entries": [{"quality_rating": 8}],
            }
        )
    )

    assert len(result.parsed_input.body_metrics) == 1
    assert len(result.parsed_input.activities) == 1
    assert len(result.parsed_input.food_entries) == 1
    assert len(result.parsed_input.workouts) == 1
    assert len(result.parsed_input.workouts[0].sets) == 1
    assert len(result.parsed_input.sleep_entries) == 1


def test_fully_empty_records_are_removed_from_every_domain():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "body_metrics": [{}],
                "activities": [{}],
                "food_entries": [{"items": []}],
                "workouts": [{"sets": []}],
                "sleep_entries": [{}],
            }
        )
    )

    assert result.parsed_input.body_metrics == []
    assert result.parsed_input.activities == []
    assert result.parsed_input.food_entries == []
    assert result.parsed_input.workouts == []
    assert result.parsed_input.sleep_entries == []


def test_zero_values_are_meaningful_not_empty():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "activities": [{"steps": 0, "active_minutes": 0}],
                "sleep_entries": [{"duration_minutes": 0}],
                "workouts": [{"duration_minutes": 0, "sets": []}],
            }
        )
    )

    assert len(result.parsed_input.activities) == 1
    assert len(result.parsed_input.sleep_entries) == 1
    assert len(result.parsed_input.workouts) == 1


def test_unsupported_time_drops_activity_but_keeps_metadata():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "activities": [
                    {"steps": 8000, "time_status": "unsupported"}
                ]
            },
            warnings=["Could not resolve 'Three Tuesdays ago'."],
            unparsed_fragments=[
                "Three Tuesdays ago I think I walked about eight thousand steps"
            ],
        )
    )

    assert result.parsed_input.activities == []
    assert result.warnings == ["Could not resolve 'Three Tuesdays ago'."]
    assert "eight thousand steps" in result.unparsed_fragments[0]


def test_unsupported_time_drops_records_across_all_domains():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "body_metrics": [{"weight_kg": 95, "time_status": "unsupported"}],
                "food_entries": [
                    {
                        "items": [{"food_name": "rice"}],
                        "time_status": "unsupported",
                    }
                ],
                "workouts": [
                    {"workout_type": "legs", "time_status": "unsupported", "sets": []}
                ],
                "sleep_entries": [
                    {"duration_minutes": 420, "time_status": "unsupported"}
                ],
            }
        )
    )

    assert result.parsed_input.body_metrics == []
    assert result.parsed_input.food_entries == []
    assert result.parsed_input.workouts == []
    assert result.parsed_input.sleep_entries == []


def test_absent_time_still_keeps_valid_undated_activity():
    result = normalize_interpretation_result(
        InterpretationResult(parsed_input={"activities": [{"steps": 8000}]})
    )

    assert len(result.parsed_input.activities) == 1


def test_supported_relative_time_still_keeps_record():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "activities": [
                    {"steps": 8000, "time_expression": "yesterday"}
                ]
            }
        )
    )

    assert len(result.parsed_input.activities) == 1


def test_explicit_aware_time_still_keeps_record():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "body_metrics": [
                    {
                        "weight_kg": 95,
                        "measured_at": "2026-07-08T12:00:00+00:00",
                        "time_status": "unsupported",
                    }
                ]
            }
        )
    )

    assert len(result.parsed_input.body_metrics) == 1


def test_fitness_label_normalization_is_lowercase_trimmed_and_aliased():
    assert normalize_fitness_label("Dinner") == "dinner"
    assert normalize_fitness_label(" Back ") == "back"
    assert normalize_fitness_label("Bench press") == "bench press"
    assert normalize_fitness_label("Deadlifts") == "deadlifts"
    assert normalize_fitness_label("run") == "running"
    assert normalize_fitness_label("running") == "running"
    assert normalize_fitness_label(None) is None
    assert normalize_fitness_label("   ") == ""


def test_lexical_normalization_changes_only_controlled_fields():
    result = normalize_interpretation_result(
        InterpretationResult(
            parsed_input={
                "food_entries": [
                    {
                        "meal_type": " Dinner ",
                        "items": [{"food_name": "Chicken Breast"}],
                    }
                ],
                "workouts": [
                    {
                        "workout_type": " Back ",
                        "notes": "Keep this Wording",
                        "sets": [
                            {"exercise_name": " Bench press "},
                            {"exercise_name": "run"},
                            {"exercise_name": "Deadlifts"},
                        ],
                    }
                ],
            },
            warnings=["Keep Warning Case"],
            unparsed_fragments=["Keep Fragment Case"],
        )
    )

    food = result.parsed_input.food_entries[0]
    workout = result.parsed_input.workouts[0]
    assert food.meal_type == "dinner"
    assert food.items[0].food_name == "Chicken Breast"
    assert workout.workout_type == "back"
    assert [item.exercise_name for item in workout.sets] == [
        "bench press",
        "running",
        "deadlifts",
    ]
    assert workout.notes == "Keep this Wording"
    assert result.warnings == ["Keep Warning Case"]
    assert result.unparsed_fragments == ["Keep Fragment Case"]

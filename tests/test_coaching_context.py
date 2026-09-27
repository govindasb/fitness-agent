from datetime import date
import json

from agent.coaching_context import (
    _training_assessment_permission,
    get_coaching_context,
)


def test_coaching_context_is_compact_and_json_serializable(monkeypatch):
    production = {
        "generated_at": "2026-07-03T16:00:00+00:00",
        "timezone": "America/New_York",
        "profile": {
            "goal": "fat_loss",
            "target_weight_kg": 90.0,
            "starting_weight_kg": 98.1,
            "secondary_goals": ["strength"],
        },
        "weight": {"days_with_weight": 2, "window_days": 14, "latest_weight_kg": 96.0},
        "nutrition": {"days_with_food": 1, "daily": [{"date": "x"}]},
        "activity": {"days_with_data": 1, "daily": [{"date": "x"}]},
        "sleep": {"days_with_sleep": 1, "daily": [{"date": "x"}]},
        "training": {"days_with_workouts": 1, "daily": [{"date": "x"}]},
    }
    adherence = {
        "coverage": {
            "nutrition_days_logged": 1, "nutrition_days_requested": 7,
            "calorie_days_available": 0, "protein_days_available": 0,
            "activity_days_logged": 1, "activity_days_requested": 7,
            "steps_days_available": 1, "training_sessions_total": 3,
            "training_sessions_classified": 3, "training_sessions_unclassified": 0,
        },
        "nutrition": {"logged_days": 1},
        "activity": {"logged_days": 1},
        "training": {"training_classification_coverage_percent": 100.0},
    }
    monkeypatch.setattr("agent.coaching_context.build_fitness_context", lambda *args, **kwargs: production)
    monkeypatch.setattr("agent.coaching_context.get_target_adherence", lambda *args, **kwargs: adherence)
    result = get_coaching_context(object(), reference=date(2026, 7, 3))

    assert result["goal"]["goal"] == "fat_loss"
    assert result["constraints"]["can_assess_calorie_adherence"] is False
    assert result["constraints"]["can_assess_training_adherence"] is False
    assert result["constraints"]["training_adherence_assessment_reason"] == "workout_log_completeness_unknown"
    assert result["coverage"]["weight_days_logged"] == 2
    assert result["coverage"]["weight_days_requested"] == 14
    assert "daily" not in result["current_state"]["nutrition"]
    json.dumps(result)


def test_training_permission_is_denied_until_log_completeness_signal_exists():
    for _observations in (
        (3, 3, 0),  # logged sessions, fully classified
        (8, 8, 0),  # sessions exceeding target, fully classified
        (3, 2, 1),  # partially classified
        (0, 0, 0),  # no sessions
    ):
        allowed, reason = _training_assessment_permission()
        assert allowed is False
        assert reason == "workout_log_completeness_unknown"

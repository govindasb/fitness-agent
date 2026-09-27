from datetime import date, datetime, timezone
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.adherence import classify_workout_type, get_target_adherence
from database.connection import Base
from database.repository import (
    save_activity_entry,
    save_food_entry,
    save_raw_event,
    save_workout_session,
)


engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def add_event(db, text="event"):
    return save_raw_event(db, text)


def test_daily_adherence_calculates_targets_and_preserves_missing_as_null():
    with Session() as db:
        event = add_event(db)
        when = datetime(2026, 7, 3, 16, tzinfo=timezone.utc)
        save_food_entry(db, event.id, "meal", estimated_calories=2450, protein_g=170, consumed_at=when)
        save_activity_entry(db, event.id, when, steps=5000)

        result = get_target_adherence(db, days=2, reference=date(2026, 7, 3))

    assert result["daily"][0]["has_nutrition_data"] is False
    assert result["daily"][1]["calories_actual"] == 2450
    assert result["daily"][1]["calories_difference"] == 0
    assert result["daily"][1]["calories_percent_of_target"] == 100.0
    assert result["daily"][1]["steps_percent_of_target"] == 50.0
    assert result["daily"][0]["steps_actual"] is None
    assert result["nutrition"]["logged_days"] == 1
    assert result["activity"]["logged_days"] == 1
    assert result["daily"][1]["has_calorie_data"] is True
    assert result["daily"][1]["has_protein_data"] is True


def test_food_presence_is_distinct_from_metric_availability_and_completeness():
    with Session() as db:
        event = add_event(db)
        when = datetime(2026, 7, 3, 16, tzinfo=timezone.utc)
        save_food_entry(db, event.id, "unknown", consumed_at=when)
        save_food_entry(db, event.id, "partial", estimated_calories=500, consumed_at=when)
        result = get_target_adherence(db, days=1, reference=date(2026, 7, 3))

    day = result["daily"][0]
    assert day["has_nutrition_data"] is True
    assert day["has_calorie_data"] is False
    assert day["has_protein_data"] is False
    assert day["calories_actual"] is None
    assert day["calories_percent_of_target"] is None
    assert day["calorie_entries_total"] == 2
    assert day["calorie_entries_with_data"] == 1
    assert result["coverage"]["nutrition_days_logged"] == 1
    assert result["coverage"]["calorie_days_available"] == 0


def test_activity_presence_is_distinct_from_step_availability():
    with Session() as db:
        event = add_event(db)
        when = datetime(2026, 7, 3, 16, tzinfo=timezone.utc)
        save_activity_entry(db, event.id, when)
        result = get_target_adherence(db, days=1, reference=date(2026, 7, 3))

    day = result["daily"][0]
    assert day["has_activity_data"] is True
    assert day["has_steps_data"] is False
    assert day["steps_actual"] is None
    assert day["steps_percent_of_target"] is None
    assert result["coverage"]["activity_days_logged"] == 1
    assert result["coverage"]["steps_days_available"] == 0


def test_partial_data_averages_only_known_days_and_result_is_json_serializable():
    with Session() as db:
        event = add_event(db)
        save_food_entry(db, event.id, "meal", estimated_calories=2000, consumed_at=datetime(2026, 7, 2, 16, tzinfo=timezone.utc))
        save_food_entry(db, event.id, "meal", consumed_at=datetime(2026, 7, 3, 16, tzinfo=timezone.utc))
        result = get_target_adherence(db, days=2, reference=date(2026, 7, 3))

    assert result["nutrition"]["average_calories_on_logged_days"] == 2000
    assert result["nutrition"]["average_protein_g_on_logged_days"] is None
    json.dumps(result)


def test_training_classification_and_proportional_targets():
    assert classify_workout_type("strength") == "strength"
    assert classify_workout_type("running") == "cardio"
    assert classify_workout_type("Chest") == "strength"
    assert classify_workout_type(" back ") == "strength"
    for label in (
        "legs", "shoulders", "arms", "biceps", "triceps", "push", "pull",
        "upper body", "lower body", "weights", "weight training",
        "resistance", "bodybuilding", "powerlifting",
    ):
        assert classify_workout_type(label) == "strength"
    for label in ("cardio", "cycling", "swimming", "walking", "rowing", "elliptical"):
        assert classify_workout_type(label) == "cardio"
    assert classify_workout_type("yoga") is None

    with Session() as db:
        event = add_event(db)
        when = datetime(2026, 7, 3, 16, tzinfo=timezone.utc)
        save_workout_session(db, event.id, workout_type="strength", started_at=when)
        save_workout_session(db, event.id, workout_type="running", started_at=when)
        save_workout_session(db, event.id, workout_type="yoga", started_at=when)
        result = get_target_adherence(db, days=14, reference=date(2026, 7, 3))

    training = result["training"]
    assert training["strength_sessions_actual"] == 1
    assert training["strength_sessions_target"] == 8.0
    assert training["cardio_sessions_actual"] == 1
    assert training["cardio_sessions_target"] == 6.0
    assert result["coverage"]["training_sessions_unclassified"] == 1
    assert result["training"]["training_classification_coverage_percent"] == 66.7


def test_zero_training_sessions_have_unknown_classification_coverage():
    with Session() as db:
        result = get_target_adherence(db, days=1, reference=date(2026, 7, 3))

    assert result["training"]["training_classification_coverage_percent"] is None


def test_body_part_sessions_are_all_classified_as_strength():
    with Session() as db:
        event = add_event(db)
        when = datetime(2026, 7, 3, 16, tzinfo=timezone.utc)
        for _ in range(7):
            save_workout_session(db, event.id, workout_type="chest", started_at=when)
        save_workout_session(db, event.id, workout_type="back", started_at=when)
        result = get_target_adherence(db, days=7, reference=date(2026, 7, 3))

    training = result["training"]
    coverage = result["coverage"]
    assert training["strength_sessions_actual"] == 8
    assert training["cardio_sessions_actual"] == 0
    assert coverage["training_sessions_total"] == 8
    assert coverage["training_sessions_classified"] == 8
    assert coverage["training_sessions_unclassified"] == 0

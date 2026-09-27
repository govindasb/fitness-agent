from datetime import datetime, timezone
from database.repository import (
    save_activity_entry,
    save_body_metric,
    save_exercise_set,
    save_food_entry,
    save_raw_event,
    save_sleep_entry,
    save_workout_session,
)
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dashboard.metrics import get_dashboard_metrics
from database.connection import Base


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_dashboard_metrics_returns_all_domains():
    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=datetime(
                2026,
                9,
                17,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )

    assert metrics["days_requested"] == 7

    assert set(metrics) == {
    "days_requested",
    "goal",
    "weight",
    "steps",
    "training",
    "nutrition",
    "sleep",
    "coverage",
    }

    assert len(metrics["weight"]["daily"]) == 7
    assert len(metrics["steps"]["daily"]) == 7
    assert len(metrics["training"]["daily"]) == 7
    assert len(metrics["nutrition"]["daily"]) == 7
    assert len(metrics["sleep"]["daily"]) == 7


def test_dashboard_metrics_preserves_missing_data():
    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=datetime(
                2026,
                9,
                17,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )

    assert metrics["weight"]["latest_weight_kg"] is None
    assert metrics["weight"]["change_kg"] is None

    assert metrics["steps"]["latest_steps"] is None
    assert metrics["steps"]["average_steps_on_logged_days"] is None

    assert metrics["nutrition"]["average_calories_on_recorded_days"] is None
    assert metrics["nutrition"]["average_protein_on_recorded_days"] is None

    assert metrics["sleep"]["average_duration_minutes_on_recorded_days"] is None

    assert metrics["training"]["workout_count"] == 0

def test_dashboard_metrics_calculates_goal_progress():
    measured_at = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        event = save_raw_event(db, "Weight 96.5 kg")

        save_body_metric(
            db,
            source_event_id=event.id,
            measured_at=measured_at,
            weight_kg=96.5,
        )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=measured_at,
        )

    assert metrics["goal"] == {
        "starting_weight_kg": 98.1,
        "target_weight_kg": 90.0,
        "current_weight_kg": 96.5,
        "weight_lost_kg": 1.6,
        "remaining_kg": 6.5,
        "progress_percent": 19.8,
    }

def test_dashboard_metrics_reports_empty_data_coverage():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert metrics["coverage"] == {
        "weight": {
            "days_logged": 0,
            "days_requested": 7,
        },
        "steps": {
            "days_logged": 0,
            "days_requested": 7,
        },
        "nutrition": {
            "days_logged": 0,
            "days_requested": 7,
            "calorie_days_available": 0,
            "protein_days_available": 0,
        },
        "sleep": {
            "days_logged": 0,
            "days_requested": 7,
            "duration_days_available": 0,
        },
        "training": {
            "workout_count": 0,
            "classified_workouts": 0,
            "unclassified_workouts": 0,
        },
    }

def test_dashboard_weight_trend_not_eligible_with_no_weight_data():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert metrics["weight"]["days_with_weight"] == 0
    assert metrics["weight"]["minimum_days_for_trend"] == 4
    assert metrics["weight"]["trend_eligible"] is False

def test_dashboard_weight_trend_eligible_with_sufficient_weight_data():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    measurements = [
        (datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc), 97.5),
        (datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc), 97.2),
        (datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc), 96.9),
        (datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc), 96.5),
    ]

    with Session() as db:
        for measured_at, weight_kg in measurements:
            event = save_raw_event(
                db,
                f"Weight {weight_kg} kg",
            )

            save_body_metric(
                db,
                source_event_id=event.id,
                measured_at=measured_at,
                weight_kg=weight_kg,
            )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert metrics["weight"]["days_with_weight"] == 4
    assert metrics["weight"]["minimum_days_for_trend"] == 4
    assert metrics["weight"]["trend_eligible"] is True

    assert metrics["weight"]["earliest_weight_kg"] == 97.5
    assert metrics["weight"]["latest_weight_kg"] == 96.5
    assert metrics["weight"]["change_kg"] == -1.0

def test_dashboard_step_metrics_preserve_missing_data():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert {k: v for k, v in metrics["steps"].items() if k not in {"daily", "latest_date", "latest_steps", "total_steps"}} == {
        "logged_days": 0,
        "average_steps_on_logged_days": None,
        "average_steps_percent_of_target_on_logged_days": None,
        "steps_days_available": 0,
        "days_requested": 7,
    }

def test_dashboard_step_metrics_use_only_logged_days():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    activity_logs = [
        (
            datetime(
                2026,
                9,
                16,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            8000,
        ),
        (
            datetime(
                2026,
                9,
                17,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            12000,
        ),
    ]

    with Session() as db:
        for recorded_at, steps in activity_logs:
            event = save_raw_event(
                db,
                f"{steps} steps",
            )

            save_activity_entry(
                db,
                source_event_id=event.id,
                recorded_at=recorded_at,
                steps=steps,
            )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert {k: v for k, v in metrics["steps"].items() if k not in {"daily", "latest_date", "latest_steps", "total_steps"}} == {
        "logged_days": 2,
        "average_steps_on_logged_days": 10000.0,
        "average_steps_percent_of_target_on_logged_days": 100.0,
        "steps_days_available": 2,
        "days_requested": 7,
    }

def test_dashboard_training_metrics_preserve_missing_data():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert {k: v for k, v in metrics["training"].items() if k != "daily"} == {
        "days_with_workouts": 0,
        "workout_count": 0,
        "workouts_by_type": {},
        "latest_workout_date": None,
        "latest_workout_type": None,
        "total_sets": 0,
        "set_logging_complete": None,
        "total_volume_kg": None,
        "total_duration_minutes": None,
        "classified_workouts": 0,
        "unclassified_workouts": 0,
        "classification_coverage_percent": None,
        "days_requested": 7,
    }

def test_dashboard_training_metrics_with_logged_workout():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        event = save_raw_event(
            db,
            "Chest workout: 45 minutes",
        )

        workout = save_workout_session(
            db,
            source_event_id=event.id,
            workout_type="chest",
            duration_minutes=45,
            started_at=reference,
        )

        save_exercise_set(
            db,
            workout_session_id=workout.id,
            exercise_name="Bench Press",
            set_number=1,
            weight_kg=50,
            reps=10,
        )

        save_exercise_set(
            db,
            workout_session_id=workout.id,
            exercise_name="Bench Press",
            set_number=2,
            weight_kg=60,
            reps=8,
        )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    training = metrics["training"]

    assert training["days_with_workouts"] == 1
    assert training["workout_count"] == 1
    assert training["workouts_by_type"] == {
        "chest": 1,
    }

    assert training["latest_workout_date"] == "2026-09-17"
    assert training["latest_workout_type"] == "chest"

    assert training["total_sets"] == 2
    assert training["set_logging_complete"] is True
    assert training["total_volume_kg"] == 980.0
    assert training["total_duration_minutes"] == 45

    assert training["classified_workouts"] == 1
    assert training["unclassified_workouts"] == 0
    assert training["classification_coverage_percent"] == 100.0

    assert training["days_requested"] == 7

def test_dashboard_nutrition_metrics_preserve_missing_data():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert {k: v for k, v in metrics["nutrition"].items() if k != "daily"} == {
        "days_with_food": 0,
        "days_with_calorie_data": 0,
        "days_with_protein_data": 0,
        "latest_date_with_food": None,
        "latest_calories": None,
        "latest_protein_g": None,
        "total_estimated_calories": None,
        "total_protein_g": None,
        "average_calories_on_recorded_days": None,
        "average_protein_on_recorded_days": None,
        "calorie_days_available": 0,
        "protein_days_available": 0,
        "days_requested": 7,
    }

def test_dashboard_food_logged_without_macros_preserves_unknown_nutrition():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        event = save_raw_event(
            db,
            "Lunch: rice and chicken",
        )

        save_food_entry(
            db,
            source_event_id=event.id,
            food_name="rice and chicken",
            meal_type="lunch",
            consumed_at=reference,
            is_estimated=False,
        )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    nutrition = metrics["nutrition"]

    # Food logging exists.
    assert nutrition["days_with_food"] == 1
    assert nutrition["latest_date_with_food"] == "2026-09-17"

    # Nutrient information was not provided.
    assert nutrition["days_with_calorie_data"] == 0
    assert nutrition["days_with_protein_data"] == 0

    assert nutrition["latest_calories"] is None
    assert nutrition["latest_protein_g"] is None

    assert nutrition["total_estimated_calories"] is None
    assert nutrition["total_protein_g"] is None

    assert nutrition["average_calories_on_recorded_days"] is None
    assert nutrition["average_protein_on_recorded_days"] is None

    # Adherence coverage must also remain unavailable.
    assert nutrition["calorie_days_available"] == 0
    assert nutrition["protein_days_available"] == 0

def test_dashboard_sleep_metrics_preserve_missing_data():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    assert {k: v for k, v in metrics["sleep"].items() if k != "daily"} == {
        "days_with_sleep": 0,
        "days_with_duration": 0,
        "latest_sleep_date": None,
        "latest_duration_minutes": None,
        "average_duration_minutes_on_recorded_days": None,
        "average_quality_rating": None,
        "total_sleep_minutes": None,
        "days_requested": 7,
    }


def test_dashboard_sleep_metrics_with_logged_sleep():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    sleep_start = datetime(
        2026,
        9,
        16,
        23,
        0,
        tzinfo=timezone.utc,
    )

    sleep_end = datetime(
        2026,
        9,
        17,
        6,
        30,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        event = save_raw_event(
            db,
            "Slept 7.5 hours, quality 4",
        )

        save_sleep_entry(
            db,
            source_event_id=event.id,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            duration_minutes=450,
            quality_rating=4,
        )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    sleep = metrics["sleep"]

    assert sleep["days_with_sleep"] == 1
    assert sleep["days_with_duration"] == 1

    assert sleep["latest_sleep_date"] == "2026-09-17"
    assert sleep["latest_duration_minutes"] == 450

    assert (
        sleep["average_duration_minutes_on_recorded_days"]
        == 450.0
    )
    assert sleep["average_quality_rating"] == 4.0
    assert sleep["total_sleep_minutes"] == 450

    assert sleep["days_requested"] == 7

def test_dashboard_workout_without_recorded_sets_preserves_unknown_sets():
    reference = datetime(
        2026,
        9,
        17,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with Session() as db:
        event = save_raw_event(
            db,
            "Today I did Upper B",
        )

        save_workout_session(
            db,
            source_event_id=event.id,
            workout_type="upper b",
            started_at=reference,
        )

        db.commit()

        metrics = get_dashboard_metrics(
            db,
            days=7,
            reference=reference,
        )

    training = metrics["training"]

    assert training["workout_count"] == 1
    assert training["days_with_workouts"] == 1

    # A workout was logged, but set details were not.
    # Missing set data must not be represented as zero sets performed.
    assert training["total_sets"] == 0
    assert training["set_logging_complete"] is False

    logged_day = next(
        day
        for day in training["daily"]
        if day["date"] == "2026-09-17"
    )

    assert logged_day["workout_count"] == 1
    assert logged_day["total_sets"] == 0
    assert logged_day["set_logging_complete"] is False
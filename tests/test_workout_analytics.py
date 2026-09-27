from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.workouts import (
    aggregate_workouts_by_local_day,
    summarize_workout_period,
)
from database.connection import Base
from database.repository import (
    save_exercise_set,
    save_raw_event,
    save_workout_session,
)


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


def save_workout(started_at, workout_type=None, duration=None, sets=None):
    with Session() as db:
        event = save_raw_event(db, "Workout")
        workout = save_workout_session(
            db,
            source_event_id=event.id,
            started_at=started_at,
            workout_type=workout_type,
            duration_minutes=duration,
        )
        for values in sets or []:
            save_exercise_set(
                db,
                workout_session_id=workout.id,
                exercise_name=values.pop("exercise_name", "exercise"),
                **values,
            )


def aggregate(days, reference):
    with Session() as db:
        return aggregate_workouts_by_local_day(db, days, reference)


def test_daily_workouts_aggregate_sessions_sets_volume_and_duration():
    timestamp = datetime(2026, 7, 7, 16, tzinfo=timezone.utc)
    save_workout(
        timestamp,
        "strength",
        45,
        [
            {"exercise_name": "squat", "weight_kg": 100, "reps": 5},
            {"exercise_name": "plank", "duration_seconds": 60},
        ],
    )
    save_workout(
        timestamp,
        "cardio",
        30,
        [{"exercise_name": "run", "distance_km": 5}],
    )

    result = aggregate(2, date(2026, 7, 7))

    assert result[0]["workout_count"] == 0
    assert result[0]["total_volume_kg"] is None
    assert result[1] == {
    "date": "2026-07-07",
    "workout_count": 2,
    "total_sets": 3,
    "set_logging_complete": True,
    "total_volume_kg": 500,
    "total_duration_minutes": 75,
    "workout_types": ["cardio", "strength"],
    }


def test_sets_without_weight_or_reps_do_not_create_zero_volume():
    save_workout(
        datetime(2026, 7, 7, 16, tzinfo=timezone.utc),
        "cardio",
        sets=[{"exercise_name": "run", "distance_km": 5}],
    )

    result = aggregate(1, date(2026, 7, 7))[0]

    assert result["total_sets"] == 1
    assert result["total_volume_kg"] is None
    assert result["total_duration_minutes"] is None


def test_workout_summary_counts_sessions_by_type_and_uses_latest_time():
    save_workout(
        datetime(2026, 7, 7, 20, tzinfo=timezone.utc),
        "evening",
        40,
        [{"weight_kg": 50, "reps": 10}],
    )
    save_workout(
        datetime(2026, 7, 6, 20, tzinfo=timezone.utc),
        "cardio",
        30,
    )
    save_workout(
        datetime(2026, 7, 7, 12, tzinfo=timezone.utc),
        "strength",
    )

    with Session() as db:
        daily = aggregate_workouts_by_local_day(db, 3, date(2026, 7, 8))
        summary = summarize_workout_period(
            db,
            daily,
            days=3,
            reference=date(2026, 7, 8),
        )

    assert summary == {
        "days_requested": 3,
        "days_with_workouts": 2,
        "workout_count": 3,
        "total_sets": 1,
        "set_logging_complete": False,
        "total_volume_kg": 500,
        "total_duration_minutes": 70,
        "workouts_by_type": {
            "cardio": 1,
            "evening": 1,
            "strength": 1,
        },
        "latest_workout_date": "2026-07-07",
        "latest_workout_type": "evening",
    }


def test_workout_midnight_and_dst_boundaries_use_local_dates():
    save_workout(
        datetime(2026, 3, 8, 4, 30, tzinfo=timezone.utc),
        "late",
    )
    save_workout(
        datetime(2026, 3, 8, 5, 30, tzinfo=timezone.utc),
        "early",
    )

    result = aggregate(2, date(2026, 3, 8))

    assert [day["workout_types"] for day in result] == [["late"], ["early"]]

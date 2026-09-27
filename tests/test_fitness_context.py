import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import agent.tools as tools
from database.connection import Base
from database.repository import (
    save_activity_entry,
    save_body_metric,
    save_exercise_set,
    save_food_entry,
    save_raw_event,
    save_sleep_entry,
    save_workout_session,
)


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=engine)
REFERENCE = datetime(2026, 7, 8, 16, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def reset_database(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(tools, "SessionLocal", Session)
    yield
    Base.metadata.drop_all(bind=engine)


def seed_context_data():
    with Session() as db:
        event = save_raw_event(db, "Context data")
        save_body_metric(
            db,
            source_event_id=event.id,
            measured_at=datetime(2026, 7, 7, 12, tzinfo=timezone.utc),
            weight_kg=96.5,
        )
        save_activity_entry(
            db,
            source_event_id=event.id,
            recorded_at=datetime(2026, 7, 7, 15, tzinfo=timezone.utc),
            steps=8000,
            active_minutes=45,
        )
        save_food_entry(
            db,
            source_event_id=event.id,
            consumed_at=datetime(2026, 7, 7, 16, tzinfo=timezone.utc),
            food_name="chicken",
            estimated_calories=300,
            protein_g=40,
            is_estimated=True,
        )
        save_food_entry(
            db,
            source_event_id=event.id,
            consumed_at=datetime(2026, 7, 7, 16, tzinfo=timezone.utc),
            food_name="rice",
            estimated_calories=250,
            carbs_g=55,
            is_estimated=False,
        )
        save_sleep_entry(
            db,
            source_event_id=event.id,
            sleep_start=datetime(2026, 7, 7, 3, tzinfo=timezone.utc),
            sleep_end=datetime(2026, 7, 7, 11, tzinfo=timezone.utc),
            duration_minutes=480,
            quality_rating=8,
        )
        workout = save_workout_session(
            db,
            source_event_id=event.id,
            started_at=datetime(2026, 7, 7, 20, tzinfo=timezone.utc),
            workout_type="strength",
            duration_minutes=45,
        )
        save_exercise_set(
            db,
            workout_session_id=workout.id,
            exercise_name="squat",
            weight_kg=100,
            reps=5,
        )


def test_context_has_stable_sections_profile_and_windows():
    context = tools.get_fitness_context(reference=REFERENCE)

    assert list(context) == [
        "generated_at",
        "timezone",
        "profile",
        "weight",
        "activity",
        "nutrition",
        "sleep",
        "training",
        "data_quality",
    ]
    assert context["timezone"] == "America/New_York"
    assert context["profile"]["goal"] == "fat_loss"
    assert context["profile"]["target_weight_kg"] == 90.0
    assert context["weight"]["window_days"] == 14
    assert len(context["weight"]["daily"]) == 14
    for section in ("activity", "nutrition", "sleep", "training"):
        assert context[section]["window_days"] == 7
        assert len(context[section]["daily"]) == 7


def test_all_domains_use_the_same_reference_and_represent_missing_days():
    context = tools.get_fitness_context(reference=REFERENCE)

    assert context["weight"]["daily"][-1]["date"] == "2026-07-08"
    for section in ("activity", "nutrition", "sleep", "training"):
        assert context[section]["daily"][-1]["date"] == "2026-07-08"

    assert context["weight"]["daily"][-1]["latest_weight_kg"] is None
    assert context["activity"]["daily"][-1]["steps"] is None
    assert context["nutrition"]["daily"][-1]["total_protein_g"] is None
    assert context["sleep"]["daily"][-1]["total_duration_minutes"] is None
    assert context["training"]["daily"][-1]["total_volume_kg"] is None


def test_context_summaries_and_data_quality_are_deterministic():
    seed_context_data()

    context = tools.get_fitness_context(reference=REFERENCE)

    assert context["weight"]["latest_weight_kg"] == 96.5
    assert context["activity"]["latest_steps"] == 8000
    assert context["nutrition"]["latest_calories"] == 550
    assert context["nutrition"]["latest_protein_g"] == 40
    assert context["sleep"]["latest_duration_minutes"] == 480
    assert context["training"]["latest_workout_type"] == "strength"
    assert context["data_quality"] == {
        "weight_days_logged": 1,
        "activity_days_logged": 1,
        "food_days_logged": 1,
        "calorie_days_logged": 1,
        "protein_days_logged": 1,
        "sleep_days_logged": 1,
        "workout_days_logged": 1,
        "nutrition_estimation_ratio": 0.5,
    }


def test_generated_at_is_utc_iso_and_context_is_directly_serializable():
    context = tools.get_fitness_context(reference=REFERENCE)

    generated_at = datetime.fromisoformat(context["generated_at"])
    assert generated_at == REFERENCE
    assert generated_at.tzinfo is timezone.utc
    json.dumps(context)

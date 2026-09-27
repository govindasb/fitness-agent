from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base
from database.repository import (
    mark_event_processed,
    save_activity_entry,
    save_body_metric,
    save_exercise_set,
    save_food_entry,
    save_raw_event,
    save_sleep_entry,
    save_workout_session,
)


# Temporary in-memory SQLite database used only by tests.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)

Base.metadata.create_all(bind=test_engine)


def test_database_connection():
    assert test_engine is not None
    assert Base is not None


def test_expected_tables_exist():
    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "raw_events",
        "body_metrics",
        "food_entries",
        "workout_sessions",
        "exercise_sets",
        "activity_entries",
        "sleep_entries",
    }

    assert expected_tables.issubset(tables)


def test_save_raw_event():
    db = TestSessionLocal()

    try:
        event = save_raw_event(db, "Test raw fitness event")

        assert event.id is not None
        assert event.raw_text == "Test raw fitness event"
        assert event.processing_status == "pending"

    finally:
        db.close()


def test_save_body_metric():
    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Weight this morning was 97.5 kg",
        )

        metric = save_body_metric(
            db,
            source_event_id=raw_event.id,
            weight_kg=97.5,
        )

        assert metric.id is not None
        assert metric.weight_kg == 97.5
        assert metric.source_event_id == raw_event.id

    finally:
        db.close()


def test_save_food_entry():
    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Breakfast: 2 eggs",
        )

        food = save_food_entry(
            db,
            source_event_id=raw_event.id,
            food_name="egg",
            meal_type="breakfast",
            quantity=2,
            unit="whole",
        )

        assert food.id is not None
        assert food.food_name == "egg"
        assert food.quantity == 2
        assert food.source_event_id == raw_event.id

    finally:
        db.close()


def test_save_workout():
    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Chest workout: Bench press 50kg for 10 reps",
        )

        workout = save_workout_session(
            db,
            source_event_id=raw_event.id,
            workout_type="chest",
        )

        exercise_set = save_exercise_set(
            db,
            workout_session_id=workout.id,
            exercise_name="Bench Press",
            set_number=1,
            weight_kg=50,
            reps=10,
        )

        assert workout.id is not None
        assert workout.source_event_id == raw_event.id

        assert exercise_set.id is not None
        assert exercise_set.workout_session_id == workout.id
        assert exercise_set.exercise_name == "Bench Press"
        assert exercise_set.weight_kg == 50
        assert exercise_set.reps == 10

    finally:
        db.close()


def test_save_activity_entry():
    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Walked 10,500 steps today",
        )

        activity = save_activity_entry(
            db,
            source_event_id=raw_event.id,
            steps=10500,
        )

        assert activity.id is not None
        assert activity.steps == 10500
        assert activity.source_event_id == raw_event.id

    finally:
        db.close()


def test_save_sleep_entry():
    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Slept for 7 hours and felt good",
        )

        sleep = save_sleep_entry(
            db,
            source_event_id=raw_event.id,
            duration_minutes=420,
            quality_rating=4,
            notes="Felt good",
        )

        assert sleep.id is not None
        assert sleep.duration_minutes == 420
        assert sleep.quality_rating == 4
        assert sleep.source_event_id == raw_event.id

    finally:
        db.close()


def test_mark_event_processed():
    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Weight was 97.2 kg",
        )

        updated_event = mark_event_processed(
            db,
            event_id=raw_event.id,
            event_type="body_metric",
        )

        assert updated_event.processing_status == "processed"
        assert updated_event.event_type == "body_metric"
        assert updated_event.parser_version == "manual-v1"

    finally:
        db.close()
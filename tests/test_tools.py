from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from database.connection import Base
from database.schema import (
    ActivityEntry,
    BodyMetric,
    FoodEntry,
    RawEvent,
    SleepEntry,
    WorkoutSession,
)
import agent.tools as tools
from database.repository import (
    save_activity_entry,
    save_body_metric,
    save_raw_event,
)
from database.timezone import APPLICATION_TIMEZONE

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

@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)



def test_mixed_input_uses_one_raw_event(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    result = tools.log_mixed_input(
        "Weight 96.4 kg and walked 7500 steps",
        body_metrics=[{"weight_kg": 96.4}],
        activities=[{"steps": 7500}],
    )

    db = TestSessionLocal()

    try:
        raw_events = db.query(RawEvent).all()
        body_metrics = db.query(BodyMetric).all()
        activities = db.query(ActivityEntry).all()

        assert len(raw_events) == 1
        assert len(body_metrics) == 1
        assert len(activities) == 1

        raw_event_id = raw_events[0].id

        assert result["raw_event_id"] == raw_event_id
        assert body_metrics[0].source_event_id == raw_event_id
        assert activities[0].source_event_id == raw_event_id

    finally:
        db.close()


def test_log_weight_preserves_explicit_measured_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    measured_at = datetime(2026, 9, 10, 7, 15, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_weight(
        "Weighed 96.4 kg yesterday morning",
        weight_kg=96.4,
        measured_at=measured_at,
    )

    db = TestSessionLocal()

    try:
        metric = db.get(BodyMetric, result["body_metric_id"])
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert metric.measured_at == measured_at
        assert raw_event.event_time == measured_at
    finally:
        db.close()


def test_mixed_input_preserves_explicit_body_metric_measured_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    measured_at = datetime(2026, 9, 10, 7, 15, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_mixed_input(
        "Weighed 96.4 kg yesterday morning",
        body_metrics=[{"measured_at": measured_at, "weight_kg": 96.4}],
    )

    db = TestSessionLocal()

    try:
        metric_id = result["body_metrics"][0]["body_metric_id"]
        metric = db.get(BodyMetric, metric_id)
        assert metric.measured_at == measured_at
    finally:
        db.close()


def test_log_weight_uses_default_measured_at_when_omitted(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    before_logging = datetime.now(timezone.utc)

    result = tools.log_weight(
        "Weighed 96.4 kg this morning",
        weight_kg=96.4,
    )

    after_logging = datetime.now(timezone.utc)
    db = TestSessionLocal()

    try:
        metric = db.get(BodyMetric, result["body_metric_id"])
        assert before_logging <= metric.measured_at <= after_logging
    finally:
        db.close()


def test_log_activity_preserves_explicit_recorded_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    recorded_at = datetime(2026, 9, 10, 18, 30, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_activity(
        "Walked 8500 steps yesterday",
        recorded_at=recorded_at,
        steps=8500,
    )

    db = TestSessionLocal()

    try:
        activity = db.get(ActivityEntry, result["activity_id"])
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert activity.recorded_at == recorded_at
        assert raw_event.event_time == recorded_at
    finally:
        db.close()


def test_mixed_input_preserves_explicit_activity_recorded_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    recorded_at = datetime(2026, 9, 10, 18, 30, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_mixed_input(
        "Walked 8500 steps yesterday",
        activities=[{"recorded_at": recorded_at, "steps": 8500}],
    )

    db = TestSessionLocal()

    try:
        activity_id = result["activities"][0]["activity_id"]
        activity = db.get(ActivityEntry, activity_id)
        assert activity.recorded_at == recorded_at
    finally:
        db.close()


def test_log_activity_uses_default_recorded_at_when_omitted(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    before_logging = datetime.now(timezone.utc)

    result = tools.log_activity(
        "Walked 8500 steps today",
        steps=8500,
    )

    after_logging = datetime.now(timezone.utc)
    db = TestSessionLocal()

    try:
        activity = db.get(ActivityEntry, result["activity_id"])
        assert before_logging <= activity.recorded_at <= after_logging
    finally:
        db.close()


def test_log_food_preserves_explicit_consumed_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    consumed_at = datetime(2026, 9, 10, 12, 30, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_food(
        "Ate chicken for lunch",
        items=[{"food_name": "chicken"}],
        meal_type="lunch",
        consumed_at=consumed_at,
    )

    db = TestSessionLocal()

    try:
        food = db.get(FoodEntry, result["items"][0]["food_entry_id"])
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert food.consumed_at == consumed_at
        assert raw_event.event_time == consumed_at
    finally:
        db.close()


def test_mixed_input_preserves_explicit_food_consumed_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    consumed_at = datetime(2026, 9, 10, 12, 30, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_mixed_input(
        "Ate chicken for lunch",
        food_entries=[
            {
                "meal_type": "lunch",
                "consumed_at": consumed_at,
                "items": [{"food_name": "chicken"}],
            }
        ],
    )

    db = TestSessionLocal()

    try:
        food_id = result["food_entries"][0]["items"][0]["food_entry_id"]
        food = db.get(FoodEntry, food_id)
        assert food.consumed_at == consumed_at
    finally:
        db.close()


def test_log_food_uses_default_consumed_at_when_omitted(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    before_logging = datetime.now(timezone.utc)

    result = tools.log_food(
        "Ate chicken for lunch",
        items=[{"food_name": "chicken"}],
        meal_type="lunch",
    )

    after_logging = datetime.now(timezone.utc)
    db = TestSessionLocal()

    try:
        food = db.get(FoodEntry, result["items"][0]["food_entry_id"])
        assert before_logging <= food.consumed_at <= after_logging
    finally:
        db.close()


def test_food_items_inherit_parent_consumed_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    consumed_at = datetime(2026, 9, 10, 12, 30, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_food(
        "Ate chicken and rice for lunch",
        items=[
            {"food_name": "chicken"},
            {"food_name": "rice"},
        ],
        meal_type="lunch",
        consumed_at=consumed_at,
    )

    db = TestSessionLocal()

    try:
        food_ids = [item["food_entry_id"] for item in result["items"]]
        foods = [db.get(FoodEntry, food_id) for food_id in food_ids]
        assert [food.consumed_at for food in foods] == [
            consumed_at,
            consumed_at,
        ]
    finally:
        db.close()


def test_log_workout_preserves_explicit_started_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    started_at = datetime(2026, 9, 10, 18, 0, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_workout(
        "Completed a chest workout",
        workout_type="chest",
        started_at=started_at,
    )

    db = TestSessionLocal()

    try:
        workout = db.get(WorkoutSession, result["workout_session_id"])
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert workout.started_at == started_at
        assert raw_event.event_time == started_at
    finally:
        db.close()


def test_mixed_input_preserves_explicit_workout_started_at(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    started_at = datetime(2026, 9, 10, 18, 0, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_mixed_input(
        "Completed a chest workout",
        workouts=[
            {
                "workout_type": "chest",
                "started_at": started_at,
                "sets": [],
            }
        ],
    )

    db = TestSessionLocal()

    try:
        workout_id = result["workouts"][0]["workout_session_id"]
        workout = db.get(WorkoutSession, workout_id)
        assert workout.started_at == started_at
    finally:
        db.close()


def test_log_workout_uses_default_started_at_when_omitted(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    before_logging = datetime.now(timezone.utc)

    result = tools.log_workout(
        "Completed a chest workout",
        workout_type="chest",
    )

    after_logging = datetime.now(timezone.utc)
    db = TestSessionLocal()

    try:
        workout = db.get(WorkoutSession, result["workout_session_id"])
        assert before_logging <= workout.started_at <= after_logging
    finally:
        db.close()


def test_log_sleep_preserves_explicit_start_and_end(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    sleep_start = datetime(2026, 9, 9, 23, 0, tzinfo=APPLICATION_TIMEZONE)
    sleep_end = datetime(2026, 9, 10, 7, 0, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_sleep(
        "Slept from 11 PM to 7 AM",
        sleep_start=sleep_start,
        sleep_end=sleep_end,
    )

    db = TestSessionLocal()

    try:
        sleep = db.get(SleepEntry, result["sleep_entry_id"])
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert sleep.sleep_start == sleep_start
        assert sleep.sleep_end == sleep_end
        assert raw_event.event_time == sleep_start
    finally:
        db.close()


def test_mixed_input_preserves_explicit_sleep_start_and_end(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    sleep_start = datetime(2026, 9, 9, 23, 0, tzinfo=APPLICATION_TIMEZONE)
    sleep_end = datetime(2026, 9, 10, 7, 0, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_mixed_input(
        "Slept from 11 PM to 7 AM",
        sleep_entries=[
            {
                "sleep_start": sleep_start,
                "sleep_end": sleep_end,
                "duration_minutes": 480,
            }
        ],
    )

    db = TestSessionLocal()

    try:
        sleep_id = result["sleep_entries"][0]["sleep_entry_id"]
        sleep = db.get(SleepEntry, sleep_id)
        assert sleep.sleep_start == sleep_start
        assert sleep.sleep_end == sleep_end
    finally:
        db.close()


def test_log_sleep_allows_omitted_optional_timestamps(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    result = tools.log_sleep(
        "Slept for 7 hours",
        duration_minutes=420,
    )

    db = TestSessionLocal()

    try:
        sleep = db.get(SleepEntry, result["sleep_entry_id"])
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert sleep.sleep_start is None
        assert sleep.sleep_end is None
        assert raw_event.event_time is None
    finally:
        db.close()


def test_mixed_input_sets_event_time_when_all_domain_times_agree(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)
    event_time = datetime(2026, 9, 10, 7, 15, tzinfo=APPLICATION_TIMEZONE)

    result = tools.log_mixed_input(
        "Weighed 96.4 kg and walked 7500 steps",
        body_metrics=[{"weight_kg": 96.4, "measured_at": event_time}],
        activities=[{"steps": 7500, "recorded_at": event_time}],
    )

    db = TestSessionLocal()

    try:
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert raw_event.event_time == event_time
    finally:
        db.close()


def test_mixed_input_leaves_event_time_null_for_conflicting_times(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    result = tools.log_mixed_input(
        "Weighed 96.4 kg this morning and walked tonight",
        body_metrics=[
            {
                "weight_kg": 96.4,
                "measured_at": datetime(
                    2026, 9, 10, 7, 15, tzinfo=APPLICATION_TIMEZONE
                ),
            }
        ],
        activities=[
            {
                "steps": 7500,
                "recorded_at": datetime(
                    2026, 9, 10, 20, 0, tzinfo=APPLICATION_TIMEZONE
                ),
            }
        ],
    )

    db = TestSessionLocal()

    try:
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert raw_event.event_time is None
    finally:
        db.close()


def test_mixed_input_leaves_event_time_null_when_a_domain_time_is_missing(
    monkeypatch,
):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    result = tools.log_mixed_input(
        "Weighed 96.4 kg and walked 7500 steps",
        body_metrics=[
            {
                "weight_kg": 96.4,
                "measured_at": datetime(
                    2026, 9, 10, 7, 15, tzinfo=APPLICATION_TIMEZONE
                ),
            }
        ],
        activities=[{"steps": 7500}],
    )

    db = TestSessionLocal()

    try:
        raw_event = db.get(RawEvent, result["raw_event_id"])
        assert raw_event.event_time is None
    finally:
        db.close()


def test_mixed_input_rolls_back_on_failure(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    def fail_activity(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(tools, "save_activity_entry", fail_activity)

    try:
        tools.log_mixed_input(
            "Weight 96.2 kg and walked 7000 steps",
            body_metrics=[{"weight_kg": 96.2}],
            activities=[{"steps": 7000}],
        )
    except RuntimeError:
        pass

    db = TestSessionLocal()

    try:
        assert db.query(RawEvent).count() == 0
        assert db.query(BodyMetric).count() == 0
        assert db.query(ActivityEntry).count() == 0

    finally:
        db.close()

def test_get_recent_weights_returns_latest_first(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    db = TestSessionLocal()

    try:
        raw_event_1 = save_raw_event(db, "Weight 98.0 kg")
        raw_event_2 = save_raw_event(db, "Weight 97.5 kg")

        save_body_metric(
            db,
            source_event_id=raw_event_1.id,
            weight_kg=98.0,
        )

        save_body_metric(
            db,
            source_event_id=raw_event_2.id,
            weight_kg=97.5,
        )
    finally:
        db.close()

    rows = tools.get_recent_weights(2)

    assert len(rows) == 2
    assert rows[0]["weight_kg"] == 97.5
    assert rows[1]["weight_kg"] == 98.0

def test_get_weight_summary(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    db = TestSessionLocal()

    try:
        for weight in [98.0, 97.5, 97.0]:
            raw_event = save_raw_event(
                db,
                f"Weight {weight} kg",
            )

            save_body_metric(
                db,
                source_event_id=raw_event.id,
                weight_kg=weight,
            )
    finally:
        db.close()

    summary = tools.get_weight_summary(3)

    assert summary["count"] == 3
    assert summary["latest_weight_kg"] == 97.0
    assert summary["average_weight_kg"] == 97.5

def test_get_fitness_context(monkeypatch):
    monkeypatch.setattr(tools, "SessionLocal", TestSessionLocal)

    db = TestSessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            "Weight 97 kg and walked 9000 steps",
        )

        save_body_metric(
            db,
            source_event_id=raw_event.id,
            weight_kg=97.0,
        )

        from database.repository import save_activity_entry

        save_activity_entry(
            db,
            source_event_id=raw_event.id,
            steps=9000,
        )
    finally:
        db.close()

    context = tools.get_fitness_context()

    assert context["weight"]["latest_weight_kg"] == 97.0
    assert context["activity"]["latest_steps"] == 9000
    assert context["profile"]["goal"] == "fat_loss"
    assert context["profile"]["target_weight_kg"] == 90.0
    assert context["profile"]["training_days_per_week"] == 4

    assert "nutrition" in context
    assert "sleep" in context
    assert "training" in context

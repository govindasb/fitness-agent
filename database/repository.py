from datetime import datetime

from sqlalchemy.orm import Session

from database.schema import (
    ActivityEntry,
    BodyMetric,
    ExerciseSet,
    FoodEntry,
    RawEvent,
    SleepEntry,
    WorkoutSession,
)


def _save(db: Session, obj, commit: bool):
    """
    Persist an object.

    commit=True:
        Commit immediately. Used by normal standalone repository calls.

    commit=False:
        Flush only. Used when a higher-level operation owns the transaction.
    """
    db.add(obj)

    if commit:
        db.commit()
        db.refresh(obj)
    else:
        db.flush()

    return obj


def save_raw_event(
    db: Session,
    raw_text: str,
    commit: bool = True,
    event_time: datetime | None = None,
) -> RawEvent:
    event = RawEvent(
        raw_text=raw_text,
        event_time=event_time,
    )

    return _save(db, event, commit)


def save_body_metric(
    db: Session,
    source_event_id: int,
    weight_kg: float | None = None,
    waist_cm: float | None = None,
    body_fat_percent: float | None = None,
    resting_heart_rate: int | None = None,
    commit: bool = True,
    measured_at: datetime | None = None,
) -> BodyMetric:
    metric_data = {
        "source_event_id": source_event_id,
        "weight_kg": weight_kg,
        "waist_cm": waist_cm,
        "body_fat_percent": body_fat_percent,
        "resting_heart_rate": resting_heart_rate,
    }

    if measured_at is not None:
        metric_data["measured_at"] = measured_at

    metric = BodyMetric(**metric_data)

    return _save(db, metric, commit)


def save_food_entry(
    db: Session,
    source_event_id: int,
    food_name: str,
    meal_type: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    estimated_calories: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    fiber_g: float | None = None,
    is_estimated: bool = True,
    commit: bool = True,
    consumed_at: datetime | None = None,
) -> FoodEntry:
    food_data = {
        "source_event_id": source_event_id,
        "food_name": food_name,
        "meal_type": meal_type,
        "quantity": quantity,
        "unit": unit,
        "estimated_calories": estimated_calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber_g,
        "is_estimated": is_estimated,
    }

    if consumed_at is not None:
        food_data["consumed_at"] = consumed_at

    food_entry = FoodEntry(**food_data)

    return _save(db, food_entry, commit)


def save_workout_session(
    db: Session,
    source_event_id: int,
    workout_type: str | None = None,
    duration_minutes: int | None = None,
    notes: str | None = None,
    commit: bool = True,
    started_at: datetime | None = None,
) -> WorkoutSession:
    workout_data = {
        "source_event_id": source_event_id,
        "workout_type": workout_type,
        "duration_minutes": duration_minutes,
        "notes": notes,
    }

    if started_at is not None:
        workout_data["started_at"] = started_at

    workout = WorkoutSession(**workout_data)

    return _save(db, workout, commit)


def save_exercise_set(
    db: Session,
    workout_session_id: int,
    exercise_name: str,
    set_number: int | None = None,
    weight_kg: float | None = None,
    reps: int | None = None,
    duration_seconds: int | None = None,
    distance_km: float | None = None,
    rpe: float | None = None,
    commit: bool = True,
) -> ExerciseSet:
    exercise_set = ExerciseSet(
        workout_session_id=workout_session_id,
        exercise_name=exercise_name,
        set_number=set_number,
        weight_kg=weight_kg,
        reps=reps,
        duration_seconds=duration_seconds,
        distance_km=distance_km,
        rpe=rpe,
    )

    return _save(db, exercise_set, commit)


def save_activity_entry(
    db: Session,
    source_event_id: int,
    recorded_at: datetime | None = None,
    steps: int | None = None,
    distance_km: float | None = None,
    active_minutes: int | None = None,
    calories_burned: float | None = None,
    commit: bool = True,
) -> ActivityEntry:
    activity_data = {
        "source_event_id": source_event_id,
        "steps": steps,
        "distance_km": distance_km,
        "active_minutes": active_minutes,
        "calories_burned": calories_burned,
    }

    if recorded_at is not None:
        activity_data["recorded_at"] = recorded_at

    activity = ActivityEntry(
        **activity_data,
    )

    return _save(db, activity, commit)


def save_sleep_entry(
    db: Session,
    source_event_id: int,
    sleep_start=None,
    sleep_end=None,
    duration_minutes: int | None = None,
    quality_rating: int | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> SleepEntry:
    sleep = SleepEntry(
        source_event_id=source_event_id,
        sleep_start=sleep_start,
        sleep_end=sleep_end,
        duration_minutes=duration_minutes,
        quality_rating=quality_rating,
        notes=notes,
    )

    return _save(db, sleep, commit)


def mark_event_processed(
    db: Session,
    event_id: int,
    event_type: str,
    parser_version: str = "manual-v1",
    commit: bool = True,
    event_time: datetime | None = None,
) -> RawEvent:
    event = (
        db.query(RawEvent)
        .filter(RawEvent.id == event_id)
        .first()
    )

    if event is None:
        raise ValueError(
            f"Raw event {event_id} was not found."
        )

    event.processing_status = "processed"
    event.event_type = event_type
    event.parser_version = parser_version
    if event_time is not None:
        event.event_time = event_time

    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()

    return event


def mark_event_failed(
    db: Session,
    event_id: int,
    parser_version: str,
    commit: bool = True,
) -> RawEvent:
    event = db.query(RawEvent).filter(RawEvent.id == event_id).first()

    if event is None:
        raise ValueError(f"Raw event {event_id} was not found.")

    event.processing_status = "failed"
    event.parser_version = parser_version

    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()

    return event

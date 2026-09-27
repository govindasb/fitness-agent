from analytics.activity import (
    aggregate_activity_by_local_day,
    summarize_daily_activity,
)
from analytics.food import aggregate_food_by_local_day, summarize_daily_food
from analytics.sleep import aggregate_sleep_by_local_day, summarize_daily_sleep
from analytics.weight import (
    aggregate_weight_by_local_day,
    summarize_weight_trend,
)
from analytics.workouts import (
    aggregate_workouts_by_local_day,
    summarize_workout_period,
)
from agent.context_builder import build_fitness_context
from database.connection import SessionLocal
from database.schema import ActivityEntry, FoodEntry, SleepEntry, ExerciseSet, WorkoutSession
from database.repository import (
    BodyMetric,
    mark_event_processed,
    save_activity_entry,
    save_body_metric,
    save_exercise_set,
    save_food_entry,
    save_raw_event,
    save_sleep_entry,
    save_workout_session,
)
from models.activity import ParsedActivity
from models.body_metric import ParsedBodyMetric
from models.food import ParsedFoodEntry
from models.sleep import ParsedSleep
from models.workout import ParsedWorkout
from models.parsed_input import ParsedInput
from config.profile import load_profile


def _get_mixed_event_time(validated: ParsedInput):
    event_times = [
        *(item.measured_at for item in validated.body_metrics),
        *(entry.consumed_at for entry in validated.food_entries),
        *(item.recorded_at for item in validated.activities),
        *(item.sleep_start or item.sleep_end for item in validated.sleep_entries),
        *(entry.started_at for entry in validated.workouts),
    ]

    if not event_times or any(event_time is None for event_time in event_times):
        return None

    first_event_time = event_times[0]
    if all(event_time == first_event_time for event_time in event_times):
        return first_event_time

    return None

def log_weight(
    raw_text: str,
    weight_kg: float,
    raw_event_id: int | None = None,
    measured_at=None,
):
    validated = ParsedBodyMetric(
        weight_kg=weight_kg,
        measured_at=measured_at,
    )
    weight_kg = validated.weight_kg
    measured_at = validated.measured_at
    db = SessionLocal()

    try:
        created_raw_event = raw_event_id is None

        if created_raw_event:
            raw_event = save_raw_event(
                db,
                raw_text,
                event_time=measured_at,
            )
            raw_event_id = raw_event.id

        metric = save_body_metric(
            db,
            source_event_id=raw_event_id,
            measured_at=measured_at,
            weight_kg=weight_kg,
        )

        if created_raw_event:
            mark_event_processed(
                db,
                event_id=raw_event_id,
                event_type="body_metric",
                parser_version="codex-v1",
            )

        return {
            "raw_event_id": raw_event_id,
            "body_metric_id": metric.id,
            "weight_kg": metric.weight_kg,
        }

    finally:
        db.close()


def log_activity(
    raw_text: str,
    recorded_at=None,
    steps: int | None = None,
    distance_km: float | None = None,
    active_minutes: int | None = None,
    calories_burned: float | None = None,
    raw_event_id: int | None = None,
):
    validated = ParsedActivity(
    recorded_at=recorded_at,
    steps=steps,
    distance_km=distance_km,
    active_minutes=active_minutes,
    calories_burned=calories_burned,
    )

    recorded_at = validated.recorded_at
    steps = validated.steps
    distance_km = validated.distance_km
    active_minutes = validated.active_minutes
    calories_burned = validated.calories_burned
    db = SessionLocal()

    try:
        created_raw_event = raw_event_id is None

        if created_raw_event:
            raw_event = save_raw_event(
                db,
                raw_text,
                event_time=recorded_at,
            )
            raw_event_id = raw_event.id

        activity = save_activity_entry(
            db,
            source_event_id=raw_event_id,
            recorded_at=recorded_at,
            steps=steps,
            distance_km=distance_km,
            active_minutes=active_minutes,
            calories_burned=calories_burned,
        )

        if created_raw_event:
            mark_event_processed(
                db,
                event_id=raw_event_id,
                event_type="activity",
                parser_version="codex-v1",
            )

        return {
            "raw_event_id": raw_event_id,
            "activity_id": activity.id,
            "steps": activity.steps,
            "distance_km": activity.distance_km,
            "active_minutes": activity.active_minutes,
            "calories_burned": activity.calories_burned,
        }

    finally:
        db.close()


def log_food(
    raw_text: str,
    items: list[dict],
    meal_type: str | None = None,
    raw_event_id: int | None = None,
    consumed_at=None,
):
    validated = ParsedFoodEntry(
        meal_type=meal_type,
        consumed_at=consumed_at,
        items=items,
    )

    meal_type = validated.meal_type
    consumed_at = validated.consumed_at
    items = [item.model_dump() for item in validated.items]
    db = SessionLocal()

    try:
        created_raw_event = raw_event_id is None

        if created_raw_event:
            raw_event = save_raw_event(
                db,
                raw_text,
                event_time=consumed_at,
            )
            raw_event_id = raw_event.id

        saved_items = []

        for item in items:
            food = save_food_entry(
                db,
                source_event_id=raw_event_id,
                food_name=item["food_name"],
                consumed_at=consumed_at,
                meal_type=meal_type,
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                estimated_calories=item.get("estimated_calories"),
                protein_g=item.get("protein_g"),
                carbs_g=item.get("carbs_g"),
                fat_g=item.get("fat_g"),
                fiber_g=item.get("fiber_g"),
                is_estimated=item.get("is_estimated", True),
            )

            saved_items.append(
                {
                    "food_entry_id": food.id,
                    "food_name": food.food_name,
                    "quantity": food.quantity,
                    "unit": food.unit,
                }
            )

        if created_raw_event:
            mark_event_processed(
                db,
                event_id=raw_event_id,
                event_type="food",
                parser_version="codex-v1",
            )

        return {
            "raw_event_id": raw_event_id,
            "meal_type": meal_type,
            "items": saved_items,
        }

    finally:
        db.close()


def log_sleep(
    raw_text: str,
    sleep_start=None,
    sleep_end=None,
    duration_minutes: int | None = None,
    quality_rating: int | None = None,
    notes: str | None = None,
    raw_event_id: int | None = None,
):
    validated = ParsedSleep(
    sleep_start=sleep_start,
    sleep_end=sleep_end,
    duration_minutes=duration_minutes,
    quality_rating=quality_rating,
    notes=notes,
    )

    sleep_start = validated.sleep_start
    sleep_end = validated.sleep_end
    duration_minutes = validated.duration_minutes
    quality_rating = validated.quality_rating
    notes = validated.notes
    db = SessionLocal()

    try:
        created_raw_event = raw_event_id is None

        if created_raw_event:
            raw_event = save_raw_event(
                db,
                raw_text,
                event_time=sleep_start or sleep_end,
            )
            raw_event_id = raw_event.id

        sleep = save_sleep_entry(
            db,
            source_event_id=raw_event_id,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            duration_minutes=duration_minutes,
            quality_rating=quality_rating,
            notes=notes,
        )

        if created_raw_event:
            mark_event_processed(
                db,
                event_id=raw_event_id,
                event_type="sleep",
                parser_version="codex-v1",
            )

        return {
            "raw_event_id": raw_event_id,
            "sleep_entry_id": sleep.id,
            "duration_minutes": sleep.duration_minutes,
            "quality_rating": sleep.quality_rating,
        }

    finally:
        db.close()


def log_workout(
    raw_text: str,
    workout_type: str | None = None,
    duration_minutes: int | None = None,
    notes: str | None = None,
    sets: list[dict] | None = None,
    raw_event_id: int | None = None,
    started_at=None,
):
    validated = ParsedWorkout(
    started_at=started_at,
    workout_type=workout_type,
    duration_minutes=duration_minutes,
    notes=notes,
    sets=sets or [],
    )

    started_at = validated.started_at
    workout_type = validated.workout_type
    duration_minutes = validated.duration_minutes
    notes = validated.notes
    sets = [item.model_dump() for item in validated.sets]
    db = SessionLocal()

    try:
        created_raw_event = raw_event_id is None

        if created_raw_event:
            raw_event = save_raw_event(
                db,
                raw_text,
                event_time=started_at,
            )
            raw_event_id = raw_event.id

        workout = save_workout_session(
            db,
            source_event_id=raw_event_id,
            started_at=started_at,
            workout_type=workout_type,
            duration_minutes=duration_minutes,
            notes=notes,
        )

        saved_sets = []

        for item in sets or []:
            exercise_set = save_exercise_set(
                db,
                workout_session_id=workout.id,
                exercise_name=item["exercise_name"],
                set_number=item.get("set_number"),
                weight_kg=item.get("weight_kg"),
                reps=item.get("reps"),
                duration_seconds=item.get("duration_seconds"),
                distance_km=item.get("distance_km"),
                rpe=item.get("rpe"),
            )

            saved_sets.append(
                {
                    "exercise_set_id": exercise_set.id,
                    "exercise_name": exercise_set.exercise_name,
                    "set_number": exercise_set.set_number,
                    "weight_kg": exercise_set.weight_kg,
                    "reps": exercise_set.reps,
                }
            )

        if created_raw_event:
            mark_event_processed(
                db,
                event_id=raw_event_id,
                event_type="workout",
                parser_version="codex-v1",
            )

        return {
            "raw_event_id": raw_event_id,
            "workout_session_id": workout.id,
            "workout_type": workout.workout_type,
            "sets": saved_sets,
        }

    finally:
        db.close()


def log_mixed_input(
    raw_text: str,
    body_metrics: list[dict] | None = None,
    food_entries: list[dict] | None = None,
    activities: list[dict] | None = None,
    sleep_entries: list[dict] | None = None,
    workouts: list[dict] | None = None,
):
    validated = ParsedInput(
        body_metrics=body_metrics or [],
        food_entries=food_entries or [],
        activities=activities or [],
        sleep_entries=sleep_entries or [],
        workouts=workouts or [],
    )

    db = SessionLocal()

    try:
        raw_event = save_raw_event(
            db,
            raw_text,
            commit=False,
            event_time=_get_mixed_event_time(validated),
        )

        raw_event_id = raw_event.id

        results = {
            "raw_event_id": raw_event_id,
            "body_metrics": [],
            "food_entries": [],
            "activities": [],
            "sleep_entries": [],
            "workouts": [],
        }

        for item in validated.body_metrics:
            metric = save_body_metric(
                db,
                source_event_id=raw_event_id,
                measured_at=item.measured_at,
                weight_kg=item.weight_kg,
                waist_cm=item.waist_cm,
                body_fat_percent=item.body_fat_percent,
                resting_heart_rate=item.resting_heart_rate,
                commit=False,
            )

            results["body_metrics"].append(
                {
                    "raw_event_id": raw_event_id,
                    "body_metric_id": metric.id,
                    "weight_kg": metric.weight_kg,
                }
            )

        for entry in validated.food_entries:
            saved_items = []

            for item in entry.items:
                food = save_food_entry(
                    db,
                    source_event_id=raw_event_id,
                    food_name=item.food_name,
                    consumed_at=entry.consumed_at,
                    meal_type=entry.meal_type,
                    quantity=item.quantity,
                    unit=item.unit,
                    estimated_calories=item.estimated_calories,
                    protein_g=item.protein_g,
                    carbs_g=item.carbs_g,
                    fat_g=item.fat_g,
                    fiber_g=item.fiber_g,
                    is_estimated=item.is_estimated,
                    commit=False,
                )

                saved_items.append(
                    {
                        "food_entry_id": food.id,
                        "food_name": food.food_name,
                        "quantity": food.quantity,
                        "unit": food.unit,
                    }
                )

            results["food_entries"].append(
                {
                    "raw_event_id": raw_event_id,
                    "meal_type": entry.meal_type,
                    "items": saved_items,
                }
            )

        for item in validated.activities:
            activity = save_activity_entry(
                db,
                source_event_id=raw_event_id,
                recorded_at=item.recorded_at,
                steps=item.steps,
                distance_km=item.distance_km,
                active_minutes=item.active_minutes,
                calories_burned=item.calories_burned,
                commit=False,
            )

            results["activities"].append(
                {
                    "raw_event_id": raw_event_id,
                    "activity_id": activity.id,
                    "steps": activity.steps,
                    "distance_km": activity.distance_km,
                    "active_minutes": activity.active_minutes,
                    "calories_burned": activity.calories_burned,
                }
            )

        for item in validated.sleep_entries:
            sleep = save_sleep_entry(
                db,
                source_event_id=raw_event_id,
                sleep_start=item.sleep_start,
                sleep_end=item.sleep_end,
                duration_minutes=item.duration_minutes,
                quality_rating=item.quality_rating,
                notes=item.notes,
                commit=False,
            )

            results["sleep_entries"].append(
                {
                    "raw_event_id": raw_event_id,
                    "sleep_entry_id": sleep.id,
                    "duration_minutes": sleep.duration_minutes,
                    "quality_rating": sleep.quality_rating,
                }
            )

        for entry in validated.workouts:
            workout = save_workout_session(
                db,
                source_event_id=raw_event_id,
                started_at=entry.started_at,
                workout_type=entry.workout_type,
                duration_minutes=entry.duration_minutes,
                notes=entry.notes,
                commit=False,
            )

            saved_sets = []

            for item in entry.sets:
                exercise_set = save_exercise_set(
                    db,
                    workout_session_id=workout.id,
                    exercise_name=item.exercise_name,
                    set_number=item.set_number,
                    weight_kg=item.weight_kg,
                    reps=item.reps,
                    duration_seconds=item.duration_seconds,
                    distance_km=item.distance_km,
                    rpe=item.rpe,
                    commit=False,
                )

                saved_sets.append(
                    {
                        "exercise_set_id": exercise_set.id,
                        "exercise_name": exercise_set.exercise_name,
                        "set_number": exercise_set.set_number,
                        "weight_kg": exercise_set.weight_kg,
                        "reps": exercise_set.reps,
                    }
                )

            results["workouts"].append(
                {
                    "raw_event_id": raw_event_id,
                    "workout_session_id": workout.id,
                    "workout_type": workout.workout_type,
                    "sets": saved_sets,
                }
            )

        mark_event_processed(
            db,
            event_id=raw_event_id,
            event_type="mixed",
            parser_version="codex-v1",
            commit=False,
        )

        db.commit()

        return results

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

def get_recent_weights(limit: int = 7):
    db = SessionLocal()

    try:
        rows = (
            db.query(BodyMetric)
            .filter(BodyMetric.weight_kg.isnot(None))
            .order_by(BodyMetric.measured_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "measured_at": row.measured_at,
                "weight_kg": row.weight_kg,
                "source_event_id": row.source_event_id,
            }
            for row in rows
        ]

    finally:
        db.close()


def get_weight_summary(limit: int = 7):
    rows = get_recent_weights(limit)

    weights = [
        row["weight_kg"]
        for row in rows
        if row["weight_kg"] is not None
    ]

    if not weights:
        return {
            "count": 0,
            "latest_weight_kg": None,
            "average_weight_kg": None,
        }

    return {
        "count": len(weights),
        "latest_weight_kg": weights[0],
        "average_weight_kg": round(sum(weights) / len(weights), 2),
    }

def get_recent_activities(limit: int = 7):
    db = SessionLocal()

    try:
        rows = (
            db.query(ActivityEntry)
            .order_by(ActivityEntry.recorded_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "recorded_at": row.recorded_at,
                "steps": row.steps,
                "distance_km": row.distance_km,
                "active_minutes": row.active_minutes,
                "calories_burned": row.calories_burned,
                "source_event_id": row.source_event_id,
            }
            for row in rows
        ]

    finally:
        db.close()

def get_activity_summary(limit: int = 7):
    rows = get_recent_activities(limit)

    steps = [
        row["steps"]
        for row in rows
        if row["steps"] is not None
    ]

    if not steps:
        return {
            "count": 0,
            "latest_steps": None,
            "average_steps": None,
        }

    return {
        "count": len(steps),
        "latest_steps": steps[0],
        "average_steps": round(sum(steps) / len(steps)),
    }


def get_daily_activity(
    days: int = 7,
    reference=None,
):
    db = SessionLocal()

    try:
        return aggregate_activity_by_local_day(
            db,
            days=days,
            reference=reference,
        )
    finally:
        db.close()


def get_daily_activity_summary(
    days: int = 7,
    reference=None,
):
    daily_activity = get_daily_activity(
        days=days,
        reference=reference,
    )
    return summarize_daily_activity(daily_activity)


def get_daily_food(days: int = 7, reference=None):
    db = SessionLocal()

    try:
        return aggregate_food_by_local_day(db, days=days, reference=reference)
    finally:
        db.close()


def get_daily_food_summary(days: int = 7, reference=None):
    return summarize_daily_food(
        get_daily_food(days=days, reference=reference)
    )


def get_daily_weights(days: int = 14, reference=None):
    db = SessionLocal()

    try:
        return aggregate_weight_by_local_day(
            db,
            days=days,
            reference=reference,
        )
    finally:
        db.close()


def get_weight_trend(days: int = 14, reference=None):
    return summarize_weight_trend(
        get_daily_weights(days=days, reference=reference)
    )


def get_daily_sleep(days: int = 7, reference=None):
    db = SessionLocal()

    try:
        return aggregate_sleep_by_local_day(
            db,
            days=days,
            reference=reference,
        )
    finally:
        db.close()


def get_daily_sleep_summary(days: int = 7, reference=None):
    return summarize_daily_sleep(
        get_daily_sleep(days=days, reference=reference)
    )


def get_daily_workouts(days: int = 7, reference=None):
    db = SessionLocal()

    try:
        return aggregate_workouts_by_local_day(
            db,
            days=days,
            reference=reference,
        )
    finally:
        db.close()


def get_workout_period_summary(days: int = 7, reference=None):
    db = SessionLocal()

    try:
        daily_workouts = aggregate_workouts_by_local_day(
            db,
            days=days,
            reference=reference,
        )
        return summarize_workout_period(
            db,
            daily_workouts,
            days=days,
            reference=reference,
        )
    finally:
        db.close()


def get_recent_food_entries(limit: int = 10):
    db = SessionLocal()

    try:
        rows = (
            db.query(FoodEntry)
            .order_by(FoodEntry.consumed_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "consumed_at": row.consumed_at,
                "meal_type": row.meal_type,
                "food_name": row.food_name,
                "quantity": row.quantity,
                "unit": row.unit,
                "estimated_calories": row.estimated_calories,
                "protein_g": row.protein_g,
                "carbs_g": row.carbs_g,
                "fat_g": row.fat_g,
                "fiber_g": row.fiber_g,
                "is_estimated": row.is_estimated,
                "source_event_id": row.source_event_id,
            }
            for row in rows
        ]

    finally:
        db.close()

def get_food_summary(limit: int = 20):
    rows = get_recent_food_entries(limit)

    calories = [
        row["estimated_calories"]
        for row in rows
        if row["estimated_calories"] is not None
    ]

    protein = [
        row["protein_g"]
        for row in rows
        if row["protein_g"] is not None
    ]

    return {
        "entry_count": len(rows),
        "entries_with_calories": len(calories),
        "entries_with_protein": len(protein),
        "total_estimated_calories": (
            round(sum(calories), 2) if calories else None
        ),
        "total_protein_g": (
            round(sum(protein), 2) if protein else None
        ),
    }

def get_recent_sleep_entries(limit: int = 7):
    db = SessionLocal()

    try:
        rows = (
            db.query(SleepEntry)
            .order_by(SleepEntry.id.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": row.id,
                "sleep_start": row.sleep_start,
                "sleep_end": row.sleep_end,
                "duration_minutes": row.duration_minutes,
                "quality_rating": row.quality_rating,
                "notes": row.notes,
                "source_event_id": row.source_event_id,
            }
            for row in rows
        ]

    finally:
        db.close()

def get_sleep_summary(limit: int = 7):
    rows = get_recent_sleep_entries(limit)

    durations = [
        row["duration_minutes"]
        for row in rows
        if row["duration_minutes"] is not None
    ]

    quality_ratings = [
        row["quality_rating"]
        for row in rows
        if row["quality_rating"] is not None
    ]

    return {
        "count": len(rows),
        "entries_with_duration": len(durations),
        "entries_with_quality": len(quality_ratings),
        "latest_duration_minutes": (
            durations[0] if durations else None
        ),
        "average_duration_minutes": (
            round(sum(durations) / len(durations))
            if durations
            else None
        ),
        "average_quality_rating": (
            round(sum(quality_ratings) / len(quality_ratings), 2)
            if quality_ratings
            else None
        ),
    }

def get_recent_workouts(limit: int = 5):
    db = SessionLocal()

    try:
        workouts = (
            db.query(WorkoutSession)
            .order_by(WorkoutSession.started_at.desc())
            .limit(limit)
            .all()
        )

        results = []

        for workout in workouts:
            sets = (
                db.query(ExerciseSet)
                .filter(
                    ExerciseSet.workout_session_id == workout.id
                )
                .order_by(ExerciseSet.id.asc())
                .all()
            )

            results.append(
                {
                    "id": workout.id,
                    "started_at": workout.started_at,
                    "workout_type": workout.workout_type,
                    "duration_minutes": workout.duration_minutes,
                    "notes": workout.notes,
                    "source_event_id": workout.source_event_id,
                    "sets": [
                        {
                            "exercise_name": item.exercise_name,
                            "set_number": item.set_number,
                            "weight_kg": item.weight_kg,
                            "reps": item.reps,
                            "duration_seconds": item.duration_seconds,
                            "distance_km": item.distance_km,
                            "rpe": item.rpe,
                        }
                        for item in sets
                    ],
                }
            )

        return results

    finally:
        db.close()

def get_workout_summary(limit: int = 5):
    workouts = get_recent_workouts(limit)

    total_sets = 0
    total_volume_kg = 0.0

    for workout in workouts:
        for item in workout["sets"]:
            total_sets += 1

            weight = item["weight_kg"]
            reps = item["reps"]

            if weight is not None and reps is not None:
                total_volume_kg += weight * reps

    return {
        "workout_count": len(workouts),
        "total_sets": total_sets,
        "total_volume_kg": round(total_volume_kg, 2),
        "latest_workout_type": (
            workouts[0]["workout_type"]
            if workouts
            else None
        ),
    }

def get_fitness_context(reference=None):
    db = SessionLocal()

    try:
        return build_fitness_context(
            db,
            profile=load_profile(),
            reference=reference,
        )
    finally:
        db.close()

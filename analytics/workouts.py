from collections import Counter
from datetime import date, datetime

from sqlalchemy.orm import Session

from analytics.time_windows import local_date_for, local_window
from database.schema import ExerciseSet, WorkoutSession


def aggregate_workouts_by_local_day(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> list[dict]:
    dates, start_time, end_time = local_window(days, reference)
    workouts = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.started_at >= start_time,
            WorkoutSession.started_at < end_time,
        )
        .all()
    )
    workout_ids = [workout.id for workout in workouts]
    sets = (
        db.query(ExerciseSet)
        .filter(ExerciseSet.workout_session_id.in_(workout_ids))
        .all()
        if workout_ids
        else []
    )
    sets_by_workout: dict[int, list[ExerciseSet]] = {}
    for exercise_set in sets:
        sets_by_workout.setdefault(
            exercise_set.workout_session_id,
            [],
        ).append(exercise_set)

    workouts_by_date: dict[date, list[WorkoutSession]] = {}
    for workout in workouts:
        workouts_by_date.setdefault(
            local_date_for(workout.started_at),
            [],
        ).append(workout)

    results = []
    for current_date in dates:
        daily_workouts = workouts_by_date.get(current_date, [])
        daily_sets = [
            exercise_set
            for workout in daily_workouts
            for exercise_set in sets_by_workout.get(workout.id, [])
        ]
        set_logging_complete = (
            all(
                bool(sets_by_workout.get(workout.id))
                for workout in daily_workouts
            )
            if daily_workouts
            else None
        )
        volumes = [
            exercise_set.weight_kg * exercise_set.reps
            for exercise_set in daily_sets
            if exercise_set.weight_kg is not None
            and exercise_set.reps is not None
        ]
        durations = [
            workout.duration_minutes
            for workout in daily_workouts
            if workout.duration_minutes is not None
        ]
        results.append(
            {
                "date": current_date.isoformat(),
                "workout_count": len(daily_workouts),
                "total_sets": len(daily_sets),
                "set_logging_complete": set_logging_complete,
                "total_volume_kg": sum(volumes) if volumes else None,
                "total_duration_minutes": (
                    sum(durations) if durations else None
                ),
                "workout_types": sorted(
                    {
                        workout.workout_type
                        for workout in daily_workouts
                        if workout.workout_type is not None
                    }
                ),
            }
        )
    return results


def summarize_workout_period(
    db: Session,
    daily_workouts: list[dict],
    days: int,
    reference: date | datetime | None = None,
) -> dict:
    _, start_time, end_time = local_window(days, reference)
    workouts = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.started_at >= start_time,
            WorkoutSession.started_at < end_time,
        )
        .order_by(WorkoutSession.started_at.asc())
        .all()
    )
    type_counts = Counter(
        workout.workout_type
        for workout in workouts
        if workout.workout_type is not None
    )
    volume_days = [
        day for day in daily_workouts if day["total_volume_kg"] is not None
    ]
    duration_days = [
        day
        for day in daily_workouts
        if day["total_duration_minutes"] is not None
    ]
    set_days = [
        day
        for day in daily_workouts
        if day["workout_count"] > 0
    ]

    has_workouts = bool(set_days)
    has_complete_set_data = (
        has_workouts
        and all(day["total_sets"] is not None for day in set_days)
    )
    latest = workouts[-1] if workouts else None
    workout_days = [
        day
        for day in daily_workouts
        if day["workout_count"] > 0
    ]

    set_logging_complete = (
        all(day["set_logging_complete"] is True for day in workout_days)
        if workout_days
        else None
    )

    return {
        "days_requested": len(daily_workouts),
        "days_with_workouts": sum(
            day["workout_count"] > 0 for day in daily_workouts
        ),
        "workout_count": len(workouts),
        "total_sets": sum(
            day["total_sets"]
            for day in daily_workouts
        ),
        "set_logging_complete": set_logging_complete,
        "total_volume_kg": (
            sum(day["total_volume_kg"] for day in volume_days)
            if volume_days
            else None
        ),
        "total_duration_minutes": (
            sum(day["total_duration_minutes"] for day in duration_days)
            if duration_days
            else None
        ),
        "workouts_by_type": dict(sorted(type_counts.items())),
        "latest_workout_date": (
            local_date_for(latest.started_at).isoformat() if latest else None
        ),
        "latest_workout_type": latest.workout_type if latest else None,
    }

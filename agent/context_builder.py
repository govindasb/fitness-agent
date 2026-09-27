from datetime import date, datetime

from sqlalchemy.orm import Session

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
from database.timezone import APPLICATION_TIMEZONE, to_utc, utc_now


def _generated_at(reference: date | datetime | None) -> datetime:
    if isinstance(reference, datetime):
        return to_utc(reference)
    return utc_now()


def _summary_with_window(summary: dict, window_days: int) -> dict:
    return {
        "window_days": window_days,
        **{
            key: value
            for key, value in summary.items()
            if key != "days_requested"
        },
    }


def build_fitness_context(
    db: Session,
    profile: dict,
    reference: date | datetime | None = None,
) -> dict:
    generated_at = _generated_at(reference)
    window_reference = reference if reference is not None else generated_at

    daily_weight = aggregate_weight_by_local_day(
        db,
        days=14,
        reference=window_reference,
    )
    daily_activity = aggregate_activity_by_local_day(
        db,
        days=7,
        reference=window_reference,
    )
    daily_food = aggregate_food_by_local_day(
        db,
        days=7,
        reference=window_reference,
    )
    daily_sleep = aggregate_sleep_by_local_day(
        db,
        days=7,
        reference=window_reference,
    )
    daily_workouts = aggregate_workouts_by_local_day(
        db,
        days=7,
        reference=window_reference,
    )

    weight = _summary_with_window(
        summarize_weight_trend(daily_weight),
        14,
    )
    weight["daily"] = [
        {
            "date": day["date"],
            "latest_weight_kg": day["latest_weight_kg"],
        }
        for day in daily_weight
    ]

    activity = _summary_with_window(
        summarize_daily_activity(daily_activity),
        7,
    )
    activity["daily"] = [
        {
            "date": day["date"],
            "steps": day["steps"],
            "active_minutes": day["active_minutes"],
            "distance_km": day["distance_km"],
        }
        for day in daily_activity
    ]

    nutrition = _summary_with_window(
        summarize_daily_food(daily_food),
        7,
    )
    nutrition["daily"] = [
        {
            "date": day["date"],
            "total_estimated_calories": day["total_estimated_calories"],
            "total_protein_g": day["total_protein_g"],
            "total_carbs_g": day["total_carbs_g"],
            "total_fat_g": day["total_fat_g"],
            "entry_count": day["entry_count"],
            "estimated_entry_count": day["estimated_entry_count"],
        }
        for day in daily_food
    ]

    sleep = _summary_with_window(
        summarize_daily_sleep(daily_sleep),
        7,
    )
    sleep["daily"] = [
        {
            "date": day["date"],
            "total_duration_minutes": day["total_duration_minutes"],
            "average_quality_rating": day["average_quality_rating"],
            "session_count": day["session_count"],
        }
        for day in daily_sleep
    ]

    training = _summary_with_window(
        summarize_workout_period(
            db,
            daily_workouts,
            days=7,
            reference=window_reference,
        ),
        7,
    )
    training["daily"] = [
        {
            "date": day["date"],
            "workout_count": day["workout_count"],
            "total_sets": day["total_sets"],
            "total_volume_kg": day["total_volume_kg"],
            "total_duration_minutes": day["total_duration_minutes"],
            "workout_types": day["workout_types"],
        }
        for day in daily_workouts
    ]

    food_entry_count = sum(day["entry_count"] for day in daily_food)
    estimated_food_count = sum(
        day["estimated_entry_count"] for day in daily_food
    )
    data_quality = {
        "weight_days_logged": weight["days_with_weight"],
        "activity_days_logged": activity["days_with_data"],
        "food_days_logged": nutrition["days_with_food"],
        "calorie_days_logged": nutrition["days_with_calorie_data"],
        "protein_days_logged": nutrition["days_with_protein_data"],
        "sleep_days_logged": sleep["days_with_sleep"],
        "workout_days_logged": training["days_with_workouts"],
        "nutrition_estimation_ratio": (
            round(estimated_food_count / food_entry_count, 4)
            if food_entry_count
            else None
        ),
    }

    return {
        "generated_at": generated_at.isoformat(),
        "timezone": str(APPLICATION_TIMEZONE),
        "profile": profile,
        "weight": weight,
        "activity": activity,
        "nutrition": nutrition,
        "sleep": sleep,
        "training": training,
        "data_quality": data_quality,
    }

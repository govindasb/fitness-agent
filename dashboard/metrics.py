from datetime import date, datetime

from sqlalchemy.orm import Session

from analytics.activity import (
    aggregate_activity_by_local_day,
    summarize_daily_activity,
)
from analytics.adherence import get_target_adherence
from analytics.food import (
    aggregate_food_by_local_day,
    summarize_daily_food,
)
from analytics.sleep import (
    aggregate_sleep_by_local_day,
    summarize_daily_sleep,
)
from analytics.weight import (
    aggregate_weight_by_local_day,
    summarize_weight_trend,
)
from analytics.workouts import (
    aggregate_workouts_by_local_day,
    summarize_workout_period,
)
from config.profile import load_profile


def get_dashboard_metrics(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> dict:
    """Build deterministic metrics for the read-only dashboard."""

    # Daily domain data
    daily_weight = aggregate_weight_by_local_day(
        db,
        days=days,
        reference=reference,
    )
    daily_activity = aggregate_activity_by_local_day(
        db,
        days=days,
        reference=reference,
    )
    daily_workouts = aggregate_workouts_by_local_day(
        db,
        days=days,
        reference=reference,
    )
    daily_food = aggregate_food_by_local_day(
        db,
        days=days,
        reference=reference,
    )
    daily_sleep = aggregate_sleep_by_local_day(
        db,
        days=days,
        reference=reference,
    )

    # Domain summaries
    weight_summary = summarize_weight_trend(daily_weight)
    minimum_weight_days_for_trend = max(3, (days + 1) // 2)

    weight_trend_eligible = (
        weight_summary["days_with_weight"]
        >= minimum_weight_days_for_trend
    )
    activity_summary = summarize_daily_activity(daily_activity)

    workout_summary = summarize_workout_period(
        db,
        daily_workouts,
        days=days,
        reference=reference,
    )

    food_summary = summarize_daily_food(daily_food)
    sleep_summary = summarize_daily_sleep(daily_sleep)

    # Configured profile and goal progress
    profile = load_profile()

    starting_weight_kg = profile["starting_weight_kg"]
    target_weight_kg = profile["target_weight_kg"]
    current_weight_kg = weight_summary["latest_weight_kg"]

    if current_weight_kg is not None:
        total_goal_change_kg = (
            starting_weight_kg - target_weight_kg
        )
        weight_lost_kg = round(
            starting_weight_kg - current_weight_kg,
            2,
        )
        remaining_kg = round(
            current_weight_kg - target_weight_kg,
            2,
        )

        progress_percent = (
            round(
                weight_lost_kg / total_goal_change_kg * 100,
                1,
            )
            if total_goal_change_kg > 0
            else None
        )
    else:
        weight_lost_kg = None
        remaining_kg = None
        progress_percent = None

    # Deterministic target adherence
    adherence = get_target_adherence(
        db,
        days=days,
        reference=reference,
    )
    activity_adherence = adherence["activity"]

    step_metrics = {
        "logged_days": activity_adherence["logged_days"],
        "average_steps_on_logged_days": activity_adherence[
            "average_steps_on_logged_days"
        ],
        "average_steps_percent_of_target_on_logged_days": (
            activity_adherence[
                "average_steps_percent_of_target_on_logged_days"
            ]
        ),
        "steps_days_available": adherence["coverage"][
            "steps_days_available"
        ],
        "days_requested": days,
    }

    training_coverage = adherence["coverage"]

    training_metrics = {
        "days_with_workouts": workout_summary["days_with_workouts"],
        "workout_count": workout_summary["workout_count"],
        "workouts_by_type": workout_summary["workouts_by_type"],
        "latest_workout_date": workout_summary["latest_workout_date"],
        "latest_workout_type": workout_summary["latest_workout_type"],
        "total_sets": workout_summary["total_sets"],
        "set_logging_complete": workout_summary[
            "set_logging_complete"
        ],
        "total_volume_kg": workout_summary["total_volume_kg"],
        "total_duration_minutes": workout_summary[
            "total_duration_minutes"
        ],
        "classified_workouts": training_coverage[
            "training_sessions_classified"
        ],
        "unclassified_workouts": training_coverage[
            "training_sessions_unclassified"
        ],
        "classification_coverage_percent": training_coverage[
            "training_classification_coverage_percent"
        ],
        "days_requested": days,
    }

    nutrition_metrics = {
    "days_with_food": food_summary["days_with_food"],
    "days_with_calorie_data": food_summary[
        "days_with_calorie_data"
    ],
    "days_with_protein_data": food_summary[
        "days_with_protein_data"
    ],
    "latest_date_with_food": food_summary[
        "latest_date_with_food"
    ],
    "latest_calories": food_summary["latest_calories"],
    "latest_protein_g": food_summary["latest_protein_g"],
    "total_estimated_calories": food_summary[
        "total_estimated_calories"
    ],
    "total_protein_g": food_summary["total_protein_g"],
    "average_calories_on_recorded_days": food_summary[
        "average_calories_on_recorded_days"
    ],
    "average_protein_on_recorded_days": food_summary[
        "average_protein_on_recorded_days"
    ],
    "calorie_days_available": adherence["coverage"][
        "calorie_days_available"
    ],
    "protein_days_available": adherence["coverage"][
        "protein_days_available"
    ],
    "days_requested": days,
    }

    sleep_metrics = {
        "days_with_sleep": sleep_summary["days_with_sleep"],
        "days_with_duration": sleep_summary["days_with_duration"],
        "latest_sleep_date": sleep_summary["latest_sleep_date"],
        "latest_duration_minutes": sleep_summary[
            "latest_duration_minutes"
        ],
        "average_duration_minutes_on_recorded_days": sleep_summary[
            "average_duration_minutes_on_recorded_days"
        ],
        "average_quality_rating": sleep_summary[
            "average_quality_rating"
        ],
        "total_sleep_minutes": sleep_summary[
            "total_sleep_minutes"
        ],
        "days_requested": days,
    }

    # Data coverage
    coverage = {
        "weight": {
            "days_logged": weight_summary["days_with_weight"],
            "days_requested": days,
        },
        "steps": {
            "days_logged": activity_summary["days_with_steps"],
            "days_requested": days,
        },
        "nutrition": {
            "days_logged": food_summary["days_with_food"],
            "days_requested": days,
            "calorie_days_available": adherence["coverage"][
                "calorie_days_available"
            ],
            "protein_days_available": adherence["coverage"][
                "protein_days_available"
            ],
        },
        "sleep": {
            "days_logged": sleep_summary["days_with_sleep"],
            "days_requested": days,
            "duration_days_available": sleep_summary[
                "days_with_duration"
            ],
        },
        "training": {
            "workout_count": workout_summary["workout_count"],
            "classified_workouts": adherence["coverage"][
                "training_sessions_classified"
            ],
            "unclassified_workouts": adherence["coverage"][
                "training_sessions_unclassified"
            ],
        },
    }

    return {
        "days_requested": days,
        "goal": {
            "starting_weight_kg": starting_weight_kg,
            "target_weight_kg": target_weight_kg,
            "current_weight_kg": current_weight_kg,
            "weight_lost_kg": weight_lost_kg,
            "remaining_kg": remaining_kg,
            "progress_percent": progress_percent,
        },
        "weight": {
            **weight_summary,
            "trend_eligible": weight_trend_eligible,
            "minimum_days_for_trend": minimum_weight_days_for_trend,
            "daily": daily_weight,
        },
        "steps": {
            **step_metrics,
            "latest_date": activity_summary["latest_date"],
            "latest_steps": activity_summary["latest_steps"],
            "total_steps": activity_summary["total_steps"],
            "daily": daily_activity,
        },
        "training": {
            **training_metrics,
            "daily": daily_workouts,
        },
        "nutrition": {
            **nutrition_metrics,
            "daily": daily_food,
        },
        "sleep": {
            **sleep_metrics,
            "daily": daily_sleep,
        },
        "coverage": coverage,
    }
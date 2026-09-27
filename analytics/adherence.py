from datetime import date, datetime

from sqlalchemy.orm import Session

from analytics.activity import aggregate_activity_by_local_day
from analytics.food import aggregate_food_by_local_day
from analytics.workouts import aggregate_workouts_by_local_day, summarize_workout_period
from config.coaching_targets import load_coaching_targets


STRENGTH_TYPES = {
    "strength", "weights", "weight training", "resistance", "bodybuilding",
    "powerlifting", "chest", "back", "legs", "shoulders", "arms",
    "biceps", "triceps", "push", "pull", "upper body", "lower body",
}
CARDIO_TYPES = {"cardio", "running", "cycling", "swimming", "walking", "rowing", "elliptical"}


def classify_workout_type(workout_type: str | None) -> str | None:
    """Classify only explicit, well-known workout labels."""
    if workout_type is None:
        return None
    label = workout_type.strip().lower()
    if label in STRENGTH_TYPES:
        return "strength"
    if label in CARDIO_TYPES:
        return "cardio"
    return None


def _percent(actual: float | int | None, target: float | int) -> float | None:
    return round(actual / target * 100, 1) if actual is not None else None


def _difference(actual: float | int | None, target: float | int):
    return round(actual - target, 2) if actual is not None else None


def get_target_adherence(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> dict:
    """Compare recorded daily activity and nutrition with configured targets."""
    targets = load_coaching_targets()
    daily_food = aggregate_food_by_local_day(db, days, reference)
    daily_activity = aggregate_activity_by_local_day(db, days, reference)
    daily_workouts = aggregate_workouts_by_local_day(db, days, reference)
    workout_summary = summarize_workout_period(db, daily_workouts, days, reference)

    daily = []
    for food, activity in zip(daily_food, daily_activity):
        calories_complete = (
            food["entry_count"] > 0
            and food["entries_with_calories"] == food["entry_count"]
        )
        protein_complete = (
            food["entry_count"] > 0
            and food["entries_with_protein"] == food["entry_count"]
        )
        calories = food["total_estimated_calories"] if calories_complete else None
        protein = food["total_protein_g"] if protein_complete else None
        steps = activity["steps"]
        daily.append(
            {
                "date": food["date"],
                "calories_actual": calories,
                "calories_target": targets.daily_calories,
                "calories_difference": _difference(calories, targets.daily_calories),
                "calories_percent_of_target": _percent(calories, targets.daily_calories),
                "has_calorie_data": calories_complete,
                "calorie_entries_total": food["entry_count"],
                "calorie_entries_with_data": food["entries_with_calories"],
                "protein_actual_g": protein,
                "protein_target_g": targets.daily_protein_g,
                "protein_difference_g": _difference(protein, targets.daily_protein_g),
                "protein_percent_of_target": _percent(protein, targets.daily_protein_g),
                "has_protein_data": protein_complete,
                "protein_entries_total": food["entry_count"],
                "protein_entries_with_data": food["entries_with_protein"],
                "has_nutrition_data": food["entry_count"] > 0,
                "steps_actual": steps,
                "steps_target": targets.daily_steps,
                "steps_difference": _difference(steps, targets.daily_steps),
                "steps_percent_of_target": _percent(steps, targets.daily_steps),
                "has_activity_data": activity["record_count"] > 0,
                "has_steps_data": steps is not None,
            }
        )

    nutrition_logged = [day for day in daily_food if day["entry_count"] > 0]
    calorie_days = [
        day for day in daily if day["has_calorie_data"]
    ]
    protein_days = [
        day for day in daily if day["has_protein_data"]
    ]
    activity_logged = [day for day in daily_activity if day["record_count"] > 0]
    step_days = [day for day in daily_activity if day["steps"] is not None]

    strength_actual = sum(
        count for label, count in workout_summary["workouts_by_type"].items()
        if classify_workout_type(label) == "strength"
    )
    cardio_actual = sum(
        count for label, count in workout_summary["workouts_by_type"].items()
        if classify_workout_type(label) == "cardio"
    )
    classified = strength_actual + cardio_actual
    scaled_strength = targets.strength_sessions_per_week * days / 7
    scaled_cardio = targets.cardio_sessions_per_week * days / 7

    return {
        "days_requested": days,
        "daily": daily,
        "nutrition": {
            "logged_days": len(nutrition_logged),
            "available_calorie_days": len(calorie_days),
            "available_protein_days": len(protein_days),
            "average_calories_on_available_days": round(sum(d["calories_actual"] for d in calorie_days) / len(calorie_days), 2) if calorie_days else None,
            "average_protein_g_on_available_days": round(sum(d["protein_actual_g"] for d in protein_days) / len(protein_days), 2) if protein_days else None,
            "average_calories_percent_of_target_on_available_days": round(sum(d["calories_percent_of_target"] for d in calorie_days) / len(calorie_days), 1) if calorie_days else None,
            "average_protein_percent_of_target_on_available_days": round(sum(d["protein_percent_of_target"] for d in protein_days) / len(protein_days), 1) if protein_days else None,
            # Compatibility aliases: these now mean metric-available days.
            "average_calories_on_logged_days": round(sum(d["calories_actual"] for d in calorie_days) / len(calorie_days), 2) if calorie_days else None,
            "average_protein_g_on_logged_days": round(sum(d["protein_actual_g"] for d in protein_days) / len(protein_days), 2) if protein_days else None,
        },
        "activity": {
            "logged_days": len(activity_logged),
            "average_steps_on_logged_days": round(sum(d["steps"] for d in step_days) / len(step_days), 2) if step_days else None,
            "average_steps_percent_of_target_on_logged_days": round(sum(d["steps"] / targets.daily_steps * 100 for d in step_days) / len(step_days), 1) if step_days and targets.daily_steps else None,
        },
        "training": {
            "strength_sessions_actual": strength_actual,
            "strength_sessions_target": scaled_strength,
            "cardio_sessions_actual": cardio_actual,
            "cardio_sessions_target": scaled_cardio,
            "strength_percent_of_target": _percent(strength_actual, scaled_strength) if scaled_strength else None,
            "cardio_percent_of_target": _percent(cardio_actual, scaled_cardio) if scaled_cardio else None,
            "training_classification_coverage_percent": (
                round(classified / workout_summary["workout_count"] * 100, 1)
                if workout_summary["workout_count"]
                else None
            ),
        },
        "coverage": {
            "nutrition_days_logged": len(nutrition_logged),
            "nutrition_days_requested": days,
            "calorie_days_available": len(calorie_days),
            "protein_days_available": len(protein_days),
            "activity_days_logged": len(activity_logged),
            "activity_days_requested": days,
            "steps_days_available": len(step_days),
            "training_sessions_total": workout_summary["workout_count"],
            "training_sessions_classified": classified,
            "training_sessions_unclassified": workout_summary["workout_count"] - classified,
            "training_classification_coverage_percent": (
                round(classified / workout_summary["workout_count"] * 100, 1)
                if workout_summary["workout_count"]
                else None
            ),
        },
    }

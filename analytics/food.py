from datetime import date, datetime

from sqlalchemy.orm import Session

from analytics.time_windows import local_date_for, local_window
from database.schema import FoodEntry


NUTRIENTS = {
    "calories": "estimated_calories",
    "protein": "protein_g",
    "carbs": "carbs_g",
    "fat": "fat_g",
    "fiber": "fiber_g",
}


def _known_values(rows: list[FoodEntry], field: str) -> list[float]:
    return [
        value
        for row in rows
        if (value := getattr(row, field)) is not None
    ]


def aggregate_food_by_local_day(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> list[dict]:
    dates, start_time, end_time = local_window(days, reference)
    rows = (
        db.query(FoodEntry)
        .filter(
            FoodEntry.consumed_at >= start_time,
            FoodEntry.consumed_at < end_time,
        )
        .all()
    )

    rows_by_date: dict[date, list[FoodEntry]] = {}
    for row in rows:
        rows_by_date.setdefault(local_date_for(row.consumed_at), []).append(row)

    results = []
    for current_date in dates:
        daily_rows = rows_by_date.get(current_date, [])
        known = {
            name: _known_values(daily_rows, field)
            for name, field in NUTRIENTS.items()
        }
        results.append(
            {
                "date": current_date.isoformat(),
                "entry_count": len(daily_rows),
                "entries_with_calories": len(known["calories"]),
                "entries_with_protein": len(known["protein"]),
                "entries_with_carbs": len(known["carbs"]),
                "entries_with_fat": len(known["fat"]),
                "entries_with_fiber": len(known["fiber"]),
                "estimated_entry_count": sum(
                    row.is_estimated for row in daily_rows
                ),
                "total_estimated_calories": (
                    sum(known["calories"]) if known["calories"] else None
                ),
                "total_protein_g": (
                    sum(known["protein"]) if known["protein"] else None
                ),
                "total_carbs_g": (
                    sum(known["carbs"]) if known["carbs"] else None
                ),
                "total_fat_g": (
                    sum(known["fat"]) if known["fat"] else None
                ),
                "total_fiber_g": (
                    sum(known["fiber"]) if known["fiber"] else None
                ),
            }
        )
    return results


def summarize_daily_food(daily_food: list[dict]) -> dict:
    food_days = [day for day in daily_food if day["entry_count"] > 0]
    calorie_days = [
        day
        for day in daily_food
        if day["total_estimated_calories"] is not None
    ]
    protein_days = [
        day for day in daily_food if day["total_protein_g"] is not None
    ]
    latest_food = food_days[-1] if food_days else None
    latest_calories = calorie_days[-1] if calorie_days else None
    latest_protein = protein_days[-1] if protein_days else None

    total_calories = (
        sum(day["total_estimated_calories"] for day in calorie_days)
        if calorie_days
        else None
    )
    total_protein = (
        sum(day["total_protein_g"] for day in protein_days)
        if protein_days
        else None
    )

    return {
        "days_requested": len(daily_food),
        "days_with_food": len(food_days),
        "days_with_calorie_data": len(calorie_days),
        "days_with_protein_data": len(protein_days),
        "latest_date_with_food": (
            latest_food["date"] if latest_food else None
        ),
        "latest_calories": (
            latest_calories["total_estimated_calories"]
            if latest_calories
            else None
        ),
        "latest_protein_g": (
            latest_protein["total_protein_g"] if latest_protein else None
        ),
        "total_estimated_calories": total_calories,
        "total_protein_g": total_protein,
        "average_calories_on_recorded_days": (
            round(total_calories / len(calorie_days), 2)
            if calorie_days
            else None
        ),
        "average_protein_on_recorded_days": (
            round(total_protein / len(protein_days), 2)
            if protein_days
            else None
        ),
    }

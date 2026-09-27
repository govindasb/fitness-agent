from datetime import date, datetime

from sqlalchemy.orm import Session

from database.schema import ActivityEntry
from analytics.time_windows import local_date_for, local_window


def _sum_known(rows: list[ActivityEntry], field: str):
    values = [
        value
        for row in rows
        if (value := getattr(row, field)) is not None
    ]
    return sum(values) if values else None


def aggregate_activity_by_local_day(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> list[dict]:
    dates, start_time, end_time = local_window(days, reference)

    rows = (
        db.query(ActivityEntry)
        .filter(
            ActivityEntry.recorded_at >= start_time,
            ActivityEntry.recorded_at < end_time,
        )
        .all()
    )

    rows_by_date: dict[date, list[ActivityEntry]] = {}
    for row in rows:
        local_date = local_date_for(row.recorded_at)
        rows_by_date.setdefault(local_date, []).append(row)

    results = []
    for current_date in dates:
        daily_rows = rows_by_date.get(current_date, [])
        results.append(
            {
                "date": current_date.isoformat(),
                "steps": _sum_known(daily_rows, "steps"),
                "distance_km": _sum_known(daily_rows, "distance_km"),
                "active_minutes": _sum_known(daily_rows, "active_minutes"),
                "calories_burned": _sum_known(
                    daily_rows,
                    "calories_burned",
                ),
                "record_count": len(daily_rows),
            }
        )

    return results


def summarize_daily_activity(daily_activity: list[dict]) -> dict:
    days_with_data = [
        day for day in daily_activity if day["record_count"] > 0
    ]
    days_with_steps = [
        day for day in daily_activity if day["steps"] is not None
    ]
    latest_with_steps = days_with_steps[-1] if days_with_steps else None

    if days_with_steps:
        total_steps = sum(day["steps"] for day in days_with_steps)
        average_steps = round(total_steps / len(days_with_steps), 2)
    else:
        total_steps = None
        average_steps = None

    return {
        "days_requested": len(daily_activity),
        "days_with_data": len(days_with_data),
        "days_with_steps": len(days_with_steps),
        "latest_date": (
            latest_with_steps["date"] if latest_with_steps else None
        ),
        "latest_steps": (
            latest_with_steps["steps"] if latest_with_steps else None
        ),
        "total_steps": total_steps,
        "average_steps_on_recorded_days": average_steps,
    }

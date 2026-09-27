from datetime import date, datetime

from sqlalchemy.orm import Session

from analytics.time_windows import local_date_for, local_window
from database.schema import BodyMetric


def aggregate_weight_by_local_day(
    db: Session,
    days: int = 14,
    reference: date | datetime | None = None,
) -> list[dict]:
    dates, start_time, end_time = local_window(days, reference)
    rows = (
        db.query(BodyMetric)
        .filter(
            BodyMetric.measured_at >= start_time,
            BodyMetric.measured_at < end_time,
            BodyMetric.weight_kg.isnot(None),
        )
        .order_by(BodyMetric.measured_at.asc())
        .all()
    )

    rows_by_date: dict[date, list[BodyMetric]] = {}
    for row in rows:
        rows_by_date.setdefault(local_date_for(row.measured_at), []).append(row)

    results = []
    for current_date in dates:
        weights = [
            row.weight_kg for row in rows_by_date.get(current_date, [])
        ]
        results.append(
            {
                "date": current_date.isoformat(),
                "measurement_count": len(weights),
                "first_weight_kg": weights[0] if weights else None,
                "latest_weight_kg": weights[-1] if weights else None,
                "average_weight_kg": (
                    sum(weights) / len(weights) if weights else None
                ),
                "min_weight_kg": min(weights) if weights else None,
                "max_weight_kg": max(weights) if weights else None,
            }
        )
    return results


def summarize_weight_trend(daily_weights: list[dict]) -> dict:
    recorded_days = [
        day for day in daily_weights if day["measurement_count"] > 0
    ]
    earliest = recorded_days[0] if recorded_days else None
    latest = recorded_days[-1] if recorded_days else None

    if recorded_days:
        measurement_count = sum(
            day["measurement_count"] for day in recorded_days
        )
        total_weight = sum(
            day["average_weight_kg"] * day["measurement_count"]
            for day in recorded_days
        )
        average_weight = round(total_weight / measurement_count, 2)
        minimum = min(day["min_weight_kg"] for day in recorded_days)
        maximum = max(day["max_weight_kg"] for day in recorded_days)
        change = round(
            latest["latest_weight_kg"] - earliest["latest_weight_kg"],
            2,
        )
    else:
        average_weight = minimum = maximum = change = None

    return {
        "days_requested": len(daily_weights),
        "days_with_weight": len(recorded_days),
        "latest_date": latest["date"] if latest else None,
        "latest_weight_kg": latest["latest_weight_kg"] if latest else None,
        "earliest_date": earliest["date"] if earliest else None,
        "earliest_weight_kg": (
            earliest["latest_weight_kg"] if earliest else None
        ),
        "change_kg": change,
        "average_weight_kg": average_weight,
        "min_weight_kg": minimum,
        "max_weight_kg": maximum,
    }

from datetime import date, datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from analytics.time_windows import local_date_for, local_window
from database.schema import SleepEntry


def _session_time(row: SleepEntry):
    return row.sleep_end or row.sleep_start


def aggregate_sleep_by_local_day(
    db: Session,
    days: int = 7,
    reference: date | datetime | None = None,
) -> list[dict]:
    dates, start_time, end_time = local_window(days, reference)
    rows = (
        db.query(SleepEntry)
        .filter(
            or_(
                and_(
                    SleepEntry.sleep_end.isnot(None),
                    SleepEntry.sleep_end >= start_time,
                    SleepEntry.sleep_end < end_time,
                ),
                and_(
                    SleepEntry.sleep_end.is_(None),
                    SleepEntry.sleep_start >= start_time,
                    SleepEntry.sleep_start < end_time,
                ),
            )
        )
        .all()
    )

    rows_by_date: dict[date, list[SleepEntry]] = {}
    for row in rows:
        rows_by_date.setdefault(local_date_for(_session_time(row)), []).append(row)

    results = []
    for current_date in dates:
        daily_rows = rows_by_date.get(current_date, [])
        durations = [
            row.duration_minutes
            for row in daily_rows
            if row.duration_minutes is not None
        ]
        qualities = [
            row.quality_rating
            for row in daily_rows
            if row.quality_rating is not None
        ]
        total_duration = sum(durations) if durations else None
        results.append(
            {
                "date": current_date.isoformat(),
                "session_count": len(daily_rows),
                "total_duration_minutes": total_duration,
                "average_duration_minutes": (
                    total_duration / len(durations)
                    if durations
                    else None
                ),
                "average_quality_rating": (
                    sum(qualities) / len(qualities)
                    if qualities
                    else None
                ),
                "sessions_with_duration": len(durations),
                "sessions_with_quality": len(qualities),
            }
        )
    return results


def summarize_daily_sleep(daily_sleep: list[dict]) -> dict:
    sleep_days = [day for day in daily_sleep if day["session_count"] > 0]
    duration_days = [
        day
        for day in daily_sleep
        if day["total_duration_minutes"] is not None
    ]
    quality_days = [
        day
        for day in daily_sleep
        if day["average_quality_rating"] is not None
    ]
    latest_sleep = sleep_days[-1] if sleep_days else None
    latest_duration = duration_days[-1] if duration_days else None
    total_sleep = (
        sum(day["total_duration_minutes"] for day in duration_days)
        if duration_days
        else None
    )

    quality_observations = sum(
        day["sessions_with_quality"] for day in quality_days
    )
    weighted_quality = sum(
        day["average_quality_rating"] * day["sessions_with_quality"]
        for day in quality_days
    )

    return {
        "days_requested": len(daily_sleep),
        "days_with_sleep": len(sleep_days),
        "days_with_duration": len(duration_days),
        "latest_sleep_date": (
            latest_sleep["date"] if latest_sleep else None
        ),
        "latest_duration_minutes": (
            latest_duration["total_duration_minutes"]
            if latest_duration
            else None
        ),
        "average_duration_minutes_on_recorded_days": (
            round(total_sleep / len(duration_days), 2)
            if duration_days
            else None
        ),
        "average_quality_rating": (
            round(weighted_quality / quality_observations, 2)
            if quality_observations
            else None
        ),
        "total_sleep_minutes": total_sleep,
    }

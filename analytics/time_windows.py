from datetime import date, datetime, time, timedelta

from database.timezone import (
    APPLICATION_TIMEZONE,
    to_application_timezone,
    utc_now,
)


def local_reference_date(reference: date | datetime | None) -> date:
    if reference is None:
        return to_application_timezone(utc_now()).date()
    if isinstance(reference, datetime):
        return to_application_timezone(reference).date()
    return reference


def local_date_range(
    days: int,
    reference: date | datetime | None,
) -> list[date]:
    if days < 1:
        raise ValueError("days must be at least 1")

    end_date = local_reference_date(reference)
    start_date = end_date - timedelta(days=days - 1)
    return [start_date + timedelta(days=offset) for offset in range(days)]


def local_window(
    days: int,
    reference: date | datetime | None,
) -> tuple[list[date], datetime, datetime]:
    dates = local_date_range(days, reference)
    start = datetime.combine(
        dates[0],
        time.min,
        tzinfo=APPLICATION_TIMEZONE,
    )
    end = datetime.combine(
        dates[-1] + timedelta(days=1),
        time.min,
        tzinfo=APPLICATION_TIMEZONE,
    )
    return dates, start, end


def local_date_for(value: datetime) -> date:
    return to_application_timezone(value).date()

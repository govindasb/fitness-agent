from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


APPLICATION_TIMEZONE = ZoneInfo("America/New_York")
UTC = timezone.utc


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Explicit timestamps must include timezone information.")
    return value


def to_utc(value: datetime) -> datetime:
    return require_aware(value).astimezone(UTC)


def to_utc_naive(value: datetime) -> datetime:
    return to_utc(value).replace(tzinfo=None)


def from_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(UTC)
    return value.replace(tzinfo=UTC)


def to_application_timezone(value: datetime) -> datetime:
    return require_aware(value).astimezone(APPLICATION_TIMEZONE)


def utc_now() -> datetime:
    return datetime.now(UTC)


def legacy_local_naive_to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        raise ValueError("Legacy migration expects a naive local timestamp.")
    return value.replace(tzinfo=APPLICATION_TIMEZONE).astimezone(UTC).replace(
        tzinfo=None
    )


class UTCDateTime(TypeDecorator):
    """Store UTC-naive in SQLite and expose timezone-aware UTC datetimes."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return to_utc_naive(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return from_utc_naive(value)

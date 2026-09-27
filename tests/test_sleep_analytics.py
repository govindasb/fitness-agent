from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.sleep import aggregate_sleep_by_local_day, summarize_daily_sleep
from database.connection import Base
from database.repository import save_raw_event, save_sleep_entry


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def save_sleep(start=None, end=None, **values):
    with Session() as db:
        event = save_raw_event(db, "Sleep")
        save_sleep_entry(
            db,
            source_event_id=event.id,
            sleep_start=start,
            sleep_end=end,
            **values,
        )


def aggregate(days, reference):
    with Session() as db:
        return aggregate_sleep_by_local_day(db, days, reference)


def test_overnight_sleep_is_assigned_to_local_end_date():
    save_sleep(
        datetime(2026, 7, 7, 3, tzinfo=timezone.utc),
        datetime(2026, 7, 7, 11, tzinfo=timezone.utc),
        duration_minutes=480,
    )

    result = aggregate(2, date(2026, 7, 7))

    assert result[0]["session_count"] == 0
    assert result[1]["date"] == "2026-07-07"
    assert result[1]["total_duration_minutes"] == 480


def test_sleep_start_is_fallback_when_end_is_missing():
    save_sleep(
        start=datetime(2026, 7, 7, 3, 30, tzinfo=timezone.utc),
        duration_minutes=60,
    )

    result = aggregate(2, date(2026, 7, 7))

    assert result[0]["date"] == "2026-07-06"
    assert result[0]["session_count"] == 1


def test_daily_sleep_aggregates_sessions_and_preserves_unknowns():
    timestamp = datetime(2026, 7, 7, 12, tzinfo=timezone.utc)
    save_sleep(end=timestamp, duration_minutes=420, quality_rating=8)
    save_sleep(end=timestamp, duration_minutes=90)
    save_sleep(end=timestamp, quality_rating=6)

    result = aggregate(1, date(2026, 7, 7))[0]

    assert result == {
        "date": "2026-07-07",
        "session_count": 3,
        "total_duration_minutes": 510,
        "average_duration_minutes": 255.0,
        "average_quality_rating": 7.0,
        "sessions_with_duration": 2,
        "sessions_with_quality": 2,
    }


def test_sleep_summary_uses_only_days_with_known_values():
    save_sleep(
        end=datetime(2026, 7, 5, 12, tzinfo=timezone.utc),
        duration_minutes=420,
        quality_rating=8,
    )
    save_sleep(end=datetime(2026, 7, 8, 12, tzinfo=timezone.utc))
    save_sleep(
        end=datetime(2026, 7, 7, 12, tzinfo=timezone.utc),
        duration_minutes=480,
        quality_rating=6,
    )

    summary = summarize_daily_sleep(aggregate(4, date(2026, 7, 8)))

    assert summary == {
        "days_requested": 4,
        "days_with_sleep": 3,
        "days_with_duration": 2,
        "latest_sleep_date": "2026-07-08",
        "latest_duration_minutes": 480,
        "average_duration_minutes_on_recorded_days": 450.0,
        "average_quality_rating": 7.0,
        "total_sleep_minutes": 900,
    }


def test_sleep_dst_boundary_uses_end_or_fallback_local_date():
    save_sleep(end=datetime(2026, 3, 8, 4, 30, tzinfo=timezone.utc))
    save_sleep(end=datetime(2026, 3, 8, 5, 30, tzinfo=timezone.utc))

    result = aggregate(2, date(2026, 3, 8))

    assert [day["session_count"] for day in result] == [1, 1]

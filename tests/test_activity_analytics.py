from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.activity import (
    aggregate_activity_by_local_day,
    summarize_daily_activity,
)
from database.connection import Base
from database.repository import save_activity_entry, save_raw_event


test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _save_activity(recorded_at: datetime, **values):
    db = TestSessionLocal()
    try:
        raw_event = save_raw_event(db, "Activity analytics test")
        save_activity_entry(
            db,
            source_event_id=raw_event.id,
            recorded_at=recorded_at,
            **values,
        )
    finally:
        db.close()


def _aggregate(days: int, reference: date):
    db = TestSessionLocal()
    try:
        return aggregate_activity_by_local_day(
            db,
            days=days,
            reference=reference,
        )
    finally:
        db.close()


def test_multiple_records_on_same_local_day_are_aggregated():
    _save_activity(
        datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc),
        steps=3000,
        distance_km=2.0,
        active_minutes=20,
    )
    _save_activity(
        datetime(2026, 7, 2, 22, 0, tzinfo=timezone.utc),
        steps=4500,
        distance_km=3.25,
        active_minutes=30,
        calories_burned=250,
    )

    result = _aggregate(days=1, reference=date(2026, 7, 2))

    assert result == [
        {
            "date": "2026-07-02",
            "steps": 7500,
            "distance_km": 5.25,
            "active_minutes": 50,
            "calories_burned": 250,
            "record_count": 2,
        }
    ]


def test_utc_times_across_midnight_use_new_york_local_dates():
    _save_activity(
        datetime(2026, 7, 2, 3, 30, tzinfo=timezone.utc),
        steps=1000,
    )
    _save_activity(
        datetime(2026, 7, 2, 4, 30, tzinfo=timezone.utc),
        steps=2000,
    )

    result = _aggregate(days=2, reference=date(2026, 7, 2))

    assert [(day["date"], day["steps"]) for day in result] == [
        ("2026-07-01", 1000),
        ("2026-07-02", 2000),
    ]


def test_requested_range_includes_days_without_records():
    _save_activity(
        datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc),
        steps=5000,
    )

    result = _aggregate(days=3, reference=date(2026, 7, 3))

    assert result[0] == {
        "date": "2026-07-01",
        "steps": None,
        "distance_km": None,
        "active_minutes": None,
        "calories_burned": None,
        "record_count": 0,
    }
    assert result[1]["record_count"] == 0
    assert result[2]["steps"] == 5000


def test_unknown_numeric_values_remain_missing():
    _save_activity(
        datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc),
        distance_km=2.5,
    )

    result = _aggregate(days=1, reference=date(2026, 7, 3))

    assert result[0]["record_count"] == 1
    assert result[0]["steps"] is None
    assert result[0]["distance_km"] == 2.5
    assert result[0]["active_minutes"] is None
    assert result[0]["calories_burned"] is None


def test_summary_ignores_days_with_unknown_steps():
    daily_activity = [
        {
            "date": "2026-07-01",
            "steps": 4000,
            "distance_km": None,
            "active_minutes": None,
            "calories_burned": None,
            "record_count": 1,
        },
        {
            "date": "2026-07-02",
            "steps": None,
            "distance_km": 2.0,
            "active_minutes": None,
            "calories_burned": None,
            "record_count": 1,
        },
        {
            "date": "2026-07-03",
            "steps": 8000,
            "distance_km": None,
            "active_minutes": None,
            "calories_burned": None,
            "record_count": 1,
        },
        {
            "date": "2026-07-04",
            "steps": None,
            "distance_km": None,
            "active_minutes": None,
            "calories_burned": None,
            "record_count": 0,
        },
    ]

    summary = summarize_daily_activity(daily_activity)

    assert summary == {
        "days_requested": 4,
        "days_with_data": 3,
        "days_with_steps": 2,
        "latest_date": "2026-07-03",
        "latest_steps": 8000,
        "total_steps": 12000,
        "average_steps_on_recorded_days": 6000.0,
    }


def test_summary_returns_null_totals_when_no_steps_are_known():
    daily_activity = _aggregate(days=2, reference=date(2026, 7, 3))

    summary = summarize_daily_activity(daily_activity)

    assert summary["total_steps"] is None
    assert summary["average_steps_on_recorded_days"] is None
    assert summary["latest_date"] is None
    assert summary["latest_steps"] is None


def test_activity_near_dst_boundary_uses_correct_local_date():
    _save_activity(
        datetime(2026, 3, 8, 4, 30, tzinfo=timezone.utc),
        steps=1000,
    )
    _save_activity(
        datetime(2026, 3, 8, 5, 30, tzinfo=timezone.utc),
        steps=2000,
    )

    result = _aggregate(days=2, reference=date(2026, 3, 8))

    assert [(day["date"], day["steps"]) for day in result] == [
        ("2026-03-07", 1000),
        ("2026-03-08", 2000),
    ]

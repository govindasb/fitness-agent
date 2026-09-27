from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.weight import (
    aggregate_weight_by_local_day,
    summarize_weight_trend,
)
from database.connection import Base
from database.repository import save_body_metric, save_raw_event


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


def save_weight(measured_at, weight):
    with Session() as db:
        event = save_raw_event(db, "Body metric")
        save_body_metric(
            db,
            source_event_id=event.id,
            measured_at=measured_at,
            weight_kg=weight,
        )


def aggregate(days, reference):
    with Session() as db:
        return aggregate_weight_by_local_day(db, days, reference)


def test_daily_weight_orders_multiple_measurements_by_timestamp():
    save_weight(datetime(2026, 7, 3, 22, tzinfo=timezone.utc), 96.0)
    save_weight(datetime(2026, 7, 3, 12, tzinfo=timezone.utc), 97.0)

    result = aggregate(1, date(2026, 7, 3))[0]

    assert result == {
        "date": "2026-07-03",
        "measurement_count": 2,
        "first_weight_kg": 97.0,
        "latest_weight_kg": 96.0,
        "average_weight_kg": 96.5,
        "min_weight_kg": 96.0,
        "max_weight_kg": 97.0,
    }


def test_null_weights_are_excluded_and_missing_days_are_present():
    save_weight(datetime(2026, 7, 3, 12, tzinfo=timezone.utc), None)

    result = aggregate(2, date(2026, 7, 3))

    assert all(day["measurement_count"] == 0 for day in result)
    assert all(day["latest_weight_kg"] is None for day in result)


def test_weight_trend_uses_daily_latest_measurements():
    save_weight(datetime(2026, 7, 1, 12, tzinfo=timezone.utc), 98.0)
    save_weight(datetime(2026, 7, 1, 20, tzinfo=timezone.utc), 97.5)
    save_weight(datetime(2026, 7, 3, 12, tzinfo=timezone.utc), 96.5)

    summary = summarize_weight_trend(aggregate(4, date(2026, 7, 4)))

    assert summary["days_with_weight"] == 2
    assert summary["earliest_date"] == "2026-07-01"
    assert summary["earliest_weight_kg"] == 97.5
    assert summary["latest_date"] == "2026-07-03"
    assert summary["latest_weight_kg"] == 96.5
    assert summary["change_kg"] == -1.0
    assert summary["average_weight_kg"] == 97.33
    assert summary["min_weight_kg"] == 96.5
    assert summary["max_weight_kg"] == 98.0


def test_weight_midnight_and_dst_boundaries_use_local_dates():
    save_weight(datetime(2026, 3, 8, 4, 30, tzinfo=timezone.utc), 98.0)
    save_weight(datetime(2026, 3, 8, 5, 30, tzinfo=timezone.utc), 97.5)

    result = aggregate(2, date(2026, 3, 8))

    assert [(day["date"], day["latest_weight_kg"]) for day in result] == [
        ("2026-03-07", 98.0),
        ("2026-03-08", 97.5),
    ]

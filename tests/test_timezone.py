from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base
from database.repository import save_body_metric, save_raw_event
from database.schema import BodyMetric
from database.timezone import (
    APPLICATION_TIMEZONE,
    to_application_timezone,
    to_utc,
)


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


def _save_and_reload(value: datetime) -> datetime:
    db = TestSessionLocal()
    try:
        raw_event = save_raw_event(db, "Timezone test")
        metric = save_body_metric(
            db,
            source_event_id=raw_event.id,
            weight_kg=97.0,
            measured_at=value,
        )
        metric_id = metric.id
    finally:
        db.close()

    db = TestSessionLocal()
    try:
        return db.get(BodyMetric, metric_id).measured_at
    finally:
        db.close()


def test_new_york_timestamp_is_stored_as_utc_and_restored_aware():
    local_value = datetime(
        2026, 7, 1, 12, 0, tzinfo=APPLICATION_TIMEZONE
    )

    loaded = _save_and_reload(local_value)

    assert loaded == datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc)
    assert loaded.tzinfo is timezone.utc

    with test_engine.connect() as connection:
        stored = connection.execute(
            text("SELECT measured_at FROM body_metrics")
        ).scalar_one()
    assert stored == "2026-07-01 16:00:00.000000"


def test_other_timezone_normalizes_to_the_same_utc_instant():
    los_angeles = ZoneInfo("America/Los_Angeles")
    local_value = datetime(2026, 7, 1, 9, 0, tzinfo=los_angeles)

    loaded = _save_and_reload(local_value)

    assert loaded == datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc)


def test_naive_explicit_timestamp_is_rejected():
    db = TestSessionLocal()
    try:
        raw_event = save_raw_event(db, "Naive timestamp test")
        with pytest.raises(StatementError, match="timezone information"):
            save_body_metric(
                db,
                source_event_id=raw_event.id,
                weight_kg=97.0,
                measured_at=datetime(2026, 7, 1, 12, 0),
            )
    finally:
        db.rollback()
        db.close()


def test_utc_round_trip_through_sqlite():
    utc_value = datetime(2026, 7, 1, 16, 0, 1, 234567, tzinfo=timezone.utc)

    loaded = _save_and_reload(utc_value)

    assert loaded == utc_value
    assert loaded.tzinfo is timezone.utc


def test_local_day_conversion_across_midnight():
    before_midnight = datetime(2026, 7, 1, 3, 30, tzinfo=timezone.utc)
    after_midnight = datetime(2026, 7, 1, 4, 30, tzinfo=timezone.utc)

    assert to_application_timezone(before_midnight).date().isoformat() == "2026-06-30"
    assert to_application_timezone(after_midnight).date().isoformat() == "2026-07-01"


def test_dst_spring_forward_skips_nonexistent_local_hour():
    before_jump = datetime(2026, 3, 8, 6, 30, tzinfo=timezone.utc)
    after_jump = before_jump + timedelta(hours=1)

    local_before = to_application_timezone(before_jump)
    local_after = to_application_timezone(after_jump)

    assert (local_before.hour, local_before.utcoffset()) == (
        1,
        timedelta(hours=-5),
    )
    assert (local_after.hour, local_after.utcoffset()) == (
        3,
        timedelta(hours=-4),
    )


def test_dst_fall_back_fold_values_are_distinct_utc_instants():
    first = datetime(
        2026, 11, 1, 1, 30, tzinfo=APPLICATION_TIMEZONE, fold=0
    )
    second = datetime(
        2026, 11, 1, 1, 30, tzinfo=APPLICATION_TIMEZONE, fold=1
    )

    assert to_utc(first) == datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)
    assert to_utc(second) == datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)

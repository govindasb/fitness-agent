from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analytics.food import aggregate_food_by_local_day, summarize_daily_food
from database.connection import Base
from database.repository import save_food_entry, save_raw_event


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


def save_food(consumed_at, name, **values):
    with Session() as db:
        event = save_raw_event(db, f"Ate {name}")
        save_food_entry(
            db,
            source_event_id=event.id,
            consumed_at=consumed_at,
            food_name=name,
            **values,
        )


def aggregate(days, reference):
    with Session() as db:
        return aggregate_food_by_local_day(db, days, reference)


def test_daily_food_aggregates_items_and_preserves_partial_macros():
    timestamp = datetime(2026, 7, 3, 16, tzinfo=timezone.utc)
    with Session() as db:
        event = save_raw_event(db, "Ate chicken and rice")
        save_food_entry(
            db,
            source_event_id=event.id,
            consumed_at=timestamp,
            food_name="chicken",
            estimated_calories=300,
            protein_g=40,
            is_estimated=True,
        )
        save_food_entry(
            db,
            source_event_id=event.id,
            consumed_at=timestamp,
            food_name="rice",
            estimated_calories=250,
            carbs_g=55,
            is_estimated=True,
        )

    result = aggregate(2, date(2026, 7, 3))

    assert result[0]["entry_count"] == 0
    assert result[0]["total_estimated_calories"] is None
    assert result[1] == {
        "date": "2026-07-03",
        "entry_count": 2,
        "entries_with_calories": 2,
        "entries_with_protein": 1,
        "entries_with_carbs": 1,
        "entries_with_fat": 0,
        "entries_with_fiber": 0,
        "estimated_entry_count": 2,
        "total_estimated_calories": 550,
        "total_protein_g": 40,
        "total_carbs_g": 55,
        "total_fat_g": None,
        "total_fiber_g": None,
    }


def test_food_uses_new_york_date_across_utc_midnight():
    save_food(
        datetime(2026, 7, 2, 3, 30, tzinfo=timezone.utc),
        "snack",
        estimated_calories=100,
    )
    save_food(
        datetime(2026, 7, 2, 4, 30, tzinfo=timezone.utc),
        "breakfast",
        estimated_calories=200,
    )

    result = aggregate(2, date(2026, 7, 2))

    assert [day["total_estimated_calories"] for day in result] == [100, 200]


def test_food_summary_uses_only_days_with_known_nutrients():
    save_food(
        datetime(2026, 7, 1, 16, tzinfo=timezone.utc),
        "meal one",
        estimated_calories=400,
        protein_g=30,
    )
    save_food(
        datetime(2026, 7, 4, 16, tzinfo=timezone.utc),
        "unknown meal",
    )
    save_food(
        datetime(2026, 7, 3, 16, tzinfo=timezone.utc),
        "meal three",
        estimated_calories=600,
        protein_g=50,
    )

    summary = summarize_daily_food(aggregate(4, date(2026, 7, 4)))

    assert summary == {
        "days_requested": 4,
        "days_with_food": 3,
        "days_with_calorie_data": 2,
        "days_with_protein_data": 2,
        "latest_date_with_food": "2026-07-04",
        "latest_calories": 600,
        "latest_protein_g": 50,
        "total_estimated_calories": 1000,
        "total_protein_g": 80,
        "average_calories_on_recorded_days": 500.0,
        "average_protein_on_recorded_days": 40.0,
    }


def test_food_dst_boundary_groups_by_local_date():
    save_food(
        datetime(2026, 3, 8, 4, 30, tzinfo=timezone.utc),
        "late snack",
        protein_g=10,
    )
    save_food(
        datetime(2026, 3, 8, 5, 30, tzinfo=timezone.utc),
        "early snack",
        protein_g=20,
    )

    result = aggregate(2, date(2026, 3, 8))

    assert [day["total_protein_g"] for day in result] == [10, 20]

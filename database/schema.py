from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base
from database.timezone import UTCDateTime, utc_now


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_time: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

class BodyMetric(Base):
    __tablename__ = "body_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    measured_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )

    weight_kg: Mapped[float | None] = mapped_column(nullable=True)
    waist_cm: Mapped[float | None] = mapped_column(nullable=True)
    body_fat_percent: Mapped[float | None] = mapped_column(nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(nullable=True)

    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

class FoodEntry(Base):
    __tablename__ = "food_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    consumed_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )

    meal_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    food_name: Mapped[str] = mapped_column(String(200), nullable=False)

    quantity: Mapped[float | None] = mapped_column(nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)

    estimated_calories: Mapped[float | None] = mapped_column(nullable=True)
    protein_g: Mapped[float | None] = mapped_column(nullable=True)
    carbs_g: Mapped[float | None] = mapped_column(nullable=True)
    fat_g: Mapped[float | None] = mapped_column(nullable=True)
    fiber_g: Mapped[float | None] = mapped_column(nullable=True)

    is_estimated: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )

    workout_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    duration_minutes: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

class ExerciseSet(Base):
    __tablename__ = "exercise_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    workout_session_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    exercise_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    set_number: Mapped[int | None] = mapped_column(nullable=True)

    weight_kg: Mapped[float | None] = mapped_column(nullable=True)
    reps: Mapped[int | None] = mapped_column(nullable=True)

    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    distance_km: Mapped[float | None] = mapped_column(nullable=True)

    rpe: Mapped[float | None] = mapped_column(nullable=True)

class ActivityEntry(Base):
    __tablename__ = "activity_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    recorded_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )

    steps: Mapped[int | None] = mapped_column(nullable=True)
    distance_km: Mapped[float | None] = mapped_column(nullable=True)
    active_minutes: Mapped[int | None] = mapped_column(nullable=True)
    calories_burned: Mapped[float | None] = mapped_column(nullable=True)

    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

class SleepEntry(Base):
    __tablename__ = "sleep_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    sleep_start: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )

    sleep_end: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )

    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)

    quality_rating: Mapped[int | None] = mapped_column(nullable=True)

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

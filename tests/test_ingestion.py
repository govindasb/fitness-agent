import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import agent.ingestion as ingestion
from agent.interpreter import (
    InterpretationResult,
    RelativeTimeResolver,
    StaticInterpreter,
)
from database.connection import Base
from database.schema import ActivityEntry, BodyMetric, RawEvent
from database.timezone import APPLICATION_TIMEZONE
from models.parsed_input import ParsedInput


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=engine)
REFERENCE = datetime(
    2026,
    7,
    8,
    15,
    30,
    tzinfo=APPLICATION_TIMEZONE,
)


@pytest.fixture(autouse=True)
def reset_database(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(ingestion, "SessionLocal", Session)
    yield
    Base.metadata.drop_all(bind=engine)


def test_raw_event_is_committed_before_interpretation():
    raw_text = "Walked 9000 steps today"

    class InspectingInterpreter:
        def interpret(self, text, reference=None):
            with Session() as db:
                event = db.query(RawEvent).one()
                assert event.raw_text == raw_text
                assert event.processing_status == "pending"
            return {"activities": [{"steps": 9000, "recorded_at": REFERENCE}]}

    result = ingestion.ingest_fitness_message(
        raw_text,
        InspectingInterpreter(),
        reference=REFERENCE,
    )

    assert result["status"] == "processed"


def test_successful_single_domain_ingestion_sets_status_and_event_time():
    result = ingestion.ingest_fitness_message(
        "Walked 9000 steps today",
        StaticInterpreter(
            {"activities": [{"steps": 9000, "recorded_at": REFERENCE}]}
        ),
        reference=REFERENCE,
    )

    with Session() as db:
        event = db.get(RawEvent, result["raw_event_id"])
        activity = db.query(ActivityEntry).one()
        assert event.processing_status == "processed"
        assert event.event_type == "activity"
        assert event.parser_version == "fitness-interpreter-v1"
        assert event.event_time == REFERENCE
        assert activity.source_event_id == event.id


def test_successful_mixed_ingestion_uses_one_raw_event_and_shared_source():
    result = ingestion.ingest_fitness_message(
        "Weight 96.2 kg and 9000 steps",
        StaticInterpreter(
            {
                "body_metrics": [
                    {"weight_kg": 96.2, "measured_at": REFERENCE}
                ],
                "activities": [
                    {"steps": 9000, "recorded_at": REFERENCE}
                ],
            }
        ),
        reference=REFERENCE,
    )

    with Session() as db:
        events = db.query(RawEvent).all()
        metric = db.query(BodyMetric).one()
        activity = db.query(ActivityEntry).one()
        assert len(events) == 1
        assert events[0].event_type == "mixed"
        assert metric.source_event_id == events[0].id
        assert activity.source_event_id == events[0].id


def test_parser_failure_preserves_raw_event_and_marks_failed():
    class FailingInterpreter:
        def interpret(self, raw_text, reference=None):
            raise RuntimeError("parser unavailable")


    result = ingestion.ingest_fitness_message(
        "Unparseable message",
        FailingInterpreter(),
        reference=REFERENCE,
    )

    with Session() as db:
        event = db.query(RawEvent).one()
        assert event.raw_text == "Unparseable message"
        assert event.processing_status == "failed"
        assert event.parser_version == "fitness-interpreter-v1"
        assert db.query(ActivityEntry).count() == 0
    assert result["status"] == "failed"
    assert result["unparsed_fragments"] == ["Unparseable message"]


def test_validation_failure_preserves_raw_event():
    result = ingestion.ingest_fitness_message(
        "Walked negative steps",
        StaticInterpreter({"activities": [{"steps": -1}]}),
        reference=REFERENCE,
    )

    with Session() as db:
        assert db.query(RawEvent).one().processing_status == "failed"
        assert db.query(ActivityEntry).count() == 0
    assert "Interpretation failed" in result["warnings"][0]


def test_structured_failure_rolls_back_records_but_preserves_raw(
    monkeypatch,
):
    def fail_activity(*args, **kwargs):
        raise RuntimeError("forced persistence failure")

    monkeypatch.setattr(ingestion, "save_activity_entry", fail_activity)
    result = ingestion.ingest_fitness_message(
        "Weight 96.2 kg and 9000 steps",
        StaticInterpreter(
            {
                "body_metrics": [
                    {"weight_kg": 96.2, "measured_at": REFERENCE}
                ],
                "activities": [
                    {"steps": 9000, "recorded_at": REFERENCE}
                ],
            }
        ),
        reference=REFERENCE,
    )

    with Session() as db:
        assert db.query(RawEvent).one().processing_status == "failed"
        assert db.query(BodyMetric).count() == 0
        assert db.query(ActivityEntry).count() == 0
    assert result["stored"] == ingestion._empty_stored()


def test_conflicting_event_times_leave_raw_event_time_null():
    result = ingestion.ingest_fitness_message(
        "Morning weight and evening steps",
        StaticInterpreter(
            {
                "body_metrics": [
                    {"weight_kg": 96.2, "measured_at": REFERENCE}
                ],
                "activities": [
                    {
                        "steps": 9000,
                        "recorded_at": REFERENCE + timedelta(hours=5),
                    }
                ],
            }
        ),
        reference=REFERENCE,
    )

    with Session() as db:
        assert db.get(RawEvent, result["raw_event_id"]).event_time is None


def test_warnings_fragments_and_result_are_json_serializable():
    interpretation = InterpretationResult(
        parsed_input=ParsedInput(
            activities=[{"steps": 9000, "recorded_at": REFERENCE}]
        ),
        warnings=["Meal details were incomplete."],
        unparsed_fragments=["and had some lunch"],
    )

    result = ingestion.ingest_fitness_message(
        "Walked 9000 steps and had some lunch",
        StaticInterpreter(interpretation),
        reference=REFERENCE,
    )

    assert result["warnings"] == ["Meal details were incomplete."]
    assert result["unparsed_fragments"] == ["and had some lunch"]
    json.dumps(result)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("today", datetime(2026, 7, 8, 15, 30, tzinfo=APPLICATION_TIMEZONE)),
        (
            "yesterday",
            datetime(2026, 7, 7, 15, 30, tzinfo=APPLICATION_TIMEZONE),
        ),
        (
            "this morning",
            datetime(2026, 7, 8, 8, 0, tzinfo=APPLICATION_TIMEZONE),
        ),
        (
            "tonight",
            datetime(2026, 7, 8, 20, 0, tzinfo=APPLICATION_TIMEZONE),
        ),
    ],
)
def test_relative_point_time_resolution(expression, expected):
    resolved = RelativeTimeResolver(REFERENCE).resolve(expression)

    assert resolved.timestamp == expected
    assert resolved.timestamp.utcoffset() is not None


def test_last_night_resolves_an_aware_overnight_period():
    resolved = RelativeTimeResolver(REFERENCE).resolve("last night")

    assert resolved.sleep_start == datetime(
        2026, 7, 7, 22, tzinfo=APPLICATION_TIMEZONE
    )
    assert resolved.sleep_end == datetime(
        2026, 7, 8, 7, tzinfo=APPLICATION_TIMEZONE
    )
    assert resolved.sleep_start.utcoffset() is not None
    assert resolved.sleep_end.utcoffset() is not None


def test_last_night_handles_spring_dst_transition():
    reference = datetime(
        2026,
        3,
        8,
        12,
        tzinfo=APPLICATION_TIMEZONE,
    )

    resolved = RelativeTimeResolver(reference).resolve("last night")

    assert resolved.sleep_start.utcoffset() == timedelta(hours=-5)
    assert resolved.sleep_end.utcoffset() == timedelta(hours=-4)


def test_unsupported_relative_expression_is_not_guessed():
    assert RelativeTimeResolver(REFERENCE).resolve("three Tuesdays ago") is None

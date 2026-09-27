from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import agent.ingestion as ingestion
from agent.interpreter import FitnessInterpreter, InterpretationResult
from agent.openai_interpreter import (
    OpenAIFitnessInterpreter,
    OpenAIInterpretationError,
)
from config.openai import DEFAULT_OPENAI_MODEL
from database.connection import Base
from database.schema import ActivityEntry, BodyMetric, RawEvent
from database.timezone import APPLICATION_TIMEZONE


REFERENCE = datetime(
    2026,
    7,
    8,
    15,
    30,
    tzinfo=APPLICATION_TIMEZONE,
)


class FakeResponses:
    def __init__(self, output=None, error=None, status="completed", usage=None):
        self.output = output
        self.error = error
        self.status = status
        self.usage = usage
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            status=self.status,
            output_parsed=self.output,
            usage=self.usage,
        )


def fake_client(output=None, error=None, status="completed", usage=None):
    responses = FakeResponses(
        output=output,
        error=error,
        status=status,
        usage=usage,
    )
    return SimpleNamespace(responses=responses), responses


def activity_result(**metadata):
    return InterpretationResult(
        parsed_input={
            "activities": [
                {
                    "steps": 9000,
                    "time_expression": "today",
                }
            ]
        },
        **metadata,
    )


def test_openai_interpreter_satisfies_protocol():
    client, _ = fake_client(activity_result())
    interpreter = OpenAIFitnessInterpreter(client=client)

    assert isinstance(interpreter, FitnessInterpreter)


def test_model_configuration_and_structured_responses_request(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    client, responses = fake_client(activity_result())
    interpreter = OpenAIFitnessInterpreter(client=client)

    result = interpreter.interpret("Walked 9000 steps today", REFERENCE)

    call = responses.calls[0]
    assert interpreter.model == "configured-model"
    assert call["model"] == "configured-model"
    assert call["store"] is False
    assert call["text_format"] is InterpretationResult
    assert call["input"] == "Walked 9000 steps today"
    assert "America/New_York" in call["instructions"]
    assert REFERENCE.isoformat() in call["instructions"]
    assert result.parsed_input.activities[0].recorded_at == REFERENCE


def test_default_model_is_used_when_environment_override_is_absent(
    monkeypatch,
):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client, _ = fake_client(activity_result())

    interpreter = OpenAIFitnessInterpreter(client=client)

    assert interpreter.model == DEFAULT_OPENAI_MODEL


def test_response_usage_is_exposed_for_explicit_evaluation():
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=25,
        total_tokens=125,
    )
    client, _ = fake_client(activity_result(), usage=usage)
    interpreter = OpenAIFitnessInterpreter(client=client)

    interpreter.interpret("Walked today", REFERENCE)

    assert interpreter.last_usage == {
        "input_tokens": 100,
        "output_tokens": 25,
        "total_tokens": 125,
    }


def test_provider_warnings_and_unparsed_fragments_are_preserved():
    client, _ = fake_client(
        activity_result(
            warnings=["Meal details were unclear."],
            unparsed_fragments=["and ate something"],
        )
    )

    result = OpenAIFitnessInterpreter(client=client).interpret(
        "Walked and ate something",
        REFERENCE,
    )

    assert result.warnings == ["Meal details were unclear."]
    assert result.unparsed_fragments == ["and ate something"]


def test_empty_model_body_record_is_normalized_but_metadata_remains():
    client, _ = fake_client(
        InterpretationResult(
            parsed_input={"body_metrics": [{}]},
            warnings=["Pounds conversion skipped."],
            unparsed_fragments=["I weigh 216 lb."],
        )
    )

    result = OpenAIFitnessInterpreter(client=client).interpret(
        "I weigh 216 lb.",
        REFERENCE,
    )

    assert result.parsed_input.body_metrics == []
    assert result.warnings == ["Pounds conversion skipped."]
    assert result.unparsed_fragments == ["I weigh 216 lb."]


def test_unsupported_time_record_is_normalized_by_openai_adapter():
    client, _ = fake_client(
        InterpretationResult(
            parsed_input={
                "activities": [{"steps": 8000, "time_status": "unsupported"}]
            },
            warnings=["Unsupported date."],
            unparsed_fragments=["Three Tuesdays ago I walked 8000 steps"],
        )
    )

    result = OpenAIFitnessInterpreter(client=client).interpret(
        "Three Tuesdays ago I walked 8000 steps",
        REFERENCE,
    )

    assert result.parsed_input.activities == []
    assert result.warnings == ["Unsupported date."]


def test_lexical_labels_are_normalized_by_openai_adapter():
    client, _ = fake_client(
        InterpretationResult(
            parsed_input={
                "food_entries": [
                    {"meal_type": "Dinner", "items": [{"food_name": "Rice"}]}
                ],
                "workouts": [
                    {
                        "workout_type": " Back ",
                        "sets": [{"exercise_name": "run"}],
                    }
                ],
            }
        )
    )

    result = OpenAIFitnessInterpreter(client=client).interpret(
        "Dinner and back run",
        REFERENCE,
    )

    assert result.parsed_input.food_entries[0].meal_type == "dinner"
    assert result.parsed_input.food_entries[0].items[0].food_name == "Rice"
    assert result.parsed_input.workouts[0].workout_type == "back"
    assert result.parsed_input.workouts[0].sets[0].exercise_name == "running"


def test_provider_result_is_revalidated_and_naive_timestamp_is_rejected():
    client, _ = fake_client(
        {
            "parsed_input": {
                "body_metrics": [
                    {
                        "weight_kg": 96.2,
                        "measured_at": "2026-07-08T08:00:00",
                    }
                ]
            },
            "warnings": [],
            "unparsed_fragments": [],
        }
    )

    with pytest.raises(OpenAIInterpretationError, match="timezone information"):
        OpenAIFitnessInterpreter(client=client).interpret(
            "Weight 96.2 kg",
            REFERENCE,
        )


def test_provider_exception_becomes_interpretation_error():
    client, _ = fake_client(error=TimeoutError("network timeout"))

    with pytest.raises(OpenAIInterpretationError, match="network timeout"):
        OpenAIFitnessInterpreter(client=client).interpret(
            "Walked today",
            REFERENCE,
        )


@pytest.mark.parametrize(
    ("output", "status"),
    [
        (None, "completed"),
        (activity_result(), "incomplete"),
    ],
)
def test_missing_or_incomplete_response_fails_cleanly(output, status):
    client, _ = fake_client(output=output, status=status)

    with pytest.raises(OpenAIInterpretationError):
        OpenAIFitnessInterpreter(client=client).interpret(
            "Walked today",
            REFERENCE,
        )


def test_missing_api_key_fails_cleanly(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    interpreter = OpenAIFitnessInterpreter()

    with pytest.raises(OpenAIInterpretationError, match="OPENAI_API_KEY"):
        interpreter.interpret("Walked today", REFERENCE)


test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine)


@pytest.fixture
def ingestion_database(monkeypatch):
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(ingestion, "SessionLocal", TestSession)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_mocked_openai_ingestion_preserves_one_raw_event_and_records(
    ingestion_database,
):
    output = InterpretationResult(
        parsed_input={
            "body_metrics": [
                {"weight_kg": 96.2, "time_expression": "this morning"}
            ],
            "activities": [
                {"steps": 9000, "time_expression": "today"}
            ],
        }
    )
    client, _ = fake_client(output)
    interpreter = OpenAIFitnessInterpreter(client=client)
    raw_text = "I weighed 96.2 kg this morning and walked 9000 steps today"

    result = ingestion.ingest_fitness_message(
        raw_text,
        interpreter,
        reference=REFERENCE,
    )

    with TestSession() as db:
        event = db.query(RawEvent).one()
        metric = db.query(BodyMetric).one()
        activity = db.query(ActivityEntry).one()
        assert event.raw_text == raw_text
        assert event.processing_status == "processed"
        assert event.event_type == "mixed"
        assert metric.source_event_id == event.id
        assert activity.source_event_id == event.id
    assert result["status"] == "processed"


def test_provider_failure_through_ingestion_preserves_failed_raw_event(
    ingestion_database,
):
    client, _ = fake_client(error=RuntimeError("provider failure"))
    interpreter = OpenAIFitnessInterpreter(client=client)

    result = ingestion.ingest_fitness_message(
        "Walked 9000 steps today",
        interpreter,
        reference=REFERENCE,
    )

    with TestSession() as db:
        event = db.query(RawEvent).one()
        assert event.raw_text == "Walked 9000 steps today"
        assert event.processing_status == "failed"
        assert db.query(ActivityEntry).count() == 0
    assert result["status"] == "failed"

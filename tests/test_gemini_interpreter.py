from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import agent.ingestion as ingestion
from agent.gemini_interpreter import (
    GeminiFitnessInterpreter,
    GeminiInterpretationError,
    sanitize_schema_for_gemini,
)
from agent.interpreter import FitnessInterpreter, InterpretationResult
from config.gemini import DEFAULT_GEMINI_MODEL, get_gemini_api_key
from database.connection import Base
from database.schema import ActivityEntry, BodyMetric, RawEvent
from database.timezone import APPLICATION_TIMEZONE


REFERENCE = datetime(2026, 7, 8, 15, 30, tzinfo=APPLICATION_TIMEZONE)


class FakeModels:
    def __init__(self, parsed=None, error=None, usage=None, text=None):
        self.parsed = parsed
        self.error = error
        self.usage = usage
        self.text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            parsed=self.parsed,
            usage_metadata=self.usage,
            text=self.text,
        )


def fake_client(parsed=None, error=None, usage=None, text=None):
    models = FakeModels(
        parsed=parsed,
        error=error,
        usage=usage,
        text=text,
    )
    return SimpleNamespace(models=models), models


def activity_result(**metadata):
    return InterpretationResult(
        parsed_input={
            "activities": [{"steps": 9000, "time_expression": "today"}]
        },
        **metadata,
    )


def contains_key(value, target):
    if isinstance(value, dict):
        return target in value or any(
            contains_key(child, target) for child in value.values()
        )
    if isinstance(value, list):
        return any(contains_key(child, target) for child in value)
    return False


def test_schema_sanitizer_removes_unsupported_constraints_recursively():
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "exclusiveMaximum": 10,
                    "default": 1,
                },
            }
        },
    }

    sanitized = sanitize_schema_for_gemini(schema)

    assert not contains_key(sanitized, "exclusiveMinimum")
    assert not contains_key(sanitized, "exclusiveMaximum")
    assert not contains_key(sanitized, "default")
    assert schema["properties"]["items"]["items"]["exclusiveMinimum"] == 0


def test_schema_sanitizer_preserves_supported_structure_and_references():
    schema = {
        "$defs": {"Metric": {"type": "number", "minimum": 0}},
        "type": "object",
        "properties": {
            "metric": {
                "anyOf": [{"$ref": "#/$defs/Metric"}, {"type": "null"}]
            }
        },
        "required": ["metric"],
        "additionalProperties": False,
    }

    assert sanitize_schema_for_gemini(schema) == schema


def test_gemini_interpreter_satisfies_protocol():
    client, _ = fake_client(activity_result())

    assert isinstance(GeminiFitnessInterpreter(client=client), FitnessInterpreter)


def test_default_and_environment_model_selection(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    client, _ = fake_client(activity_result())
    assert DEFAULT_GEMINI_MODEL == "gemini-3.5-flash-lite"
    assert GeminiFitnessInterpreter(client=client).model == DEFAULT_GEMINI_MODEL

    monkeypatch.setenv("GEMINI_MODEL", "configured-gemini")
    assert GeminiFitnessInterpreter(client=client).model == "configured-gemini"


def test_constructor_model_override_wins(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "environment-model")
    client, _ = fake_client(activity_result())

    assert GeminiFitnessInterpreter(client=client, model="override-model").model == "override-model"


def test_gemini_api_key_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    assert get_gemini_api_key() == "test-gemini-key"


def test_structured_schema_instructions_reference_and_timezone():
    client, models = fake_client(activity_result())
    interpreter = GeminiFitnessInterpreter(client=client, model="gemini-test")

    result = interpreter.interpret("Walked 9000 steps today", REFERENCE)

    call = models.calls[0]
    config = call["config"]
    assert call["model"] == "gemini-test"
    assert call["contents"] == "Walked 9000 steps today"
    assert config.response_mime_type == "application/json"
    assert config.response_schema is None
    assert config.response_json_schema == sanitize_schema_for_gemini(
        InterpretationResult.model_json_schema()
    )
    assert not contains_key(config.response_json_schema, "exclusiveMinimum")
    assert not contains_key(config.response_json_schema, "exclusiveMaximum")
    assert not contains_key(config.response_json_schema, "default")
    assert "extract" in config.system_instruction.lower()
    assert "America/New_York" in config.system_instruction
    assert REFERENCE.isoformat() in config.system_instruction
    assert result.parsed_input.activities[0].recorded_at == REFERENCE


def test_result_is_revalidated_and_metadata_preserved():
    client, _ = fake_client(
        {
            "parsed_input": {"activities": [{"steps": 9000}]},
            "warnings": ["Unclear meal."],
            "unparsed_fragments": ["and something else"],
        }
    )

    result = GeminiFitnessInterpreter(client=client).interpret(
        "Walked and something else",
        REFERENCE,
    )

    assert isinstance(result, InterpretationResult)
    assert result.warnings == ["Unclear meal."]
    assert result.unparsed_fragments == ["and something else"]


def test_empty_model_body_record_is_normalized_but_metadata_remains():
    client, _ = fake_client(
        InterpretationResult(
            parsed_input={"body_metrics": [{}]},
            warnings=["Pounds conversion skipped."],
            unparsed_fragments=["I weigh 216 lb."],
        )
    )

    result = GeminiFitnessInterpreter(client=client).interpret(
        "I weigh 216 lb.",
        REFERENCE,
    )

    assert result.parsed_input.body_metrics == []
    assert result.warnings == ["Pounds conversion skipped."]
    assert result.unparsed_fragments == ["I weigh 216 lb."]


def test_unsupported_time_record_is_normalized_by_gemini_adapter():
    client, _ = fake_client(
        InterpretationResult(
            parsed_input={
                "activities": [{"steps": 8000, "time_status": "unsupported"}]
            },
            warnings=["Unsupported date."],
            unparsed_fragments=["Three Tuesdays ago I walked 8000 steps"],
        )
    )

    result = GeminiFitnessInterpreter(client=client).interpret(
        "Three Tuesdays ago I walked 8000 steps",
        REFERENCE,
    )

    assert result.parsed_input.activities == []
    assert result.warnings == ["Unsupported date."]


def test_lexical_labels_are_normalized_by_gemini_adapter():
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

    result = GeminiFitnessInterpreter(client=client).interpret(
        "Dinner and back run",
        REFERENCE,
    )

    assert result.parsed_input.food_entries[0].meal_type == "dinner"
    assert result.parsed_input.food_entries[0].items[0].food_name == "Rice"
    assert result.parsed_input.workouts[0].workout_type == "back"
    assert result.parsed_input.workouts[0].sets[0].exercise_name == "running"


def test_json_text_is_parsed_when_parsed_value_is_unavailable():
    client, _ = fake_client(
        text=(
            '{"parsed_input":{"activities":[{"steps":9000}]},'
            '"warnings":[],"unparsed_fragments":[]}'
        )
    )

    result = GeminiFitnessInterpreter(client=client).interpret(
        "Walked 9000 steps",
        REFERENCE,
    )

    assert result.parsed_input.activities[0].steps == 9000


def test_naive_provider_timestamp_fails_revalidation_boundary():
    client, _ = fake_client(
        {
            "parsed_input": {
                "body_metrics": [
                    {"weight_kg": 96.2, "measured_at": "2026-07-08T08:00:00"}
                ]
            }
        }
    )

    with pytest.raises(GeminiInterpretationError, match="timezone information"):
        GeminiFitnessInterpreter(client=client).interpret("Weight 96.2 kg", REFERENCE)


def test_malformed_structured_response_fails_revalidation():
    client, _ = fake_client(
        {"parsed_input": {"activities": [{"steps": -1}]}}
    )

    with pytest.raises(GeminiInterpretationError, match="greater than or equal"):
        GeminiFitnessInterpreter(client=client).interpret("Negative steps", REFERENCE)


@pytest.mark.parametrize(
    "parsed",
    [
        {"parsed_input": {"body_metrics": [{"weight_kg": 0}]}},
        {
            "parsed_input": {
                "food_entries": [
                    {"items": [{"food_name": "rice", "quantity": -1}]}
                ]
            }
        },
    ],
)
def test_reduced_provider_schema_does_not_weaken_final_validation(parsed):
    client, _ = fake_client(parsed)

    with pytest.raises(GeminiInterpretationError):
        GeminiFitnessInterpreter(client=client).interpret(
            "Invalid value",
            REFERENCE,
        )


def test_original_pydantic_schema_retains_strict_constraints():
    assert contains_key(
        InterpretationResult.model_json_schema(),
        "exclusiveMinimum",
    )


def test_missing_api_key_fails_cleanly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(GeminiInterpretationError, match="GEMINI_API_KEY"):
        GeminiFitnessInterpreter().interpret("Walked today", REFERENCE)


def test_provider_error_is_mapped():
    client, _ = fake_client(error=RuntimeError("quota exceeded"))

    with pytest.raises(GeminiInterpretationError, match="quota exceeded"):
        GeminiFitnessInterpreter(client=client).interpret("Walked today", REFERENCE)


def test_missing_structured_response_is_mapped():
    client, _ = fake_client(parsed=None)

    with pytest.raises(GeminiInterpretationError, match="no structured interpretation"):
        GeminiFitnessInterpreter(client=client).interpret("Walked today", REFERENCE)


def test_gemini_usage_maps_to_shared_evaluator_shape():
    usage = SimpleNamespace(
        prompt_token_count=90,
        candidates_token_count=20,
        total_token_count=110,
    )
    client, _ = fake_client(activity_result(), usage=usage)
    interpreter = GeminiFitnessInterpreter(client=client)

    interpreter.interpret("Walked today", REFERENCE)

    assert interpreter.last_usage == {
        "input_tokens": 90,
        "output_tokens": 20,
        "total_tokens": 110,
    }


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


def test_mocked_gemini_ingestion_preserves_one_raw_event_and_records(
    ingestion_database,
):
    client, _ = fake_client(
        InterpretationResult(
            parsed_input={
                "body_metrics": [
                    {"weight_kg": 96.2, "time_expression": "this morning"}
                ],
                "activities": [
                    {"steps": 9000, "time_expression": "today"}
                ],
            }
        )
    )
    raw_text = "I weighed 96.2 kg this morning and walked 9000 steps today"

    result = ingestion.ingest_fitness_message(
        raw_text,
        GeminiFitnessInterpreter(client=client),
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


def test_gemini_failure_through_ingestion_preserves_failed_raw_event(
    ingestion_database,
):
    client, _ = fake_client(error=RuntimeError("Gemini unavailable"))

    result = ingestion.ingest_fitness_message(
        "Walked 9000 steps today",
        GeminiFitnessInterpreter(client=client),
        reference=REFERENCE,
    )

    with TestSession() as db:
        event = db.query(RawEvent).one()
        assert event.raw_text == "Walked 9000 steps today"
        assert event.processing_status == "failed"
        assert db.query(ActivityEntry).count() == 0
    assert result["status"] == "failed"

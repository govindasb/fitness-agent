import argparse
import json
from datetime import datetime

from agent.interpreter import (
    FitnessInterpreter,
    InterpretationResult,
    JsonInterpreter,
)
from database.connection import SessionLocal
from database.repository import (
    mark_event_failed,
    mark_event_processed,
    save_activity_entry,
    save_body_metric,
    save_exercise_set,
    save_food_entry,
    save_raw_event,
    save_sleep_entry,
    save_workout_session,
)
from models.parsed_input import ParsedInput


PARSER_VERSION = "fitness-interpreter-v1"


def _empty_stored() -> dict[str, list]:
    return {
        "body_metrics": [],
        "food_entries": [],
        "activities": [],
        "sleep_entries": [],
        "workouts": [],
    }


def _validate_interpretation(value) -> InterpretationResult:
    if isinstance(value, InterpretationResult):
        return value
    if isinstance(value, ParsedInput):
        return InterpretationResult(parsed_input=value)
    if isinstance(value, dict) and "parsed_input" in value:
        return InterpretationResult.model_validate(value)
    return InterpretationResult(
        parsed_input=ParsedInput.model_validate(value)
    )


def _event_type(parsed: ParsedInput) -> str:
    domains = [
        name
        for name, records in (
            ("body_metric", parsed.body_metrics),
            ("food", parsed.food_entries),
            ("activity", parsed.activities),
            ("sleep", parsed.sleep_entries),
            ("workout", parsed.workouts),
        )
        if records
    ]
    if not domains:
        return "unparsed"
    return domains[0] if len(domains) == 1 else "mixed"


def _event_time(parsed: ParsedInput):
    timestamps = [
        *(item.measured_at for item in parsed.body_metrics),
        *(entry.consumed_at for entry in parsed.food_entries),
        *(item.recorded_at for item in parsed.activities),
        *(item.sleep_start or item.sleep_end for item in parsed.sleep_entries),
        *(entry.started_at for entry in parsed.workouts),
    ]
    if not timestamps or any(timestamp is None for timestamp in timestamps):
        return None
    first = timestamps[0]
    return first if all(timestamp == first for timestamp in timestamps) else None


def _persist_structured(db, raw_event_id: int, parsed: ParsedInput) -> dict:
    stored = _empty_stored()

    for item in parsed.body_metrics:
        row = save_body_metric(
            db,
            source_event_id=raw_event_id,
            measured_at=item.measured_at,
            weight_kg=item.weight_kg,
            waist_cm=item.waist_cm,
            body_fat_percent=item.body_fat_percent,
            resting_heart_rate=item.resting_heart_rate,
            commit=False,
        )
        stored["body_metrics"].append({"body_metric_id": row.id})

    for entry in parsed.food_entries:
        for item in entry.items:
            row = save_food_entry(
                db,
                source_event_id=raw_event_id,
                consumed_at=entry.consumed_at,
                food_name=item.food_name,
                meal_type=entry.meal_type,
                quantity=item.quantity,
                unit=item.unit,
                estimated_calories=item.estimated_calories,
                protein_g=item.protein_g,
                carbs_g=item.carbs_g,
                fat_g=item.fat_g,
                fiber_g=item.fiber_g,
                is_estimated=item.is_estimated,
                commit=False,
            )
            stored["food_entries"].append({"food_entry_id": row.id})

    for item in parsed.activities:
        row = save_activity_entry(
            db,
            source_event_id=raw_event_id,
            recorded_at=item.recorded_at,
            steps=item.steps,
            distance_km=item.distance_km,
            active_minutes=item.active_minutes,
            calories_burned=item.calories_burned,
            commit=False,
        )
        stored["activities"].append({"activity_id": row.id})

    for item in parsed.sleep_entries:
        row = save_sleep_entry(
            db,
            source_event_id=raw_event_id,
            sleep_start=item.sleep_start,
            sleep_end=item.sleep_end,
            duration_minutes=item.duration_minutes,
            quality_rating=item.quality_rating,
            notes=item.notes,
            commit=False,
        )
        stored["sleep_entries"].append({"sleep_entry_id": row.id})

    for entry in parsed.workouts:
        workout = save_workout_session(
            db,
            source_event_id=raw_event_id,
            started_at=entry.started_at,
            workout_type=entry.workout_type,
            duration_minutes=entry.duration_minutes,
            notes=entry.notes,
            commit=False,
        )
        set_ids = []
        for item in entry.sets:
            row = save_exercise_set(
                db,
                workout_session_id=workout.id,
                exercise_name=item.exercise_name,
                set_number=item.set_number,
                weight_kg=item.weight_kg,
                reps=item.reps,
                duration_seconds=item.duration_seconds,
                distance_km=item.distance_km,
                rpe=item.rpe,
                commit=False,
            )
            set_ids.append(row.id)
        stored["workouts"].append(
            {
                "workout_session_id": workout.id,
                "exercise_set_ids": set_ids,
            }
        )

    return stored


def _failed_result(
    raw_event_id: int,
    raw_text: str,
    message: str,
    warnings: list[str] | None = None,
    unparsed_fragments: list[str] | None = None,
) -> dict:
    return {
        "raw_event_id": raw_event_id,
        "status": "failed",
        "stored": _empty_stored(),
        "warnings": [*(warnings or []), message],
        "unparsed_fragments": unparsed_fragments or [raw_text],
    }


def _mark_failed(raw_event_id: int):
    db = SessionLocal()
    try:
        mark_event_failed(
            db,
            event_id=raw_event_id,
            parser_version=PARSER_VERSION,
        )
    finally:
        db.close()


def ingest_fitness_message(
    raw_text: str,
    interpreter: FitnessInterpreter,
    reference: datetime | None = None,
) -> dict:
    db = SessionLocal()
    try:
        raw_event = save_raw_event(db, raw_text)
        raw_event_id = raw_event.id
    finally:
        db.close()

    try:
        interpretation = _validate_interpretation(
            interpreter.interpret(raw_text, reference=reference)
        )
    except Exception as exc:
        _mark_failed(raw_event_id)
        return _failed_result(
            raw_event_id,
            raw_text,
            f"Interpretation failed: {exc}",
        )

    db = SessionLocal()
    try:
        stored = _persist_structured(
            db,
            raw_event_id,
            interpretation.parsed_input,
        )
        mark_event_processed(
            db,
            event_id=raw_event_id,
            event_type=_event_type(interpretation.parsed_input),
            parser_version=PARSER_VERSION,
            event_time=_event_time(interpretation.parsed_input),
            commit=False,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        db.close()
        _mark_failed(raw_event_id)
        return _failed_result(
            raw_event_id,
            raw_text,
            f"Structured persistence failed: {exc}",
            warnings=interpretation.warnings,
            unparsed_fragments=interpretation.unparsed_fragments,
        )
    else:
        db.close()

    return {
        "raw_event_id": raw_event_id,
        "status": "processed",
        "stored": stored,
        "warnings": interpretation.warnings,
        "unparsed_fragments": interpretation.unparsed_fragments,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Persist a fitness message through the selected interpreter."
    )
    parser.add_argument("message")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--parsed-json",
        help="ParsedInput JSON; this is a deterministic demo, not AI parsing.",
    )
    modes.add_argument(
        "--openai",
        action="store_true",
        help="Interpret the message with the OpenAI Responses API.",
    )
    modes.add_argument(
        "--gemini",
        action="store_true",
        help="Interpret the message with the Gemini API.",
    )
    args = parser.parse_args()
    if args.openai:
        from agent.openai_interpreter import OpenAIFitnessInterpreter

        interpreter = OpenAIFitnessInterpreter()
    elif args.gemini:
        from agent.gemini_interpreter import GeminiFitnessInterpreter

        interpreter = GeminiFitnessInterpreter()
    else:
        interpreter = JsonInterpreter(args.parsed_json)
    result = ingest_fitness_message(
        args.message,
        interpreter,
    )
    print(json.dumps(result, indent=2))
    if result["status"] != "processed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from datetime import date, datetime
from typing import Callable

from agent.coach import FitnessCoach, generate_grounded_coaching
from agent.coaching_context import get_coaching_context
from agent.ingestion import FitnessInterpreter, ingest_fitness_message
from database.connection import SessionLocal
from models.coaching_response import CoachingResponse


class FitnessAgentService:
    """Application-facing composition of provider-neutral fitness boundaries."""

    def __init__(
        self,
        interpreter: FitnessInterpreter,
        coach: FitnessCoach,
        session_factory: Callable = SessionLocal,
    ):
        self.interpreter = interpreter
        self.coach = coach
        self.session_factory = session_factory

    def log(
        self,
        raw_text: str,
        reference: datetime | None = None,
    ) -> dict:
        """Persist a fitness message without depending on coaching availability."""
        return ingest_fitness_message(
            raw_text,
            self.interpreter,
            reference=reference,
        )

    def get_context(
        self,
        days: int = 7,
        reference: date | datetime | None = None,
    ) -> dict:
        db = self.session_factory()
        try:
            return get_coaching_context(db, days=days, reference=reference)
        finally:
            db.close()

    def get_coaching(
        self,
        days: int = 7,
        reference: date | datetime | None = None,
    ) -> CoachingResponse:
        context = self.get_context(days=days, reference=reference)
        return generate_grounded_coaching(context, self.coach)

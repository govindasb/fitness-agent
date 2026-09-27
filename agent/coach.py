from typing import Protocol

from pydantic import ValidationError

from agent.coaching_grounding import validate_coaching_response
from models.coaching_response import CoachingResponse


class FitnessCoach(Protocol):
    """Provider-neutral interface for generating structured coaching output."""

    def coach(self, context: dict) -> CoachingResponse:
        ...


class CoachingStructureError(ValueError):
    """Raised when a coach does not return a valid CoachingResponse."""

    def __init__(self, error: ValidationError):
        self.validation_error = error
        super().__init__("Coach output failed CoachingResponse validation")


class StaticCoach:
    """Deterministic coach implementation for tests and local development."""

    def __init__(self, response: CoachingResponse):
        self.response = response

    def coach(self, context: dict) -> CoachingResponse:
        return self.response


def generate_grounded_coaching(
    context: dict,
    coach: FitnessCoach,
) -> CoachingResponse:
    """Generate, structurally validate, and deterministically ground coaching."""
    try:
        response = CoachingResponse.model_validate(coach.coach(context))
    except ValidationError as error:
        raise CoachingStructureError(error) from error
    return validate_coaching_response(context, response)

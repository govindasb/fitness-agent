import json
from pathlib import Path

from models.coaching_targets import CoachingTargets


COACHING_TARGETS_PATH = Path(__file__).parent / "coaching_targets.json"


def load_coaching_targets() -> CoachingTargets:
    """Load and validate the centrally configured coaching targets."""

    with COACHING_TARGETS_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return CoachingTargets.model_validate(payload)

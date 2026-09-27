import json
from pathlib import Path


PROFILE_PATH = Path(__file__).parent / "profile.json"


def load_profile() -> dict:
    with PROFILE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)
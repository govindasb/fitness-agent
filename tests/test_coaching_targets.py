import pytest
from pydantic import ValidationError

import config.coaching_targets as coaching_config
from config.coaching_targets import load_coaching_targets
from config.profile import load_profile
from models.coaching_targets import CoachingTargets


def test_valid_configuration_loads():
    targets = load_coaching_targets()

    assert targets.model_dump() == {
        "daily_calories": 2450,
        "daily_protein_g": 170.0,
        "daily_steps": 10000,
        "strength_sessions_per_week": 4,
        "cardio_sessions_per_week": 3,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("daily_calories", 0),
        ("daily_protein_g", 0),
        ("daily_steps", -1),
        ("strength_sessions_per_week", -1),
        ("cardio_sessions_per_week", -1),
    ],
)
def test_target_values_have_sensible_validation(field, value):
    payload = load_coaching_targets().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError):
        CoachingTargets.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"daily_calories": 2450},
        {"daily_calories": "not-a-number"},
    ],
)
def test_malformed_or_missing_configuration_fails_validation(payload):
    with pytest.raises(ValidationError):
        CoachingTargets.model_validate(payload)


def test_malformed_configuration_file_fails_clearly(tmp_path, monkeypatch):
    path = tmp_path / "coaching_targets.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(coaching_config, "COACHING_TARGETS_PATH", path)

    with pytest.raises(ValueError):
        load_coaching_targets()


def test_missing_configuration_file_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(
        coaching_config, "COACHING_TARGETS_PATH", tmp_path / "missing.json"
    )

    with pytest.raises(FileNotFoundError):
        load_coaching_targets()


def test_profile_configuration_remains_separate_and_unchanged():
    profile = load_profile()
    targets = load_coaching_targets()

    assert profile["goal"] == "fat_loss"
    assert "daily_calories" not in profile
    assert "daily_protein_g" not in profile
    assert targets.daily_calories == 2450

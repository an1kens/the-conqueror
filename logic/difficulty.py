"""Difficulty presets merged into scenario config at game start."""

from __future__ import annotations

from logic.balance_config import load_tuning

PRESETS: dict[str, dict] = {
    "easy": {
        "win_control_percent": 0.55,
        "us_mil_aid": 5,
        "us_eco_aid": 3,
        "us_battle_bonus": 1.15,
        "ai_rate_mult": 0.85,
        "axis_response_chance": 0.6,
        "ceasefire_foe_rebuild": 3,
    },
    "normal": {
        "win_control_percent": 0.65,
        "us_mil_aid": 3,
        "us_eco_aid": 2,
        "us_battle_bonus": 1.1,
        "ai_rate_mult": 1.0,
        "axis_response_chance": 0.75,
        "ceasefire_foe_rebuild": 4,
    },
    "hard": {
        "win_control_percent": 0.70,
        "us_mil_aid": 2,
        "us_eco_aid": 1,
        "us_battle_bonus": 1.05,
        "ai_rate_mult": 1.15,
        "axis_response_chance": 0.85,
        "ceasefire_foe_rebuild": 6,
    },
}

DEFAULT_DIFFICULTY = "normal"
DEFAULT_SCENARIO_ID = "global"

# Global has 63 contestable territories — lower control % and cap weekly AI noise.
SCENARIO_PRESETS: dict[str, dict[str, dict]] = {
    "global": {
        "easy": {
            "win_control_percent": 0.38,
            "ai_rate_mult": 0.70,
            "max_ai_actions_per_week": 10,
        },
        "normal": {
            "win_control_percent": 0.42,
            "ai_rate_mult": 0.78,
            "max_ai_actions_per_week": 12,
        },
        "hard": {
            "win_control_percent": 0.48,
            "ai_rate_mult": 0.90,
            "max_ai_actions_per_week": 16,
        },
    },
}

SCENARIO_LABELS = {
    "global": "Global Conquest (21 powers)",
    "south_asia": "South Asia Flashpoint",
}


def win_control_percent_for(
    difficulty: str = DEFAULT_DIFFICULTY,
    *,
    scenario_id: str = DEFAULT_SCENARIO_ID,
) -> float:
    """Win threshold shown in UI and applied at game start (per difficulty preset)."""
    scenario_overrides = SCENARIO_PRESETS.get(scenario_id, {}).get(difficulty)
    if scenario_overrides and "win_control_percent" in scenario_overrides:
        return float(scenario_overrides["win_control_percent"])
    return float(PRESETS.get(difficulty, PRESETS[DEFAULT_DIFFICULTY])["win_control_percent"])


def apply_difficulty(scenario: dict, difficulty: str = DEFAULT_DIFFICULTY) -> dict:
    """Merge preset into scenario dict; normal still picks up live AI/US tuning."""
    preset = dict(PRESETS.get(difficulty, PRESETS[DEFAULT_DIFFICULTY]))
    tuning = scenario.get("balance_tuning") or load_tuning()
    if difficulty == DEFAULT_DIFFICULTY:
        preset["us_mil_aid"] = tuning["us_support"]["mil_aid"]
        preset["us_eco_aid"] = tuning["us_support"]["eco_aid"]
        preset["us_battle_bonus"] = tuning["us_support"]["battle_bonus"]
        preset["axis_response_chance"] = tuning["ai"]["axis_response_chance"]
    scenario_id = scenario.get("id", DEFAULT_SCENARIO_ID)
    scenario_overrides = SCENARIO_PRESETS.get(scenario_id, {}).get(difficulty, {})
    preset.update(scenario_overrides)
    scenario = dict(scenario)
    scenario["difficulty"] = difficulty
    for key, value in preset.items():
        scenario[key] = value
    return scenario


def apply_difficulty_overlay(scenario: dict) -> dict:
    """Re-apply difficulty preset after balance tuning is attached."""
    return apply_difficulty(
        scenario, scenario.get("difficulty", DEFAULT_DIFFICULTY)
    )

"""Load analyst-adjustable balance knobs (merged into scenario at runtime)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
TUNING_PATH = SCENARIOS_DIR / "balance_tuning.json"

_DEFAULTS: dict | None = None


def _default_tuning() -> dict:
    return {
        "version": 1,
        "updated_at": None,
        "updated_by": "defaults",
        "notes": [],
        "scenario": {"win_control_percent": 0.65},
        "us_support": {
            "mil_aid": 3,
            "eco_aid": 2,
            "battle_bonus": 1.1,
            "aid_interval_weeks": 2,
        },
        "battle": {
            "defender_home_bonus": 1.12,
            "wartime_attrition_mult": 1.35,
        },
        "invasion": {"min_military_at_war": 45},
        "ai": {
            "rival_boost_pakistan": 0.55,
            "rival_boost_china": 0.58,
            "axis_response_chance": 0.75,
        },
    }


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_tuning(*, reload: bool = False) -> dict:
    global _DEFAULTS
    if _DEFAULTS is not None and not reload:
        return _DEFAULTS

    base = _default_tuning()
    if TUNING_PATH.exists():
        with open(TUNING_PATH) as f:
            on_disk = json.load(f)
        base = _deep_merge(base, on_disk)
    _DEFAULTS = base
    return base


def apply_tuning_to_scenario(scenario: dict) -> dict:
    tuning = load_tuning()
    scenario = dict(scenario)
    scenario["balance_tuning"] = tuning
    us = tuning["us_support"]
    scenario.setdefault("us_mil_aid", us["mil_aid"])
    scenario.setdefault("us_eco_aid", us["eco_aid"])
    scenario.setdefault("us_battle_bonus", us["battle_bonus"])
    return scenario


def save_tuning(tuning: dict) -> None:
    global _DEFAULTS
    TUNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TUNING_PATH, "w") as f:
        json.dump(tuning, f, indent=2)
        f.write("\n")
    _DEFAULTS = None
    load_tuning(reload=True)


def get(section: str, key: str, default=None):
    return load_tuning().get(section, {}).get(key, default)

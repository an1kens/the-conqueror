"""Apply bounded tuning adjustments from analyst recommendations."""

from __future__ import annotations

from datetime import datetime, timezone

from analyst.recommender import analyze
from logic.balance_config import load_tuning, save_tuning

BOUNDS = {
    "scenario": {
        "win_control_percent": (0.55, 0.78),
    },
    "us_support": {
        "mil_aid": (1, 6),
        "eco_aid": (0, 4),
        "battle_bonus": (1.0, 1.25),
        "aid_interval_weeks": (1, 4),
    },
    "battle": {
        "defender_home_bonus": (1.0, 1.3),
        "wartime_attrition_mult": (1.0, 1.7),
    },
    "invasion": {
        "min_military_at_war": (35, 60),
    },
    "ai": {
        "rival_boost_pakistan": (0.35, 0.8),
        "rival_boost_china": (0.35, 0.8),
        "axis_response_chance": (0.4, 0.95),
    },
}


def _clamp(section: str, key: str, value):
    lo, hi = BOUNDS[section][key]
    if isinstance(value, float) and key != "aid_interval_weeks":
        return max(lo, min(hi, round(value, 2)))
    if key == "aid_interval_weeks":
        return int(max(lo, min(hi, round(value))))
    return max(lo, min(hi, value))


def apply_analysis(*, dry_run: bool = False) -> dict:
    result = analyze()
    if result["status"] == "no_data":
        return {"applied": False, "analysis": result}

    tuning = load_tuning(reload=True)
    changes: list[str] = []

    for section, keys in result.get("tuning_adjustments", {}).items():
        if section not in tuning:
            tuning[section] = {}
        for key, new_val in keys.items():
            if key not in BOUNDS.get(section, {}):
                continue
            old_val = tuning[section].get(key)
            clamped = _clamp(section, key, new_val)
            if old_val != clamped:
                changes.append(f"{section}.{key}: {old_val} → {clamped}")
                tuning[section][key] = clamped

    if not changes:
        return {"applied": False, "analysis": result, "changes": []}

    tuning["updated_at"] = datetime.now(timezone.utc).isoformat()
    tuning["updated_by"] = "vision_analyst"
    note = (
        f"Auto-tune from {result['metrics']['session_count']} sessions: "
        + "; ".join(c["issue"] for c in result["recommendations"][:3])
    )
    tuning.setdefault("notes", []).append(note)
    tuning["notes"] = tuning["notes"][-12:]

    if not dry_run:
        save_tuning(tuning)

    return {"applied": not dry_run, "analysis": result, "changes": changes, "tuning": tuning}

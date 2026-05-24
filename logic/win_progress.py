"""Victory progress helpers for UI."""

from __future__ import annotations

import math

from state.game_state import GameState


def win_progress(state: GameState) -> dict:
    """
    Return territory counts toward map-control victory.
    Elimination wins are handled separately in the simulation.
    """
    player = state.player_country or ""
    contestable = state.contestable_territories()
    total = len(contestable)
    owned = len(state.territories_controlled_by(player) & contestable)
    threshold = float(state.scenario.get("win_control_percent", 0.65))
    needed = math.ceil(total * threshold) if total else 0
    remaining = max(0, needed - owned)
    pct = int(state.control_percent(player) * 100) if player else 0
    threshold_pct = int(threshold * 100)
    return {
        "owned": owned,
        "needed": needed,
        "total": total,
        "remaining": remaining,
        "control_percent": pct,
        "threshold_percent": threshold_pct,
    }


def format_win_progress_line(state: GameState) -> str:
    p = win_progress(state)
    if p["total"] == 0:
        return "No contestable territory"
    scope = (
        "world"
        if state.scenario.get("geo_scope") == "world"
        or state.scenario.get("id") == "global"
        else "map"
    )
    return (
        f"{p['owned']}/{p['total']} territories ({scope}) · need {p['needed']} for "
        f"{p['threshold_percent']}% win"
        + (f" ({p['remaining']} more)" if p["remaining"] else " — threshold met")
    )

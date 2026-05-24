"""Player-facing defeat and victory summaries."""

from __future__ import annotations

from logic.economy import MIN_STABILITY_TO_INVADE, invasion_stability_ok
from logic.relationships import HOSTILE_MAX, WAR_MAX, get_relationship, relationship_band
from state.game_state import GameState


def build_defeat_summary(state: GameState) -> tuple[str, str, str]:
    """Return (title, body, impact) for journal."""
    player = state.player_country or ""
    p = state.get(player) if player else None
    reasons: list[str] = []
    if not p:
        return "Why you lost", "No player nation.", "Start a new game."

    losses = [
        (terr, foe)
        for terr, foe in getattr(state, "territories_lost_this_week", [])
    ]
    if losses:
        by_foe: dict[str, list[str]] = {}
        for terr, foe in losses:
            by_foe.setdefault(foe, []).append(terr)
        parts = [f"{foe} took {', '.join(ts)}" for foe, ts in by_foe.items()]
        reasons.append("Territory lost: " + "; ".join(parts))
    else:
        owners = state.territory_owner()
        rivals = state.scenario.get("primary_rivals", ())
        for foe in rivals:
            if foe in state.eliminated_countries:
                continue
            held = [t for t in state.contestable_territories() if owners.get(t) == foe]
            if held:
                sample = ", ".join(held[:3]) + ("…" if len(held) > 3 else "")
                reasons.append(f"{foe} holds {len(held)} region(s) ({sample})")

    if not invasion_stability_ok(p):
        reasons.append(
            f"Stability {p.stability} — below {MIN_STABILITY_TO_INVADE} needed to invade"
        )

    rivals = state.scenario.get("primary_rivals", ("Pakistan", "China"))
    at_war = []
    for foe in rivals:
        if foe in state.eliminated_countries:
            continue
        if get_relationship(p, foe) <= WAR_MAX:
            at_war.append(foe)
    if len(at_war) >= 2:
        alive = [
            f
            for f in rivals
            if f not in state.eliminated_countries and state.get(f).territories
        ]
        if len(alive) >= 2:
            reasons.append(
                f"Multi-front war — {', '.join(alive)} still hold territory"
            )

    if not reasons:
        reasons.append("All contestable territory lost")

    body = ". ".join(reasons)
    title = "Why you lost"
    impact = "Rebuild a new strategy: one front at a time, watch stability"
    return title, body, impact


def build_victory_summary(state: GameState) -> tuple[str, str, str]:
    player = state.player_country or ""
    p = state.get(player)
    control = state.control_percent(player)
    title = "Victory"
    body = (
        f"You control {control:.0%} of the region "
        f"({len(p.territories)} territories)."
    )
    impact = f"Conquests this campaign: {state.player_conquests}"
    return title, body, impact

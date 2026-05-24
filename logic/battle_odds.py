"""Deterministic invasion odds estimate (mirrors battle.py without RNG rolls)."""

from __future__ import annotations

import math

from country import Country
from logic.balance_config import load_tuning
from logic.relationships import WAR_MAX, get_relationship
from logic.us_support import battle_bonus_if_us_allied
from state.game_state import GameState


def _defender_power(defender: Country, territory: str) -> float:
    cfg = load_tuning()["battle"]
    power = float(defender.military_strength)
    if territory in defender.territories:
        power *= float(cfg["defender_home_bonus"])
    return power


def estimate_invasion_win_percent(
    attacker: Country,
    defender: Country,
    state: GameState,
    *,
    territory: str | None = None,
    intensity: float = 1.0,
) -> int:
    """
    Approximate chance attacker wins the power comparison in resolve_battle.
    Uses expected uniform factors (1.0) — actual battles still roll RNG.
    """
    territory = territory or (defender.territories[0] if defender.territories else defender.capital)
    atk_power = float(attacker.military_strength) * intensity
    atk_power *= battle_bonus_if_us_allied(state, attacker.name)
    def_power = _defender_power(defender, territory)
    if def_power <= 0:
        return 95
    threshold = def_power * 0.95
    margin = (atk_power - threshold) / threshold
    pct = int(50 + 42 * math.tanh(margin * 2.2))
    return max(8, min(92, pct))


def invasion_odds_label(percent: int) -> str:
    if percent >= 68:
        return "Favorable"
    if percent >= 52:
        return "Slight edge"
    if percent >= 38:
        return "Risky"
    return "Unfavorable"


def format_invasion_odds(
    attacker: Country,
    defender: Country,
    state: GameState,
    *,
    territory: str | None = None,
) -> str | None:
    """Human-readable odds line for UI, or None if invasion not applicable."""
    territory = territory or (defender.territories[0] if defender.territories else None)
    if not territory:
        return None
    rel = get_relationship(attacker, defender.name)
    if defender.nuclear and rel > WAR_MAX:
        return "Invade locked — pressure until at war"
    pct = estimate_invasion_win_percent(
        attacker, defender, state, territory=territory
    )
    label = invasion_odds_label(pct)
    return f"Invade odds ~{pct}% ({label}) — RNG still applies"

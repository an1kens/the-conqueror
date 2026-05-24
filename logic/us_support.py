"""Alliance support — multiple friendly allies, aid scaled by ally military strength."""

import random

from logic.balance_config import load_tuning
from logic.relationships import ALLIED_MIN, HOSTILE_MAX, WAR_MAX, get_relationship

SANCTION_MIL_PENALTY_ECONOMY_MAX = 20
SANCTION_MIL_PENALTY = 2


def _us_cfg(scenario: dict) -> dict:
    tuning = scenario.get("balance_tuning") or load_tuning()
    us = tuning["us_support"]
    return {
        "mil_aid": int(scenario.get("us_mil_aid", us["mil_aid"])),
        "eco_aid": int(scenario.get("us_eco_aid", us["eco_aid"])),
        "battle_bonus": float(scenario.get("us_battle_bonus", us["battle_bonus"])),
        "aid_interval_weeks": int(us["aid_interval_weeks"]),
    }


def allied_partners(state, player_name: str | None = None) -> list:
    """Countries at 80+ relations with the player (full military aid eligible)."""
    player_name = player_name or state.player_country
    if not player_name:
        return []
    player = state.get(player_name)
    partners = []
    for country in state.countries:
        if country.name == player_name:
            continue
        if country.name in state.eliminated_countries:
            continue
        if get_relationship(player, country.name) >= ALLIED_MIN:
            partners.append(country)
    return partners


def india_us_allied(state) -> bool:
    """True if the player has at least one full alliance (80+)."""
    return bool(allied_partners(state))


def _player_at_war(state) -> list[str]:
    """Countries the player is openly at war with."""
    player = state.player_country
    if not player:
        return []
    p = state.get(player)
    foes = []
    for country in state.countries:
        if country.name == player:
            continue
        if country.name in state.eliminated_countries:
            continue
        if get_relationship(p, country.name) <= WAR_MAX:
            foes.append(country.name)
    return foes


def _aid_scale(ally_military: int) -> float:
    return max(0.35, min(1.0, ally_military / 100.0))


def battle_bonus_if_us_allied(state, attacker_name: str) -> float:
    if attacker_name != state.player_country:
        return 1.0
    cfg = _us_cfg(state.scenario)
    base_bonus = float(cfg["battle_bonus"])
    best = 1.0
    for ally in allied_partners(state):
        extra = (base_bonus - 1.0) * _aid_scale(ally.military_strength)
        best = max(best, 1.0 + extra)
    return best


def apply_us_weekly_support(simulation) -> list[str]:
    """Biweekly aid from each allied partner (80+) while player is at war."""
    state = simulation.state
    player_name = state.player_country
    if not player_name:
        return []

    foes = _player_at_war(state)
    if not foes:
        return []

    allies = allied_partners(state)
    if not allies:
        return []

    cfg = _us_cfg(state.scenario)
    interval = int(cfg["aid_interval_weeks"])
    if state.turn_number % interval != 0:
        return []

    player = state.get(player_name)
    headlines = []
    base_mil = cfg["mil_aid"]
    base_eco = cfg["eco_aid"]

    for ally in allies:
        scale = _aid_scale(ally.military_strength)
        mil_aid = max(1, int(base_mil * scale))
        eco_aid = max(1, int(base_eco * scale))
        mil_before = player.military_strength
        player.military_strength = min(100, player.military_strength + mil_aid)
        player.economic_power = min(100, player.economic_power + eco_aid)
        state.record_journal(
            "usa",
            f"{ally.name} military aid",
            f"Shipments from {ally.name} (military {ally.military_strength}).",
            impact=f"Military {mil_before} → {player.military_strength}, "
            f"economy → {player.economic_power}",
        )
        headlines.append(f"{ally.name} aid")

    if foes and allies and random.random() < 0.5:
        ally = random.choice(allies)
        target_name = random.choice(foes)
        from logic.focused_events import _resolve_focused_sanction

        foe = state.get(target_name)
        _resolve_focused_sanction(ally, foe, state, 0.9)
        state.record_journal(
            "usa",
            f"{ally.name} pressured {target_name}",
            f"{ally.name} sanctioned your enemy in support of the alliance.",
            impact=f"{target_name} economy {foe.economic_power}",
        )
        headlines.append(f"{ally.name} vs {target_name}")

    if random.random() < 0.25:
        ally = random.choice(allies)
        state.record_journal(
            "usa",
            f"{ally.name} diplomatic backing",
            "UN statements backed your position. Your stability +2.",
        )
        player.stability = min(100, player.stability + 2)
        headlines.append("UN backing")

    return headlines

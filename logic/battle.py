"""Battle resolution with quantitative casualties on both sides."""

import random

from country import Country
from logic.balance_config import load_tuning
from logic.economy import (
    apply_battle_stability_loss,
    clamp_military_to_economy,
    stability_attrition_multiplier,
)
from logic.war import BattleReport, declare_war, find_war


def _battle_cfg() -> dict:
    return load_tuning()["battle"]


def _casualty_scale(country: Country, military_loss: int) -> int:
    """Estimate personnel casualties (thousands) from abstract military loss."""
    base = country.population * 0.15
    return max(100, int(base * (military_loss / 100) * random.uniform(0.6, 1.4)))


def _defender_power(defender: Country, territory: str) -> float:
    cfg = _battle_cfg()
    power = defender.military_strength * random.uniform(0.85, 1.15)
    if territory in defender.territories:
        power *= float(cfg["defender_home_bonus"])
    return power


def resolve_battle(
    attacker: Country,
    defender: Country,
    state,
    *,
    intensity: float = 1.0,
    territory: str | None = None,
    at_war: bool = False,
) -> BattleReport:
    """Fight over a territory; may transfer control. No stat floors in focused mode."""
    territory = territory or (defender.territories[0] if defender.territories else defender.capital)
    turn = state.turn_number

    atk_power = attacker.military_strength * intensity * random.uniform(0.85, 1.15)
    def_power = _defender_power(defender, territory)
    attacker_wins = atk_power > def_power * 0.95

    loss_mult = float(_battle_cfg()["wartime_attrition_mult"]) if at_war else 1.0
    if attacker_wins:
        atk_mil_loss = max(3, int(5 * intensity * loss_mult))
        def_mil_loss = max(6, int(12 * intensity * loss_mult))
    else:
        atk_mil_loss = max(6, int(13 * intensity * loss_mult))
        def_mil_loss = max(3, int(5 * intensity * loss_mult))

    attacker.military_strength = max(0, attacker.military_strength - atk_mil_loss)
    defender.military_strength = max(0, defender.military_strength - def_mil_loss)
    stab_mult = 1.25 if at_war else 1.0
    atk_stab_mult = stability_attrition_multiplier(attacker.stability)
    def_stab_mult = stability_attrition_multiplier(defender.stability)
    apply_battle_stability_loss(
        attacker, int(4 * intensity * stab_mult * atk_stab_mult), state
    )
    apply_battle_stability_loss(
        defender, int(7 * intensity * stab_mult * def_stab_mult), state
    )
    clamp_military_to_economy(attacker)
    clamp_military_to_economy(defender)

    atk_cas = _casualty_scale(attacker, atk_mil_loss)
    def_cas = _casualty_scale(defender, def_mil_loss)

    war = find_war(state.active_wars, attacker.name, defender.name)
    if not war:
        war = declare_war(state.active_wars, attacker.name, defender.name, turn)
    war.add_casualties(attacker.name, atk_cas)
    war.add_casualties(defender.name, def_cas)

    territory_changed = False
    holder = defender.name
    if attacker_wins and territory in defender.territories:
        defender.territories.remove(territory)
        attacker.territories.append(territory)
        territory_changed = True
        holder = attacker.name
        if defender.name == state.player_country:
            state.territories_lost_this_week.append((territory, attacker.name))
        if attacker.name == state.player_country:
            state.player_conquests += 1

    outcome = "captured" if territory_changed else "held"
    summary = (
        f"Battle for {territory} (Week {turn}): {attacker.name} vs {defender.name}. "
        f"{attacker.name} lost {atk_cas:,} ({atk_mil_loss} military). "
        f"{defender.name} lost {def_cas:,} ({def_mil_loss} military). "
        f"{holder} {outcome} {territory}."
    )

    return BattleReport(
        turn=turn,
        attacker=attacker.name,
        defender=defender.name,
        territory=territory,
        attacker_casualties=atk_cas,
        defender_casualties=def_cas,
        attacker_loss_military=atk_mil_loss,
        defender_loss_military=def_mil_loss,
        territory_changed=territory_changed,
        holder_after=holder,
        summary=summary,
    )

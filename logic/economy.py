"""Economy and stability influence recovery caps and battle attrition."""

from country import Country

COLLAPSED_ECONOMY_MIL_CAP = 50
LOW_ECONOMY_MIL_CAP_BASE = 55
MIN_STABILITY_TO_INVADE = 25
MAX_STABILITY_LOSS_PER_WEEK = 15


def peacetime_military_recovery(economic_power: int) -> int:
    if economic_power >= 70:
        return 4
    if economic_power >= 50:
        return 3
    if economic_power >= 30:
        return 2
    return 1


def wartime_military_recovery(economic_power: int) -> int:
    if economic_power >= 50:
        return 2
    if economic_power >= 25:
        return 1
    return 0


def military_cap(country: Country) -> int:
    eco = country.economic_power
    if eco <= 0:
        return COLLAPSED_ECONOMY_MIL_CAP
    if eco < 20:
        return min(100, LOW_ECONOMY_MIL_CAP_BASE + eco)
    return 100


def clamp_military_to_economy(country: Country) -> int:
    """Pull military down to economy-linked cap. Returns amount reduced."""
    cap = military_cap(country)
    before = country.military_strength
    if before > cap:
        country.military_strength = cap
    return before - country.military_strength


def stability_attrition_multiplier(stability: int) -> float:
    """Low stability increases battle stability losses."""
    return 1.0 + max(0, (55 - stability)) / 80.0


def invasion_stability_ok(country: Country) -> bool:
    return country.stability >= MIN_STABILITY_TO_INVADE


def apply_battle_stability_loss(country: Country, raw_loss: int, state) -> int:
    """Apply stability loss; cap total player loss per week. Returns actual loss."""
    raw_loss = max(0, int(raw_loss))
    if raw_loss == 0:
        return 0
    player = getattr(state, "player_country", None)
    if player and country.name == player:
        spent = getattr(state, "player_stability_loss_this_week", 0)
        room = max(0, MAX_STABILITY_LOSS_PER_WEEK - spent)
        actual = min(raw_loss, room)
        state.player_stability_loss_this_week = spent + actual
        country.stability = max(0, country.stability - actual)
        return actual
    country.stability = max(0, country.stability - raw_loss)
    return raw_loss


def collapsed_economy(country: Country) -> bool:
    return country.economic_power <= 0

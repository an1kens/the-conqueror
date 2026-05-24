from country import Country
from logic.balance_config import load_tuning
from state.game_state import GameState

ALLIED_MIN = 80
TRANSITION_DURATIONS = {
    "alliance_formed": 3,
    "war_declared": 3,
}
FRIENDLY_MIN = 40
HOSTILE_MAX = -40
WAR_MAX = -80


def detect_transition(old_score: int, new_score: int) -> str | None:
    old_band = relationship_band(old_score)
    new_band = relationship_band(new_score)
    if old_band != "allied" and new_band == "allied" and new_score >= ALLIED_MIN:
        return "alliance_formed"
    if old_band != "at_war" and new_band == "at_war" and new_score <= WAR_MAX:
        return "war_declared"
    return None


def relationship_band(score: int) -> str:
    if score >= ALLIED_MIN:
        return "allied"
    if score >= FRIENDLY_MIN:
        return "friendly"
    if score <= WAR_MAX:
        return "at_war"
    if score <= HOSTILE_MAX:
        return "hostile"
    return "neutral"


def get_relationship(country: Country, other_name: str) -> int:
    return country.relationships.get(other_name, 0)


def set_relationship(a: Country, b_name: str, score: int, b: Country | None = None) -> int:
    score = max(-100, min(100, score))
    a.relationships[b_name] = score
    if b is not None:
        b.relationships[a.name] = score
    return score


def _queue_transition(state: GameState | None, a: Country, b: Country, old_score: int, new_score: int) -> None:
    if state is None:
        return
    transition = detect_transition(old_score, new_score)
    if transition:
        state.pending_diplomatic.append((transition, a.name, b.name))


def adjust_relationship(
    a: Country,
    b_name: str,
    delta: int,
    b: Country | None = None,
    state: GameState | None = None,
) -> int:
    old_score = get_relationship(a, b_name)
    new_score = set_relationship(a, b_name, old_score + delta, b)
    if b is not None:
        _queue_transition(state, a, b, old_score, new_score)
    return new_score


def can_invade(
    attacker: Country, target: Country, *, scenario: dict | None = None
) -> bool:
    """Nuclear powers require war; hostile non-nuclear may be invaded without war."""
    rel = get_relationship(attacker, target.name)
    at_war = rel <= WAR_MAX
    if target.nuclear and not at_war:
        return False
    if at_war:
        tuning = (scenario or {}).get("balance_tuning") or load_tuning()
        floor = int(tuning["invasion"]["min_military_at_war"])
        return attacker.military_strength >= floor
    if target.nuclear:
        return False
    if rel > HOSTILE_MAX:
        return False
    return attacker.military_strength > target.military_strength + 20

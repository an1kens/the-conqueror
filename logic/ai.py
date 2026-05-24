import random
from dataclasses import dataclass

from country import Country
from logic.events import create_event
from logic.relationships import WAR_MAX, can_invade, get_relationship, relationship_band
from state.game_state import GameState

PERSONALITY_ACTIONS = {
    "aggressive": ["attack", "sanction", "attack"],
    "diplomatic": ["negotiate", "ally", "negotiate"],
    "opportunistic": ["negotiate", "attack", "sanction", "ally"],
    "defensive": ["negotiate", "ally", "negotiate"],
    "isolationist": ["negotiate", "sanction"],
}


@dataclass
class AIDecision:
    event_type: str
    target: str
    intensity: float
    reactive: bool = False


def pick_targets(country: Country, state: GameState, action: str) -> list[str]:
    others = [
        c
        for c in state.countries
        if c.name != country.name
        and c.name not in getattr(state, "eliminated_countries", set())
        and (action != "attack" or c.territories)
    ]
    if action in ("attack", "sanction"):
        hostile = [
            c.name
            for c in others
            if get_relationship(country, c.name) <= -20
        ]
        if hostile:
            return hostile
        return [
            c.name
            for c in others
            if relationship_band(get_relationship(country, c.name)) != "allied"
        ]
    if action in ("negotiate", "ally"):
        friendly = [
            c.name
            for c in others
            if get_relationship(country, c.name) >= 20
        ]
        if friendly:
            return friendly
        return [c.name for c in others]
    return [c.name for c in others]


def rational_action(country: Country, state: GameState) -> str:
    personality = country.personality_type
    options = PERSONALITY_ACTIONS.get(personality, ["negotiate"])
    at_war = [
        c.name
        for c in state.countries
        if c.name != country.name and get_relationship(country, c.name) <= WAR_MAX
    ]
    if at_war and personality in ("aggressive", "opportunistic", "defensive"):
        return "attack"
    if personality == "diplomatic" and country.stability < 50:
        return "negotiate"
    return options[0]


def apply_volatility(country: Country, base_intensity: float) -> float:
    """High volatility pushes intensity toward extremes."""
    roll = random.random()
    if roll < country.volatility:
        return min(2.0, base_intensity * (1.0 + country.volatility))
    return base_intensity


def choose_proactive_action(country: Country, state: GameState) -> AIDecision | None:
    action = rational_action(country, state)
    if action == "attack":
        candidates = [
            state.get(name)
            for name in pick_targets(country, state, action)
            if can_invade(country, state.get(name))
        ]
        if not candidates:
            action = "sanction"
        else:
            target_name = random.choice([c.name for c in candidates])
            intensity = apply_volatility(country, 1.0)
            return AIDecision(action, target_name, intensity, reactive=False)
    targets = pick_targets(country, state, action)
    if not targets:
        return None
    target_name = random.choice(targets)
    intensity = apply_volatility(country, 1.0)
    return AIDecision(action, target_name, intensity, reactive=False)


def choose_reactive_action(country: Country, state: GameState, provoker: str, provocation: str) -> AIDecision:
    intensity = apply_volatility(country, 1.2)
    if provocation in ("attack", "sanction"):
        if country.personality_type in ("aggressive", "opportunistic") and can_invade(
            country, state.get(provoker)
        ):
            return AIDecision("attack", provoker, intensity, reactive=True)
        return AIDecision("sanction", provoker, intensity, reactive=True)
    return AIDecision("negotiate", provoker, intensity * 0.5, reactive=True)


def decision_to_event(decision: AIDecision, source_name: str):
    return create_event(
        decision.event_type,
        source_name,
        decision.target,
        intensity=decision.intensity,
        reactive=decision.reactive,
    )

from dataclasses import dataclass, field
from typing import Callable

from country import Country
from logic.relationships import TRANSITION_DURATIONS, adjust_relationship, relationship_band
from state.game_state import GameState

EVENT_DURATIONS = {
    "attack": 5,
    "negotiate": 10,
    "sanction": 7,
    "ally": 12,
    **TRANSITION_DURATIONS,
}

STAT_FLOOR = 15
MIN_TERRITORIES = 1


@dataclass
class GameEvent:
    event_type: str
    source: str
    target: str
    days_remaining: float
    intensity: float = 1.0
    reactive: bool = False
    metadata: dict = field(default_factory=dict)


class EventQueue:
    def __init__(self):
        self.events: list[GameEvent] = []

    def enqueue(self, event: GameEvent) -> None:
        self.events.append(event)

    def tick(self, game_days: float, state: GameState, on_resolve: Callable[[GameEvent, GameState], None]) -> None:
        still_active = []
        for event in self.events:
            event.days_remaining -= game_days
            if event.days_remaining <= 0:
                on_resolve(event, state)
            else:
                still_active.append(event)
        self.events = still_active


def create_event(
    event_type: str,
    source: str,
    target: str,
    intensity: float = 1.0,
    reactive: bool = False,
    duration: float | None = None,
) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        source=source,
        target=target,
        days_remaining=duration or EVENT_DURATIONS.get(event_type, 5),
        intensity=intensity,
        reactive=reactive,
    )


def resolve_event(event: GameEvent, state: GameState) -> None:
    source = state.get(event.source)
    target = state.get(event.target)
    intensity = event.intensity

    if event.event_type == "attack":
        _resolve_attack(source, target, state, intensity)
    elif event.event_type == "negotiate":
        _resolve_negotiate(source, target, state, intensity)
    elif event.event_type == "sanction":
        _resolve_sanction(source, target, state, intensity)
    elif event.event_type == "ally":
        _resolve_ally(source, target, state, intensity)
    elif event.event_type == "alliance_formed":
        _resolve_alliance_formed(source, target, state)
    elif event.event_type == "war_declared":
        _resolve_war_declared(source, target, state)


def _clamp_stats(country: Country) -> None:
    country.military_strength = max(STAT_FLOOR, country.military_strength)
    country.economic_power = max(STAT_FLOOR, country.economic_power)
    country.stability = max(STAT_FLOOR, country.stability)
    if not country.territories:
        country.territories = [country.capital]


def _record_conquest(state: GameState, conqueror: Country, victim: Country, territory: str) -> None:
    if conqueror.name == state.player_country:
        state.player_conquests += 1
    if len(victim.territories) <= MIN_TERRITORIES:
        state.defeated_countries.add(victim.name)


def _resolve_attack(source: Country, target: Country, state: GameState, intensity: float) -> None:
    rel_drop = int(15 * intensity)
    adjust_relationship(source, target.name, -rel_drop, target, state=state)
    target.military_strength = max(STAT_FLOOR, target.military_strength - int(5 * intensity))
    target.stability = max(STAT_FLOOR, target.stability - int(8 * intensity))
    source.military_strength = max(STAT_FLOOR, source.military_strength - int(2 * intensity))

    if (
        target.stability < 20
        and source.territories
        and len(target.territories) > MIN_TERRITORIES
    ):
        conquered = target.territories.pop(0)
        source.territories.append(conquered)
        _record_conquest(state, source, target, conquered)
        state.log(f"{source.name} seized {conquered} from {target.name}")

    _clamp_stats(target)
    _clamp_stats(source)
    state.log(
        f"{source.name} attack on {target.name} resolved "
        f"(relations: {relationship_band(target.relationships[source.name])})"
    )


def _resolve_negotiate(source: Country, target: Country, state: GameState, intensity: float) -> None:
    gain = int(12 * intensity)
    adjust_relationship(source, target.name, gain, target, state=state)
    source.economic_power = min(100, source.economic_power + 1)
    state.log(f"{source.name} improved relations with {target.name} (+{gain})")


def _resolve_sanction(source: Country, target: Country, state: GameState, intensity: float) -> None:
    drop = int(10 * intensity)
    adjust_relationship(source, target.name, -drop, target, state=state)
    target.economic_power = max(STAT_FLOOR, target.economic_power - int(6 * intensity))
    target.stability = max(STAT_FLOOR, target.stability - int(4 * intensity))
    _clamp_stats(target)
    state.log(f"{source.name} sanctions against {target.name} took effect")


def _resolve_ally(source: Country, target: Country, state: GameState, intensity: float) -> None:
    gain = int(20 * intensity)
    adjust_relationship(source, target.name, gain, target, state=state)
    band = relationship_band(target.relationships[source.name])
    if band == "allied":
        state.log(f"{source.name} and {target.name} are allied")
    else:
        state.log(f"{source.name} moved closer to alliance with {target.name}")


def _resolve_alliance_formed(source: Country, target: Country, state: GameState) -> None:
    source.stability = min(100, source.stability + 5)
    target.stability = min(100, target.stability + 5)
    state.log(
        f"ALLIANCE: {source.name} and {target.name} are now allied "
        f"(+5 stability each)"
    )


def _resolve_war_declared(source: Country, target: Country, state: GameState) -> None:
    source.military_strength = min(100, source.military_strength + 3)
    target.military_strength = min(100, target.military_strength + 3)
    state.log(
        f"WAR DECLARED: {source.name} and {target.name} are at war "
        f"(+3 military readiness each)"
    )

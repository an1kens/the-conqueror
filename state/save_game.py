"""Save and load focused scenario games."""

from __future__ import annotations

import json
from pathlib import Path

from country import Country
from logic.events import EventQueue, GameEvent
from logic.focused_simulation import FocusedSimulation
from logic.game_clock import GameClock
from logic.war import War
from state.game_state import GameState

SAVE_PATH = Path(__file__).resolve().parent.parent / "save.json"
SAVE_VERSION = 1


def _country_to_dict(c: Country) -> dict:
    return {
        "name": c.name,
        "capital": c.capital,
        "flag_image": c.flag_image,
        "territories": list(c.territories),
        "military_strength": c.military_strength,
        "economic_power": c.economic_power,
        "population": c.population,
        "stability": c.stability,
        "personality_type": c.personality_type,
        "decision_frequency": c.decision_frequency,
        "volatility": c.volatility,
        "nuclear": c.nuclear,
        "relationships": dict(c.relationships),
        "action_cooldown": c.action_cooldown,
    }


def _country_from_dict(d: dict) -> Country:
    c = Country(
        d["name"],
        d["capital"],
        d["flag_image"],
        list(d["territories"]),
        d["military_strength"],
        d["economic_power"],
        d["population"],
        d["stability"],
        d["personality_type"],
        d["decision_frequency"],
        d["volatility"],
        d["nuclear"],
    )
    c.relationships = dict(d.get("relationships", {}))
    c.action_cooldown = d.get("action_cooldown", 0)
    return c


def _war_to_dict(w: War) -> dict:
    return {
        "country_a": w.country_a,
        "country_b": w.country_b,
        "started_turn": w.started_turn,
        "active": w.active,
        "casualties_a": w.casualties_a,
        "casualties_b": w.casualties_b,
        "ceasefire_turn": w.ceasefire_turn,
    }


def _war_from_dict(d: dict) -> War:
    return War(
        d["country_a"],
        d["country_b"],
        d["started_turn"],
        active=d.get("active", True),
        casualties_a=d.get("casualties_a", 0),
        casualties_b=d.get("casualties_b", 0),
        ceasefire_turn=d.get("ceasefire_turn"),
    )


def _event_to_dict(e: GameEvent) -> dict:
    return {
        "event_type": e.event_type,
        "source": e.source,
        "target": e.target,
        "days_remaining": e.days_remaining,
        "intensity": e.intensity,
        "reactive": e.reactive,
    }


def _event_from_dict(d: dict) -> GameEvent:
    return GameEvent(
        d["event_type"],
        d["source"],
        d["target"],
        d["days_remaining"],
        intensity=d.get("intensity", 1.0),
        reactive=d.get("reactive", False),
    )


def serialize_simulation(sim: FocusedSimulation) -> dict:
    state = sim.state
    return {
        "version": SAVE_VERSION,
        "scenario": state.scenario,
        "game_day": sim.clock.game_day,
        "actions_this_turn": sim.actions_this_turn,
        "invasions_this_turn": sim.invasions_this_turn,
        "state": {
            "player_country": state.player_country,
            "winner": state.winner,
            "loser": state.loser,
            "event_log": list(state.event_log),
            "player_log": list(state.player_log),
            "defeated_countries": sorted(state.defeated_countries),
            "eliminated_countries": sorted(state.eliminated_countries),
            "player_conquests": state.player_conquests,
            "pending_diplomatic": list(state.pending_diplomatic),
            "pending_reactions": list(state.pending_reactions),
            "pending_axis_responses": list(state.pending_axis_responses),
            "turn_number": state.turn_number,
            "active_wars": [_war_to_dict(w) for w in state.active_wars],
            "battle_reports": [],
            "non_territorial": sorted(state.non_territorial),
            "pending_player_alert": state.pending_player_alert,
            "player_journal": list(state.player_journal),
            "northern_front_opened": state.northern_front_opened,
            "countries": [_country_to_dict(c) for c in state.countries],
        },
        "events": [_event_to_dict(e) for e in sim.events.events],
    }


def save_game(sim: FocusedSimulation, path: Path | None = None) -> Path:
    path = path or SAVE_PATH
    payload = serialize_simulation(sim)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def has_save(path: Path | None = None) -> bool:
    path = path or SAVE_PATH
    return path.exists()


def load_game(path: Path | None = None) -> FocusedSimulation | None:
    path = path or SAVE_PATH
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    if data.get("version") != SAVE_VERSION:
        return None

    countries = [_country_from_dict(c) for c in data["state"]["countries"]]
    scenario = data["scenario"]
    state = GameState(countries, scenario=scenario)
    s = data["state"]
    state.player_country = s.get("player_country")
    state.winner = s.get("winner")
    state.loser = s.get("loser")
    state.event_log = list(s.get("event_log", []))
    state.player_log = list(s.get("player_log", []))
    state.defeated_countries = set(s.get("defeated_countries", []))
    state.eliminated_countries = set(s.get("eliminated_countries", []))
    state.player_conquests = s.get("player_conquests", 0)
    state.pending_diplomatic = list(s.get("pending_diplomatic", []))
    state.pending_reactions = [tuple(x) for x in s.get("pending_reactions", [])]
    state.pending_axis_responses = [tuple(x) for x in s.get("pending_axis_responses", [])]
    state.turn_number = s.get("turn_number", 1)
    state.active_wars = [_war_from_dict(w) for w in s.get("active_wars", [])]
    state.battle_reports = []
    state.non_territorial = set(s.get("non_territorial", []))
    state.pending_player_alert = s.get("pending_player_alert")
    state.player_journal = list(s.get("player_journal", []))
    state.northern_front_opened = s.get("northern_front_opened", False)

    sim = FocusedSimulation(state)
    sim.clock.game_day = data.get("game_day", 0)
    sim.actions_this_turn = data.get("actions_this_turn", 0)
    sim.invasions_this_turn = data.get("invasions_this_turn", 0)
    sim.events = EventQueue()
    for ed in data.get("events", []):
        sim.events.enqueue(_event_from_dict(ed))
    return sim

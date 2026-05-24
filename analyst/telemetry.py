"""Record player inputs and world state from focused-mode sessions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from logic.relationships import get_relationship, relationship_band
from state.game_state import GameState

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "gameplay_sessions"
INDEX_PATH = DATA_DIR / "index.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _country_snapshot(state: GameState, name: str) -> dict:
    c = state.get(name)
    return {
        "territories": list(c.territories),
        "military": c.military_strength,
        "economy": c.economic_power,
        "stability": c.stability,
        "personality": c.personality_type,
    }


def _relationships_snapshot(state: GameState, player: str) -> dict:
    p = state.get(player)
    return {
        other: {
            "score": get_relationship(p, other),
            "band": relationship_band(get_relationship(p, other)),
        }
        for other in state.country_by_name
        if other != player
    }


class GameplayRecorder:
    """Append-only session log for vision analyst."""

    def __init__(self) -> None:
        self.session_id: str | None = None
        self._path: Path | None = None
        self._events: list[dict] = []
        self._started_at: str | None = None

    @property
    def active(self) -> bool:
        return self.session_id is not None

    def start_session(self, state: GameState) -> str:
        if self.active:
            self.end_session(state, outcome="abandoned")

        self.session_id = uuid.uuid4().hex[:12]
        self._started_at = _utc_now()
        self._events = []
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._path = DATA_DIR / f"{self.session_id}.json"

        meta = {
            "session_id": self.session_id,
            "scenario_id": state.scenario.get("id", "south_asia"),
            "player_country": state.player_country,
            "started_at": self._started_at,
            "ended_at": None,
            "outcome": None,
            "tuning_version": state.scenario.get("balance_tuning", {}).get("version"),
            "events": self._events,
        }
        self._write(meta)
        self._append_event(
            "session_start",
            week=state.turn_number,
            snapshot=self._world_snapshot(state),
        )
        self._update_index(outcome=None)
        return self.session_id

    def record_player_action(
        self,
        state: GameState,
        *,
        action: str,
        target: str,
        success: bool,
        message: str,
    ) -> None:
        if not self.active:
            return
        self._append_event(
            "player_action",
            week=state.turn_number,
            action=action,
            target=target,
            success=success,
            message=message,
            snapshot=self._world_snapshot(state),
        )

    def record_week_advanced(
        self,
        state: GameState,
        *,
        messages: list[str],
    ) -> None:
        if not self.active:
            return
        self._append_event(
            "week_advanced",
            week=state.turn_number,
            messages=messages,
            snapshot=self._world_snapshot(state),
            journal_tail=state.player_journal[-5:],
        )

    def end_session(self, state: GameState, *, outcome: str) -> None:
        if not self.active:
            return
        self._append_event(
            "session_end",
            week=state.turn_number,
            outcome=outcome,
            snapshot=self._world_snapshot(state),
        )
        data = self._read()
        data["ended_at"] = _utc_now()
        data["outcome"] = outcome
        self._write(data)
        self._update_index(outcome=outcome)
        self.session_id = None
        self._path = None
        self._events = []

    def _world_snapshot(self, state: GameState) -> dict:
        player = state.player_country or "India"
        p = state.get(player)
        return {
            "turn": state.turn_number,
            "control_percent": round(state.control_percent(player), 3),
            "player": {
                "territories": list(p.territories),
                "military": p.military_strength,
                "economy": p.economic_power,
                "stability": p.stability,
            },
            "countries": {
                c.name: _country_snapshot(state, c.name)
                for c in state.countries
                if c.name not in state.non_territorial
            },
            "relationships": _relationships_snapshot(state, player),
            "eliminated": sorted(state.eliminated_countries),
            "active_wars": len([w for w in state.active_wars if w.active]),
            "winner": state.winner,
            "loser": state.loser,
        }

    def _append_event(self, event_type: str, **payload) -> None:
        entry = {"type": event_type, "at": _utc_now(), **payload}
        self._events.append(entry)
        data = self._read()
        data["events"] = self._events
        self._write(data)

    def _read(self) -> dict:
        with open(self._path) as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def _update_index(self, *, outcome: str | None) -> None:
        index = {"sessions": []}
        if INDEX_PATH.exists():
            with open(INDEX_PATH) as f:
                index = json.load(f)
        sessions = [s for s in index.get("sessions", []) if s["id"] != self.session_id]
        sessions.append(
            {
                "id": self.session_id,
                "started_at": self._started_at,
                "ended_at": _utc_now() if outcome else None,
                "outcome": outcome,
                "path": str(self._path.name),
            }
        )
        index["sessions"] = sorted(sessions, key=lambda s: s["started_at"], reverse=True)
        with open(INDEX_PATH, "w") as f:
            json.dump(index, f, indent=2)
            f.write("\n")


def list_sessions() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    with open(INDEX_PATH) as f:
        return json.load(f).get("sessions", [])


def load_session(session_id: str) -> dict | None:
    path = DATA_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def load_all_completed_sessions() -> list[dict]:
    out = []
    for meta in list_sessions():
        if meta.get("outcome") in ("win", "loss"):
            session = load_session(meta["id"])
            if session:
                out.append(session)
    return out

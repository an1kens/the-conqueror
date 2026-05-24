"""High score tracking and persistence."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from state.game_state import GameState

if False:  # TYPE_CHECKING
    from logic.simulation import Simulation

SCORES_PATH = Path(__file__).resolve().parent.parent / "scores.json"
MAX_ENTRIES = 20


@dataclass
class RunScore:
    player_country: str
    territories: int
    days_survived: int
    countries_defeated: int
    won: bool
    total_score: int


def compute_score(state: GameState, days_survived: float, won: bool) -> RunScore:
    player_name = state.player_country or "Spectator"
    if state.player_country:
        player = state.get(state.player_country)
        territories = len(player.territories)
        defeated = len(state.defeated_countries)
    else:
        territories = 0
        defeated = 0

    days = int(days_survived)
    total = territories * 100 + days * 2 + defeated * 500
    if won and state.player_country == state.winner:
        total += 10_000

    return RunScore(
        player_country=player_name,
        territories=territories,
        days_survived=days,
        countries_defeated=defeated,
        won=won,
        total_score=total,
    )


def score_from_simulation(simulation, *, won: bool | None = None) -> RunScore:
    won = won if won is not None else (
        simulation.state.winner == simulation.state.player_country
    )
    return compute_score(
        simulation.state,
        simulation.clock.game_day,
        won=bool(won),
    )


def load_scores(path: Path | None = None) -> list[dict]:
    path = path or SCORES_PATH
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("scores", [])


def save_run(score: RunScore, path: Path | None = None) -> list[dict]:
    path = path or SCORES_PATH
    scores = load_scores(path)
    scores.append(asdict(score))
    scores.sort(key=lambda s: s["total_score"], reverse=True)
    scores = scores[:MAX_ENTRIES]
    with open(path, "w") as f:
        json.dump({"scores": scores}, f, indent=2)
    return scores

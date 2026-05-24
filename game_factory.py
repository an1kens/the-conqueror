"""Create game sessions."""

from logic.difficulty import DEFAULT_DIFFICULTY
from logic.focused_player import FocusedPlayer
from logic.focused_simulation import FocusedSimulation
from logic.game_clock import GameClock
from logic.player import PlayerController
from logic.simulation import Simulation
from state.loader import load_game_state
from state.scenario_loader import load_scenario


def _add_intro_journals(state) -> None:
    win_pct = int(state.scenario.get("win_control_percent", 0.65) * 100)
    diff = state.scenario.get("difficulty", DEFAULT_DIFFICULTY).title()
    player = state.player_country or "your nation"
    win_lines = [f"Control {win_pct}% of the map"]
    if state.scenario.get("win_on_rivals_eliminated"):
        rivals = ", ".join(state.scenario.get("primary_rivals", []))
        win_lines.append(f"or eliminate {rivals}")
    state.record_journal(
        "system",
        "Scenario start",
        f"Playing as {player} ({diff}). {' — '.join(win_lines)}.",
        impact="2 orders/week, max 1 invasion | Ally friendly powers | Rebuild / Peace",
    )
    state.record_journal(
        "system",
        "Rules of engagement",
        "Nuclear rivals require war before invasion. Hostile non-nuclear rivals "
        "can be invaded with a military edge.",
        impact="Friendly nations (40+): Ally. Full aid at 80+ (scaled by ally military)",
    )


def create_focused_game(
    scenario_id: str = "global",
    *,
    difficulty: str = DEFAULT_DIFFICULTY,
    intro: bool = True,
    player_country: str | None = None,
) -> tuple[FocusedSimulation, FocusedPlayer]:
    state = load_scenario(
        scenario_id, difficulty=difficulty, player_country=player_country
    )
    simulation = FocusedSimulation(state)
    player = FocusedPlayer(simulation)
    if intro:
        _add_intro_journals(state)
    return simulation, player


def create_game(player_index: int | None = None) -> tuple[Simulation, PlayerController]:
    """Legacy 21-country real-time mode."""
    state = load_game_state()
    clock = GameClock(days_per_real_second=10)
    simulation = Simulation(state, clock)
    player = PlayerController(simulation)

    if player_index is not None:
        names = [c.name for c in state.countries]
        if 0 <= player_index < len(names):
            player.assign_country(names[player_index])

    return simulation, player

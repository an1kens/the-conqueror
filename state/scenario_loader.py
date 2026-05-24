import json
from pathlib import Path

from country import Country
from state.game_state import GameState
from logic.balance_config import apply_tuning_to_scenario
from state.loader import populate_relationships

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
PROJECT_ROOT = SCENARIOS_DIR.parent


def _resolve_data_path(filename: str) -> Path:
    path = SCENARIOS_DIR / filename
    if path.exists():
        return path
    path = PROJECT_ROOT / filename
    if path.exists():
        return path
    raise FileNotFoundError(f"Data file not found: {filename}")


def load_scenario(
    scenario_id: str = "global",
    *,
    difficulty: str = "normal",
    player_country: str | None = None,
) -> GameState:
    from logic.balance_config import load_tuning
    from logic.difficulty import apply_difficulty

    load_tuning(reload=True)
    meta_path = SCENARIOS_DIR / f"{scenario_id}.json"
    with open(meta_path) as f:
        scenario = json.load(f)
    scenario = apply_tuning_to_scenario(scenario)
    scenario = apply_difficulty(scenario, difficulty)

    countries_path = _resolve_data_path(scenario["countries_file"])
    with open(countries_path) as f:
        countries_data = json.load(f)

    countries = [
        Country(
            c["name"],
            c["capital"],
            c["flag_image"],
            list(c["territories"]),
            c["military_strength"],
            c["economic_power"],
            c["population"],
            c["stability"],
            c["personality_type"],
            c["decision_frequency"],
            c["volatility"],
            c["nuclear"],
        )
        for c in countries_data
    ]

    rel_path = _resolve_data_path(scenario["relationships_file"])
    with open(rel_path) as f:
        rel_data = json.load(f)

    populate_relationships(countries, rel_data.get("default_score", 0), rel_data["pairs"])
    state = GameState(countries, scenario=scenario)
    chosen = player_country or scenario.get("player_country")
    if chosen and chosen in state.country_by_name:
        state.player_country = chosen
    else:
        state.player_country = scenario.get("player_country")
    return state

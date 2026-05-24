import json
from pathlib import Path

from country import Country
from state.game_state import GameState

DATA_DIR = Path(__file__).resolve().parent.parent


def load_countries(path: Path | None = None) -> list[Country]:
    path = path or DATA_DIR / "countries.json"
    with open(path) as f:
        countries_data = json.load(f)

    countries = []
    for c in countries_data:
        countries.append(
            Country(
                c["name"],
                c["capital"],
                c["flag_image"],
                c["territories"],
                c["military_strength"],
                c["economic_power"],
                c["population"],
                c["stability"],
                c["personality_type"],
                c["decision_frequency"],
                c["volatility"],
                c["nuclear"],
            )
        )
    return countries


def load_relationship_pairs(path: Path | None = None) -> tuple[int, list[dict]]:
    path = path or DATA_DIR / "relationships.json"
    with open(path) as f:
        data = json.load(f)
    return data.get("default_score", 0), data["pairs"]


def populate_relationships(countries: list[Country], default_score: int, pairs: list[dict]) -> None:
    names = [c.name for c in countries]
    lookup = {c.name: c for c in countries}

    for country in countries:
        country.relationships = {name: default_score for name in names}
        country.relationships[country.name] = 100

    for pair in pairs:
        a, b, score = pair["a"], pair["b"], pair["score"]
        if a not in lookup or b not in lookup:
            continue
        lookup[a].relationships[b] = score
        lookup[b].relationships[a] = score


def load_game_state(
    countries_path: Path | None = None,
    relationships_path: Path | None = None,
) -> GameState:
    countries = load_countries(countries_path)
    default_score, pairs = load_relationship_pairs(relationships_path)
    populate_relationships(countries, default_score, pairs)
    return GameState(countries)

from __future__ import annotations

from country import Country


class GameState:
    """Single source of truth for the world. Only logic layer mutates this."""

    def __init__(self, countries: list[Country], *, scenario: dict | None = None):
        self.countries = countries
        self.country_by_name = {c.name: c for c in countries}
        self.player_country: str | None = None
        self.winner: str | None = None
        self.loser: str | None = None
        self.event_log: list[str] = []
        self.player_log: list[str] = []
        self.defeated_countries: set[str] = set()
        self.eliminated_countries: set[str] = set()
        self.player_conquests: int = 0
        self.pending_diplomatic: list = []
        self.pending_reactions: list[tuple[str, str, str]] = []
        self.pending_axis_responses: list[tuple[str, str]] = []
        self.scenario: dict = scenario if scenario is not None else {}
        self.focused_mode = bool(scenario)
        self.turn_number = 1
        self.active_wars: list = []
        self.battle_reports: list = []
        self.non_territorial: set[str] = set(self.scenario.get("non_territorial", []))
        self.pending_player_alert: str | None = None
        self.player_journal: list[dict] = []
        self.northern_front_opened: bool = False
        self.player_stability_loss_this_week: int = 0
        self.territories_lost_this_week: list[tuple[str, str]] = []
        self.pending_attack_sources_on_player: list[str] = []

    def get(self, name: str) -> Country:
        return self.country_by_name[name]

    def all_territories(self) -> set[str]:
        territories = set()
        for country in self.countries:
            territories.update(country.territories)
        return territories

    def territory_owner(self) -> dict[str, str]:
        owners = {}
        for country in self.countries:
            for territory in country.territories:
                owners[territory] = country.name
        return owners

    def log(self, message: str) -> None:
        self.event_log.append(message)
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]

    def log_player(self, message: str) -> None:
        """Player-facing feed (your nation + direct threats)."""
        self.log(message)
        self.player_log.append(message)
        if len(self.player_log) > 80:
            self.player_log = self.player_log[-80:]

    def record_journal(
        self,
        kind: str,
        title: str,
        body: str,
        *,
        impact: str = "",
        week: int | None = None,
    ) -> None:
        """Structured event for the UI timeline (kind: battle, order, pressure, peace, usa, recover, system)."""
        week = week if week is not None else self.turn_number
        entry = {
            "week": week,
            "kind": kind,
            "title": title,
            "body": body,
            "impact": impact,
        }
        self.player_journal.append(entry)
        line = f"[{kind.upper()}] {title} — {body}"
        if impact:
            line += f" ({impact})"
        self.log_player(line)
        if len(self.player_journal) > 60:
            self.player_journal = self.player_journal[-60:]

    def contestable_territories(self) -> set[str]:
        territories = set()
        for country in self.countries:
            if country.name in self.non_territorial:
                continue
            territories.update(country.territories)
        return territories

    def territories_controlled_by(self, country_name: str) -> set[str]:
        c = self.get(country_name)
        return set(c.territories)

    def control_percent(self, country_name: str) -> float:
        contestable = self.contestable_territories()
        if not contestable:
            return 0.0
        owned = self.territories_controlled_by(country_name) & contestable
        return len(owned) / len(contestable)

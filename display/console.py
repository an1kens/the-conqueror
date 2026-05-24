"""Read-only display layer. Never mutates GameState."""

from logic.game_clock import GameClock
from logic.relationships import relationship_band
from logic.simulation import Simulation
from state.game_state import GameState


class ConsoleDisplay:
    def __init__(self, state: GameState, simulation: Simulation):
        self.state = state
        self.simulation = simulation

    @property
    def clock(self) -> GameClock:
        return self.simulation.clock

    def render_status(self) -> str:
        lines = [
            f"=== The Conqueror | Day {int(self.clock.game_day)} "
            f"(Year {self.clock.game_year()}) ===",
            f"Clock: {'PAUSED' if self.clock.paused else 'RUNNING'}"
            + (" (react!)" if self.simulation.needs_player_response else "")
            + " | "
            f"Active events: {len(self.simulation.events.events)}",
        ]
        if self.state.player_country:
            player = self.state.get(self.state.player_country)
            lines.append(
                f"Player: {player.name} | Territories: {len(player.territories)} | "
                f"Cooldown: {player.action_cooldown:.0f} days"
            )
        if self.state.winner:
            lines.append(f"WINNER: {self.state.winner}")
        return "\n".join(lines)

    def render_recent_events(self, count: int = 8) -> str:
        recent = self.state.event_log[-count:]
        if not recent:
            return "(no events yet)"
        return "\n".join(recent)

    def render_relationships(self, country_name: str, limit: int = 5) -> str:
        country = self.state.get(country_name)
        pairs = [
            (other, score, relationship_band(score))
            for other, score in country.relationships.items()
            if other != country_name
        ]
        pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        lines = [f"Top relationships for {country_name}:"]
        for other, score, band in pairs[:limit]:
            lines.append(f"  {other}: {score} ({band})")
        return "\n".join(lines)

    def render_player_panel(self) -> str:
        if not self.state.player_country:
            return ""
        p = self.state.get(self.state.player_country)
        pending = self.simulation.player_pending_reaction
        lines = [
            f"-- {p.name} --",
            f"  Capital: {p.capital} | Personality: {p.personality_type}",
            f"  Military {p.military_strength} | Economy {p.economic_power} | "
            f"Stability {p.stability} | Pop {p.population}M",
            f"  Territories: {', '.join(p.territories)}",
            f"  Nuclear: {'yes' if p.nuclear else 'no'} | "
            f"Cooldown: {p.action_cooldown:.0f} days",
        ]
        if pending:
            provoker, provocation = pending
            lines.append(
                f"  >>> REACT to {provoker} ({provocation}) — commands bypass cooldown <<<"
            )
        return "\n".join(lines)

    def render_targets(self) -> str:
        if not self.state.player_country:
            return "Pick a country first."
        player = self.state.get(self.state.player_country)
        lines = ["Targets (use action + number, e.g. 'a 3'):"]
        idx = 1
        for c in self.state.countries:
            if c.name == player.name:
                continue
            rel = player.relationships[c.name]
            lines.append(f"  {idx:2} {c.name} — rel {rel} ({relationship_band(rel)})")
            idx += 1
        return "\n".join(lines)

    @staticmethod
    def render_help() -> str:
        return """
Commands (action + target number):
  a <n>  attack      n <n>  negotiate
  s <n>  sanction    l <n>  ally (diplomacy)

Meta:
  t  list targets    i  your stats    h  help
  p  pause clock     r  resume        q  quit

When another country attacks or sanctions you, react immediately (no cooldown).
"""

    def render_full(self) -> str:
        parts = [self.render_status()]
        panel = self.render_player_panel()
        if panel:
            parts.append(panel)
        parts.append("\n-- Recent --\n" + self.render_recent_events())
        return "\n".join(parts)

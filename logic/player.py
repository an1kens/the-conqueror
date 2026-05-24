"""Player control layer — validates and queues actions through the event system."""

from dataclasses import dataclass

from country import Country
from logic.events import EVENT_DURATIONS
from logic.relationships import can_invade, get_relationship, relationship_band
from logic.simulation import Simulation
from state.game_state import GameState

PLAYER_ACTIONS = ("attack", "negotiate", "sanction", "ally")


@dataclass
class ActionResult:
    success: bool
    message: str


class PlayerController:
    """Logic-layer interface for human player actions."""

    def __init__(self, simulation: Simulation):
        self.simulation = simulation

    @property
    def state(self) -> GameState:
        return self.simulation.state

    @property
    def country(self) -> Country | None:
        name = self.state.player_country
        return self.state.get(name) if name else None

    @property
    def has_pending_reaction(self) -> bool:
        return self.simulation.player_pending_reaction is not None

    @property
    def can_take_proactive_action(self) -> bool:
        player = self.country
        if not player:
            return False
        return player.action_cooldown <= 0 or self.has_pending_reaction

    def targets(self) -> list[Country]:
        if not self.country:
            return []
        return [c for c in self.state.countries if c.name != self.country.name]

    def target_by_index(self, index: int) -> Country | None:
        targets = self.targets()
        if 1 <= index <= len(targets):
            return targets[index - 1]
        return None

    def provoker_target_index(self) -> int | None:
        pending = self.simulation.player_pending_reaction
        if not pending:
            return None
        provoker_name, _ = pending
        for i, country in enumerate(self.targets(), 1):
            if country.name == provoker_name:
                return i
        return None

    def suggested_reactive_command(self) -> str | None:
        """Quick command hint, e.g. 's 2' to sanction the provoker."""
        idx = self.provoker_target_index()
        if idx is None:
            return None
        pending = self.simulation.player_pending_reaction
        if not pending:
            return None
        _, provocation = pending
        if provocation == "attack":
            return f"a {idx}  (counter-attack)  or  s {idx}  (sanction)"
        return f"s {idx}  (sanction)  or  n {idx}  (negotiate)"

    def validate_action(self, event_type: str, target: Country) -> ActionResult:
        player = self.country
        if not player:
            return ActionResult(False, "No country selected.")

        if event_type not in PLAYER_ACTIONS:
            return ActionResult(False, f"Unknown action '{event_type}'.")

        if not self.can_take_proactive_action and not self.has_pending_reaction:
            return ActionResult(
                False,
                f"Action cooldown: {player.action_cooldown:.0f} game-days remaining.",
            )

        if event_type == "attack":
            if not can_invade(player, target):
                if target.nuclear:
                    return ActionResult(
                        False,
                        f"Cannot invade {target.name} — nuclear deterrence.",
                    )
                return ActionResult(
                    False,
                    f"Cannot invade {target.name} — insufficient leverage "
                    f"(military {player.military_strength} vs {target.military_strength}).",
                )

        band = relationship_band(get_relationship(player, target.name))
        if event_type == "ally" and band == "at_war":
            return ActionResult(False, f"Cannot ally with {target.name} while at war.")

        return ActionResult(True, "OK")

    def queue_action(
        self,
        event_type: str,
        target_name: str,
        intensity: float = 1.0,
        *,
        reactive: bool = False,
    ) -> ActionResult:
        if not self.country:
            return ActionResult(False, "No country selected.")

        if target_name not in self.state.country_by_name:
            return ActionResult(False, f"Unknown country: {target_name}")
        target = self.state.get(target_name)

        if target.name == self.country.name:
            return ActionResult(False, "Cannot target yourself.")

        if not reactive:
            check = self.validate_action(event_type, target)
            if not check.success:
                return check

        provoker = ""
        if reactive and self.simulation.player_pending_reaction:
            provoker, _ = self.simulation.player_pending_reaction

        ok = self.simulation.queue_player_action(
            event_type,
            target_name,
            intensity=intensity,
            reactive=reactive,
        )
        if not ok:
            return ActionResult(False, "Action could not be queued.")

        duration = EVENT_DURATIONS.get(event_type, 5)

        msg = (
            f"{event_type.capitalize()} vs {target_name} queued "
            f"({duration} game-days to resolve)."
        )
        if reactive:
            msg = f"Reactive {msg}"
            if provoker:
                msg += f" (responding to {provoker})"

        return ActionResult(True, msg)

    def queue_action_by_index(
        self,
        event_type: str,
        target_index: int,
        intensity: float = 1.0,
        *,
        reactive: bool = False,
    ) -> ActionResult:
        target = self.target_by_index(target_index)
        if not target:
            return ActionResult(False, f"Invalid target number {target_index}.")
        return self.queue_action(event_type, target.name, intensity, reactive=reactive)

    def assign_country(self, country_name: str) -> ActionResult:
        if country_name not in self.state.country_by_name:
            return ActionResult(False, f"Unknown country: {country_name}")
        self.state.player_country = country_name
        country = self.state.get(country_name)
        return ActionResult(
            True,
            f"You are now {country_name} — capital {country.capital}, "
            f"{len(country.territories)} territories, "
            f"military {country.military_strength}, stability {country.stability}.",
        )


ACTION_ALIASES = {
    "a": "attack",
    "attack": "attack",
    "n": "negotiate",
    "negotiate": "negotiate",
    "s": "sanction",
    "sanction": "sanction",
    "l": "ally",
    "ally": "ally",
}


def parse_command(line: str) -> tuple[str, str, int] | tuple[str, None, None]:
    """
    Parse a command line.
    Returns (kind, action, target_index) where kind is 'action', 'meta', or 'empty'.
    """
    parts = line.strip().lower().split()
    if not parts:
        return ("empty", None, None)

    meta_commands = {
        "p": "pause",
        "pause": "pause",
        "r": "resume",
        "resume": "resume",
        "t": "targets",
        "targets": "targets",
        "h": "help",
        "help": "help",
        "q": "quit",
        "quit": "quit",
        "i": "info",
        "info": "info",
        "status": "info",
    }
    if parts[0] in meta_commands:
        return ("meta", meta_commands[parts[0]], None)

    action = ACTION_ALIASES.get(parts[0])
    if not action:
        return ("empty", None, None)

    if len(parts) < 2:
        return ("empty", None, None)

    try:
        target_index = int(parts[1])
    except ValueError:
        return ("empty", None, None)

    return ("action", action, target_index)


def execute_command(controller: PlayerController, line: str) -> ActionResult | str | None:
    """
    Execute a parsed command.
    Returns ActionResult for actions, str for meta display, None if empty/ignored.
    """
    kind, value, target_index = parse_command(line)
    sim = controller.simulation

    if kind == "empty":
        return None

    if kind == "meta":
        if value == "pause":
            sim.manual_pause = True
            sim.clock.pause()
            return "pause"
        if value == "resume":
            if controller.has_pending_reaction:
                return ActionResult(False, "Respond to the attack first.")
            sim.manual_pause = False
            sim.clock.resume()
            return "resume"
        if value == "quit":
            return "quit"
        if value in ("targets", "help", "info"):
            return value
        return None

    reactive = controller.has_pending_reaction
    return controller.queue_action_by_index(
        value, target_index, reactive=reactive
    )

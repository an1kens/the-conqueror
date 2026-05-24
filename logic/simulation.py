from logic.ai import choose_proactive_action, choose_reactive_action, decision_to_event
from logic.events import EventQueue, create_event, resolve_event
from logic.game_clock import GameClock
from logic.relationships import adjust_relationship
from state.game_state import GameState


class Simulation:
    """Logic layer: advances clock, cooldowns, events, and AI."""

    def __init__(self, state: GameState, clock: GameClock | None = None):
        self.state = state
        self.clock = clock or GameClock()
        self.events = EventQueue()
        self._pending_reactions: list[tuple[str, str, str]] = []
        self.player_pending_reactions: list[tuple[str, str]] = []
        self.manual_pause: bool = False

    @property
    def needs_player_response(self) -> bool:
        return bool(self.player_pending_reactions)

    @property
    def player_pending_reaction(self) -> tuple[str, str] | None:
        if not self.player_pending_reactions:
            return None
        return self.player_pending_reactions[0]

    def clear_current_player_reaction(self) -> None:
        if self.player_pending_reactions:
            self.player_pending_reactions.pop(0)

    def tick(self, real_delta_seconds: float) -> None:
        if self.needs_player_response or self.manual_pause or self.state.winner:
            return

        game_days = self.clock.advance(real_delta_seconds)
        if game_days <= 0:
            return

        self._tick_cooldowns(game_days)
        self._flush_pending_diplomatic()
        self._tick_proactive_ai(game_days)
        self.events.tick(game_days, self.state, resolve_event)
        self._process_reactions()
        self._check_win_condition()

    def _flush_pending_diplomatic(self) -> None:
        pending = self.state.pending_diplomatic
        self.state.pending_diplomatic = []
        for transition, source_name, target_name in pending:
            self.events.enqueue(
                create_event(transition, source_name, target_name, intensity=1.0)
            )
            self.state.log(
                f"[Day {int(self.clock.game_day)}] Diplomatic event: "
                f"{transition.replace('_', ' ')} — {source_name} / {target_name}"
            )

    def _tick_cooldowns(self, game_days: float) -> None:
        for country in self.state.countries:
            if country.action_cooldown > 0:
                country.action_cooldown = max(0, country.action_cooldown - game_days)

    def _tick_proactive_ai(self, game_days: float) -> None:
        for country in self.state.countries:
            if country.action_cooldown > 0:
                continue
            if self.state.player_country == country.name:
                continue

            decision = choose_proactive_action(country, self.state)
            if decision is None:
                country.action_cooldown = country.decision_frequency
                continue

            event = decision_to_event(decision, country.name)
            self.events.enqueue(event)
            self._queue_reaction(decision.target, country.name, decision.event_type)
            country.action_cooldown = country.decision_frequency
            self.state.log(
                f"[Day {int(self.clock.game_day)}] {country.name} begins "
                f"{decision.event_type} vs {decision.target}"
            )

    def queue_player_action(
        self,
        event_type: str,
        target_name: str,
        intensity: float = 1.0,
        *,
        reactive: bool = False,
    ) -> bool:
        if not self.state.player_country:
            return False
        player = self.state.get(self.state.player_country)
        if not reactive and player.action_cooldown > 0:
            return False

        event = create_event(
            event_type,
            player.name,
            target_name,
            intensity=intensity,
            reactive=reactive,
        )
        self.events.enqueue(event)
        self._queue_reaction(target_name, player.name, event_type)
        if reactive:
            self.clear_current_player_reaction()
        else:
            player.action_cooldown = player.decision_frequency
        self.state.log(
            f"[Day {int(self.clock.game_day)}] Player ({player.name}): "
            f"{event_type} vs {target_name}"
        )
        return True

    def _queue_reaction(self, victim: str, provoker: str, provocation: str) -> None:
        if victim == provoker:
            return
        self._pending_reactions.append((victim, provoker, provocation))

    def _process_reactions(self) -> None:
        pending = self._pending_reactions
        self._pending_reactions = []
        for victim_name, provoker_name, provocation in pending:
            if victim_name == self.state.player_country:
                entry = (provoker_name, provocation)
                if entry not in self.player_pending_reactions:
                    self.player_pending_reactions.append(entry)
                self.clock.pause()
                self.manual_pause = False
                self.state.log(
                    f"*** {provoker_name} {provocation}ed you — "
                    f"clock paused; choose a response ***"
                )
                continue

            victim = self.state.get(victim_name)
            decision = choose_reactive_action(victim, self.state, provoker_name, provocation)
            event = decision_to_event(decision, victim.name)
            self.events.enqueue(event)
            victim.action_cooldown = 0
            adjust_relationship(
                victim, provoker_name, -5, self.state.get(provoker_name), state=self.state
            )
            self.state.log(
                f"{victim.name} reacts to {provoker_name} with {decision.event_type}"
            )

    def _check_win_condition(self) -> None:
        if self.state.winner:
            return
        all_territories = self.state.all_territories()
        if not all_territories:
            return
        for country in self.state.countries:
            if set(country.territories) >= all_territories:
                self.state.winner = country.name
                self.clock.pause()
                self.state.log(f"{country.name} controls the world!")
                if self.state.player_country:
                    self.save_score(won=True)
                return

    def save_score(self, *, won: bool = False) -> None:
        if self.state.player_country:
            from logic.scoring import save_run, score_from_simulation

            save_run(score_from_simulation(self, won=won))

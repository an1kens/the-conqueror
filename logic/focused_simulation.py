"""Turn-based simulation for the focused South Asia scenario."""

import random

from logic.ai import choose_proactive_action, choose_reactive_action
from logic.balance_config import load_tuning
from logic.economy import (
    clamp_military_to_economy,
    peacetime_military_recovery,
    wartime_military_recovery,
)
from logic.events import EventQueue, create_event
from logic.focused_events import FOCUSED_DURATIONS, resolve_focused_event
from logic.game_clock import GameClock
from logic.relationships import WAR_MAX, adjust_relationship, get_relationship, relationship_band
from logic.game_summary import build_defeat_summary, build_victory_summary
from logic.war import declare_war, find_war
from state.game_state import GameState

AI_ACTION_RATES = {
    "aggressive": 0.65,
    "opportunistic": 0.60,
    "defensive": 0.50,
    "diplomatic": 0.40,
    "isolationist": 0.35,
}
class FocusedSimulation:
    """One week per turn; no real-time ticking."""

    def __init__(self, state: GameState):
        self.state = state
        self.clock = GameClock(days_per_real_second=0)
        self.clock.paused = True
        self.events = EventQueue()
        self.actions_this_turn = 0
        self.invasions_this_turn = 0
        self.max_player_actions = 2
        self.max_invasions_per_turn = 1

    @property
    def week_days(self) -> int:
        return int(self.state.scenario.get("week_days", 7))

    @property
    def axis_response_chance(self) -> float:
        tuning = self.state.scenario.get("balance_tuning") or load_tuning()
        return float(tuning["ai"]["axis_response_chance"])

    def queue_action(
        self,
        event_type: str,
        source_name: str,
        target_name: str,
        intensity: float = 1.0,
        *,
        counts_as_player_order: bool = False,
        territory: str | None = None,
    ) -> bool:
        if self.state.winner or self.state.loser:
            return False
        if event_type not in FOCUSED_DURATIONS:
            return False
        duration = FOCUSED_DURATIONS[event_type]
        event = create_event(
            event_type,
            source_name,
            target_name,
            intensity=intensity,
            duration=duration,
        )
        if territory:
            event.metadata["territory"] = territory
        self.events.enqueue(event)
        rel = relationship_band(
            self.state.get(source_name).relationships.get(target_name, 0)
        )
        if event_type in ("attack", "ceasefire") or rel == "at_war":
            declare_war(
                self.state.active_wars,
                source_name,
                target_name,
                self.state.turn_number,
            )
        player = self.state.player_country
        msg = (
            f"Week {self.state.turn_number}: {source_name} ordered "
            f"{event_type} vs {target_name} (resolves end of week)."
        )
        if source_name == player or target_name == player:
            self.state.log_player(msg)
            if source_name == player and counts_as_player_order:
                kind = {
                    "attack": "order",
                    "sanction": "pressure",
                    "negotiate": "peace",
                    "ceasefire": "peace",
                    "ally": "usa",
                    "rearm": "recover",
                }.get(event_type, "order")
                self.state.record_journal(
                    kind,
                    f"Your order: {event_type}",
                    f"Against {target_name} — resolves when you advance the week.",
                    impact="Pending",
                    week=self.state.turn_number,
                )
        else:
            self.state.log(msg)
        return True

    def advance_week(self) -> list[str]:
        """Resolve week: events, AI, elimination, win/lose. Returns status messages."""
        if self.state.winner or self.state.loser:
            return ["Game over."]

        messages = []
        self.state.pending_player_alert = None
        self.state.player_stability_loss_this_week = 0
        self.state.territories_lost_this_week = []
        player = self.state.player_country
        self.state.pending_attack_sources_on_player = [
            e.source
            for e in self.events.events
            if e.event_type == "attack"
            and player
            and e.target == player
        ]
        days = float(self.week_days)
        self.clock.game_day += days

        self._flush_diplomatic()
        self.events.tick(days, self.state, resolve_focused_event)
        self.state.pending_attack_sources_on_player = []
        self._process_axis_responses()
        self._process_reactions()
        self._weekly_upkeep()
        self._enemy_peacetime_rebuild()
        from logic.us_support import apply_us_weekly_support

        us_headlines = apply_us_weekly_support(self)
        if us_headlines:
            messages.append("Allied support: " + ", ".join(us_headlines))
        self._ai_weekly_actions()
        self._check_eliminations()
        self._check_northern_front()
        messages.extend(self._check_victory())

        self.state.turn_number += 1
        self.actions_this_turn = 0
        self.invasions_this_turn = 0
        return messages

    def _weekly_upkeep(self) -> None:
        player = self.state.player_country
        if not player:
            return
        p = self.state.get(player)
        at_war = any(
            p.relationships.get(other, 0) <= WAR_MAX
            for other in self.state.country_by_name
            if other != player
        )
        before = p.military_strength
        gain = (
            wartime_military_recovery(p.economic_power)
            if at_war
            else peacetime_military_recovery(p.economic_power)
        )
        if gain > 0:
            p.military_strength = min(100, p.military_strength + gain)
            clamp_military_to_economy(p)
            title = "Wartime attrition recovery" if at_war else "Peacetime recovery"
            body = (
                "Minimal reinforcements while fighting continues."
                if at_war
                else f"Recovery scales with economy ({p.economic_power})."
            )
            if p.military_strength > before:
                self.state.record_journal(
                    "recover",
                    title,
                    body,
                    impact=f"Military {before} → {p.military_strength}",
                )

    def _enemy_peacetime_rebuild(self) -> None:
        """Rivals not at war with India slowly rebuild if player chose ceasefire."""
        player = self.state.player_country
        if not player:
            return
        india = self.state.get(player)
        for country in self.state.countries:
            if country.name in (player, *self.state.non_territorial):
                continue
            if country.name in self.state.eliminated_countries:
                continue
            if get_relationship(india, country.name) <= WAR_MAX:
                continue
            before = country.military_strength
            gain = peacetime_military_recovery(country.economic_power)
            if gain > 0:
                country.military_strength = min(100, country.military_strength + gain)
                clamp_military_to_economy(country)
                if country.military_strength > before and before < 70:
                    self.state.log(
                        f"{country.name} rebuilt forces during the lull "
                        f"(military {before} → {country.military_strength})."
                    )

    def _flush_diplomatic(self) -> None:
        pending = self.state.pending_diplomatic
        self.state.pending_diplomatic = []
        for transition, a, b in pending:
            self.events.enqueue(create_event(transition, a, b, duration=1))

    def _ai_action_chance(self, country) -> float:
        tuning = self.state.scenario.get("balance_tuning") or load_tuning()
        scenario_boost = self.state.scenario.get("rival_boost") or {}
        rival_boost = {
            "Pakistan": tuning["ai"]["rival_boost_pakistan"],
            "China": tuning["ai"]["rival_boost_china"],
            **scenario_boost,
        }
        base = AI_ACTION_RATES.get(country.personality_type, 0.50)
        if self.state.player_country:
            base = max(base, rival_boost.get(country.name, base))
        mult = float(self.state.scenario.get("ai_rate_mult", 1.0))
        return min(0.95, base * mult)

    def _process_reactions(self) -> None:
        pending = self.state.pending_reactions
        self.state.pending_reactions = []
        player = self.state.player_country
        for victim_name, provoker_name, provocation in pending:
            if victim_name == player:
                continue
            if victim_name in self.state.eliminated_countries:
                continue
            victim = self.state.get(victim_name)
            decision = choose_reactive_action(
                victim, self.state, provoker_name, provocation
            )
            if decision.event_type == "attack":
                target = self.state.get(decision.target)
                if not target.territories:
                    decision.event_type = "sanction"
            self.queue_action(
                decision.event_type,
                victim_name,
                decision.target,
                intensity=decision.intensity,
            )

    def _process_axis_responses(self) -> None:
        pending = self.state.pending_axis_responses
        self.state.pending_axis_responses = []
        player = self.state.player_country
        for partner_name, aggressor_name in pending:
            if partner_name in self.state.eliminated_countries:
                continue
            if random.random() > self.axis_response_chance:
                continue
            partner = self.state.get(partner_name)
            if aggressor_name == player:
                rel = get_relationship(partner, aggressor_name)
                if rel > WAR_MAX:
                    self.queue_action("sanction", partner_name, aggressor_name, 1.1)
                else:
                    from logic.relationships import can_invade

                    if can_invade(partner, self.state.get(aggressor_name)):
                        self.queue_action("attack", partner_name, aggressor_name, 1.15)
                    else:
                        self.queue_action("sanction", partner_name, aggressor_name, 1.1)
                self.state.record_journal(
                    "system",
                    f"{partner_name} backs their partner",
                    f"{partner_name} countered your pressure on a rival axis.",
                    impact="Counter-pressure or counter-attack queued",
                )

    def _check_northern_front(self) -> None:
        if not self.state.scenario.get("northern_front"):
            return
        if self.state.northern_front_opened:
            return
        pak = self.state.country_by_name.get("Pakistan")
        triggered = False
        if pak:
            if "Pakistan" in self.state.eliminated_countries:
                triggered = True
            elif len(pak.territories) < 2:
                triggered = True
        if not triggered:
            return
        china = self.state.country_by_name.get("China")
        if not china or "China" in self.state.eliminated_countries:
            return
        player = self.state.player_country
        if not player:
            return
        p = self.state.get(player)
        self.state.northern_front_opened = True
        adjust_relationship(china, player, -30, p, state=self.state)
        self.state.record_journal(
            "system",
            "Northern front opens",
            "Pakistan's collapse pulls China into direct confrontation with you.",
            impact="Relations with China sharply worse; expect pressure and attacks",
        )
        self.queue_action("sanction", "China", player, intensity=1.2)

    def _ai_weekly_actions(self) -> None:
        player = self.state.player_country
        max_actions = int(self.state.scenario.get("max_ai_actions_per_week", 999))
        actions_taken = 0
        rivals = set(self.state.scenario.get("primary_rivals", []))
        for country in self.state.countries:
            if actions_taken >= max_actions:
                break
            if country.name == player:
                continue
            if country.name in self.state.eliminated_countries:
                continue
            if country.name in self.state.non_territorial:
                if random.random() < 0.35:
                    self._ai_diplomatic_action(country)
                    actions_taken += 1
                continue
            if (
                self.state.scenario.get("geo_scope") == "world"
                and rivals
                and country.name not in rivals
                and random.random() > 0.25
            ):
                continue
            if random.random() > self._ai_action_chance(country):
                continue
            decision = choose_proactive_action(country, self.state)
            if not decision:
                continue
            if decision.event_type == "attack":
                target = self.state.get(decision.target)
                if not target.territories:
                    decision.event_type = "sanction"
            self.queue_action(
                decision.event_type,
                country.name,
                decision.target,
                intensity=decision.intensity,
            )
            actions_taken += 1

    def _ai_diplomatic_action(self, country) -> None:
        others = [
            c.name
            for c in self.state.countries
            if c.name != country.name and c.name != self.state.player_country
        ]
        if not others:
            return
        target = random.choice(others)
        action = random.choice(["negotiate", "sanction", "ally"])
        self.queue_action(action, country.name, target, intensity=0.8)

    def _check_eliminations(self) -> None:
        for country in self.state.countries:
            if country.name in self.state.non_territorial:
                continue
            if not country.territories:
                self.state.eliminated_countries.add(country.name)

    def _check_victory(self) -> list[str]:
        msgs = []
        player = self.state.player_country
        if not player:
            return msgs

        p = self.state.get(player)
        if player in self.state.eliminated_countries or not p.territories:
            self.state.loser = player
            self._record_defeat_summary("no territory")
            self.state.log_player("DEFEAT: Your nation holds no territory.")
            msgs.append("Defeat — you lost all territory.")
            return msgs

        if p.capital and p.capital not in p.territories and p.territories:
            pass
        elif p.capital and p.capital not in p.territories and not p.territories:
            self.state.loser = player
            self._record_defeat_summary("capital lost")
            self.state.log_player(f"DEFEAT: Capital {p.capital} fell.")
            msgs.append("Defeat — capital lost.")
            return msgs

        threshold = float(self.state.scenario.get("win_control_percent", 0.65))
        control = self.state.control_percent(player)
        enemies = [
            c.name
            for c in self.state.countries
            if c.name != player
            and c.name not in self.state.non_territorial
            and c.name not in self.state.eliminated_countries
        ]
        if control >= threshold:
            self.state.winner = player
            title, body, impact = build_victory_summary(self.state)
            self.state.record_journal("system", title, body, impact=impact)
            self.state.log_player(
                f"VICTORY: You control {control:.0%} of the region "
                f"({len(p.territories)} territories)."
            )
            msgs.append(f"Victory — {control:.0%} regional control.")
            return msgs

        if enemies and all(n in self.state.eliminated_countries for n in enemies):
            self.state.winner = player
            title, body, impact = build_victory_summary(self.state)
            self.state.record_journal("system", title, body, impact=impact)
            self.state.log_player("VICTORY: All rival nations eliminated.")
            msgs.append("Victory — all enemies eliminated.")
            return msgs

        if self.state.scenario.get("win_on_rivals_eliminated"):
            rivals = list(self.state.scenario.get("primary_rivals", []))
            if rivals and all(r in self.state.eliminated_countries for r in rivals):
                self.state.winner = player
                title, body, impact = build_victory_summary(self.state)
                self.state.record_journal("system", title, body, impact=impact)
                names = ", ".join(rivals)
                self.state.log_player(f"VICTORY: Primary rivals eliminated ({names}).")
                msgs.append(f"Victory — eliminated {names}.")
        return msgs

    def _record_defeat_summary(self, _reason: str) -> None:
        title, body, impact = build_defeat_summary(self.state)
        self.state.record_journal("system", title, body, impact=impact)

    def pending_player_orders(self) -> list[str]:
        """Human-readable orders queued for the current week (resolve on advance)."""
        player = self.state.player_country
        if not player:
            return []
        labels = {
            "attack": "Invade",
            "sanction": "Pressure",
            "negotiate": "Peace talks",
            "ceasefire": "Ceasefire",
            "ally": "Ally",
            "rearm": "Rebuild",
        }
        lines = []
        for event in self.events.events:
            if event.source != player:
                continue
            label = labels.get(event.event_type, event.event_type)
            terr = event.metadata.get("territory")
            if terr and event.event_type == "attack":
                lines.append(f"{label} {terr} ({event.target})")
            else:
                lines.append(f"{label} vs {event.target}")
        return lines

    def active_wars_for_player(self) -> list[dict]:
        player = self.state.player_country
        if not player:
            return []
        rows = []
        for war in self.state.active_wars:
            if not war.active:
                continue
            if player not in (war.country_a, war.country_b):
                continue
            foe = war.other(player)
            rows.append(
                {
                    "enemy": foe,
                    "since": war.started_turn,
                    "your_dead": war.casualties_a
                    if player == war.country_a
                    else war.casualties_b,
                    "their_dead": war.casualties_b
                    if player == war.country_a
                    else war.casualties_a,
                }
            )
        return rows

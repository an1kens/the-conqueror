from dataclasses import dataclass

from logic.economy import MIN_STABILITY_TO_INVADE, invasion_stability_ok
from logic.focused_simulation import FocusedSimulation
from logic.relationships import (
    ALLIED_MIN,
    FRIENDLY_MIN,
    HOSTILE_MAX,
    WAR_MAX,
    can_invade,
    get_relationship,
    relationship_band,
)
from logic.us_support import allied_partners
from logic.war import find_war


@dataclass
class ActionResult:
    success: bool
    message: str


class FocusedPlayer:
    def __init__(self, simulation: FocusedSimulation):
        self.simulation = simulation

    @property
    def state(self):
        return self.simulation.state

    @property
    def country(self):
        name = self.state.player_country
        return self.state.get(name) if name else None

    def orders_remaining(self) -> int:
        return max(
            0, self.simulation.max_player_actions - self.simulation.actions_this_turn
        )

    def targets(self) -> list[str]:
        if not self.country:
            return []
        return [
            c.name
            for c in self.state.countries
            if c.name != self.country.name
            and c.name not in self.state.eliminated_countries
        ]

    def strategic_hint(self) -> str:
        if not self.country:
            return ""
        p = self.country
        hints = [
            f"<b>{self.orders_remaining()}</b> order(s) left this week "
            f"(max <b>{self.simulation.max_invasions_per_turn}</b> invasion)."
        ]
        rivals = self.state.scenario.get("primary_rivals", ("Pakistan", "China"))
        rival_rels = []
        for foe in rivals:
            if foe in self.targets():
                rival_rels.append((foe, get_relationship(p, foe)))
        at_war_rivals = [f for f, rel in rival_rels if rel <= WAR_MAX]
        hostile_rivals = [f for f, rel in rival_rels if rel <= HOSTILE_MAX]
        if len(at_war_rivals) >= 2:
            hints.append(
                f"<b>Multi-front war</b> — fighting {', '.join(at_war_rivals)}. "
                "Finish one rival before pushing both."
            )
        elif len(hostile_rivals) >= 2 and at_war_rivals:
            other = [f for f in hostile_rivals if f not in at_war_rivals]
            if other:
                hints.append(
                    f"<b>{at_war_rivals[0]}</b> at war while <b>{other[0]}</b> remains hostile — "
                    "consider one front at a time."
                )

        for foe in rivals:
            if foe not in self.targets():
                continue
            rel = get_relationship(p, foe)
            band = relationship_band(rel)
            if band == "at_war":
                t = self.state.get(foe)
                first = t.territories[0] if t.territories else "?"
                hints.append(
                    f"At war with {foe} — <b>Invade</b> to capture {first}."
                )
            elif rel > WAR_MAX:
                need = WAR_MAX - rel
                hints.append(
                    f"{foe} is {band} ({rel}). ~{max(1, need // 12)} pressure "
                    f"actions to reach open war."
                )
        ally = self.state.scenario.get("ally_country", "United States")
        ally_rel = get_relationship(p, ally)
        if ally_rel >= 80:
            hints.append(
                f"{ally} alliance: biweekly aid <b>only while at war</b>. "
                "Ceasefire pauses allied shipments."
            )
        elif ally_rel >= 40:
            hints.append(
                f"{ally} friendly ({ally_rel}) — ally for wartime aid."
            )
        if not invasion_stability_ok(p):
            hints.append(
                f"Stability {p.stability} — need {MIN_STABILITY_TO_INVADE}+ to invade. "
                f"Use <b>Rebuild</b> (+10) or <b>Peace</b> ceasefire (+8); talks (+3) if not at war."
            )
        if p.economic_power < 25:
            hints.append(
                f"Economy weak ({p.economic_power}) — recovery and military cap are reduced."
            )
        if p.military_strength < 50:
            hints.append(
                f"Military low ({p.military_strength}) — <b>Rebuild</b> or ceasefire to recover."
            )
        return "<br>".join(hints)

    def can_attack(self, target_name: str) -> tuple[bool, str]:
        if not self.country:
            return False, "No player."
        if self.simulation.invasions_this_turn >= self.simulation.max_invasions_per_turn:
            return False, "You already ordered an invasion this week."
        if not invasion_stability_ok(self.country):
            return False, (
                f"Stability too low ({self.country.stability}). "
                f"Need {MIN_STABILITY_TO_INVADE}+ to invade."
            )
        target = self.state.get(target_name)
        if not target.territories:
            return False, f"{target_name} has no territory to invade."
        rel = get_relationship(self.country, target_name)
        band = relationship_band(rel)
        if not can_invade(
            self.country, target, scenario=self.state.scenario
        ):
            if target.nuclear and rel > WAR_MAX:
                return False, (
                    f"Cannot invade {target_name} yet (relations {rel}). "
                    f"Use Pressure until 'at war' (below -80), then Invade."
                )
            if rel > HOSTILE_MAX:
                return False, (
                    f"Cannot invade {target_name} ({band}, {rel}). "
                    f"Relations must be hostile or at war first."
                )
            return False, (
                f"Military too weak ({self.country.military_strength}) vs "
                f"{target_name} ({target.military_strength}). "
                f"Need a stronger edge vs hostile non-nuclear rivals."
            )
        territory = target.territories[0]
        return True, f"Ready to invade — primary target: {territory}."

    def act(
        self,
        event_type: str,
        target_name: str,
        *,
        territory: str | None = None,
    ) -> ActionResult:
        if self.state.winner or self.state.loser:
            return ActionResult(False, "Game over.")
        if self.simulation.actions_this_turn >= self.simulation.max_player_actions:
            return ActionResult(
                False,
                f"You used all {self.simulation.max_player_actions} orders. Advance the week.",
            )

        rel = get_relationship(self.country, target_name)
        band = relationship_band(rel)
        ceasefire_note = ""

        if event_type == "attack":
            band = relationship_band(get_relationship(self.country, target_name))
            if band in ("friendly", "allied"):
                return ActionResult(
                    False,
                    f"Cannot invade {target_name} — relations are {band}. "
                    f"Invade locked until relations worsen.",
                )
            ok, msg = self.can_attack(target_name)
            if not ok:
                return ActionResult(False, msg)
        elif event_type == "peace":
            war = find_war(self.state.active_wars, self.country.name, target_name)
            if war and war.active:
                event_type = "ceasefire"
                pending = [
                    e.source
                    for e in self.simulation.events.events
                    if e.event_type == "attack"
                    and e.target == self.country.name
                    and e.source == target_name
                ]
                if pending:
                    ceasefire_note = (
                        f" {len(pending)} attack(s) from {target_name} may still "
                        f"resolve this week before the ceasefire holds."
                    )
            else:
                event_type = "negotiate"
                if band == "at_war":
                    return ActionResult(
                        False,
                        "Still at war — use Ceasefire (Peace) or keep fighting.",
                    )
        elif event_type == "ally":
            if target_name == self.country.name:
                return ActionResult(False, "Cannot ally with yourself.")
            if band == "at_war":
                return ActionResult(False, "Cannot ally while at war.")
            if rel < FRIENDLY_MIN:
                return ActionResult(
                    False,
                    f"Relations with {target_name} are {band} ({rel}). "
                    f"Need friendly (40+) to Ally.",
                )
            if rel >= ALLIED_MIN:
                return ActionResult(
                    False,
                    f"Already fully allied with {target_name} ({rel}). "
                    f"Aid scales with their military strength.",
                )
        elif event_type == "rearm":
            target_name = self.country.name

        attack_territory = territory if event_type == "attack" else None
        if attack_territory and attack_territory not in self.state.get(target_name).territories:
            attack_territory = None
        ok = self.simulation.queue_action(
            event_type,
            self.country.name,
            target_name,
            counts_as_player_order=True,
            territory=attack_territory,
        )
        if ok:
            self.simulation.actions_this_turn += 1
            if event_type == "attack":
                self.simulation.invasions_this_turn += 1
            remaining = self.orders_remaining()
            extra = ""
            if event_type == "attack":
                extra = " Expect a battle report with casualties on both sides."
            elif event_type == "sanction" and band == "at_war":
                extra = " (Wartime pressure only — use Invade to capture land.)"
            elif event_type == "ceasefire":
                extra = (
                    " Foe rebuilds military; allied aid pauses until you are fighting again."
                    f"{ceasefire_note}"
                )
            elif event_type == "ally":
                extra = f" Relations with {target_name} now {get_relationship(self.country, target_name)} (80+ unlocks wartime aid)."
            return ActionResult(
                True,
                f"Order {self.simulation.actions_this_turn}/"
                f"{self.simulation.max_player_actions}: {event_type} vs {target_name}. "
                f"{remaining} order(s) left.{extra}",
            )
        return ActionResult(False, "Could not queue action.")

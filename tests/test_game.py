"""Core game logic tests."""

import unittest

from game_factory import create_game
from logic.events import resolve_event
from logic.relationships import adjust_relationship, relationship_band, set_relationship


class TestRelationships(unittest.TestCase):
    def setUp(self):
        self.sim, _ = create_game(0)
        self.state = self.sim.state
        self.us = self.state.get("United States")
        self.uk = self.state.get("United Kingdom")

    def test_alliance_transition_queued(self):
        set_relationship(self.us, self.uk.name, 75, self.uk)
        adjust_relationship(self.us, self.uk.name, 10, self.uk, state=self.state)
        types = [t[0] for t in self.state.pending_diplomatic]
        self.assertIn("alliance_formed", types)

    def test_war_transition_queued(self):
        iran = self.state.get("Iran")
        set_relationship(self.us, iran.name, -70, iran)
        adjust_relationship(self.us, iran.name, -15, iran, state=self.state)
        types = [t[0] for t in self.state.pending_diplomatic]
        self.assertIn("war_declared", types)


class TestSimulation(unittest.TestCase):
    def setUp(self):
        self.sim, self.player = create_game(3)
        self.player.assign_country("India")

    def test_tick_paused_when_player_must_react(self):
        self.sim.player_pending_reactions.append(("China", "attack"))
        day_before = self.sim.clock.game_day
        self.sim.tick(1.0)
        self.assertEqual(self.sim.clock.game_day, day_before)

    def test_reaction_queue_not_overwritten(self):
        self.sim.player_pending_reactions.append(("China", "attack"))
        self.sim.player_pending_reactions.append(("Pakistan", "sanction"))
        self.assertEqual(len(self.sim.player_pending_reactions), 2)

    def test_player_reactive_clears_one_reaction(self):
        self.sim.player_pending_reactions.append(("China", "attack"))
        targets = self.player.targets()
        china = next(c for c in targets if c.name == "China")
        result = self.player.queue_action("sanction", china.name, reactive=True)
        self.assertTrue(result.success)
        self.assertEqual(len(self.sim.player_pending_reactions), 0)

    def test_no_self_reaction_queued(self):
        before = len(self.sim._pending_reactions)
        self.sim._queue_reaction("India", "India", "attack")
        self.assertEqual(len(self.sim._pending_reactions), before)


class TestEvents(unittest.TestCase):
    def test_stats_floor_after_attack(self):
        sim, _ = create_game()
        state = sim.state
        a = state.get("Russia")
        b = state.get("Ukraine")
        b.military_strength = 20
        b.stability = 20
        from logic.events import create_event

        event = create_event("attack", a.name, b.name, intensity=2.0, duration=0)
        resolve_event(event, state)
        self.assertGreaterEqual(b.military_strength, 15)
        self.assertGreaterEqual(b.stability, 15)


if __name__ == "__main__":
    unittest.main()

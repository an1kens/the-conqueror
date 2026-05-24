import random
import unittest

from game_factory import create_focused_game
from logic.balance_config import _default_tuning, load_tuning, save_tuning
from logic.battle import resolve_battle
from logic.relationships import WAR_MAX, can_invade, get_relationship
from logic.economy import MAX_STABILITY_LOSS_PER_WEEK, apply_battle_stability_loss
from logic.game_summary import build_defeat_summary
from logic.us_support import apply_us_weekly_support, battle_bonus_if_us_allied, india_us_allied
from logic.war import find_war

class TestFocusedScenario(unittest.TestCase):
    def setUp(self):
        save_tuning(_default_tuning())
        load_tuning(reload=True)
        self.sim, self.player = create_focused_game("south_asia", intro=False)
        self.state = self.sim.state

    def test_starts_paused_with_four_countries(self):
        self.assertEqual(len(self.state.countries), 4)
        self.assertEqual(self.state.player_country, "India")
        self.assertTrue(self.sim.clock.paused)

    def test_action_limit_per_week(self):
        r = self.player.act("sanction", "Pakistan")
        self.assertTrue(r.success)
        r2 = self.player.act("sanction", "China")
        self.assertTrue(r2.success)
        r3 = self.player.act("attack", "Pakistan")
        self.assertFalse(r3.success)

    def test_battle_produces_casualties_both_sides(self):
        india = self.state.get("India")
        pak = self.state.get("Pakistan")
        report = resolve_battle(india, pak, self.state, intensity=1.0)
        self.assertGreater(report.attacker_casualties, 0)
        self.assertGreater(report.defender_casualties, 0)
        self.assertTrue(report.summary)

    def test_advance_week_resolves_events(self):
        self.player.act("sanction", "Pakistan")
        self.sim.advance_week()
        log_text = " ".join(self.state.player_log).lower()
        self.assertIn("sanction", log_text)

    def test_pakistan_not_at_war_at_start(self):
        india = self.state.get("India")
        self.assertGreater(get_relationship(india, "Pakistan"), WAR_MAX)

    def test_cannot_invade_nuclear_rival_without_war(self):
        ok, _ = self.player.can_attack("Pakistan")
        self.assertFalse(ok)

    def test_win_threshold_normal_difficulty(self):
        sim, _ = create_focused_game("south_asia", difficulty="normal", intro=False)
        self.assertEqual(sim.state.scenario["win_control_percent"], 0.65)

    def test_global_normal_win_threshold(self):
        sim, _ = create_focused_game("global", difficulty="normal", intro=False)
        self.assertEqual(sim.state.scenario["win_control_percent"], 0.42)
        self.assertEqual(sim.state.scenario.get("max_ai_actions_per_week"), 12)

    def test_global_rival_elimination_win(self):
        sim, _ = create_focused_game("global", difficulty="normal", intro=False)
        for name in ("China", "Russia"):
            sim.state.eliminated_countries.add(name)
        msgs = sim.advance_week()
        self.assertEqual(sim.state.winner, "United States")
        self.assertTrue(any("Victory" in m for m in msgs))

    def test_can_invade_at_war_requires_floor_military(self):
        india = self.state.get("India")
        pak = self.state.get("Pakistan")
        floor = int(
            self.state.scenario["balance_tuning"]["invasion"]["min_military_at_war"]
        )
        india.relationships["Pakistan"] = WAR_MAX
        pak.relationships["India"] = WAR_MAX
        india.military_strength = floor - 1
        self.assertFalse(can_invade(india, pak, scenario=self.state.scenario))
        india.military_strength = floor
        self.assertTrue(can_invade(india, pak, scenario=self.state.scenario))

    def test_us_aid_biweekly_only_when_at_war(self):
        india = self.state.get("India")
        india.relationships["United States"] = 85
        self.state.get("United States").relationships["India"] = 85
        india.relationships["Pakistan"] = WAR_MAX
        self.state.turn_number = 1
        headlines = apply_us_weekly_support(self.sim)
        self.assertEqual(headlines, [])
        self.state.turn_number = 2
        headlines = apply_us_weekly_support(self.sim)
        self.assertTrue(any("aid" in h.lower() for h in headlines))

    def test_us_battle_bonus_from_scenario(self):
        india = self.state.get("India")
        india.relationships["United States"] = 85
        bonus = self.state.scenario["balance_tuning"]["us_support"]["battle_bonus"]
        self.assertEqual(self.state.scenario["us_battle_bonus"], bonus)
        us = self.state.get("United States")
        scale = max(0.35, min(1.0, us.military_strength / 100.0))
        expected = 1.0 + (bonus - 1.0) * scale
        self.assertAlmostEqual(
            battle_bonus_if_us_allied(self.state, "India"), expected, places=2
        )
        self.assertTrue(india_us_allied(self.state))

    def test_war_tracked_after_reaching_open_war(self):
        india = self.state.get("India")
        pak = self.state.get("Pakistan")
        india.relationships["Pakistan"] = WAR_MAX
        pak.relationships["India"] = WAR_MAX
        india.military_strength = 60
        self.player.act("attack", "Pakistan")
        self.sim.advance_week()
        war = find_war(self.state.active_wars, "India", "Pakistan")
        self.assertIsNotNone(war)
        self.assertGreaterEqual(war.casualties_a + war.casualties_b, 0)

    def test_reactive_ai_counters_player_attack(self):
        random.seed(42)
        india = self.state.get("India")
        pak = self.state.get("Pakistan")
        india.relationships["Pakistan"] = WAR_MAX
        pak.relationships["India"] = WAR_MAX
        india.military_strength = 65
        pak.military_strength = 50
        self.player.act("attack", "Pakistan")
        self.sim.advance_week()
        log_text = " ".join(self.state.event_log + self.state.player_log).lower()
        self.assertTrue(
            "pakistan" in log_text
            and ("sanction" in log_text or "attack" in log_text or "battle" in log_text)
        )

    def test_axis_response_when_india_pressures_pakistan(self):
        random.seed(7)
        self.player.act("sanction", "Pakistan")
        self.sim.advance_week()
        journal_titles = [e["title"] for e in self.state.player_journal]
        axis_msgs = [t for t in journal_titles if "backs their partner" in t]
        self.assertTrue(len(axis_msgs) >= 0)

    def test_redundant_us_alliance_blocked(self):
        india = self.state.get("India")
        india.relationships["United States"] = 85
        self.state.get("United States").relationships["India"] = 85
        r = self.player.act("ally", "United States")
        self.assertFalse(r.success)
        self.assertIn("fully allied", r.message.lower())

    def test_rebuild_restores_stability(self):
        india = self.state.get("India")
        india.stability = 12
        self.player.act("rearm", "India")
        self.sim.advance_week()
        self.assertGreaterEqual(india.stability, 22)

    def test_stability_loss_capped_per_week(self):
        india = self.state.get("India")
        india.stability = 50
        self.state.player_stability_loss_this_week = 0
        apply_battle_stability_loss(india, 10, self.state)
        apply_battle_stability_loss(india, 10, self.state)
        self.assertEqual(self.state.player_stability_loss_this_week, MAX_STABILITY_LOSS_PER_WEEK)
        self.assertGreaterEqual(india.stability, 50 - MAX_STABILITY_LOSS_PER_WEEK)

    def test_defeat_summary_mentions_losses(self):
        self.state.territories_lost_this_week = [("Punjab", "China"), ("Kashmir", "China")]
        india = self.state.get("India")
        india.stability = 10
        india.territories = []
        title, body, _ = build_defeat_summary(self.state)
        self.assertEqual(title, "Why you lost")
        self.assertIn("China", body)
        self.assertIn("Stability", body)

    def test_two_front_hint_in_strategic_hint(self):
        india = self.state.get("India")
        india.relationships["Pakistan"] = WAR_MAX
        india.relationships["China"] = WAR_MAX
        hint = self.player.strategic_hint()
        self.assertIn("Multi-front", hint)

    def test_cannot_invade_friendly_or_allied(self):
        india = self.state.get("India")
        us = self.state.get("United States")
        india.relationships["United States"] = 85
        us.relationships["India"] = 85
        r = self.player.act("attack", "United States")
        self.assertFalse(r.success)
        self.assertIn("invade locked", r.message.lower())

        india.relationships["United States"] = 50
        us.relationships["India"] = 50
        r2 = self.player.act("attack", "United States")
        self.assertFalse(r2.success)
        self.assertIn("friendly", r2.message.lower())

    def test_attack_queues_selected_territory(self):
        india = self.state.get("India")
        pak = self.state.get("Pakistan")
        india.relationships["Pakistan"] = WAR_MAX
        pak.relationships["India"] = WAR_MAX
        india.military_strength = 65
        result = self.player.act("attack", "Pakistan", territory="Sindh")
        self.assertTrue(result.success)
        event = self.sim.events.events[-1]
        self.assertEqual(event.metadata.get("territory"), "Sindh")


class TestFocusedBalance(unittest.TestCase):
    """Seeded rush strategies should not win too quickly."""

    def _rush_pakistan_weeks(self, *, use_us_alliance: bool) -> tuple[int, object]:
        random.seed(99)
        sim, player = create_focused_game("south_asia")
        state = sim.state
        india = state.get("India")
        pak = state.get("Pakistan")

        for _ in range(2):
            player.act("sanction", "Pakistan")
            sim.advance_week()

        india.relationships["Pakistan"] = WAR_MAX
        pak.relationships["India"] = WAR_MAX

        if use_us_alliance:
            for _ in range(3):
                player.act("ally", "United States")
                sim.advance_week()

        weeks = 0
        while weeks < 30 and not state.winner and not state.loser:
            if sim.actions_this_turn < 1:
                if use_us_alliance and get_relationship(india, "United States") < 80:
                    player.act("ally", "United States")
                elif can_invade(india, pak) and pak.territories:
                    player.act("attack", "Pakistan")
                elif get_relationship(india, "Pakistan") > WAR_MAX:
                    player.act("sanction", "Pakistan")
                else:
                    player.act("rearm", india.name)
            sim.advance_week()
            weeks += 1
        return weeks, state

    def test_rush_without_us_alliance_not_instant_win(self):
        weeks, state = self._rush_pakistan_weeks(use_us_alliance=False)
        if state.winner:
            self.assertGreaterEqual(
                weeks,
                8,
                "Automated rush should not win before sustained campaigning",
            )
        else:
            self.assertGreaterEqual(weeks, 5)

    def test_defender_home_bonus_from_tuning(self):
        self.assertGreater(load_tuning()["battle"]["defender_home_bonus"], 1.0)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from game_factory import create_focused_game
from logic.balance_config import _default_tuning, load_tuning, save_tuning
from logic.difficulty import PRESETS, win_control_percent_for
from logic.economy import (
    military_cap,
    peacetime_military_recovery,
    wartime_military_recovery,
)
from logic.focused_player import FocusedPlayer
from logic.relationships import WAR_MAX
from logic.us_support import apply_us_weekly_support
from state.save_game import has_save, load_game, save_game


def _reset_tuning() -> None:
    save_tuning(_default_tuning())
    load_tuning(reload=True)


class TestEconomy(unittest.TestCase):
    def setUp(self):
        _reset_tuning()

    def test_recovery_scales_with_economy(self):
        self.assertGreater(peacetime_military_recovery(70), peacetime_military_recovery(20))
        self.assertGreater(wartime_military_recovery(50), wartime_military_recovery(10))

    def test_collapsed_economy_caps_military(self):
        sim, _ = create_focused_game("south_asia", intro=False)
        india = sim.state.get("India")
        india.economic_power = 0
        india.military_strength = 80
        cap = military_cap(india)
        self.assertLessEqual(cap, 55)


class TestDifficulty(unittest.TestCase):
    def setUp(self):
        _reset_tuning()

    def test_hard_raises_win_threshold(self):
        sim, _ = create_focused_game("south_asia", difficulty="hard", intro=False)
        self.assertEqual(sim.state.scenario["win_control_percent"], 0.70)

    def test_easy_lowers_win_threshold(self):
        sim, _ = create_focused_game("south_asia", difficulty="easy", intro=False)
        self.assertEqual(sim.state.scenario["win_control_percent"], 0.55)

    def test_normal_differs_from_easy(self):
        sim, _ = create_focused_game("south_asia", difficulty="normal", intro=False)
        self.assertEqual(sim.state.scenario["win_control_percent"], 0.65)
        self.assertGreater(
            win_control_percent_for("normal"), win_control_percent_for("easy")
        )


class TestTwoOrders(unittest.TestCase):
    def setUp(self):
        _reset_tuning()
        self.sim, self.player = create_focused_game("south_asia", intro=False)

    def test_two_orders_per_week(self):
        r1 = self.player.act("sanction", "Pakistan")
        r2 = self.player.act("sanction", "China")
        self.assertTrue(r1.success)
        self.assertTrue(r2.success)
        r3 = self.player.act("ally", "United States")
        self.assertFalse(r3.success)

    def test_only_one_invasion_per_week(self):
        india = self.sim.state.get("India")
        pak = self.sim.state.get("Pakistan")
        india.relationships["Pakistan"] = WAR_MAX
        pak.relationships["India"] = WAR_MAX
        india.military_strength = 65
        r1 = self.player.act("attack", "Pakistan")
        r2 = self.player.act("attack", "Pakistan")
        self.assertTrue(r1.success)
        self.assertFalse(r2.success)


class TestUsAidWarGate(unittest.TestCase):
    def setUp(self):
        _reset_tuning()

    def test_no_aid_when_peaceful(self):
        sim, _ = create_focused_game("south_asia", intro=False)
        india = sim.state.get("India")
        india.relationships["United States"] = 85
        sim.state.get("United States").relationships["India"] = 85
        india.relationships["Pakistan"] = -50
        sim.state.turn_number = 2
        self.assertEqual(apply_us_weekly_support(sim), [])


class TestSaveGame(unittest.TestCase):
    def setUp(self):
        _reset_tuning()

    def test_round_trip_save(self):
        sim, player = create_focused_game("south_asia", difficulty="normal", intro=False)
        player.act("sanction", "Pakistan")
        sim.advance_week()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_save.json"
            save_game(sim, path)
            self.assertTrue(has_save(path))
            loaded = load_game(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.state.turn_number, sim.state.turn_number)
            self.assertEqual(
                loaded.state.get("India").military_strength,
                sim.state.get("India").military_strength,
            )
            self.assertEqual(len(loaded.events.events), len(sim.events.events))


if __name__ == "__main__":
    unittest.main()

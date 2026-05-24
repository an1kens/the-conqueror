import unittest
from unittest import mock

from analyst.recommender import analyze
from game_factory import create_focused_game
from logic.balance_config import _default_tuning, load_tuning, save_tuning
from logic.battle_odds import (
    estimate_invasion_win_percent,
    format_invasion_odds,
    invasion_odds_label,
)
from logic.win_progress import format_win_progress_line, win_progress


class TestWinProgress(unittest.TestCase):
    def setUp(self):
        self.sim, _ = create_focused_game("south_asia", intro=False)
        self.state = self.sim.state

    def test_starting_progress_three_of_nine(self):
        wp = win_progress(self.state)
        self.assertEqual(wp["owned"], 3)
        self.assertEqual(wp["total"], 9)
        self.assertEqual(wp["needed"], 6)
        self.assertEqual(wp["remaining"], 3)

    def test_format_line(self):
        line = format_win_progress_line(self.state)
        self.assertIn("3/9", line)
        self.assertIn("need 6", line)


class TestBattleOdds(unittest.TestCase):
    def setUp(self):
        self.sim, _ = create_focused_game("south_asia", intro=False)
        self.state = self.sim.state
        self.india = self.state.get("India")
        self.pak = self.state.get("Pakistan")

    def test_stronger_attacker_higher_odds(self):
        weak = estimate_invasion_win_percent(
            self.india, self.pak, self.state, territory="Sindh"
        )
        self.india.military_strength = 95
        strong = estimate_invasion_win_percent(
            self.india, self.pak, self.state, territory="Sindh"
        )
        self.assertGreater(strong, weak)

    def test_nuclear_blocked_before_war(self):
        line = format_invasion_odds(self.india, self.pak, self.state)
        self.assertIn("locked", line or "")

    def test_labels_cover_range(self):
        self.assertEqual(invasion_odds_label(70), "Favorable")
        self.assertEqual(invasion_odds_label(45), "Risky")


class TestAnalystTooHard(unittest.TestCase):
    def setUp(self):
        save_tuning(_default_tuning())
        load_tuning(reload=True)

    def test_low_win_rate_triggers_easier_tuning(self):
        sessions = [
            {
                "session_id": f"loss{i}",
                "outcome": "loss",
                "events": [
                    {
                        "type": "player_action",
                        "week": 1,
                        "action": "sanction",
                        "target": "Pakistan",
                    },
                    {"type": "session_end", "week": 5, "snapshot": {"turn": 5}},
                ],
            }
            for i in range(4)
        ]
        with mock.patch(
            "analyst.metrics.load_all_completed_sessions", return_value=sessions
        ):
            result = analyze()
        issues = [r["issue"] for r in result["recommendations"]]
        self.assertIn("too_hard", issues)
        self.assertIn("scenario", result["tuning_adjustments"])
        self.assertLess(
            result["tuning_adjustments"]["scenario"]["win_control_percent"],
            0.65,
        )


if __name__ == "__main__":
    unittest.main()

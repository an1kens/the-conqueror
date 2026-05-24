import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from analyst.metrics import aggregate_metrics, session_summary
from analyst.recommender import analyze
from analyst.telemetry import GameplayRecorder
from analyst.tuner import apply_analysis
from game_factory import create_focused_game
from logic.balance_config import _default_tuning, load_tuning, save_tuning


class TestVisionAnalyst(unittest.TestCase):
    def setUp(self):
        save_tuning(_default_tuning())
        load_tuning(reload=True)

    def test_recorder_writes_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "sessions"
            with mock.patch("analyst.telemetry.DATA_DIR", data_dir), mock.patch(
                "analyst.telemetry.INDEX_PATH", data_dir / "index.json"
            ):
                sim, _ = create_focused_game("south_asia")
                rec = GameplayRecorder()
                session_id = rec.start_session(sim.state)
                rec.record_player_action(
                    sim.state,
                    action="sanction",
                    target="Pakistan",
                    success=True,
                    message="ok",
                )
                rec.end_session(sim.state, outcome="win")
                path = data_dir / f"{session_id}.json"
                self.assertTrue(path.exists())
                data = json.loads(path.read_text())
                self.assertEqual(data["outcome"], "win")
                self.assertGreaterEqual(len(data["events"]), 2)

    def test_session_summary_detects_pressure(self):
        session = {
            "session_id": "abc",
            "outcome": "win",
            "events": [
                {
                    "type": "player_action",
                    "week": 1,
                    "action": "sanction",
                    "target": "Pakistan",
                },
                {
                    "type": "player_action",
                    "week": 3,
                    "action": "attack",
                    "target": "Pakistan",
                },
                {"type": "session_end", "week": 10, "snapshot": {"turn": 10}},
            ],
        }
        s = session_summary(session)
        self.assertTrue(s["pressure_before_attack"])

    def test_analyze_no_data(self):
        with mock.patch("analyst.metrics.load_all_completed_sessions", return_value=[]):
            result = analyze()
        self.assertEqual(result["status"], "no_data")

    def test_apply_analysis_dry_run(self):
        with mock.patch("analyst.tuner.save_tuning"):
            sessions = [
            {
                "session_id": "fast1",
                "outcome": "win",
                "events": [
                    {
                        "type": "player_action",
                        "week": 1,
                        "action": "attack",
                        "target": "Pakistan",
                    },
                    {"type": "session_end", "week": 8, "snapshot": {"turn": 8}},
                ],
            }
        ]
            with mock.patch(
                "analyst.metrics.load_all_completed_sessions", return_value=sessions
            ):
                outcome = apply_analysis(dry_run=True)
        self.assertIn("analysis", outcome)


if __name__ == "__main__":
    unittest.main()

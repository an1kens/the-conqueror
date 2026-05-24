"""Rule-based vision analyst — recommendations from session metrics."""

from __future__ import annotations

import json
from pathlib import Path

from analyst.metrics import aggregate_metrics
from logic.balance_config import load_tuning

VISION_PATH = Path(__file__).resolve().parent / "vision_spec.json"


def load_vision_spec() -> dict:
    with open(VISION_PATH) as f:
        return json.load(f)


def analyze(metrics: dict | None = None) -> dict:
    metrics = metrics if metrics is not None else aggregate_metrics()
    vision = load_vision_spec()
    goals = vision["focused_slice_goals"]
    tuning = load_tuning()

    if metrics.get("session_count", 0) == 0:
        return {
            "status": "no_data",
            "metrics": metrics,
            "recommendations": [],
            "tuning_adjustments": {},
            "narrative": metrics.get("message", "Play games in the app to collect data."),
        }

    recs: list[dict] = []
    adjustments: dict = {}

    avg_win = metrics.get("avg_weeks_to_win")
    if avg_win is not None:
        if avg_win < goals["target_weeks_to_win_easy_max"]:
            recs.append(
                {
                    "issue": "wins_too_fast",
                    "detail": f"Avg win at week {avg_win:.1f} (target {goals['target_weeks_to_win']}).",
                    "vision": "Campaign should feel earned, not a steamroll.",
                }
            )
            adjustments.setdefault("scenario", {})["win_control_percent"] = min(
                0.75, tuning["scenario"]["win_control_percent"] + 0.03
            )
            adjustments.setdefault("us_support", {})["mil_aid"] = max(
                1, tuning["us_support"]["mil_aid"] - 1
            )
            adjustments.setdefault("us_support", {})["battle_bonus"] = max(
                1.0, round(tuning["us_support"]["battle_bonus"] - 0.05, 2)
            )
            adjustments.setdefault("ai", {})["axis_response_chance"] = min(
                0.9, tuning["ai"]["axis_response_chance"] + 0.05
            )
        elif avg_win > goals["target_weeks_to_win_hard_min"]:
            recs.append(
                {
                    "issue": "wins_too_slow",
                    "detail": f"Avg win at week {avg_win:.1f} (target {goals['target_weeks_to_win']}).",
                    "vision": "Readable does not mean grindy — players should see progress.",
                }
            )
            adjustments.setdefault("scenario", {})["win_control_percent"] = max(
                0.55, tuning["scenario"]["win_control_percent"] - 0.02
            )
            adjustments.setdefault("us_support", {})["mil_aid"] = min(
                5, tuning["us_support"]["mil_aid"] + 1
            )

    us_wr = metrics.get("us_alliance_win_rate", 0)
    if us_wr > goals["us_alliance_win_rate_max"]:
        recs.append(
            {
                "issue": "us_alliance_dominates",
                "detail": f"{us_wr:.0%} of wins used US alliance.",
                "vision": "US should help, not be the only viable strategy.",
            }
        )
        adjustments.setdefault("us_support", {})["aid_interval_weeks"] = min(
            4, tuning["us_support"]["aid_interval_weeks"] + 1
        )
        adjustments.setdefault("us_support", {})["battle_bonus"] = max(
            1.0, round(tuning["us_support"]["battle_bonus"] - 0.05, 2)
        )

    attack_only = metrics.get("attack_only_win_rate", 0)
    if attack_only > goals["attack_only_win_rate_max"]:
        recs.append(
            {
                "issue": "skips_escalation",
                "detail": f"{attack_only:.0%} of wins never used pressure before invading.",
                "vision": "Nuclear rivals require pressure → at war → invade.",
            }
        )
        adjustments.setdefault("invasion", {})["min_military_at_war"] = min(
            55, tuning["invasion"]["min_military_at_war"] + 3
        )

    pressure_rate = metrics.get("pressure_before_attack_rate", 0)
    if pressure_rate < goals["pressure_before_war_rate_min"]:
        recs.append(
            {
                "issue": "low_pressure_usage",
                "detail": f"Only {pressure_rate:.0%} of games pressured before attacking.",
                "vision": "Relationships and timed escalation are core to the sim.",
            }
        )

    china_rate = metrics.get("avg_china_counter_signals", 0)
    if metrics["session_count"] >= 2 and china_rate < goals["china_counter_rate_min"]:
        recs.append(
            {
                "issue": "china_passive",
                "detail": f"Low China counter-activity ({china_rate:.1f} signals/game).",
                "vision": "Multi-front pressure via Pakistan–China axis.",
            }
        )
        adjustments.setdefault("ai", {})["rival_boost_china"] = min(
            0.75, tuning["ai"]["rival_boost_china"] + 0.05
        )
        adjustments.setdefault("ai", {})["axis_response_chance"] = min(
            0.9, tuning["ai"]["axis_response_chance"] + 0.05
        )

    win_rate = metrics.get("win_rate", 0)
    loss_rate = metrics.get("losses", 0) / metrics["session_count"]
    if metrics["session_count"] >= 3 and win_rate < 0.25:
        recs.append(
            {
                "issue": "too_hard",
                "detail": (
                    f"Win rate {win_rate:.0%} over {metrics['session_count']} games "
                    f"(target band allows ~{1 - goals['player_defeat_rate_min']:.0%}+ wins)."
                ),
                "vision": "Normal should be beatable in ~15–25 weeks with escalation play.",
            }
        )
        adjustments.setdefault("scenario", {})["win_control_percent"] = max(
            0.55, tuning["scenario"]["win_control_percent"] - 0.02
        )
        adjustments.setdefault("battle", {})["defender_home_bonus"] = max(
            1.0, round(tuning["battle"]["defender_home_bonus"] - 0.03, 2)
        )
        adjustments.setdefault("battle", {})["wartime_attrition_mult"] = max(
            1.0, round(tuning["battle"]["wartime_attrition_mult"] - 0.05, 2)
        )
        adjustments.setdefault("ai", {})["axis_response_chance"] = max(
            0.4, round(tuning["ai"]["axis_response_chance"] - 0.05, 2)
        )
        adjustments.setdefault("ai", {})["rival_boost_pakistan"] = max(
            0.35, round(tuning["ai"]["rival_boost_pakistan"] - 0.03, 2)
        )
        adjustments.setdefault("ai", {})["rival_boost_china"] = max(
            0.35, round(tuning["ai"]["rival_boost_china"] - 0.03, 2)
        )
        adjustments.setdefault("us_support", {})["mil_aid"] = min(
            6, tuning["us_support"]["mil_aid"] + 1
        )
        adjustments.setdefault("invasion", {})["min_military_at_war"] = max(
            35, tuning["invasion"]["min_military_at_war"] - 2
        )

    if loss_rate < goals["player_defeat_rate_min"]:
        recs.append(
            {
                "issue": "too_easy",
                "detail": f"Only {loss_rate:.0%} defeats across sessions.",
                "vision": "Risk of defeat makes conquest meaningful.",
            }
        )
        adjustments.setdefault("battle", {})["wartime_attrition_mult"] = min(
            1.6, tuning["battle"]["wartime_attrition_mult"] + 0.05
        )
        adjustments.setdefault("battle", {})["defender_home_bonus"] = min(
            1.25, tuning["battle"]["defender_home_bonus"] + 0.02
        )

    if not recs:
        recs.append(
            {
                "issue": "on_track",
                "detail": "Metrics sit near vision targets for the focused slice.",
                "vision": "Continue collecting sessions before large shifts.",
            }
        )

    narrative = _build_narrative(metrics, recs, vision)
    return {
        "status": "ok",
        "metrics": metrics,
        "recommendations": recs,
        "tuning_adjustments": adjustments,
        "narrative": narrative,
    }


def _build_narrative(metrics: dict, recs: list[dict], vision: dict) -> str:
    lines = [
        "# Vision Analyst Report",
        "",
        f"Sessions analyzed: **{metrics['session_count']}** "
        f"({metrics.get('wins', 0)} wins, {metrics.get('losses', 0)} losses)",
        "",
    ]
    if metrics.get("avg_weeks_to_win"):
        lines.append(
            f"- Avg weeks to win: **{metrics['avg_weeks_to_win']:.1f}** "
            f"(vision target {vision['focused_slice_goals']['target_weeks_to_win']})"
        )
    lines.append(f"- Win rate: **{metrics.get('win_rate', 0):.0%}**")
    lines.append(
        f"- US alliance in wins: **{metrics.get('us_alliance_win_rate', 0):.0%}**"
    )
    lines.append(
        f"- Pressure before first attack: **{metrics.get('pressure_before_attack_rate', 0):.0%}**"
    )
    lines.append("")
    lines.append("## Findings")
    for r in recs:
        lines.append(f"- **{r['issue']}**: {r['detail']}")
    lines.append("")
    lines.append("## Vision gaps still in play")
    for gap in vision.get("vision_gaps_to_close", []):
        lines.append(f"- {gap}")
    return "\n".join(lines)

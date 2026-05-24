"""Aggregate gameplay sessions into vision-alignment metrics."""

from __future__ import annotations

from analyst.telemetry import load_all_completed_sessions


def _player_actions(session: dict) -> list[dict]:
    return [e for e in session.get("events", []) if e["type"] == "player_action"]


def _week_events(session: dict) -> list[dict]:
    return [e for e in session.get("events", []) if e["type"] == "week_advanced"]


def session_summary(session: dict) -> dict:
    actions = _player_actions(session)
    weeks = _week_events(session)
    end = next((e for e in session.get("events", []) if e["type"] == "session_end"), None)
    final_snap = end["snapshot"] if end else (weeks[-1]["snapshot"] if weeks else {})

    attacks = [a for a in actions if a.get("action") == "attack"]
    sanctions = [a for a in actions if a.get("action") == "sanction"]
    us_allies = [a for a in actions if a.get("action") == "ally" and a.get("target") == "United States"]
    rearm = [a for a in actions if a.get("action") == "rearm"]

    first_attack_week = attacks[0]["week"] if attacks else None
    first_us_week = us_allies[0]["week"] if us_allies else None
    pressure_before_attack = False
    if attacks and sanctions:
        pressure_before_attack = any(s["week"] <= attacks[0]["week"] for s in sanctions)

    china_counters = 0
    for w in weeks:
        for entry in w.get("journal_tail", []):
            title = entry.get("title", "").lower()
            if "china" in title and (
                "backs" in title or "battle" in title or "pressure" in title
            ):
                china_counters += 1

    return {
        "session_id": session["session_id"],
        "outcome": session.get("outcome"),
        "weeks_played": final_snap.get("turn", len(weeks)),
        "final_control": final_snap.get("control_percent", 0),
        "attack_count": len(attacks),
        "sanction_count": len(sanctions),
        "us_ally_count": len(us_allies),
        "rearm_count": len(rearm),
        "first_attack_week": first_attack_week,
        "first_us_week": first_us_week,
        "pressure_before_attack": pressure_before_attack,
        "used_us_alliance": len(us_allies) > 0,
        "attack_only": len(attacks) > 0 and len(sanctions) == 0,
        "china_counter_signals": china_counters,
    }


def aggregate_metrics(sessions: list[dict] | None = None) -> dict:
    sessions = sessions if sessions is not None else load_all_completed_sessions()
    summaries = [session_summary(s) for s in sessions]
    if not summaries:
        return {
            "session_count": 0,
            "summaries": [],
            "message": "No completed gameplay sessions yet. Play a game in the app first.",
        }

    wins = [s for s in summaries if s["outcome"] == "win"]
    losses = [s for s in summaries if s["outcome"] == "loss"]

    def avg(items, key):
        vals = [s[key] for s in items if s.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "session_count": len(summaries),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(summaries),
        "avg_weeks_to_win": avg(wins, "weeks_played"),
        "avg_weeks_all": avg(summaries, "weeks_played"),
        "us_alliance_win_rate": (
            len([s for s in wins if s["used_us_alliance"]]) / len(wins) if wins else 0
        ),
        "attack_only_win_rate": (
            len([s for s in wins if s["attack_only"]]) / len(wins) if wins else 0
        ),
        "pressure_before_attack_rate": (
            len([s for s in summaries if s["pressure_before_attack"]]) / len(summaries)
        ),
        "avg_first_us_week": avg(
            [s for s in summaries if s["first_us_week"]], "first_us_week"
        ),
        "avg_china_counter_signals": avg(summaries, "china_counter_signals"),
        "summaries": summaries,
    }

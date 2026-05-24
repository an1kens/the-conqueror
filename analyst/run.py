#!/usr/bin/env python3
"""Vision analyst CLI — read gameplay sessions and tune balance toward the original vision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyst.recommender import analyze
from analyst.telemetry import list_sessions, load_all_completed_sessions
from analyst.tuner import apply_analysis

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "analyst_reports"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze stored gameplay and adjust balance toward the original vision."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write bounded changes to scenarios/balance_tuning.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing tuning file",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List recorded gameplay sessions",
    )
    args = parser.parse_args()

    if args.list:
        for s in list_sessions():
            print(
                f"{s['id']}  outcome={s.get('outcome')}  "
                f"started={s.get('started_at')}"
            )
        return

    sessions = load_all_completed_sessions()
    print(f"Completed sessions: {len(sessions)}")

    if args.apply or args.dry_run:
        outcome = apply_analysis(dry_run=args.dry_run)
        analysis = outcome["analysis"]
    else:
        analysis = analyze()
        outcome = {"applied": False, "changes": []}

    print(analysis["narrative"])
    print()

    if analysis.get("tuning_adjustments"):
        print("Proposed tuning adjustments:")
        print(json.dumps(analysis["tuning_adjustments"], indent=2))
        print()

    if outcome.get("changes"):
        print("Applied changes:" if outcome.get("applied") else "Would apply:")
        for line in outcome["changes"]:
            print(f"  - {line}")
    elif not args.apply and not args.dry_run:
        print("Run with --apply to write tuning, or --dry-run to preview.")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "latest.json"
    with open(report_path, "w") as f:
        json.dump(analysis, f, indent=2)
        f.write("\n")
    md_path = REPORTS_DIR / "latest.md"
    md_path.write_text(analysis["narrative"] + "\n")
    prompt_path = REPORTS_DIR / "cursor_prompt.md"
    prompt_path.write_text(_cursor_prompt(analysis))
    print(f"\nReports written to {REPORTS_DIR}/")


def _cursor_prompt(analysis: dict) -> str:
    return f"""# Cursor: Vision gameplay review

You are tuning **The Conqueror** South Asia focused mode toward this vision:
- Relationships drive escalation (pressure → at war → invade for nuclear rivals)
- Timed weekly resolution, not instant outcomes
- Personality-driven AI with reactive counters and Pakistan–China axis
- US alliance helpful but not mandatory for victory
- Wins in ~15–25 weeks; meaningful defeat risk

## Latest metrics
```json
{json.dumps({k: v for k, v in analysis.get("metrics", {}).items() if k != "summaries"}, indent=2)}
```

## Analyst findings
{chr(10).join(f"- {r['issue']}: {r['detail']}" for r in analysis.get("recommendations", []))}

## Suggested code/data focus
- `scenarios/balance_tuning.json` (auto-tuned knobs)
- `logic/focused_simulation.py` (AI aggression, reactions)
- `logic/us_support.py` (alliance power)
- `analyst/vision_spec.json` (targets)

Read `data/gameplay_sessions/*.json` for raw player action timelines.
Proposed tuning deltas:
```json
{json.dumps(analysis.get("tuning_adjustments", {}), indent=2)}
```
"""


if __name__ == "__main__":
    main()

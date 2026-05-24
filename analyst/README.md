# Vision Analyst

Sidecar system that learns from your **in-app gameplay** and nudges balance toward the original Conqueror vision.

## What it does

1. **Records** every order, week advance, and end state while you play (`python app.py`).
2. **Analyzes** completed sessions against targets in `analyst/vision_spec.json`.
3. **Tunes** bounded knobs in `scenarios/balance_tuning.json` (win %, US aid, AI aggression, battle cost, etc.).
4. **Writes reports** to `data/analyst_reports/latest.md` and `cursor_prompt.md` for Cursor review.

New games automatically load the latest tuning.

## In the app

- Gameplay is recorded silently each session.
- On **win/loss**, the analyst runs in the background and may update tuning.
- Click **Vision analyst** anytime to re-run analysis manually.

## CLI

```bash
# List recorded sessions
python3 -m analyst.run --list

# Report only (no file changes)
python3 -m analyst.run

# Preview tuning changes
python3 -m analyst.run --dry-run

# Apply bounded balance updates
python3 -m analyst.run --apply
```

## Cursor workflow

After several playtests, open `data/analyst_reports/cursor_prompt.md` in chat and ask the agent to refine AI, events, or UI using the raw sessions under `data/gameplay_sessions/`.

## Vision targets (focused slice)

- Wins in roughly **15–25 weeks**
- **US alliance** helpful but not required for most wins
- **Pressure before invade** on nuclear rivals
- **Pakistan–China axis** counters India
- Meaningful **defeat risk**

Adjust targets in `analyst/vision_spec.json`; the rule engine will follow on the next `--apply`.

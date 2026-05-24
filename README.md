# The Conqueror

Geopolitical strategy simulation in Python.

## Play (recommended)

**Global Conquest** — turn-based world campaign (default):

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8080 → read the **3-step onboarding**, pick **scenario** (Global is default), **nation**, and **difficulty**, then **Start game**.

An alternate **South Asia Flashpoint** scenario (4 powers, regional map) is available on the start screen.

### How a week works

1. **Click a territory** on the geo map (or choose a rival in the sidebar).
2. Queue up to **two orders** per week (**one invasion** max): Invade, Pressure, Peace, Rebuild, Ally.
3. Click **Advance week** in the header (auto-saves to `save.json`).
4. **Intelligence feeds** at the top show your orders, battles, and threats (world wire on the left).

### Difficulty (Global — normal)

- **Easy** — 38% world map control, slower AI, stronger allied aid.
- **Normal** — 42% map control (recommended).
- **Hard** — 48% map control, tougher rivals.

South Asia uses higher thresholds (55% / 65% / 70%). The header shows territory progress (e.g. `3/63 · need 27 for 42% win`). Selecting a rival territory shows **invasion odds** before you queue Invade.

### Victory & defeat

- **Win (Global):** Control enough world territory (see difficulty), **or** eliminate **China and Russia**.
- **Win (South Asia):** Control enough regional territory, **or** eliminate Pakistan and China.
- **Lose:** Lose all your territories.

### Economy & diplomacy

- Military **recovery scales with economy**; collapsed economy caps military strength.
- **Ceasefire** lets foes rebuild; **allied aid only flows while you are at war**.
- **Ally** targets a friendly selected power, or your scenario’s default ally (UK in Global, US in South Asia).
- Nuclear rivals: use **Pressure** until relations are **at war**, then **Invade**.

### Why this mode exists

The old 21-country real-time mode was too fast and hard to follow. The focused turn-based UI is built to be **readable and conclusive**.

## Console (legacy 21-country mode)

```bash
python main.py
```

## Vision analyst (learns from your play)

While you play in the app, sessions are saved under `data/gameplay_sessions/`. On win/loss, a sidecar analyzer compares your games to `analyst/vision_spec.json` and can adjust `scenarios/balance_tuning.json` within safe bounds.

```bash
python3 -m analyst.run --list    # sessions
python3 -m analyst.run           # report
python3 -m analyst.run --apply   # apply tuning
```

See [analyst/README.md](analyst/README.md).

## Tests

```bash
python3 -m unittest discover tests -v
```

## Architecture

```
State → Logic → Display
```

- `scenarios/` — focused scenario data (`global.json`, `south_asia.json`)
- `logic/focused_simulation.py` — turn-based week advance
- `logic/difficulty.py` — per-scenario difficulty presets
- `logic/battle.py` — casualties both sides
- `logic/war.py` — wars, ceasefire, death tolls
- `display/focused_ui.py` — map-first NiceGUI (Plotly geo + flags)
- `display/south_asia_map.py` — territory markers & country borders
- `scenarios/global_territory_map.json` — world lat/lon & flag assets

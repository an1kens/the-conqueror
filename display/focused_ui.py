"""Single-screen map UI — compact header, map + command column, top toasts."""

from __future__ import annotations

import threading

from nicegui import ui

from analyst.recommender import analyze
from analyst.telemetry import GameplayRecorder
from analyst.tuner import apply_analysis
from display.notification_stack import INTELLIGENCE_CSS, NotificationStack
from display.south_asia_map import (
    build_owner_stylesheet,
    build_scenario_map,
    country_color,
    load_map_data,
    map_file_for_state,
    owner_css_class,
    parse_plotly_territory_click,
    territory_owner_country,
)
from game_factory import create_focused_game
from logic.battle_odds import format_invasion_odds
from logic.difficulty import (
    DEFAULT_DIFFICULTY,
    DEFAULT_SCENARIO_ID,
    SCENARIO_LABELS,
    win_control_percent_for,
)
from state.save_game import save_game
from logic.focused_player import FocusedPlayer
from logic.focused_simulation import FocusedSimulation
from logic.relationships import ALLIED_MIN, FRIENDLY_MIN, get_relationship, relationship_band
from logic.scoring import compute_score, save_run
from logic.economy import MIN_STABILITY_TO_INVADE, invasion_stability_ok
from logic.us_support import allied_partners, india_us_allied
from logic.win_progress import format_win_progress_line, win_progress

DEFAULT_SCENARIO = DEFAULT_SCENARIO_ID


def _format_pending_orders(sim: FocusedSimulation) -> str:
    player = sim.state.player_country
    if not player:
        return ""
    labels = {
        "attack": "Invade",
        "sanction": "Pressure",
        "negotiate": "Peace talks",
        "ceasefire": "Ceasefire",
        "ally": "Ally",
        "rearm": "Rebuild",
    }
    lines = []
    for event in sim.events.events:
        if event.source != player:
            continue
        action = labels.get(event.event_type, event.event_type)
        terr = event.metadata.get("territory")
        suffix = f" → {terr}" if terr else ""
        lines.append(f"{action} vs {event.target}{suffix}")
    return lines

COUNTRY_SHORT = {
    "United States": "USA",
    "United Kingdom": "UK",
    "China": "China",
    "Russia": "Russia",
    "India": "India",
    "France": "France",
    "Germany": "Germany",
    "Japan": "Japan",
    "South Korea": "Korea",
    "Israel": "Israel",
    "Pakistan": "Pakistan",
    "Iran": "Iran",
    "Saudi Arabia": "Saudi",
    "Turkey": "Turkey",
    "Brazil": "Brazil",
    "North Korea": "N.Korea",
    "Australia": "Australia",
    "Ukraine": "Ukraine",
    "South Africa": "S.Africa",
    "Indonesia": "Indonesia",
    "Argentina": "Argentina",
}


def _country_label(name: str, scenario: dict | None = None) -> str:
    if scenario:
        if name == scenario.get("ally_country"):
            return scenario.get("ally_short") or COUNTRY_SHORT.get(name, name[:6])
        for rival in scenario.get("primary_rivals", []):
            if name == rival:
                return COUNTRY_SHORT.get(name, name[:6])
    return COUNTRY_SHORT.get(name, name[:8])


SELECT_PROPS = 'dense outlined options-dense popup-content-class="tc-select-menu"'

VIEWPORT_CSS = """
<style>
html, body {
  margin: 0;
  min-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}
.nicegui-content {
  padding: 0 !important;
  max-width: 100% !important;
  overflow: visible !important;
}
/* Quasar menus must sit above map/plotly and not be clipped by panels */
.tc-select-menu, .q-menu, .q-dialog {
  z-index: 10050 !important;
}
.q-menu .q-item { min-height: 40px; }
.game-viewport {
  min-height: 100vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(160deg, #1e3a5f 0%, #0f2744 40%, #0c1929 100%);
  overflow-x: hidden;
  overflow-y: auto;
  box-sizing: border-box;
}
.game-header {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(90deg, #2563eb 0%, #1d4ed8 50%, #1e40af 100%);
  border-bottom: 2px solid #fbbf24;
  flex-wrap: wrap;
  row-gap: 8px;
  box-shadow: 0 2px 16px rgba(37, 99, 235, 0.4);
}
.game-header .title {
  font-size: 1.2rem; font-weight: 900; color: #fff;
  text-shadow: 0 1px 3px rgba(0,0,0,0.3);
  flex-shrink: 0;
}
.game-header .status-pill {
  font-size: 12px; color: #e0f2fe; font-weight: 600;
  flex: 1 1 180px; min-width: 0;
  line-height: 1.45;
}
.game-header .phase-pill {
  font-size: 11px; font-weight: 800; letter-spacing: 0.06em;
  text-transform: uppercase; color: #1e3a8a;
  background: #fcd34d; padding: 5px 12px;
  border-radius: 8px; flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.game-header .header-actions {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.win-progress-wrap {
  width: 100%; flex-basis: 100%;
  display: flex; flex-direction: column; gap: 4px;
  padding: 6px 14px 8px;
}
.win-progress-text {
  font-size: 12px; font-weight: 700; color: #fef9c3;
  letter-spacing: 0.02em; line-height: 1.4;
}
.game-main {
  flex: 1 1 auto;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 14px 20px;
  overflow: visible;
  min-height: 420px;
}
.map-zone {
  flex: 1 1 55%;
  min-width: 0;
  min-height: 300px;
  max-height: min(520px, 55vh);
  display: flex;
  flex-direction: column;
  border: 2px solid #38bdf8;
  border-radius: 12px;
  overflow: hidden;
  background: #1e4976;
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.2);
  position: relative;
  z-index: 1;
}
.map-zone .plotly-parent {
  flex: 1 1 auto;
  min-height: 240px;
  width: 100%;
  position: relative;
  pointer-events: auto;
}
.map-zone .plotly-parent > div {
  width: 100% !important;
  height: 100% !important;
  min-height: 240px !important;
}
.command-panel {
  flex: 0 0 320px;
  width: 320px;
  max-width: 44vw;
  min-width: 260px;
  position: relative;
  z-index: 20;
  overflow: visible;
  pointer-events: auto;
}
.command-panel-scroll {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: min(72vh, calc(100vh - 240px));
  overflow-y: auto;
  overflow-x: visible;
  padding-right: 6px;
  padding-bottom: 16px;
  -webkit-overflow-scrolling: touch;
}
.command-panel-scroll::-webkit-scrollbar { width: 8px; }
.command-panel-scroll::-webkit-scrollbar-thumb {
  background: #94a3b8; border-radius: 4px;
}
.select-field { position: relative; z-index: 40; width: 100%; }
.terr-scroll {
  max-height: 280px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 2px;
}
@media (max-width: 900px) {
  .game-main {
    flex-direction: column;
    min-height: auto;
  }
  .map-zone {
    flex: 0 0 auto;
    width: 100%;
    max-height: 42vh;
    min-height: 260px;
  }
  .command-panel {
    flex: 0 0 auto;
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }
  .command-panel-scroll {
    max-height: none;
    overflow-y: visible;
  }
  .intel-dual { flex-direction: column; }
}
.start-overlay.hidden {
  display: none !important;
  pointer-events: none !important;
  visibility: hidden !important;
  z-index: -1 !important;
}
.start-overlay {
  pointer-events: auto;
  z-index: 2000;
}
.game-viewport.game-blocked {
  pointer-events: none;
}
.game-viewport.game-blocked .start-overlay {
  pointer-events: auto;
}
.panel-block {
  background: linear-gradient(145deg, #f8fafc 0%, #e2e8f0 100%);
  border: 2px solid #94a3b8;
  border-radius: 12px; padding: 14px;
  color: #1e293b;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  flex-shrink: 0;
}
.panel-block .text-gray-400 { color: #475569 !important; }
.panel-title {
  font-size: 1.05rem; font-weight: 800; color: #0f172a !important;
  line-height: 1.35; margin-bottom: 4px;
  word-break: break-word;
}
.panel-label {
  font-size: 11px; font-weight: 700; color: #475569 !important;
  text-transform: uppercase; letter-spacing: 0.05em;
  margin-bottom: 6px; display: block;
}
.panel-detail { margin-top: 4px; }
.terr-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
}
.map-legend {
  display: flex; flex-wrap: wrap; gap: 4px 8px;
  padding: 6px 10px; font-size: 10px; font-weight: 700;
  background: rgba(15, 39, 68, 0.85); color: #e2e8f0;
  border-top: 1px solid rgba(148, 163, 184, 0.35);
}
.map-legend span {
  display: inline-flex; align-items: center; gap: 4px;
}
.map-legend i {
  display: inline-block; width: 10px; height: 10px;
  border-radius: 2px; border: 1px solid rgba(255,255,255,0.35);
}
.flag-row { display: flex; flex-wrap: wrap; gap: 5px; }
.stat-line { font-size: 13px; color: #334155; line-height: 1.5; font-weight: 500; }
.stat-line b { color: #0f172a; font-weight: 800; }
.odds-line {
  font-size: 12px; color: #b45309; font-weight: 700;
  background: #fffbeb; padding: 6px 8px; border-radius: 8px; margin-top: 6px;
  border: 1px solid #fcd34d;
}
.ally-line {
  font-size: 13px; color: #1e3a8a; line-height: 1.4; font-weight: 600;
  background: #dbeafe; padding: 6px 8px; border-radius: 8px; margin-top: 6px;
  border: 1px solid #93c5fd;
}
.flag-btn { color: #1e293b !important; font-weight: 700 !important; }
.flag-btn.selected { outline: 2px solid #f59e0b !important; }
.action-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  margin-top: 10px;
}
.action-grid .q-btn {
  min-height: 44px !important;
  font-size: 13px !important;
  pointer-events: auto !important;
}
.panel-block .q-btn { pointer-events: auto !important; }
.invade-locked-btn {
  background: #e2e8f0 !important; color: #64748b !important;
  opacity: 1 !important;
}
.locked-line {
  font-size: 12px; color: #64748b; font-weight: 700;
  background: #f1f5f9; padding: 8px 10px; border-radius: 8px;
  margin-top: 8px; border: 1px solid #cbd5e1; line-height: 1.4;
}
.hint-box {
  font-size: 12px; color: #334155; line-height: 1.5;
  background: #f8fafc; padding: 10px; border-radius: 8px;
  margin-top: 8px; border: 1px solid #cbd5e1;
}
.hint-box b { color: #0f172a; }
.start-overlay {
  position: fixed; inset: 0; z-index: 2000;
  display: flex; align-items: center; justify-content: center;
  background: rgba(12, 25, 41, 0.88);
  backdrop-filter: blur(6px);
}
.start-card {
  width: min(520px, 94vw);
  max-height: 90vh; overflow-y: auto;
  background: linear-gradient(160deg, #f8fafc 0%, #e2e8f0 100%);
  border: 3px solid #fbbf24;
  border-radius: 16px;
  padding: 24px 28px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.45);
}
.start-card h2 { margin: 0 0 8px; color: #0f172a !important; font-size: 1.5rem; }
.start-card .subtitle { color: #475569 !important; font-size: 14px; margin-bottom: 16px; }
.start-card .start-label {
  color: #334155 !important; font-size: 14px; font-weight: 700;
}
.start-overlay .q-field__native,
.start-overlay .q-field__label,
.start-overlay .q-item__label,
.start-overlay .q-field__input,
.start-overlay .nicegui-label {
  color: #0f172a !important;
}
.start-overlay .q-field--outlined .q-field__control {
  background: #fff !important;
}
.start-overlay .q-field__native,
.start-overlay .q-field__append,
.start-overlay .q-select__dropdown-icon {
  color: #0f172a !important;
}
.onboard-step {
  display: flex; gap: 12px; align-items: flex-start;
  padding: 10px 0; border-bottom: 1px solid #cbd5e1;
}
.onboard-step:last-of-type { border-bottom: none; }
.step-num {
  flex-shrink: 0; width: 28px; height: 28px;
  background: #2563eb; color: #fff; font-weight: 800;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 14px;
}
.step-body { font-size: 13px; color: #334155; line-height: 1.45; }
.step-body b { color: #0f172a; }
</style>
"""

def bootstrap_balance_from_sessions() -> None:
    """Apply analyst tuning when recent sessions show very low win rate."""
    result = analyze()
    if result.get("status") != "ok":
        return
    metrics = result["metrics"]
    if metrics.get("session_count", 0) < 3:
        return
    if metrics.get("win_rate", 1) >= 0.25:
        return
    if result.get("tuning_adjustments"):
        apply_analysis()


class FocusedUI:
    def __init__(self) -> None:
        self.sim: FocusedSimulation | None = None
        self.player: FocusedPlayer | None = None
        self.recorder = GameplayRecorder()
        self.difficulty: str = DEFAULT_DIFFICULTY
        self.scenario_id: str = DEFAULT_SCENARIO
        self.selected_territory: str | None = None
        self.selected_country: str | None = None
        self._chosen_country: str = "United States"
        self._terr_chip_container = None
        self._map_legend = None
        self._country_picker = None
        self.notifications = NotificationStack(max_visible=6, wire_max_visible=2)
        self._territory_buttons: dict[str, ui.button] = {}
        self._action_buttons: list = []
        self._invade_btn = None
        self._advance_btn = None
        self._hint_line = None
        self.status_label = None
        self.phase_label = None
        self.win_progress_label = None
        self.win_progress_bar = None
        self.territory_title = None
        self.territory_detail = None
        self.ally_panel = None
        self.stat_line = None
        self.map_plot = None
        self._ui_ready = False
        self._start_overlay = None
        self._difficulty_select = None
        self._country_select = None
        self._scenario_select = None
        self._start_desc = None
        self._orders_line = None
        self._ally_btn = None
        self._unused_orders_dialog = None
        self._game_viewport = None

    def start(
        self,
        difficulty: str | None = None,
        player_country: str | None = None,
        scenario_id: str | None = None,
    ) -> None:
        if difficulty:
            self.difficulty = difficulty
        if player_country:
            self._chosen_country = player_country
        if scenario_id:
            self.scenario_id = scenario_id
        self.sim, self.player = create_focused_game(
            self.scenario_id,
            difficulty=self.difficulty,
            player_country=self._chosen_country,
        )
        self.recorder.start_session(self.sim.state)
        self.selected_territory = None
        self.selected_country = self.sim.state.player_country
        self.notifications.reset()
        if self._country_picker:
            opts = {c.name: c.name for c in self.sim.state.countries}
            self._country_picker.set_options(
                opts, value=self.sim.state.player_country
            )
        self._hide_start_screen()
        self.refresh()

    def _hide_start_screen(self) -> None:
        if self._start_overlay is not None:
            self._start_overlay.classes(add="hidden")
        if self._game_viewport is not None:
            self._game_viewport.classes(remove="game-blocked")
        ui.timer(0.15, self._resize_map, once=True)

    def _show_start_screen(self) -> None:
        self.sim = None
        self.player = None
        self.selected_territory = None
        self.selected_country = None
        self.notifications.reset()
        if self._start_overlay is not None:
            self._start_overlay.classes(remove="hidden")
        if self._game_viewport is not None:
            self._game_viewport.classes(add="game-blocked")
        self._set_controls_enabled(False)

    def _resize_map(self) -> None:
        """Refresh map after overlay closes so Plotly has real dimensions."""
        if not self.sim or not self.map_plot:
            return
        try:
            fig = build_scenario_map(
                self.sim.state, selected_territory=self.selected_territory
            )
            fig.update_layout(height=400, autosize=True)
            self.map_plot.update_figure(fig)
        except Exception:
            pass

    def refresh(self) -> None:
        if not self.sim or not self.player or not self._ui_ready:
            return
        state, p = self.sim.state, self.player.country
        wp = win_progress(state)

        player_name = state.player_country or "—"
        self.status_label.set_text(
            f"Week {state.turn_number} · {player_name} · "
            f"{wp['control_percent']}% world · "
            f"Orders {self.sim.actions_this_turn}/{self.sim.max_player_actions} · "
            f"{self.difficulty.title()}"
        )
        self.win_progress_label.set_text(format_win_progress_line(state))
        bar_value = (
            min(1.0, wp["owned"] / wp["needed"]) if wp["needed"] else 1.0
        )
        self.win_progress_bar.value = bar_value

        if state.winner:
            self.phase_label.set_text("Victory")
        elif state.loser:
            self.phase_label.set_text("Defeat")
        elif self.sim.actions_this_turn < self.sim.max_player_actions:
            self.phase_label.set_text("Your move")
        else:
            self.phase_label.set_text("Advance week")

        if p and self.stat_line:
            stab_warn = ""
            if not invasion_stability_ok(p):
                stab_warn = (
                    f"<div class='odds-line' style='margin-top:6px'>"
                    f"Stability {p.stability} — cannot invade (need {MIN_STABILITY_TO_INVADE}+). "
                    f"<b>Rebuild</b> +10 or <b>Peace</b> ceasefire +8; stop fighting on two fronts."
                    f"</div>"
                )
            self.stat_line.set_content(
                f"<div class='stat-line'>"
                f"<b>Mil</b> {p.military_strength} · <b>Eco</b> {p.economic_power} · "
                f"<b>Stab</b> {p.stability}</div>{stab_warn}"
            )
            self._refresh_ally_panel(state, p)

        if self.map_plot is not None:
            fig = build_scenario_map(
                state, selected_territory=self.selected_territory
            )
            fig.update_layout(height=400, autosize=True)
            self.map_plot.update_figure(fig)

        self._refresh_territory_panel(state)
        self._rebuild_territory_chips(state)
        self._update_territory_button_styles(state)
        self._update_map_legend(state)
        self.notifications.sync_journal(state.player_journal)
        self._set_controls_enabled(not (state.winner or state.loser))
        self._update_invade_button()
        self._update_ally_button()
        self._refresh_orders_panel()
        if self._hint_line and self.player:
            hint = self.player.strategic_hint()
            self._hint_line.set_content(
                f"<div class='hint-box'>{hint}</div>" if hint else ""
            )

    def _invade_locked_state_for(self, target: str) -> tuple[bool, str]:
        if not self.player or not self.player.country or not target:
            return False, ""
        if target == self.sim.state.player_country:
            return True, "Cannot invade your own territory"
        rel = get_relationship(self.player.country, target)
        band = relationship_band(rel)
        if band in ("friendly", "allied") or rel >= FRIENDLY_MIN:
            return True, f"{target} is {band} ({rel}) — invade locked"
        return False, ""

    def _invade_target(self) -> str | None:
        if not self.sim:
            return None
        return self._action_target()

    def _invade_locked_state(self) -> tuple[bool, str]:
        """Return (locked, reason) for the current invasion target."""
        if not self.sim or not self.player or not self.player.country:
            return True, ""
        target = self._invade_target()
        if not target:
            return False, ""
        return self._invade_locked_state_for(target)

    def _update_invade_button(self) -> None:
        if self._invade_btn is None:
            return
        locked, reason = self._invade_locked_state()
        if locked:
            self._invade_btn.set_text("Invade locked")
            self._invade_btn.disable()
            self._invade_btn.props("flat dense no-caps invade-locked-btn")
            if reason:
                self._invade_btn.tooltip(reason)
        else:
            self._invade_btn.set_text("Invade")
            self._invade_btn.enable()
            self._invade_btn.props("color=negative dense no-caps")
            self._invade_btn.tooltip("Invade selected rival territory")

    def _ally_target(self) -> tuple[str, str]:
        """Return (country_name, button_label) for the Ally action."""
        scenario = self.sim.state.scenario
        default_ally = scenario.get("ally_country", "United Kingdom")
        short = scenario.get("ally_short") or _country_label(default_ally, scenario)
        player = self.sim.state.player_country
        selected = self._action_target()
        if (
            selected
            and selected != player
            and self.player
            and self.player.country
        ):
            rel = get_relationship(self.player.country, selected)
            if FRIENDLY_MIN <= rel < ALLIED_MIN:
                label = _country_label(selected, scenario)
                return selected, f"Ally {label}"
        return default_ally, f"Ally {short}"

    def _update_ally_button(self) -> None:
        if self._ally_btn is None or not self.sim or not self.player:
            return
        _, label = self._ally_target()
        self._ally_btn.set_text(label)
        target, _ = self._ally_target()
        if self.player and self.player.country:
            rel = get_relationship(self.player.country, target)
            if rel >= ALLIED_MIN:
                self._ally_btn.disable()
                self._ally_btn.tooltip(f"Already allied with {target} ({rel})")
            else:
                self._ally_btn.enable()
                self._ally_btn.tooltip(
                    f"Improve relations with {target} (need friendly 40+)"
                )

    def _refresh_orders_panel(self) -> None:
        if self._orders_line is None or not self.sim:
            return
        pending = _format_pending_orders(self.sim)
        remaining = self.player.orders_remaining() if self.player else 0
        if pending:
            items = "<br>".join(f"• {line}" for line in pending)
            self._orders_line.set_content(
                f"<div class='hint-box'><b>This week</b> ({remaining} order(s) left)<br>"
                f"{items}<br><i>Resolves when you advance the week.</i></div>"
            )
        elif self.sim and not (self.sim.state.winner or self.sim.state.loser):
            self._orders_line.set_content(
                f"<div class='hint-box'><b>{remaining}</b> order(s) remaining this week.</div>"
                if remaining
                else "<div class='hint-box'>No orders queued — advance the week.</div>"
            )
        else:
            self._orders_line.set_content("")

    def _set_controls_enabled(self, enabled: bool) -> None:
        for i, btn in enumerate(self._action_buttons):
            if i == 0 and self._invade_btn is not None:
                continue
            if btn is self._ally_btn:
                continue
            (btn.enable if enabled else btn.disable)()
        if enabled:
            self._update_invade_button()
            self._update_ally_button()
        elif self._invade_btn is not None:
            self._invade_btn.disable()
        if self._ally_btn is not None:
            (self._ally_btn.enable if enabled else self._ally_btn.disable)()
        if self._advance_btn is not None:
            (self._advance_btn.enable if enabled else self._advance_btn.disable)()

    def _style_country_title(self, country_name: str | None, state) -> None:
        if not self.territory_title or not country_name or country_name == "—":
            return
        color = country_color(country_name, state=state)
        self.territory_title.style(f"color: {color}; font-weight: 800;")

    def _country_stats_html(self, state, country_name: str) -> str:
        c = state.get(country_name)
        data = load_map_data(map_file_for_state(state))
        emoji = data["flags"].get(country_name, {}).get("emoji", "")
        terrs = ", ".join(c.territories) if c.territories else "none"
        player = state.player_country
        rel_block = ""
        if player and country_name != player:
            sc = get_relationship(self.player.country, country_name)
            rel_block = (
                f"<br><b>Relations:</b> {relationship_band(sc)} ({sc})"
            )
        elif country_name == player:
            rel_block = "<br><i>Your nation</i>"
        nuclear = " · ☢ nuclear" if c.nuclear else ""
        return (
            f"<div class='stat-line'>"
            f"<b>{emoji} {country_name}</b>{nuclear}<br>"
            f"<b>Military</b> {c.military_strength} · "
            f"<b>Economy</b> {c.economic_power} · "
            f"<b>Stability</b> {c.stability}<br>"
            f"<b>Territories ({len(c.territories)}):</b> {terrs}"
            f"{rel_block}</div>"
        )

    def _refresh_ally_panel(self, state, p) -> None:
        if not self.ally_panel:
            return
        partners = allied_partners(state)
        if partners:
            names = ", ".join(
                f"{a.name} ({a.military_strength})" for a in partners[:4]
            )
            extra = f" +{len(partners) - 4} more" if len(partners) > 4 else ""
            self.ally_panel.set_content(
                f'<div class="ally-line">★ <b>Allied ({len(partners)})</b> — '
                f"{names}{extra}<br>Biweekly aid while you are at war "
                f"(strength scales with each ally\'s military)</div>"
            )
        else:
            self.ally_panel.set_content(
                '<div class="ally-line">Select a <b>friendly (40+)</b> power and '
                "use <b>Ally</b>. Full wartime aid unlocks at <b>80+</b>.</div>"
            )

    def _invasion_odds_html(self, state, owner: str) -> str:
        if not self.player or not self.player.country:
            return ""
        if owner in ("—", state.player_country):
            return ""
        attacker = self.player.country
        defender = state.get(owner)
        territory = self.selected_territory
        if territory and territory not in defender.territories:
            territory = defender.territories[0] if defender.territories else None
        line = format_invasion_odds(
            attacker, defender, state, territory=territory
        )
        if not line:
            return ""
        return f"<div class='odds-line'>⚔ {line}</div>"

    def _refresh_territory_panel(self, state) -> None:
        player = state.player_country
        odds_html = ""
        focus = self.selected_country or player
        if self.selected_territory:
            owner = territory_owner_country(state, self.selected_territory) or "—"
            if owner != "—":
                self.selected_country = owner
                focus = owner
            battle = ""
            if (
                state.battle_reports
                and state.battle_reports[-1].territory == self.selected_territory
            ):
                r = state.battle_reports[-1]
                battle = (
                    f"<div class='odds-line'>⚔ Week {r.turn}: {r.attacker} vs "
                    f"{r.defender}</div>"
                )
            locked_html = ""
            if focus and focus != "—" and focus != player:
                locked, lock_msg = self._invade_locked_state_for(focus)
                if locked:
                    locked_html = f"<div class='locked-line'>🔒 {lock_msg}</div>"
                else:
                    odds_html = self._invasion_odds_html(state, focus)
            self.territory_title.set_text(f"Territory: {self.selected_territory}")
            self._style_country_title(focus, state)
            body = self._country_stats_html(state, focus) if focus != "—" else ""
            self.territory_detail.set_content(f"{body}{locked_html}{battle}{odds_html}")
        elif focus:
            locked_html = ""
            if focus != player:
                locked, lock_msg = self._invade_locked_state_for(focus)
                if locked:
                    locked_html = f"<div class='locked-line'>🔒 {lock_msg}</div>"
                else:
                    odds_html = self._invasion_odds_html(state, focus)
            self.territory_title.set_text(focus)
            self._style_country_title(focus, state)
            hint = ""
            if focus != player:
                if locked_html:
                    hint = (
                        "<div class='stat-line' style='margin-top:8px'>"
                        "Use <b>Pressure</b> to worsen relations, or <b>Ally</b> / <b>Peace</b> "
                        "for diplomacy.</div>"
                    )
                else:
                    hint = (
                        "<div class='stat-line' style='margin-top:8px'>"
                        "Use <b>Pressure</b>, <b>Invade</b>, <b>Peace</b>, or <b>Ally</b> "
                        "(friendly powers only).</div>"
                    )
            self.territory_detail.set_content(
                self._country_stats_html(state, focus) + locked_html + hint + odds_html
            )
        else:
            self.territory_title.set_text("Select a country")
            self.territory_title.style("color: #0f172a;")
            self.territory_detail.set_content(
                '<div class="stat-line">Click the map or choose a power below.</div>'
            )
        if self._country_picker and focus:
            self._country_picker.set_value(focus)

    def _update_map_legend(self, state) -> None:
        if self._map_legend is None:
            return
        map_file = map_file_for_state(state)
        data = load_map_data(map_file)
        player = state.player_country
        rivals = set(state.scenario.get("primary_rivals", []))
        show = []
        if player:
            show.append(player)
        for r in rivals:
            if r in data.get("flags", {}):
                show.append(r)
        ally = state.scenario.get("ally_country")
        if ally and ally in data.get("flags", {}) and ally not in show:
            show.append(ally)
        items = []
        for country in show:
            color = country_color(country, map_file=map_file, state=state)
            short = _country_label(country, state.scenario)
            items.append(
                f"<span><i style='background:{color}'></i>{short}</span>"
            )
        self._map_legend.set_content(
            '<div class="map-legend">' + "".join(items) + "</div>"
            if items
            else ""
        )

    def _update_territory_button_styles(self, state) -> None:
        owners = state.territory_owner()
        for name, btn in self._territory_buttons.items():
            owner = owners.get(name) or None
            selected = name == self.selected_territory
            prev = getattr(btn, "_owner_cls", None)
            if prev:
                btn.classes(remove=prev)
            cls = owner_css_class(owner)
            btn.classes(add=cls)
            btn._owner_cls = cls
            if selected:
                btn.classes(add="terr-sel")
            else:
                btn.classes(remove="terr-sel")
            btn.tooltip(f"{name} — {owner or 'unclaimed'}")

    def _select_territory(self, name: str) -> None:
        self.selected_territory = name
        owner = territory_owner_country(self.sim.state, name)
        if owner:
            self.selected_country = owner
        self.refresh()

    def _select_country(self, name: str | None) -> None:
        if not name or not self.sim:
            return
        self.selected_country = name
        self.selected_territory = None
        self.refresh()

    def _territory_chip_names(self, state) -> list[str]:
        """Pick territories so chips show multiple owner colors, not only the player."""
        owners = state.territory_owner()
        contestable = sorted(state.contestable_territories())
        player = state.player_country
        max_chips = 36 if state.scenario.get("id") == "global" else 18

        if self.selected_country and self.selected_country != player:
            filtered = [
                t for t in contestable if owners.get(t) == self.selected_country
            ]
            return filtered[:max_chips] or contestable[:max_chips]

        if len(contestable) <= max_chips:
            return contestable

        picks: list[str] = []
        if self.selected_territory and self.selected_territory in contestable:
            picks.append(self.selected_territory)

        def add_for_owner(owner: str, limit: int) -> None:
            for t in contestable:
                if owners.get(t) == owner and t not in picks:
                    picks.append(t)
                    if len([p for p in picks if owners.get(p) == owner]) >= limit:
                        break

        if player:
            add_for_owner(player, 4)
        for rival in state.scenario.get("primary_rivals", []):
            add_for_owner(rival, 3)

        seen_owners = {owners.get(p) for p in picks}
        for t in contestable:
            owner = owners.get(t)
            if owner and owner not in seen_owners and t not in picks:
                picks.append(t)
                seen_owners.add(owner)
            if len(picks) >= max_chips:
                break

        for t in contestable:
            if t not in picks:
                picks.append(t)
            if len(picks) >= max_chips:
                break
        return picks[:max_chips]

    def _rebuild_territory_chips(self, state) -> None:
        if self._terr_chip_container is None:
            return
        self._terr_chip_container.clear()
        self._territory_buttons.clear()
        owners = state.territory_owner()
        names = self._territory_chip_names(state)
        with self._terr_chip_container:
            for terr in names:
                short = terr[:10] if len(terr) > 10 else terr
                owner = owners.get(terr) or None
                btn = ui.button(
                    short,
                    on_click=lambda t=terr: self._select_territory(t),
                    color=None,
                )
                btn.props("unelevated dense no-caps")
                btn.classes(f"terr-chip-btn {owner_css_class(owner)}")
                if terr == self.selected_territory:
                    btn.classes(add="terr-sel")
                btn.tooltip(f"{terr} — {owner or 'unclaimed'}")
                self._territory_buttons[terr] = btn

    def _on_map_click(self, event) -> None:
        if not self.sim:
            return
        map_file = map_file_for_state(self.sim.state)
        territory = parse_plotly_territory_click(event, map_file=map_file)
        if territory:
            self._select_territory(territory)

    def _action_target(self) -> str | None:
        if self.selected_territory:
            owner = territory_owner_country(self.sim.state, self.selected_territory)
            if owner and owner != self.sim.state.player_country:
                return owner
        player = self.sim.state.player_country
        if self.selected_country and self.selected_country != player:
            return self.selected_country
        return None

    def _notify(self, title: str, body: str = "", *, kind: str = "system", success: bool = True) -> None:
        self.notifications.push_message(
            title,
            body,
            kind=kind if success else "system",
            week=self.sim.state.turn_number if self.sim else "",
        )

    def _run_vision_analyst(self) -> None:
        try:
            apply_analysis()
        except Exception:
            pass

    def _on_game_end(self, outcome: str) -> None:
        self.recorder.end_session(self.sim.state, outcome=outcome)
        save_run(
            compute_score(
                self.sim.state,
                self.sim.clock.game_day,
                won=outcome == "win",
            )
        )
        threading.Thread(target=self._run_vision_analyst, daemon=True).start()

    def _show_end_summary(self) -> None:
        for entry in reversed(self.sim.state.player_journal):
            if entry.get("kind") != "system":
                continue
            title = entry.get("title", "")
            if title in ("Why you lost", "Victory"):
                self._notify(
                    title,
                    entry.get("body", ""),
                    kind="system",
                    success=title == "Victory",
                )
                return

    def do_action(self, action: str) -> None:
        if not self.sim or not self.player:
            self._notify("Start a game first", kind="system", success=False)
            return
        if action == "rearm":
            result = self.player.act("rearm", self.player.country.name)
            target = self.player.country.name
        elif action in ("ally_us", "ally"):
            target, _ = self._ally_target()
            result = self.player.act("ally", target)
        else:
            target = self._action_target()
            if not target:
                self._notify("Pick a territory or rival first", kind="system", success=False)
                return
            if action == "attack":
                locked, lock_msg = self._invade_locked_state_for(target)
                if locked:
                    self._notify("Invade locked", lock_msg, kind="system", success=False)
                    return
            invasion_terr = (
                self.selected_territory
                if action == "attack"
                and self.selected_territory
                and territory_owner_country(self.sim.state, self.selected_territory)
                == target
                else None
            )
            result = self.player.act(action, target, territory=invasion_terr)

        self.recorder.record_player_action(
            self.sim.state,
            action="ally" if action in ("ally_us", "ally") else action,
            target=target,
            success=result.success,
            message=result.message,
        )
        kind = "order" if result.success else "system"
        self._notify(
            "Order queued" if result.success else "Blocked",
            result.message,
            kind=kind,
            success=result.success,
        )
        self.refresh()

    def advance_week(self) -> None:
        if not self.sim:
            self._notify("Start a game first", kind="system", success=False)
            return
        if self.player and self.player.orders_remaining() > 0:
            remaining = self.player.orders_remaining()
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-2"):
                ui.label(f"You have {remaining} unused order(s) this week.").classes(
                    "text-weight-bold"
                )
                ui.label("Advance anyway? Unused orders are lost.").classes("text-sm")
                with ui.row().classes("gap-2 mt-2"):
                    ui.button(
                        "Advance anyway",
                        on_click=lambda: (dialog.close(), self._do_advance_week()),
                    ).props("color=amber")
                    ui.button("Keep planning", on_click=dialog.close).props("flat")
            dialog.open()
            return
        self._do_advance_week()

    def _do_advance_week(self) -> None:
        if not self.sim:
            return
        try:
            save_game(self.sim)
        except Exception:
            pass
        msgs = self.sim.advance_week()
        self.recorder.record_week_advanced(self.sim.state, messages=msgs)
        self._notify("Week advanced", " · ".join(msgs) if msgs else "Done", kind="system")
        if self.sim.state.winner:
            self._on_game_end("win")
            self._show_end_summary()
        elif self.sim.state.loser:
            self._on_game_end("loss")
            self._show_end_summary()
        self.refresh()

    def _begin_from_start_screen(self) -> None:
        diff = self._difficulty_select.value or DEFAULT_DIFFICULTY
        country = self._country_select.value or self._chosen_country
        scenario = (
            self._scenario_select.value if self._scenario_select else DEFAULT_SCENARIO
        )
        self.start(diff, player_country=country, scenario_id=scenario)

    def _start_win_percent(self, difficulty: str, scenario_id: str | None = None) -> int:
        sid = scenario_id or (
            self._scenario_select.value
            if self._scenario_select
            else self.scenario_id
        )
        return int(win_control_percent_for(difficulty, scenario_id=sid) * 100)

    def _update_start_description(
        self,
        *,
        difficulty: str | None = None,
        country: str | None = None,
    ) -> None:
        if self._start_desc is None:
            return
        diff = difficulty
        if diff is None and self._difficulty_select is not None:
            diff = self._difficulty_select.value
        diff = diff or DEFAULT_DIFFICULTY
        win_pct = self._start_win_percent(diff)
        nation = country
        if nation is None and self._country_select is not None:
            nation = self._country_select.value
        nation = nation or self._chosen_country
        sid = (
            self._scenario_select.value
            if self._scenario_select
            else DEFAULT_SCENARIO
        )
        preview = None
        try:
            from state.scenario_loader import load_scenario

            preview = load_scenario(sid, difficulty=diff)
        except Exception:
            pass
        scope = "world" if sid == "global" else "regional"
        win_line = f"control {win_pct}% of the {scope} map"
        if preview and preview.scenario.get("win_on_rivals_eliminated"):
            rivals = ", ".join(preview.scenario.get("primary_rivals", []))
            win_line += f", or eliminate {rivals}"
        elif preview:
            win_line += ", or eliminate all rivals"
        self._start_desc.set_text(f"Play as {nation} — {win_line}.")

    def _refresh_start_country_options(self) -> None:
        from state.scenario_loader import load_scenario

        sid = self._scenario_select.value if self._scenario_select else DEFAULT_SCENARIO
        preview = load_scenario(sid, difficulty=DEFAULT_DIFFICULTY)
        names = [c.name for c in preview.countries]
        default = preview.scenario.get("player_country", names[0])
        opts = {n: n for n in names}
        self._country_select.set_options(opts, value=default)
        self._chosen_country = default
        self._update_start_description(country=default)

    def _build_start_overlay(self) -> None:
        from state.scenario_loader import load_scenario

        preview = load_scenario(DEFAULT_SCENARIO, difficulty=DEFAULT_DIFFICULTY)
        meta = preview.scenario
        country_names = [c.name for c in preview.countries]
        country_opts = {n: n for n in country_names}
        default_nation = meta.get("player_country", self._chosen_country)

        def win_hints_for(scenario_id: str) -> dict[str, str]:
            return {
                d: f"{self._start_win_percent(d, scenario_id=scenario_id)}% map"
                for d in ("easy", "normal", "hard")
            }

        global_hints = win_hints_for("global")
        asia_hints = win_hints_for("south_asia")

        with ui.element("div").classes("start-overlay") as overlay:
            self._start_overlay = overlay
            with ui.element("div").classes("start-card"):
                ui.html("<h2>The Conqueror</h2>", sanitize=False)
                self._start_desc = ui.label("").classes("subtitle")

                ui.label("How to play").classes("start-label mt-2")
                ui.html(
                    """
                    <div class="onboard-step">
                      <span class="step-num">1</span>
                      <span class="step-body"><b>Select</b> a territory on the map
                      or a rival in the sidebar.</span>
                    </div>
                    <div class="onboard-step">
                      <span class="step-num">2</span>
                      <span class="step-body"><b>Queue up to 2 orders</b> per week
                      (one invasion max): Invade, Pressure, Peace, Rebuild, Ally.</span>
                    </div>
                    <div class="onboard-step">
                      <span class="step-num">3</span>
                      <span class="step-body"><b>Advance week</b> in the header to
                      resolve battles and AI moves (auto-saves).</span>
                    </div>
                    """,
                    sanitize=False,
                )

                ui.label("Scenario").classes("start-label mt-3")
                def on_scenario_change() -> None:
                    self._difficulty_select.set_options(difficulty_options())
                    self._refresh_start_country_options()

                self._scenario_select = ui.select(
                    SCENARIO_LABELS,
                    value=DEFAULT_SCENARIO,
                    on_change=lambda _: on_scenario_change(),
                ).classes("w-full select-field").props(SELECT_PROPS)

                ui.label("Your nation").classes("start-label mt-2")
                self._country_select = ui.select(
                    country_opts,
                    value=default_nation,
                    on_change=lambda _: self._update_start_description(),
                ).classes("w-full select-field").props(
                    SELECT_PROPS + " use-input input-debounce=0"
                )

                ui.label("Difficulty").classes("start-label mt-2")

                def difficulty_options() -> dict[str, str]:
                    sid = (
                        self._scenario_select.value
                        if self._scenario_select
                        else DEFAULT_SCENARIO
                    )
                    hints = global_hints if sid == "global" else asia_hints
                    return {
                        "easy": f"Easy — {hints['easy']}, stronger allied aid",
                        "normal": f"Normal — {hints['normal']} (recommended)",
                        "hard": f"Hard — {hints['hard']}, tougher rivals",
                    }

                self._difficulty_select = ui.select(
                    difficulty_options(),
                    value=DEFAULT_DIFFICULTY,
                    on_change=lambda _: self._update_start_description(),
                ).classes("w-full select-field").props(SELECT_PROPS)

                self._chosen_country = default_nation
                self._update_start_description(country=default_nation)

                ui.button(
                    "Start game",
                    on_click=self._begin_from_start_screen,
                ).classes("w-full mt-6").props(
                    "color=primary size=lg no-caps"
                )

    def build(self) -> None:
        ui.dark_mode().enable()
        ui.add_head_html(
            INTELLIGENCE_CSS
            + VIEWPORT_CSS
            + build_owner_stylesheet("global_territory_map.json")
            + build_owner_stylesheet("south_asia_territory_map.json")
        )

        self._build_start_overlay()

        with ui.column().classes("game-viewport w-full game-blocked") as viewport:
            self._game_viewport = viewport
            with ui.row().classes("game-header w-full items-center"):
                ui.label("The Conqueror").classes("title")
                self.phase_label = ui.label("…").classes("phase-pill")
                self.status_label = ui.label("").classes("status-pill")
                with ui.row().classes("header-actions"):
                    self._advance_btn = ui.button(
                        "Advance week", on_click=self.advance_week
                    ).props("color=amber text-color=black dense no-caps glossy")
                    ui.button(icon="refresh", on_click=self._show_start_screen).props(
                        "flat dense round color=white"
                    ).tooltip("New game / difficulty")

            with ui.row().classes("win-progress-wrap w-full"):
                self.win_progress_label = ui.label("").classes("win-progress-text")
                self.win_progress_bar = ui.linear_progress(
                    value=0, show_value=False
                ).props("color=amber track-color=blue-grey-9").classes("w-full")

            self.notifications.mount()

            with ui.row().classes("game-main w-full"):
                with ui.column().classes("map-zone"):
                    from state.scenario_loader import load_scenario

                    state = load_scenario(DEFAULT_SCENARIO, difficulty=DEFAULT_DIFFICULTY)
                    fig = build_scenario_map(state)
                    fig.update_layout(height=360, autosize=True)
                    with ui.element("div").classes("plotly-parent w-full"):
                        self.map_plot = ui.plotly(fig).classes("w-full").style(
                            "min-height: 280px; height: 100%; display: block;"
                        )
                        self.map_plot.on("plotly_click", self._on_map_click)
                    self._map_legend = ui.html("", sanitize=False).classes("w-full")

                with ui.column().classes("command-panel"):
                    with ui.column().classes("command-panel-scroll w-full"):
                        with ui.element("div").classes("panel-block"):
                            self.territory_title = ui.label("—").classes("panel-title")
                            self.territory_detail = ui.html("").classes(
                                "w-full panel-detail"
                            )
                            with ui.element("div").classes("action-grid w-full"):
                                self._invade_btn = ui.button(
                                    "Invade",
                                    on_click=lambda: self.do_action("attack"),
                                ).props("color=negative no-caps")
                                self._action_buttons = [
                                    self._invade_btn,
                                    ui.button(
                                        "Pressure",
                                        on_click=lambda: self.do_action("sanction"),
                                    ).props("no-caps"),
                                    ui.button(
                                        "Peace",
                                        on_click=lambda: self.do_action("peace"),
                                    ).props("no-caps"),
                                    ui.button(
                                        "Rebuild",
                                        on_click=lambda: self.do_action("rearm"),
                                    ).props("color=purple no-caps"),
                                    ui.button(
                                        "Ally UK",
                                        on_click=lambda: self.do_action("ally"),
                                    ).props("color=info no-caps"),
                                ]
                            self._ally_btn = self._action_buttons[-1]

                        with ui.element("div").classes("panel-block"):
                            ui.label("Orders this week").classes("panel-label mb-1")
                            self._orders_line = ui.html("", sanitize=False).classes(
                                "w-full"
                            )

                        with ui.element("div").classes("panel-block"):
                            ui.label("Select power").classes("panel-label mb-1")
                            preview_state = load_scenario(
                                DEFAULT_SCENARIO, difficulty=DEFAULT_DIFFICULTY
                            )
                            power_opts = {
                                c.name: c.name for c in preview_state.countries
                            }
                            self._country_picker = ui.select(
                                power_opts,
                                value=self._chosen_country,
                                on_change=lambda e: self._select_country(e.value),
                            ).classes("w-full select-field").props(
                                SELECT_PROPS + " use-input input-debounce=0"
                            )

                        with ui.element("div").classes("panel-block"):
                            ui.label("Territories").classes("panel-label mb-1")
                            with ui.element("div").classes("terr-scroll w-full"):
                                with ui.element("div").classes("terr-grid w-full") as terr_box:
                                    self._terr_chip_container = terr_box

                        with ui.element("div").classes("panel-block"):
                            ui.label("Your status").classes("panel-label mb-1")
                            self.stat_line = ui.html(
                                "<div class='stat-line'>Start a game to see stats.</div>",
                                sanitize=False,
                            )
                            self.ally_panel = ui.html(
                                "<div class='ally-line'>Alliance status appears here.</div>",
                                sanitize=False,
                            ).classes("mt-1 w-full")
                            self._hint_line = ui.html("", sanitize=False).classes(
                                "w-full"
                            )

        self._ui_ready = True
        self._set_controls_enabled(False)
        self._show_start_screen()


def run_focused_app() -> None:
    bootstrap_balance_from_sessions()
    app = FocusedUI()
    app.build()
    ui.run(title="The Conqueror — Global Conquest", port=8080, reload=False)

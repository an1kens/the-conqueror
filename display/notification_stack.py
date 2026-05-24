"""Intelligence feeds — player actions (large) and world wire (compact)."""

from __future__ import annotations

from nicegui import ui

KIND_META = {
    "battle": ("intel-battle", "⚔", "BATTLE"),
    "threat": ("intel-threat", "⚠", "THREAT"),
    "order": ("intel-order", "📋", "ORDER"),
    "pressure": ("intel-pressure", "◎", "PRESSURE"),
    "peace": ("intel-peace", "☮", "PEACE"),
    "usa": ("intel-usa", "★", "ALLIANCE"),
    "recover": ("intel-recover", "↻", "RECOVER"),
    "system": ("intel-system", "●", "INTEL"),
    "wire": ("intel-wire", "🌐", "WIRE"),
}

PLAYER_FEED_KINDS = frozenset(
    {"battle", "threat", "order", "pressure", "peace", "usa", "recover", "system"}
)
WIRE_FEED_KINDS = frozenset({"wire"})
PINNED_PLAYER_KINDS = frozenset({"battle", "threat"})

INTELLIGENCE_CSS = """
<style>
.intel-dual {
  flex: 0 0 auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 0;
  border-bottom: 3px solid #f59e0b;
  background: linear-gradient(180deg, #1e3a5f 0%, #172554 55%, #0f2744 100%);
}
.intel-pane {
  flex: 1 1 50%;
  min-width: 0;
  padding: 10px 14px 12px;
  box-sizing: border-box;
}
.intel-pane-wire {
  border-right: 2px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 39, 68, 0.6);
}
.intel-pane-player {
  padding-bottom: 12px;
}
.intel-heading {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 6px;
}
.intel-heading .intel-title {
  font-size: 11px; font-weight: 900; letter-spacing: 0.12em;
  color: #94a3b8; text-transform: uppercase;
}
.intel-pane-player .intel-title {
  font-size: 13px; color: #fcd34d;
  text-shadow: 0 0 12px rgba(252, 211, 77, 0.4);
}
.intel-heading .intel-hint {
  font-size: 11px; color: #bae6fd; font-weight: 500;
}
.intel-cards {
  display: flex; flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}
.intel-cards-wire { max-height: min(100px, 14vh); }
.intel-cards-player { max-height: min(110px, 15vh); }
@media (max-width: 900px) {
  .intel-dual { flex-direction: column; }
  .intel-pane-wire {
    border-right: none;
    border-bottom: 2px solid rgba(148, 163, 184, 0.35);
  }
  .intel-cards-wire { max-height: min(80px, 12vh); }
  .intel-cards-player { max-height: min(120px, 16vh); }
}
.intel-cards::-webkit-scrollbar { width: 6px; }
.intel-cards::-webkit-scrollbar-thumb { background: #f59e0b66; border-radius: 3px; }
.intel-card {
  border-radius: 10px;
  padding: 10px 12px;
  border: 2px solid rgba(255,255,255,0.35);
  box-shadow: 0 4px 14px rgba(0,0,0,0.2);
}
.intel-card .intel-top {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 4px;
}
.intel-card .intel-badge {
  font-size: 10px; font-weight: 800; letter-spacing: 0.08em;
  padding: 2px 6px; border-radius: 6px;
  background: rgba(0,0,0,0.12);
}
.intel-card .intel-kind {
  font-size: 10px; font-weight: 800; letter-spacing: 0.06em;
}
.intel-pane-player .intel-card .intel-headline { font-size: 15px; }
.intel-pane-player .intel-card .intel-body { font-size: 13px; }
.intel-pane-wire .intel-card .intel-headline { font-size: 12px; }
.intel-pane-wire .intel-card .intel-body { font-size: 11px; }
.intel-card .intel-icon { font-size: 16px; line-height: 1; }
.intel-card .intel-headline {
  font-weight: 800; line-height: 1.25;
  margin-bottom: 2px;
}
.intel-card .intel-body {
  font-weight: 500; line-height: 1.4;
  opacity: 0.95;
}
.intel-card .intel-impact {
  font-size: 11px; font-weight: 700; margin-top: 6px;
  padding-top: 6px; border-top: 2px solid rgba(0,0,0,0.12);
}
.intel-empty {
  font-size: 12px; color: #e0f2fe; font-style: italic;
  padding: 4px 0;
}
.intel-battle {
  background: linear-gradient(135deg, #fecaca 0%, #fda4af 100%);
  color: #7f1d1d;
}
.intel-battle .intel-badge { background: #991b1b22; color: #991b1b; }
.intel-threat {
  background: linear-gradient(135deg, #fed7aa 0%, #fdba74 100%);
  color: #7c2d12;
}
.intel-threat .intel-badge { background: #9a341222; color: #9a3412; }
.intel-order {
  background: linear-gradient(135deg, #bfdbfe 0%, #93c5fd 100%);
  color: #1e3a8a;
}
.intel-pressure {
  background: linear-gradient(135deg, #fde68a 0%, #fcd34d 100%);
  color: #78350f;
}
.intel-peace {
  background: linear-gradient(135deg, #bbf7d0 0%, #86efac 100%);
  color: #14532d;
}
.intel-usa {
  background: linear-gradient(135deg, #dbeafe 0%, #60a5fa 100%);
  color: #1e3a8a;
}
.intel-recover {
  background: linear-gradient(135deg, #e9d5ff 0%, #c4b5fd 100%);
  color: #4c1d95;
}
.intel-system {
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  color: #334155;
}
.intel-wire {
  background: linear-gradient(135deg, #334155 0%, #475569 100%);
  color: #e2e8f0;
  border-color: rgba(148, 163, 184, 0.4) !important;
}
.intel-wire .intel-impact { color: #fcd34d; }
</style>
"""

NOTIFICATION_CSS = INTELLIGENCE_CSS


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class _FeedColumn:
    def __init__(
        self,
        *,
        title: str,
        hint: str,
        cards_class: str,
        max_visible: int,
        empty_text: str,
        pane_class: str,
        pin_kinds: frozenset[str] | None = None,
    ) -> None:
        self.title = title
        self.hint = hint
        self.cards_class = cards_class
        self.max_visible = max_visible
        self.empty_text = empty_text
        self.pane_class = pane_class
        self._cards_container: ui.column | None = None
        self._entries: list[dict] = []

    def _card_html(self, entry: dict) -> str:
        kind = entry.get("kind", "system")
        css_class, icon, kind_label = KIND_META.get(kind, KIND_META["system"])
        title = _escape(entry.get("title", ""))
        body = _escape(entry.get("body", ""))
        impact = _escape(entry.get("impact", ""))
        week = entry.get("week", "")
        week_badge = f"W{week}" if week else ""
        badge_html = (
            f'<span class="intel-badge">{week_badge}</span>' if week_badge else ""
        )
        body_html = f'<div class="intel-body">{body}</div>' if body else ""
        impact_html = (
            f'<div class="intel-impact">{impact}</div>' if impact else ""
        )
        return (
            f'<div class="intel-card {css_class}">'
            f'<div class="intel-top">'
            f'<span class="intel-icon">{icon}</span>'
            f'<span class="intel-kind">{kind_label}</span>'
            f"{badge_html}"
            f"</div>"
            f'<div class="intel-headline">{title}</div>'
            f"{body_html}{impact_html}</div>"
        )

    def mount_into(self, parent: ui.element) -> None:
        with parent:
            with ui.element("div").classes(f"intel-pane {self.pane_class} w-full"):
                ui.html(
                    f'<div class="intel-heading">'
                    f'<span class="intel-title">{_escape(self.title)}</span>'
                    f'<span class="intel-hint">{_escape(self.hint)}</span>'
                    f"</div>",
                    sanitize=False,
                )
                self._cards_container = ui.column().classes(
                    f"intel-cards {self.cards_class} w-full"
                )
                self._render_cards()

    def _visible_entries(self) -> list[dict]:
        recent = self._entries[-self.max_visible * 2 :]
        if not getattr(self, "_pin_kinds", None):
            return list(reversed(recent[-self.max_visible :]))
        pinned = [e for e in recent if e.get("kind") in self._pin_kinds]
        rest = [e for e in recent if e.get("kind") not in self._pin_kinds]
        ordered = pinned + rest
        return list(reversed(ordered[-self.max_visible :]))

    def _render_cards(self) -> None:
        if not self._cards_container:
            return
        self._cards_container.clear()
        visible = self._visible_entries()
        with self._cards_container:
            if not visible:
                ui.html(
                    f'<div class="intel-empty">{_escape(self.empty_text)}</div>',
                    sanitize=False,
                )
            else:
                for entry in visible:
                    ui.html(self._card_html(entry), sanitize=False).classes(
                        "w-full"
                    )

    def append(self, entry: dict) -> None:
        self._entries.append(entry)
        if len(self._entries) > 32:
            self._entries = self._entries[-32:]
        self._render_cards()

    def reset(self) -> None:
        self._entries = []
        self._render_cards()


class DualIntelligenceFeed:
    """World wire (compact) + your intelligence (main)."""

    def __init__(
        self,
        *,
        max_visible: int = 5,
        wire_max_visible: int = 2,
    ) -> None:
        self._section: ui.column | None = None
        self._seen_journal_len = 0
        self.wire = _FeedColumn(
            title="World wire",
            hint="wars & captures",
            cards_class="intel-cards-wire",
            max_visible=wire_max_visible,
            empty_text="No world conflicts reported yet.",
            pane_class="intel-pane-wire",
        )
        self.player = _FeedColumn(
            title="Your intelligence",
            hint="orders, battles, threats",
            cards_class="intel-cards-player",
            max_visible=max_visible,
            empty_text="Your orders and battles appear here.",
            pane_class="intel-pane-player",
        )
        self.player._pin_kinds = PINNED_PLAYER_KINDS

    def mount(self) -> ui.column:
        self._section = ui.column().classes("intel-dual w-full")
        with self._section:
            self.wire.mount_into(self._section)
            self.player.mount_into(self._section)
        return self._section

    def sync_journal(self, journal: list[dict]) -> None:
        new_entries = journal[self._seen_journal_len :]
        self._seen_journal_len = len(journal)
        for entry in new_entries:
            kind = entry.get("kind", "system")
            payload = {
                "kind": kind,
                "title": entry.get("title", ""),
                "body": entry.get("body", ""),
                "impact": entry.get("impact", ""),
                "week": entry.get("week", ""),
            }
            if kind in WIRE_FEED_KINDS:
                self.wire.append(payload)
            else:
                self.player.append(payload)

    def push_message(
        self,
        title: str,
        body: str = "",
        *,
        kind: str = "system",
        impact: str = "",
        week: int | str = "",
    ) -> None:
        payload = {
            "kind": kind,
            "title": title,
            "body": body,
            "impact": impact,
            "week": week,
        }
        if kind in WIRE_FEED_KINDS:
            self.wire.append(payload)
        else:
            self.player.append(payload)

    def reset(self) -> None:
        self._seen_journal_len = 0
        self.wire.reset()
        self.player.reset()


# Back-compat alias
NotificationStack = DualIntelligenceFeed

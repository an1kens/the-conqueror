"""Interactive scenario map — geo territory markers and flags."""

from __future__ import annotations

import json
import re
from pathlib import Path

import plotly.graph_objects as go

from state.game_state import GameState

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
DEFAULT_MAP_FILE = "south_asia_territory_map.json"

_map_cache: dict[str, dict] = {}


def clear_map_cache() -> None:
    _map_cache.clear()


def _map_path(map_file: str) -> Path:
    return SCENARIOS_DIR / map_file


def load_map_data(map_file: str = DEFAULT_MAP_FILE) -> dict:
    if map_file not in _map_cache:
        with open(_map_path(map_file)) as f:
            _map_cache[map_file] = json.load(f)
    return _map_cache[map_file]


def map_file_for_state(state: GameState) -> str:
    return state.scenario.get("map_file", DEFAULT_MAP_FILE)


def territory_owner_country(state: GameState, territory: str) -> str | None:
    for country in state.countries:
        if territory in country.territories:
            return country.name
    return None


def country_color(
    country_name: str | None,
    *,
    map_file: str | None = None,
    state: GameState | None = None,
    default: str = "#94a3b8",
) -> str:
    """Map flag color for a country (same palette as the geo map)."""
    if not country_name:
        return default
    if map_file is None:
        map_file = map_file_for_state(state) if state else DEFAULT_MAP_FILE
    flags = load_map_data(map_file).get("flags", {})
    return flags.get(country_name, {}).get("color", default)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def contrast_text_color(hex_color: str) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0f172a" if lum > 0.58 else "#ffffff"


def owner_css_class(country: str | None) -> str:
    if not country:
        return "owner-unclaimed"
    slug = re.sub(r"[^a-z0-9]+", "-", country.lower()).strip("-")
    return f"owner-{slug}" if slug else "owner-unclaimed"


def build_owner_stylesheet(map_file: str = DEFAULT_MAP_FILE) -> str:
    """CSS rules so territory buttons use solid owner colors from the map palette."""
    data = load_map_data(map_file)
    rules = [
        ".terr-chip-btn { width: 100%; min-height: 40px; font-size: 11px; "
        "font-weight: 800; border-radius: 8px; text-transform: none; "
        "pointer-events: auto !important; cursor: pointer; }",
        ".terr-chip-btn.terr-sel { box-shadow: 0 0 0 3px #f59e0b !important; }",
        ".owner-unclaimed { background: #64748b !important; color: #fff !important; "
        "border: 2px solid #475569 !important; }",
    ]
    for name, meta in data.get("flags", {}).items():
        color = meta.get("color", "#64748b")
        text = contrast_text_color(color)
        cls = owner_css_class(name)
        rules.append(
            f".terr-chip-btn.{cls} {{ background: {color} !important; "
            f"color: {text} !important; border: 2px solid {color} !important; }}"
        )
    return "<style>\n" + "\n".join(rules) + "\n</style>"


def last_battle_territory(state: GameState) -> str | None:
    if not state.battle_reports:
        return None
    return state.battle_reports[-1].territory


def build_scenario_map(
    state: GameState,
    *,
    selected_territory: str | None = None,
) -> go.Figure:
    map_file = map_file_for_state(state)
    data = load_map_data(map_file)
    flags = data["flags"]
    owners = state.territory_owner()
    battle_site = last_battle_territory(state)
    scope = data["zoom_scope"]

    fig = go.Figure()

    for country_name, ring in data.get("country_borders", {}).items():
        lats = [p[0] for p in ring]
        lons = [p[1] for p in ring]
        controlled = sum(
            1 for t, o in owners.items() if o == country_name
        )
        meta = flags.get(country_name, {})
        fill = meta.get("color", "#64748b")
        opacity = 0.08 + min(0.22, controlled * 0.04)
        fig.add_trace(
            go.Scattergeo(
                lat=lats,
                lon=lons,
                mode="lines",
                line=dict(width=2, color=fill),
                fill="toself",
                fillcolor=fill,
                opacity=opacity,
                name=country_name,
                hoverinfo="skip",
                showlegend=False,
            )
        )

    is_world = data.get("geo_scope") == "world"
    base_size = 20 if is_world else 22
    sel_size = 28 if is_world else 32
    battle_size = 24 if is_world else 30
    marker_symbol = "square" if is_world else "circle"

    t_lats, t_lons, t_colors, t_sizes, t_custom = [], [], [], [], []
    for name, meta in data["territories"].items():
        owner = owners.get(name, "—")
        color = flags.get(owner, {}).get("color", "#94a3b8")
        size = base_size
        if name == selected_territory:
            size = sel_size
        if name == battle_site:
            size = max(size, battle_size)
        t_lats.append(meta["lat"])
        t_lons.append(meta["lon"])
        t_colors.append(color)
        t_sizes.append(size)
        t_custom.append(name)

    player = state.player_country
    marker_mode = "markers" if is_world else "markers+text"
    trace_kw: dict = dict(
        lat=t_lats,
        lon=t_lons,
        mode=marker_mode,
        marker=dict(
            size=t_sizes,
            color=t_colors,
            opacity=0.98,
            line=dict(
                width=[
                    3 if n == selected_territory else (2.5 if n == battle_site else 1)
                    for n in t_custom
                ],
                color=[
                    "#fbbf24"
                    if n == selected_territory
                    else ("#f87171" if n == battle_site else "#f8fafc")
                    for n in t_custom
                ],
            ),
            symbol=marker_symbol,
        ),
        hovertext=[
            f"<b>{n}</b><br>{owners.get(n, '—')}"
            + (" · your territory" if owners.get(n) == player else "")
            + ("<br>⚔ Recent battle" if n == battle_site else "<br>Click to select")
            for n in t_custom
        ],
        hoverinfo="text",
        customdata=t_custom,
        name="Territories",
        showlegend=False,
    )
    if not is_world:
        trace_kw["text"] = [
            flags.get(owners.get(n), {}).get("emoji", "•") for n in t_custom
        ]
        trace_kw["textposition"] = "middle center"
        trace_kw["textfont"] = dict(size=16, color="#ffffff")
    fig.add_trace(go.Scattergeo(**trace_kw))

    geo_scope = data.get("geo_scope", "asia")
    fig.update_geos(
        scope=geo_scope,
        projection_type="natural earth",
        center=dict(lat=data["center"]["lat"], lon=data["center"]["lon"]),
        lataxis_range=[scope["lat_min"], scope["lat_max"]],
        lonaxis_range=[scope["lon_min"], scope["lon_max"]],
        showcountries=True,
        countrycolor="#64748b",
        coastlinecolor="#cbd5e1",
        landcolor="#334155",
        oceancolor="#0c4a6e",
        showland=True,
        showocean=True,
        showlakes=False,
        bgcolor="rgba(0,0,0,0)",
        framewidth=0,
    )
    fig.update_layout(
        title=None,
        margin=dict(l=4, r=4, t=4, b=4),
        autosize=True,
        paper_bgcolor="#1e4976",
        plot_bgcolor="#1e4976",
        font=dict(color="#f8fafc", size=12),
        dragmode="zoom",
        uirevision=f"scenario_map_{map_file}",
    )
    return fig


build_south_asia_map = build_scenario_map


def parse_plotly_territory_click(event, *, map_file: str = DEFAULT_MAP_FILE) -> str | None:
    """Resolve territory name from NiceGUI plotly_click event."""
    if not event:
        return None
    args = getattr(event, "args", None)
    if args is None and isinstance(event, dict):
        args = event
    if not isinstance(args, dict):
        return None
    points = args.get("points") or []
    if not points:
        return None
    pt = points[0]
    custom = pt.get("customdata")
    if custom is None:
        curve = pt.get("curveNumber")
        point_index = pt.get("pointIndex")
        if curve is not None and point_index is not None:
            data = load_map_data(map_file)
            names = list(data["territories"].keys())
            territory_curve = len(data.get("country_borders", {}))
            if curve == territory_curve and 0 <= point_index < len(names):
                return names[point_index]
        return None
    if isinstance(custom, (list, tuple)):
        custom = custom[0] if custom else None
    return str(custom) if custom else None

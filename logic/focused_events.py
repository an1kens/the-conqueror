"""Event resolution for focused (turn-based) scenario — battles, elimination, ceasefire."""

from country import Country
from logic.battle import resolve_battle
from logic.events import GameEvent
from logic.relationships import WAR_MAX, adjust_relationship, relationship_band
from logic.economy import clamp_military_to_economy, collapsed_economy
from logic.us_support import SANCTION_MIL_PENALTY, SANCTION_MIL_PENALTY_ECONOMY_MAX
from logic.war import ceasefire, find_war
from state.game_state import GameState

FOCUSED_DURATIONS = {
    "attack": 1,
    "negotiate": 1,
    "sanction": 1,
    "ally": 1,
    "ceasefire": 1,
    "rearm": 1,
    "alliance_formed": 1,
    "war_declared": 1,
}


def resolve_focused_event(event: GameEvent, state: GameState) -> None:
    source = state.get(event.source)
    target = state.get(event.target)
    intensity = event.intensity

    if event.event_type == "attack":
        _resolve_focused_attack(source, target, state, intensity, event)
    elif event.event_type == "sanction":
        _resolve_focused_sanction(source, target, state, intensity)
    elif event.event_type == "negotiate":
        _resolve_focused_negotiate(source, target, state, intensity)
    elif event.event_type == "ally":
        _resolve_focused_ally(source, target, state, intensity)
    elif event.event_type == "ceasefire":
        _resolve_ceasefire(source, target, state)
    elif event.event_type == "rearm":
        _resolve_rearm(source, state)
    elif event.event_type == "war_declared":
        player = state.player_country
        msg = f"{source.name} and {target.name} are at open war."
        if player and (source.name == player or target.name == player):
            state.record_journal(
                "threat" if target.name == player else "system",
                f"War with {target.name if source.name == player else source.name}",
                msg,
                impact="Invasion unlocked against nuclear rivals",
            )
            _log_if_player(state, f"WAR DECLARED: {msg}", source.name, target.name)
        else:
            state.record_journal("wire", "War declared", msg, impact="Global conflict")
            state.log(msg)
    elif event.event_type == "alliance_formed":
        source.stability = min(100, source.stability + 5)
        target.stability = min(100, target.stability + 5)
        _log_if_player(
            state,
            f"ALLIANCE: {source.name} and {target.name} signed a defense pact.",
            source.name,
            target.name,
        )


def _pick_battle_territory(attacker: Country, defender: Country) -> str:
    """Prefer defender territories that sound contested from attacker's border."""
    priority = {
        ("India", "Pakistan"): ["Kashmir", "Punjab", "Sindh", "Khyber", "Balochistan"],
        ("India", "China"): ["Ladakh", "Aksai Chin", "Tibet Plateau"],
        ("Pakistan", "India"): ["Kashmir", "Punjab", "Rajasthan"],
        ("China", "India"): ["Ladakh", "Aksai Chin", "Kashmir"],
        ("United States", "China"): ["Manchuria", "Tibet", "Xinjiang"],
        ("United States", "Russia"): ["Crimea", "Kaliningrad", "Siberia"],
        ("China", "United States"): ["California", "New York", "Texas"],
        ("Russia", "United States"): ["California", "New York", "Texas"],
    }
    for name in priority.get((attacker.name, defender.name), []):
        if name in defender.territories:
            return name
    return defender.territories[0] if defender.territories else defender.capital


def _resolve_focused_attack(
    source: Country,
    target: Country,
    state: GameState,
    intensity: float,
    event: GameEvent,
) -> None:
    if not target.territories and target.name not in state.non_territorial:
        return
    from logic.us_support import battle_bonus_if_us_allied

    at_war = target.relationships[source.name] <= WAR_MAX
    if at_war:
        intensity = min(2.0, intensity * 1.25)
    intensity *= battle_bonus_if_us_allied(state, source.name)
    chosen = event.metadata.get("territory")
    if chosen and chosen in target.territories:
        territory = chosen
    else:
        territory = _pick_battle_territory(source, target)
    report = resolve_battle(
        source, target, state, intensity=intensity, territory=territory, at_war=at_war
    )
    _queue_reaction(state, target.name, source.name, "attack")
    _queue_axis_response(state, source.name, target.name)
    state.battle_reports.append(report)
    if not at_war:
        adjust_relationship(source, target.name, -20, target, state=state)
    player = state.player_country
    involves_player = player and (
        source.name == player or target.name == player
    )
    won = report.territory_changed and report.holder_after == source.name
    if involves_player:
        kind = "threat" if target.name == player else "battle"
        state.record_journal(
            kind,
            f"{'Victory' if won and source.name == player else 'Battle'} — {report.territory}",
            f"{report.attacker} vs {report.defender}. "
            f"Dead: {report.attacker} {report.attacker_casualties:,}, "
            f"{report.defender} {report.defender_casualties:,}.",
            impact="Territory captured" if won else "Front line unchanged",
        )
    else:
        cap = (
            f"{report.attacker} seized {report.territory}"
            if report.territory_changed
            else f"No territory change at {report.territory}"
        )
        state.record_journal(
            "wire",
            f"{report.attacker} vs {report.defender}",
            f"{report.territory}: {report.attacker} {report.attacker_casualties:,} dead, "
            f"{report.defender} {report.defender_casualties:,} dead.",
            impact=cap,
        )
    _log_if_player(state, report.summary, source.name, target.name)
    _player_highlight(state, source.name, target.name)
    _check_elimination(state, target)
    _check_elimination(state, source)


def _resolve_focused_sanction(
    source: Country, target: Country, state: GameState, intensity: float
) -> None:
    rel = target.relationships[source.name]
    at_war = rel <= WAR_MAX
    if not at_war:
        adjust_relationship(source, target.name, -12, target, state=state)
    target.economic_power = max(0, target.economic_power - int(8 * intensity))
    target.stability = max(0, target.stability - int(5 * intensity))
    if target.economic_power < SANCTION_MIL_PENALTY_ECONOMY_MAX:
        target.military_strength = max(0, target.military_strength - SANCTION_MIL_PENALTY)
    if collapsed_economy(target):
        target.military_strength = max(0, target.military_strength - 3)
    clamp_military_to_economy(target)
    band = relationship_band(target.relationships[source.name])
    _queue_reaction(state, target.name, source.name, "sanction")
    axis = state.scenario.get("axis_partners", AXIS_PARTNER)
    player = state.player_country
    if player and source.name == player and target.name in axis:
        _queue_axis_response(state, source.name, target.name)
    player = state.player_country
    if target.name == player:
        state.record_journal(
            "threat",
            f"{source.name} pressured you",
            f"Economic pressure — your economy {target.economic_power}, "
            f"stability {target.stability}.",
            impact=f"Relations → {band}",
        )
    elif source.name == player:
        state.record_journal(
            "pressure",
            f"Pressure on {target.name}",
            f"Economic warfare — their economy {target.economic_power}, "
            f"stability {target.stability}.",
            impact="No land gained" if at_war else f"Relations → {band}",
        )
    elif at_war or band in ("hostile", "at_war"):
        state.record_journal(
            "wire",
            f"{source.name} pressured {target.name}",
            f"{target.name}: economy {target.economic_power}, "
            f"stability {target.stability}.",
            impact=f"Relations → {band}",
        )
    if at_war:
        msg = (
            f"{source.name} wartime pressure on {target.name} — "
            f"economy {target.economic_power}, stability {target.stability}. "
            f"Borders unchanged: use Invade to seize territory."
        )
    else:
        msg = (
            f"{source.name} sanctioned {target.name} — "
            f"economy {target.economic_power}, stability {target.stability}. "
            f"({band} — need 'at war' to invade nuclear powers.)"
        )
    _log_if_player(state, msg, source.name, target.name)
    _player_highlight(state, source.name, target.name)


def _resolve_focused_negotiate(
    source: Country, target: Country, state: GameState, intensity: float
) -> None:
    adjust_relationship(source, target.name, 15, target, state=state)
    source.stability = min(100, source.stability + 3)
    target.stability = min(100, target.stability + 3)
    band = relationship_band(target.relationships[source.name])
    war = find_war(state.active_wars, source.name, target.name)
    if war and war.active and band != "at_war":
        ceasefire(war, state.turn_number)
        msg = (
            f"CEASEFIRE: {source.name} and {target.name} halted fighting "
            f"(war dead — {source.name}: "
            f"{war.casualties_a if source.name == war.country_a else war.casualties_b:,}, "
            f"{target.name}: "
            f"{war.casualties_b if source.name == war.country_a else war.casualties_a:,})."
        )
    else:
        msg = f"{source.name} and {target.name} held talks (relations: {band})."
    _log_if_player(state, msg, source.name, target.name)
    _player_highlight(state, source.name, target.name)


def _resolve_focused_ally(
    source: Country, target: Country, state: GameState, intensity: float
) -> None:
    adjust_relationship(source, target.name, 22, target, state=state)
    score = target.relationships[source.name]
    from logic.relationships import ALLIED_MIN, FRIENDLY_MIN

    if source.name == state.player_country:
        if score >= ALLIED_MIN:
            state.record_journal(
                "usa",
                f"Alliance with {target.name}",
                f"Full alliance active (score {score}). "
                f"Biweekly aid scales with {target.name}'s military ({target.military_strength}).",
                impact="Aid while you are at war with hostile powers",
            )
        elif score >= FRIENDLY_MIN:
            state.record_journal(
                "usa",
                f"Closer ties with {target.name}",
                f"Relations now {score} — reach 80+ for wartime military aid.",
                impact=f"Aid strength tied to {target.name}'s military",
            )
    msg = f"{source.name} sought closer ties with {target.name} (score: {score})."
    _log_if_player(state, msg, source.name, target.name)
    _player_highlight(state, source.name, target.name)


def _resolve_rearm(source: Country, state: GameState) -> None:
    before_mil = source.military_strength
    before_stab = source.stability
    source.military_strength = min(100, source.military_strength + 12)
    source.stability = min(100, source.stability + 10)
    source.economic_power = max(0, source.economic_power - 6)
    if collapsed_economy(source) or source.economic_power < 15:
        source.economic_power = min(100, source.economic_power + 18)
    clamp_military_to_economy(source)
    if source.name == state.player_country:
        state.record_journal(
            "recover",
            "Rebuild",
            "National mobilization — arms production and domestic stability programs.",
            impact=f"Military {before_mil} → {source.military_strength}, "
            f"Stability {before_stab} → {source.stability}, "
            f"Economy → {source.economic_power}",
        )
    _log_if_player(
        state,
        f"{source.name} rearmed: military {source.military_strength}, "
        f"economy {source.economic_power}.",
        source.name,
        source.name,
    )


def _resolve_ceasefire(source: Country, target: Country, state: GameState) -> None:
    war = find_war(state.active_wars, source.name, target.name)
    if not war or not war.active:
        _log_if_player(
            state,
            f"No active war between {source.name} and {target.name}.",
            source.name,
            target.name,
        )
        return
    pending_attacks = [
        s
        for s in getattr(state, "pending_attack_sources_on_player", [])
        if s == target.name
    ]
    ceasefire(war, state.turn_number)
    adjust_relationship(source, target.name, 25, target, state=state)
    foe_rebuild = int(state.scenario.get("ceasefire_foe_rebuild", 4))
    t_before = target.military_strength
    target.military_strength = min(100, target.military_strength + foe_rebuild)
    if source.name == state.player_country:
        stab_before = source.stability
        source.military_strength = min(100, source.military_strength + 6)
        source.stability = min(100, source.stability + 8)
        body = f"Front frozen — {target.name} rebuilt (+{foe_rebuild} military)."
        impact = (
            f"You +6 mil (now {source.military_strength}), "
            f"stability {stab_before} → {source.stability}. "
            f"{target.name} {t_before} → {target.military_strength}. "
            f"Allied aid pauses until you are fighting again."
        )
        if pending_attacks:
            body += (
                f" Attacks already queued from {target.name} "
                f"({len(pending_attacks)}) may still land this week."
            )
            impact += " Ceasefire limits new strikes; queued battles still resolve."
        state.record_journal(
            "peace",
            f"Ceasefire with {target.name}",
            body,
            impact=impact,
        )
    msg = (
        f"CEASEFIRE: {source.name} ↔ {target.name}. "
        f"Total dead — {source.name}: "
        f"{war.casualties_a if source.name == war.country_a else war.casualties_b:,}, "
        f"{target.name}: "
        f"{war.casualties_b if source.name == war.country_a else war.casualties_a:,}."
    )
    _log_if_player(state, msg, source.name, target.name)


def _log_if_player(state: GameState, message: str, source: str, target: str) -> None:
    player = state.player_country
    if player and (source == player or target == player):
        state.log_player(message)
    else:
        state.log(message)


def _player_highlight(state: GameState, source: str, target: str) -> None:
    player = state.player_country
    if not player:
        return
    if source == player or target == player:
        if source == player:
            state.pending_player_alert = f"You acted against {target}."
        else:
            state.pending_player_alert = f"{source} acted against you."


AXIS_PARTNER = {"Pakistan": "China", "China": "Pakistan"}


def _queue_reaction(
    state: GameState, victim_name: str, provoker_name: str, provocation: str
) -> None:
    if victim_name in state.non_territorial or victim_name in state.eliminated_countries:
        return
    if provoker_name in state.eliminated_countries:
        return
    state.pending_reactions.append((victim_name, provoker_name, provocation))


def _queue_axis_response(state: GameState, aggressor: str, victim: str) -> None:
    player = state.player_country
    axis = state.scenario.get("axis_partners", AXIS_PARTNER)
    if not player or aggressor != player or victim not in axis:
        return
    partner = axis[victim]
    if partner in state.eliminated_countries:
        return
    state.pending_axis_responses.append((partner, aggressor))


def _check_elimination(state: GameState, country: Country) -> None:
    if country.name in state.non_territorial:
        return
    if country.territories:
        return
    if country.name in state.eliminated_countries:
        return
    state.eliminated_countries.add(country.name)
    state.defeated_countries.add(country.name)
    state.log_player(f"{country.name} has been eliminated (no territories remain).")

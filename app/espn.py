"""Read-only client for ESPN's public NBA endpoints.

ESPN's public endpoints are undocumented and may change. Parsers are defensive.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import time
import re
import unicodedata

import httpx

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
COMMON = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
TIMEOUT = 12.0
HEADERS = {"User-Agent": "NBA-Value-Finder/0.2 (read-only public data client)"}
CACHE_TTL_SECONDS = 15 * 60
_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def _cached(key: tuple[str, str], loader):
    entry = _CACHE.get(key)
    if entry and time.monotonic() - entry[0] < CACHE_TTL_SECONDS:
        return entry[1]
    value = loader()
    _CACHE[key] = (time.monotonic(), value)
    return value


class ESPNError(RuntimeError):
    pass


def _get_json(url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        response = httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ESPNError(f"ESPN request failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ESPNError("ESPN returned an unexpected response format")
    return payload


def _name_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("displayName", "fullName", "shortDisplayName", "description", "name", "abbreviation"):
            found = _name_value(value.get(key))
            if found:
                return found
    return None


def _team_summary(competitor: dict[str, Any]) -> dict[str, Any]:
    team = competitor.get("team") or {}
    return {
        "id": team.get("id") if isinstance(team, dict) else None,
        "name": _name_value(team.get("displayName") or team.get("name")) if isinstance(team, dict) else _name_value(team),
        "abbreviation": _name_value(team.get("abbreviation")) if isinstance(team, dict) else None,
        "home_away": competitor.get("homeAway"),
        "score": competitor.get("score"),
        "winner": competitor.get("winner"),
    }


def get_scoreboard(date: str | None = None) -> dict[str, Any]:
    requested_date = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    if len(requested_date) != 8 or not requested_date.isdigit():
        raise ValueError("date must use YYYYMMDD format")
    cache_key = ("scoreboard", requested_date)
    cached = _CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    payload = _get_json(f"{BASE}/scoreboard", {"dates": requested_date})
    events = []
    for event in payload.get("events", []):
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions else {}
        status = (competition.get("status") or event.get("status") or {}).get("type") or {}
        competitors = competition.get("competitors") or []
        events.append({
            "id": event.get("id"), "name": event.get("name"),
            "short_name": event.get("shortName"), "date": event.get("date"),
            "status": status.get("description") or status.get("name"),
            "status_state": status.get("state"),
            "venue": (competition.get("venue") or {}).get("fullName"),
            "competitors": [_team_summary(item) for item in competitors],
            "source": "ESPN",
        })
    result = {
        "date": requested_date, "count": len(events), "events": events,
        "source": "ESPN public NBA scoreboard",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _CACHE[cache_key] = (time.monotonic(), result)
    return result



def _boxscore_player_rows(payload: dict[str, Any], event: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize ESPN's official event summary box score into player game-log rows."""
    from zoneinfo import ZoneInfo
    try:
        parsed = datetime.fromisoformat(str(event.get("date")).replace("Z", "+00:00"))
        game_day = parsed.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except (TypeError, ValueError):
        return []
    rows: list[dict[str, str]] = []
    for team_block in (payload.get("boxscore") or {}).get("players") or []:
        team = team_block.get("team") or {}
        for group in team_block.get("statistics") or []:
            names = group.get("names") or group.get("keys") or []
            for item in group.get("athletes") or []:
                athlete = item.get("athlete") or {}
                name = athlete.get("displayName") or athlete.get("fullName")
                if not name:
                    continue
                values = item.get("stats") or []
                keyed = {re.sub(r"[^a-z0-9]", "", str(k).casefold()): str(values[i]).strip()
                         for i, k in enumerate(names) if i < len(values)}
                def get(*keys):
                    for key in keys:
                        value = keyed.get(re.sub(r"[^a-z0-9]", "", key.casefold()))
                        if value not in (None, ""):
                            return value
                    return ""
                dnp = any("DNP" in str(value).upper() for value in values)
                three = get("3PM", "FG3M", "3PT")
                if "-" in three:
                    three = three.split("-", 1)[0]
                rows.append({
                    "player_id": str(athlete.get("id") or ""),
                    "player_name": str(name), "game_date": game_day,
                    "game_id": str(event.get("id") or ""),
                    "team_id": str(team.get("id") or ""),
                    "team_abbreviation": str(team.get("abbreviation") or "").upper(),
                    "min": "0:00" if dnp else get("MIN", "Minutes"),
                    "pts": get("PTS", "Points"), "reb": get("REB", "TRB", "TotalRebounds"),
                    "ast": get("AST", "Assists"), "fg3m": three,
                    "stl": get("STL", "Steals"), "blk": get("BLK", "Blocks"),
                    "tov": get("TO", "TOV", "Turnovers"),
                    "_source": "ESPN box score",
                })
    return rows


def get_boxscore_player_logs(events: list[dict[str, Any]]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Fetch box scores only for games ESPN has marked Final."""
    logs: list[dict[str, str]] = []
    checked = 0
    fetched = 0
    failures: list[str] = []
    for event in events:
        if str(event.get("status_state") or "").lower() != "post" or not event.get("id"):
            continue
        checked += 1
        event_id = str(event["id"])
        try:
            key = ("boxscore", event_id)
            cached = _CACHE.get(key)
            if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
                payload = cached[1]
            else:
                payload = _get_json(f"{BASE}/summary", {"event": event_id})
                _CACHE[key] = (time.monotonic(), payload)
            rows = _boxscore_player_rows(payload, event)
            if rows:
                logs.extend(rows)
                fetched += 1
            else:
                failures.append(f"{event_id}: no player rows")
        except ESPNError as exc:
            failures.append(f"{event_id}: {exc}")
    return logs, {
        "provider": "ESPN official NBA box scores",
        "finalized_events_checked": checked,
        "events_with_player_stats": fetched,
        "player_rows": len(logs),
        "failures": failures,
    }


def get_injuries() -> dict[str, Any]:
    cache_key = ("injuries", "league")
    cached = _CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]
    payload = _get_json(f"{BASE}/injuries")
    groups = payload.get("teams") or payload.get("injuries") or []
    players: list[dict[str, Any]] = []

    def add_entry(entry: dict[str, Any], team: dict[str, Any] | None = None) -> None:
        athlete = entry.get("athlete") or entry.get("player") or {}
        if not athlete:
            athlete = entry
        status = entry.get("status") or entry.get("type") or {}
        status_text = _name_value(status) if isinstance(status, dict) else _name_value(status)
        team_data = entry.get("team") or team or {}
        players.append({
            "player_id": athlete.get("id") if isinstance(athlete, dict) else None,
            "player": _name_value(athlete.get("displayName") or athlete.get("fullName") or athlete.get("name")) if isinstance(athlete, dict) else _name_value(athlete),
            "team_id": team_data.get("id") if isinstance(team_data, dict) else None,
            "team": _name_value(team_data.get("displayName") or team_data.get("name")) if isinstance(team_data, dict) else _name_value(team_data),
            "status": status_text,
            "details": _name_value(entry.get("details") or entry.get("comment") or entry.get("shortComment")),
            "date": entry.get("date") or entry.get("updated"),
            "source": "ESPN",
        })

    for group in groups:
        if not isinstance(group, dict):
            continue
        team = group.get("team") or {}
        entries = group.get("injuries") or group.get("items") or []
        if entries:
            for entry in entries:
                if isinstance(entry, dict):
                    add_entry(entry, team)
        elif group.get("athlete") or group.get("player"):
            add_entry(group, team)

    result = {
        "count": len(players), "players": players,
        "source": "ESPN public NBA injury report",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _CACHE[cache_key] = (time.monotonic(), result)
    return result



def _roster_name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _roster_athletes(node: Any):
    if isinstance(node, list):
        for item in node:
            yield from _roster_athletes(item)
    elif isinstance(node, dict):
        if node.get("id") and node.get("position"):
            yield node
        for key in ("athletes", "items", "entries", "positions", "groups"):
            if key in node:
                yield from _roster_athletes(node[key])


def get_team_roster_positions(team_abbreviation: str) -> dict[str, dict[str, Any]]:
    """Return current roster positions keyed by ESPN athlete ID."""
    slug = str(team_abbreviation or "").strip().lower()
    if not slug:
        return {}
    cache_key = ("roster", slug)
    cached = _CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < 24 * 60 * 60:
        return cached[1]
    payload = _get_json(f"{BASE}/teams/{slug}/roster")
    positions: dict[str, dict[str, Any]] = {}
    for athlete in _roster_athletes(payload):
        player_id = str(athlete.get("id") or "").strip()
        if not player_id or player_id in positions:
            continue
        raw = athlete.get("position") or {}
        if isinstance(raw, dict):
            abbreviation = str(raw.get("abbreviation") or raw.get("shortName") or "").upper().strip()
            name = str(raw.get("displayName") or raw.get("name") or "").strip()
        else:
            abbreviation, name = str(raw).upper().strip(), str(raw).strip()
        if abbreviation not in {"PG", "SG", "SF", "PF", "C", "G", "F", "FC", "GF"}:
            continue
        record = {
            "player_id": player_id,
            "position": abbreviation, "position_name": name or abbreviation,
            "position_source": "ESPN current team roster",
            "position_confidence": "high" if abbreviation in {"PG", "SG", "SF", "PF", "C"} else "medium",
        }
        positions[player_id] = record
        name_key = _roster_name_key(athlete.get("displayName") or athlete.get("fullName") or athlete.get("shortName"))
        if name_key and name_key not in positions:
            positions[name_key] = record
    _CACHE[cache_key] = (time.monotonic(), positions)
    return positions


def get_positions_for_teams(team_abbreviations: list[str]) -> dict[str, dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for abbreviation in sorted({str(x).strip().upper() for x in team_abbreviations if x}):
        try:
            combined.update(get_team_roster_positions(abbreviation))
        except ESPNError:
            continue
    return combined

def get_player_gamelog(player_id: str, season: int | None = None) -> dict[str, Any]:
    params = {"season": str(season)} if season else None
    payload = _get_json(f"{COMMON}/athletes/{player_id}/gamelog", params)
    labels = payload.get("labels") or payload.get("names") or []
    names = payload.get("names") or labels
    games = []
    for event in payload.get("events", []):
        values = event.get("stats") or []
        stats = {}
        for index, value in enumerate(values):
            key = names[index] if index < len(names) else f"stat_{index}"
            stats[key] = value
        opponent = event.get("opponent") or {}
        games.append({
            "event_id": event.get("id"), "date": event.get("date"),
            "opponent": opponent.get("displayName") or opponent.get("abbreviation"),
            "result": event.get("gameResult"), "stats": stats,
        })
    return {
        "player_id": str(player_id), "labels": labels, "count": len(games),
        "games": games, "source": "ESPN athlete game log",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

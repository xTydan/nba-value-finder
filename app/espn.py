"""Read-only client for ESPN's public NBA endpoints.

ESPN's public endpoints are undocumented and may change. Every parser is
defensive: missing fields stay null and never become fabricated statistics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
COMMON = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
TIMEOUT = 12.0
HEADERS = {"User-Agent": "NBA-Value-Finder/0.1 (read-only public data client)"}


class ESPNError(RuntimeError):
    """Raised when ESPN returns an unusable response."""


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


def _team_summary(competitor: dict[str, Any]) -> dict[str, Any]:
    team = competitor.get("team") or {}
    return {
        "id": team.get("id"),
        "name": team.get("displayName") or team.get("name"),
        "abbreviation": team.get("abbreviation"),
        "home_away": competitor.get("homeAway"),
        "score": competitor.get("score"),
        "winner": competitor.get("winner"),
    }


def get_scoreboard(date: str | None = None) -> dict[str, Any]:
    """Return scheduled/live/recent NBA events for YYYYMMDD (UTC date by default)."""
    requested_date = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    if len(requested_date) != 8 or not requested_date.isdigit():
        raise ValueError("date must use YYYYMMDD format")
    payload = _get_json(f"{BASE}/scoreboard", {"dates": requested_date})
    events = []
    for event in payload.get("events", []):
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions else {}
        status = (competition.get("status") or event.get("status") or {}).get("type") or {}
        competitors = competition.get("competitors") or []
        events.append({
            "id": event.get("id"),
            "name": event.get("name"),
            "short_name": event.get("shortName"),
            "date": event.get("date"),
            "status": status.get("description") or status.get("name"),
            "status_state": status.get("state"),
            "venue": (competition.get("venue") or {}).get("fullName"),
            "competitors": [_team_summary(item) for item in competitors],
            "source": "ESPN",
        })
    return {
        "date": requested_date,
        "count": len(events),
        "events": events,
        "source": "ESPN public NBA scoreboard",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_injuries() -> dict[str, Any]:
    """Return the league injury report, preserving ESPN's reported status/details."""
    payload = _get_json(f"{BASE}/injuries")
    groups = payload.get("teams") or payload.get("injuries") or []
    players: list[dict[str, Any]] = []

    def add_entry(entry: dict[str, Any], team: dict[str, Any] | None = None) -> None:
        athlete = entry.get("athlete") or entry.get("player") or {}
        if not athlete:
            athlete = entry
        status = entry.get("status") or entry.get("type") or {}
        if isinstance(status, dict):
            status_text = status.get("description") or status.get("name") or status.get("abbreviation")
        else:
            status_text = status
        team_data = entry.get("team") or team or {}
        players.append({
            "player_id": athlete.get("id"),
            "player": athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"),
            "team_id": team_data.get("id"),
            "team": team_data.get("displayName") or team_data.get("name"),
            "status": status_text,
            "details": entry.get("details") or entry.get("comment") or entry.get("shortComment"),
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

    return {
        "count": len(players),
        "players": players,
        "source": "ESPN public NBA injury report",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_player_gamelog(player_id: str, season: int | None = None) -> dict[str, Any]:
    """Return ESPN athlete game log; stats are kept as source labels + raw values."""
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
            "event_id": event.get("id"),
            "date": event.get("date"),
            "opponent": opponent.get("displayName") or opponent.get("abbreviation"),
            "result": event.get("gameResult"),
            "stats": stats,
        })
    return {
        "player_id": str(player_id),
        "labels": labels,
        "count": len(games),
        "games": games,
        "source": "ESPN athlete game log",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

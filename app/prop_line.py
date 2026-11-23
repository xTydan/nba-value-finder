"""PropLine NBA player-prop odds client. API keys stay server-side."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

BASE_URL = "https://api.prop-line.com/v1"
SPORT = "basketball_nba"
MARKETS = [
    "player_points", "player_rebounds", "player_assists", "player_threes",
    "player_steals", "player_blocks", "player_turnovers",
    "player_points_rebounds", "player_points_assists", "player_rebounds_assists",
    "player_points_rebounds_assists", "player_blocks_steals",
]
CACHE_TTL_SECONDS = 15 * 60
DEFAULT_MAX_AGE_SECONDS = 900
TIMEOUT = 20.0
_CACHE: tuple[float, dict[str, Any]] | None = None
# DFS pick'em products and exchanges are deliberately excluded from sportsbook odds.
EXCLUDED_BOOKS = {
    "prizepicks", "underdog", "kalshi", "polymarket", "polymarket_us",
    "draftkings_pick6", "dabble", "parlayplay", "sleeper", "sportzino",
    "fliff", "rebet", "prophetx", "novig", "courtside",
}
# Known traditional sportsbook operators returned by the authenticated smoke test.
# Strict allowlisting prevents DFS pick'em and prediction-market prices from leaking
# into a conventional sportsbook comparison.
ALLOWED_BOOKS = {
    "betmgm", "betrivers", "bovada", "draftkings", "elabet", "eurobet",
    "fanduel", "fanatics", "hardrockbet", "lottomatica", "pinnacle",
    "snai", "stoiximan", "superbet_pl", "sts", "tonybet", "unibet", "williamhillit",
    "eplay24", "thescorebet",
}


def _book_slug(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


class PropLineError(RuntimeError):
    pass


def _decimal_odds(price: Any) -> float | None:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    result = 1 + (100 / abs(value) if value < 0 else value / 100)
    return round(result, 4) if result > 1 else None


def _parse_events(payload: Any, now: datetime, max_age: int) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        events = payload.get("events")
        if events is None and isinstance(payload.get("data"), list):
            events = payload["data"]
    elif isinstance(payload, list):
        events = payload
    else:
        events = None
    if not isinstance(events, list):
        raise PropLineError("PropLine returned an unexpected odds response format")

    rows: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        start_raw = event.get("commence_time") or event.get("start_time")
        try:
            start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        # Only upcoming pregame fixtures. Never show frozen odds from live games.
        if start <= now or event.get("live") is True or event.get("completed") is True:
            continue

        for book in event.get("bookmakers") or []:
            if not isinstance(book, dict):
                continue
            book_key = str(book.get("key") or "").lower()
            book_title = book.get("title") or book_key
            if not book_key or book_key in EXCLUDED_BOOKS:
                continue
            if _book_slug(book_key) not in ALLOWED_BOOKS and _book_slug(book_title) not in ALLOWED_BOOKS:
                continue
            for market in book.get("markets") or []:
                if not isinstance(market, dict) or market.get("key") not in MARKETS:
                    continue
                updated_raw = market.get("last_update")
                try:
                    updated = datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue
                age = (now - updated).total_seconds()
                if age < -60 or age > max_age:
                    continue
                for outcome in market.get("outcomes") or []:
                    if not isinstance(outcome, dict):
                        continue
                    side = str(outcome.get("name") or "").strip().lower()
                    if side not in {"over", "under"}:
                        continue
                    player = outcome.get("description") or outcome.get("player_name")
                    line = outcome.get("point")
                    decimal = _decimal_odds(outcome.get("price"))
                    try:
                        line = float(line)
                    except (TypeError, ValueError):
                        continue
                    if not player or decimal is None:
                        continue
                    rows.append({
                        "event_id": str(event.get("id") or ""),
                        "home_team": event.get("home_team"),
                        "away_team": event.get("away_team"),
                        "commence_time": start.isoformat(),
                        "player": str(player),
                        "player_id": outcome.get("player_id"),
                        "market": market["key"],
                        "side": side.title(),
                        "line": line,
                        "american_odds": outcome.get("price"),
                        "decimal_odds": decimal,
                        "bookmaker": str(book_title),
                        "bookmaker_key": book_key,
                        "updated_at": updated.isoformat(),
                        "age_seconds": max(0, int(age)),
                        "source": "PropLine",
                    })
    rows.sort(key=lambda row: (row["commence_time"], row["player"].casefold(), row["market"], row["line"], row["bookmaker"]))
    return rows


def get_player_props(force_refresh: bool = False) -> dict[str, Any]:
    global _CACHE
    api_key = os.getenv("ODDS_API_KEY", "").strip()
    if not api_key:
        raise PropLineError("Brak konfiguracji ODDS_API_KEY po stronie serwera.")
    if _CACHE and not force_refresh and time.monotonic() - _CACHE[0] < CACHE_TTL_SECONDS:
        return _CACHE[1]

    max_age = int(os.getenv("ODDS_MAX_AGE_SECONDS", str(DEFAULT_MAX_AGE_SECONDS)))
    max_age = min(max(max_age, 60), 3600)
    params = {
        "markets": ",".join(MARKETS),
        "max_age": str(max_age),
        "includePregameOnly": "true",
    }
    headers = {"X-API-Key": api_key, "User-Agent": "NBA-Value-Finder/0.3"}
    try:
        response = httpx.get(f"{BASE_URL}/sports/{SPORT}/odds", params=params, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            message = "PropLine odrzucił klucz API (401). Sprawdź sekret ODDS_API_KEY."
        elif status == 403:
            message = "PropLine nie udostępnia tego zasobu na obecnym planie (403)."
        elif status == 429:
            message = "Limit zapytań PropLine został osiągnięty (429)."
        else:
            message = f"PropLine zwrócił HTTP {status}."
        raise PropLineError(message) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise PropLineError(f"Nie udało się pobrać kursów PropLine: {type(exc).__name__}") from exc

    now = datetime.now(timezone.utc)
    rows = _parse_events(payload, now, max_age)
    result = {
        "count": len(rows),
        "items": rows,
        "source": "PropLine",
        "fetched_at": now.isoformat(),
        "max_age_seconds": max_age,
        "markets_requested": MARKETS,
        "bookmakers": sorted({row["bookmaker"] for row in rows}),
        "notice": "Kursy są rzeczywistymi danymi źródłowymi; nie są jeszcze automatycznie oznaczane jako value bety.",
    }
    _CACHE = (time.monotonic(), result)
    return result


def status() -> dict[str, Any]:
    if not os.getenv("ODDS_API_KEY", "").strip():
        return {
            "provider": "PropLine NBA player props",
            "available": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "message": "Sekret ODDS_API_KEY nie jest dostępny w środowisku serwera.",
        }
    try:
        data = get_player_props()
        return {
            "provider": "PropLine NBA player props",
            "available": True,
            "checked_at": data["fetched_at"],
            "message": f"Połączenie działa. Aktualne przedmeczowe linie: {data['count']}; bukmacherzy: {', '.join(data['bookmakers']) or 'brak ofert'}.",
        }
    except PropLineError as exc:
        return {
            "provider": "PropLine NBA player props",
            "available": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "message": str(exc),
        }

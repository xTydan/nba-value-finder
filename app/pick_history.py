"""Persistent daily archive of the public top player-prop picks."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

WARSAW = ZoneInfo("Europe/Warsaw")
EASTERN = ZoneInfo("America/New_York")


def _parse_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _event_day_et(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    return parsed.astimezone(EASTERN).date().isoformat() if parsed else None


def _number(value: Any) -> float | None:
    try:
        if isinstance(value, str) and ":" in value:
            minutes, seconds = value.split(":", 1)
            return float(minutes) + float(seconds) / 60.0
        number = float(value)
        return number if number == number and abs(number) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _pick_side(row: dict[str, Any]) -> tuple[str, int, dict[str, Any] | None]:
    candidates = []
    for side in ("over", "under"):
        hits = int(row.get(f"{side}_hits") or 0)
        quotes = row.get(f"{side}_quotes") or []
        quote = next((q for q in quotes if _number(q.get("odds")) is not None and 1.70 <= float(q["odds"]) <= 2.20), None)
        if quote:
            candidates.append((hits, side, quote))
    if not candidates:
        return "", 0, None
    hits, side, quote = max(
        candidates,
        key=lambda item: (item[0], -abs(float(item[2]["odds"]) - 1.90)),
    )
    return side, hits, quote


def _team_key(value: Any) -> str:
    import re
    key = re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
    # ESPN commonly shortens the franchise name to "LA Clippers".
    if key in {"laclippers", "losangelesclippers"}:
        return "clippers"
    return key


def _settle(day_data: dict[str, Any], logs: list[dict[str, str]], stat_value, finalized_games: set[tuple[str, str, str]]) -> bool:
    changed = False
    for pick in day_data.get("picks", []):
        if pick.get("result") != "PENDING":
            continue
        player_id = str(pick.get("player_id") or "")
        game_day = pick.get("game_date_et")
        if not game_day:
            continue
        home = _team_key(pick.get("home_team"))
        away = _team_key(pick.get("away_team"))
        if not home or not away or (game_day, home, away) not in finalized_games:
            continue
        matching = [
            row for row in logs
            if (
                (player_id and str(row.get("player_id") or "") == player_id)
                or (not player_id and str(row.get("player_name") or "").casefold() == str(pick.get("player") or "").casefold())
            )
            and str(row.get("game_date") or "")[:10] == game_day
        ]
        if not matching:
            continue
        row = matching[0]
        minutes = _number(row.get("min"))
        if minutes == 0:
            pick["result"] = "VOID"
            pick["settled_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
            continue
        actual = stat_value(row, str(pick.get("market") or ""))
        if actual is None:
            continue
        line = _number(pick.get("line"))
        if line is None:
            continue
        pick["actual"] = actual
        pick["result"] = (
            "PUSH" if actual == line else
            "WIN" if (actual > line if pick["side"] == "OVER" else actual < line) else
            "LOSS"
        )
        pick["settled_at"] = datetime.now(timezone.utc).isoformat()
        changed = True
    return changed


def update_pick_history(
    board: list[dict[str, Any]],
    logs: list[dict[str, str]],
    site_data_dir: Path,
    now: datetime | None = None,
    games: list[dict[str, Any]] | None = None,
    finalized_games: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """Settle archived picks and freeze the first valid board for each Warsaw slate day."""
    from app.sportsdataverse import _stat_value

    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)

    # Determine the earliest scheduled game for each Warsaw calendar day.
    first_tipoff_by_day: dict[str, datetime] = {}
    for game in games or []:
        tipoff = _parse_datetime(game.get("date") or game.get("commence_time"))
        if not tipoff:
            continue
        tipoff = tipoff.astimezone(timezone.utc)
        slate_day = tipoff.astimezone(WARSAW).date().isoformat()
        if slate_day not in first_tipoff_by_day or tipoff < first_tipoff_by_day[slate_day]:
            first_tipoff_by_day[slate_day] = tipoff

    root_data = Path("data")
    root_data.mkdir(parents=True, exist_ok=True)
    history_path = root_data / "pick_history.json"
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(history, dict):
            raise ValueError("history root must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        history = {"version": 1, "days": {}}
    history.setdefault("version", 1)
    history.setdefault("days", {})

    # Archive every upcoming Warsaw slate day represented in the current board.
    # PropLine and ESPN use independent event IDs, so match by ET date and the
    # normalized home/away team names instead of assuming their IDs are equal.
    pending_days = sorted(
        ((day, tipoff) for day, tipoff in first_tipoff_by_day.items()
         if day not in history["days"]),
        key=lambda item: item[1],
    )
    capture_day = None
    today = now.astimezone(WARSAW).date().isoformat()

    changed = False
    finalized_games = finalized_games or set()
    for day_data in history["days"].values():
        if _settle(day_data, logs, _stat_value, finalized_games):
            changed = True

    game_keys_by_day: dict[str, set[tuple[str, str]]] = {}
    for game in games or []:
        parsed = _parse_datetime(game.get("date") or game.get("commence_time"))
        if not parsed:
            continue
        competitors = game.get("competitors") or []
        home = next((x.get("name") for x in competitors if x.get("home_away") == "home"), None)
        away = next((x.get("name") for x in competitors if x.get("home_away") == "away"), None)
        home = home or game.get("home_team")
        away = away or game.get("away_team")
        if home and away:
            day = parsed.astimezone(WARSAW).date().isoformat()
            game_keys_by_day.setdefault(day, set()).add((_team_key(home), _team_key(away)))

    for day, _tipoff in pending_days:
        candidates = []
        allowed_matchups = game_keys_by_day.get(day, set())
        for row in board:
            row_time = _parse_datetime(row.get("commence_time"))
            if not row_time or row_time.astimezone(WARSAW).date().isoformat() != day:
                continue
            matchup = (_team_key(row.get("home_team")), _team_key(row.get("away_team")))
            if allowed_matchups and matchup not in allowed_matchups:
                continue
            if not matchup[0] or not matchup[1]:
                continue
            side, hits, quote = _pick_side(row)
            sample = int(row.get("sample_size") or 0)
            if not side or not quote or sample < 8 or hits < 8:
                continue
            candidates.append((row, side, hits, quote))
        candidates.sort(
            key=lambda item: (
                item[2] / max(1, int(item[0].get("sample_size") or 0)),
                -abs(float(item[3]["odds"]) - 1.90),
                int(item[0].get("sample_size") or 0),
            ),
            reverse=True,
        )
        picks = []
        seen = set()
        for row, side, hits, quote in candidates:
            dedupe_key = (str(row.get("event_id") or ""), str(row.get("player_id") or row.get("player") or "").casefold(), str(row.get("market") or ""))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            picks.append({
                "pick_id": "|".join(str(row.get(k) or "") for k in
                    ("event_id", "player_id", "market", "line")) + "|" + side,
                "player": row.get("player"),
                "player_id": row.get("player_id"),
                "team": row.get("team") or row.get("team_abbreviation"),
                "home_team": row.get("home_team"),
                "away_team": row.get("away_team"),
                "event_id": row.get("event_id"),
                "game_date_et": _event_day_et(row.get("commence_time")),
                "market": row.get("market"),
                "line": row.get("line"),
                "side": side.upper(),
                "odds": float(quote["odds"]),
                "bookmaker": quote.get("bookmaker"),
                "l10_hits": hits,
                "l10_sample": int(row.get("sample_size") or 0),
                "captured_at": now.isoformat(),
                "result": "PENDING",
                "actual": None,
            })
            if len(picks) >= 24:
                break
        if picks:
            history["days"][day] = {
                "captured_at": now.isoformat(),
                "picks": picks,
            }
            changed = True
            if capture_day is None:
                capture_day = day

    if capture_day:
        today = capture_day
    if changed or not history_path.exists():
        history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    site_data_dir.mkdir(parents=True, exist_ok=True)
    (site_data_dir / "pick_history.json").write_text(
        json.dumps(history, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return {
        "days": len(history["days"]),
        "today_picks": len(history["days"].get(today, {}).get("picks", [])),
        "capture_day": capture_day,
        "first_tipoff": first_tipoff_by_day.get(capture_day).isoformat() if capture_day else None,
        "waiting_for_first_tipoff": False,
        "changed": changed,
        "path": str(history_path),
    }

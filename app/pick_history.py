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
        quote = next((q for q in quotes if _number(q.get("odds")) is not None), None)
        if quote:
            candidates.append((hits, side, quote))
    if not candidates:
        return "", 0, None
    hits, side, quote = max(
        candidates,
        key=lambda item: (item[0], -abs(float(item[2]["odds"]) - 1.90)),
    )
    return side, hits, quote


def _settle(day_data: dict[str, Any], logs: list[dict[str, str]], stat_value) -> bool:
    changed = False
    for pick in day_data.get("picks", []):
        if pick.get("result") != "PENDING":
            continue
        player_id = str(pick.get("player_id") or "")
        game_day = pick.get("game_date_et")
        if not player_id or not game_day:
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
        actual = stat_value(row, str(pick.get("market") or ""))
        if actual is None:
            # A box-score row with zero minutes is an official DNP/no-action.
            minutes = _number(row.get("min"))
            if minutes == 0:
                pick["result"] = "VOID"
                pick["settled_at"] = datetime.now(timezone.utc).isoformat()
                changed = True
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
) -> dict[str, Any]:
    """Settle archived picks and freeze the first qualifying daily top-24 slate."""
    from app.sportsdataverse import _stat_value

    now = now or datetime.now(timezone.utc)
    today = now.astimezone(WARSAW).date().isoformat()
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

    changed = False
    for day_data in history["days"].values():
        if _settle(day_data, logs, _stat_value):
            changed = True

    if today not in history["days"] and board:
        candidates = []
        for row in board:
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
        for row, side, hits, quote in candidates[:24]:
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
        if picks:
            history["days"][today] = {
                "captured_at": now.isoformat(),
                "picks": picks,
            }
            changed = True

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
        "changed": changed,
        "path": str(history_path),
    }

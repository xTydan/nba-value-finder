"""Build a recent-form player props board with per-game context."""
from __future__ import annotations
from collections import defaultdict
from typing import Any

PREFERRED_ODDS_MIN = 1.60
PREFERRED_ODDS_MAX = 2.20
MIN_REASONABLE_ODDS = 1.40
MAX_REASONABLE_ODDS = 3.00
MIN_HISTORY = 5


def _best_quote(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = []
    for row in rows:
        try:
            odds = float(row.get("decimal_odds"))
        except (TypeError, ValueError):
            continue
        if not MIN_REASONABLE_ODDS <= odds <= MAX_REASONABLE_ODDS:
            continue
        valid.append(row)
    if not valid:
        return None
    # Prefer the requested near-even price band, then the best available price.
    return max(valid, key=lambda row: (
        PREFERRED_ODDS_MIN <= float(row["decimal_odds"]) <= PREFERRED_ODDS_MAX,
        float(row["decimal_odds"]),
    ))


def build_props_board(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for offer in offers:
        form = offer.get("form") or {}
        values = form.get("recent_values")
        if not isinstance(values, list) or len(values) < MIN_HISTORY:
            continue
        try:
            line = float(offer.get("line"))
        except (TypeError, ValueError):
            continue
        key = (str(offer.get("event_id") or ""), str(offer.get("player") or "").casefold(),
               str(offer.get("market") or ""), line)
        if all(key[:3]):
            groups[key].append(offer)

    board = []
    for (_, _, market, line), rows in groups.items():
        sample = next((row for row in rows if (row.get("form") or {}).get("recent_values")), None)
        if not sample:
            continue
        form = sample["form"]
        values = [float(value) for value in form["recent_values"]]
        dates = form.get("recent_dates") or []
        recent_games = []
        # Dates and values are generated from the same ordered game-log rows.
        for index, value in enumerate(values):
            source = (form.get("recent_games") or [])
            detail = source[index] if index < len(source) and isinstance(source[index], dict) else {}
            recent_games.append({
                "date": dates[index] if index < len(dates) else detail.get("date"),
                "value": value,
                "game_id": detail.get("game_id"),
                "matchup": detail.get("matchup"),
                "opponent": detail.get("opponent"),
                "home_away": detail.get("home_away"),
            })
        over_hits = sum(value > line for value in values)
        under_hits = sum(value < line for value in values)
        pushes = sum(value == line for value in values)
        over_quote = _best_quote([row for row in rows if str(row.get("side", "")).lower() == "over"])
        under_quote = _best_quote([row for row in rows if str(row.get("side", "")).lower() == "under"])
        if not over_quote and not under_quote:
            continue
        base = over_quote or under_quote or sample
        board.append({
            "event_id": base.get("event_id"), "player": base.get("player"),
            "market": market, "line": line, "home_team": base.get("home_team"),
            "away_team": base.get("away_team"), "commence_time": base.get("commence_time"),
            "sample_size": len(values), "over_hits": over_hits, "under_hits": under_hits,
            "pushes": pushes, "over_rate": round(over_hits / len(values), 4),
            "under_rate": round(under_hits / len(values), 4), "recent_values": values,
            "recent_dates": dates, "recent_games": recent_games,
            "average_l10": form.get("average_l10"),
            "average_minutes_l10": form.get("average_minutes_l10"),
            "over_quote": {"odds": over_quote.get("decimal_odds"), "bookmaker": over_quote.get("bookmaker"),
                           "bookmaker_key": over_quote.get("bookmaker_key"), "age_seconds": over_quote.get("age_seconds")} if over_quote else None,
            "under_quote": {"odds": under_quote.get("decimal_odds"), "bookmaker": under_quote.get("bookmaker"),
                            "bookmaker_key": under_quote.get("bookmaker_key"), "age_seconds": under_quote.get("age_seconds")} if under_quote else None,
            "preferred_odds_range": [PREFERRED_ODDS_MIN, PREFERRED_ODDS_MAX],
            "analysis_key": base.get("analysis_key") or sample.get("analysis_key"),
            "best_side": ("over" if over_quote and (not under_quote or over_hits >= under_hits) else "under"),
        })
    board.sort(key=lambda row: (
        max(row["over_rate"] if row["over_quote"] else 0,
            row["under_rate"] if row["under_quote"] else 0),
        row["sample_size"]), reverse=True)
    return board

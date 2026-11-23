"""Build a recent-form player props board with per-game context."""
from __future__ import annotations
from collections import defaultdict
from typing import Any

PREFERRED_ODDS_MIN = 1.70
PREFERRED_ODDS_MAX = 2.20
MIN_REASONABLE_ODDS = 1.40
MAX_REASONABLE_ODDS = 3.00
MIN_HISTORY = 5


def _valid_quotes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = []
    for row in rows:
        try:
            odds = float(row.get("decimal_odds"))
        except (TypeError, ValueError):
            continue
        if MIN_REASONABLE_ODDS <= odds <= MAX_REASONABLE_ODDS:
            valid.append(row)
    return sorted(valid, key=lambda row: abs(float(row["decimal_odds"]) - 1.90))


def _best_quote(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = _valid_quotes(rows)
    if not valid:
        return None
    preferred = [row for row in valid if PREFERRED_ODDS_MIN <= float(row["decimal_odds"]) <= PREFERRED_ODDS_MAX]
    return min(preferred or valid, key=lambda row: abs(float(row["decimal_odds"]) - 1.90))


def _build_line_entry(line: float, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    sample = next((r for r in rows if isinstance((r.get("form") or {}).get("recent_values"), list)
                   and len(r["form"]["recent_values"]) >= MIN_HISTORY), None)
    if not sample:
        return None
    form = sample["form"]
    values = [float(v) for v in form["recent_values"]]
    over_hits, under_hits = sum(v > line for v in values), sum(v < line for v in values)
    pushes = sum(v == line for v in values)
    over_quotes = _valid_quotes([r for r in rows if str(r.get("side", "")).lower() == "over"])
    under_quotes = _valid_quotes([r for r in rows if str(r.get("side", "")).lower() == "under"])
    over_quote, under_quote = _best_quote(over_quotes), _best_quote(under_quotes)
    if not over_quote and not under_quote:
        return None
    available_hits = ([over_hits] if over_quote else []) + ([under_hits] if under_quote else [])
    best_hits = max(available_hits)
    best_side = "over" if over_quote and (not under_quote or over_hits >= under_hits) else "under"
    best_quote = over_quote if best_side == "over" else under_quote
    dates = form.get("recent_dates") or []
    source_games = form.get("recent_games") or []
    recent_games = []
    for i, value in enumerate(values):
        detail = source_games[i] if i < len(source_games) and isinstance(source_games[i], dict) else {}
        recent_games.append({
            "date": dates[i] if i < len(dates) else detail.get("date"), "value": value,
            "game_id": detail.get("game_id"), "matchup": detail.get("matchup"),
            "opponent": detail.get("opponent"), "home_away": detail.get("home_away"),
        })
    base = over_quote or under_quote or sample
    return {
        "event_id": base.get("event_id"), "player_id": base.get("player_id"), "player": base.get("player"),
        "player_position": base.get("player_position"), "player_position_name": base.get("player_position_name"),
        "position_confidence": base.get("position_confidence", "unknown"),
        "market": base.get("market") or sample.get("market"), "line": line,
        "home_team": base.get("home_team"), "away_team": base.get("away_team"),
        "commence_time": base.get("commence_time"), "sample_size": len(values),
        "over_hits": over_hits, "under_hits": under_hits, "pushes": pushes,
        "over_rate": round(over_hits / len(values), 4), "under_rate": round(under_hits / len(values), 4),
        "recent_values": values, "recent_dates": dates, "recent_games": recent_games,
        "average_l10": form.get("average_l10"), "average_minutes_l10": form.get("average_minutes_l10"),
        "over_quotes": [{"odds": q.get("decimal_odds"), "bookmaker": q.get("bookmaker"), "bookmaker_key": q.get("bookmaker_key"), "age_seconds": q.get("age_seconds")} for q in over_quotes],
        "under_quotes": [{"odds": q.get("decimal_odds"), "bookmaker": q.get("bookmaker"), "bookmaker_key": q.get("bookmaker_key"), "age_seconds": q.get("age_seconds")} for q in under_quotes],
        "over_quote": {"odds": over_quote.get("decimal_odds"), "bookmaker": over_quote.get("bookmaker"), "bookmaker_key": over_quote.get("bookmaker_key"), "age_seconds": over_quote.get("age_seconds")} if over_quote else None,
        "under_quote": {"odds": under_quote.get("decimal_odds"), "bookmaker": under_quote.get("bookmaker"), "bookmaker_key": under_quote.get("bookmaker_key"), "age_seconds": under_quote.get("age_seconds")} if under_quote else None,
        "preferred_odds_range": [PREFERRED_ODDS_MIN, PREFERRED_ODDS_MAX],
        "analysis_key": base.get("analysis_key") or sample.get("analysis_key"), "best_side": best_side,
        "_rank": (best_hits / len(values), best_hits, len(values),
                  -abs(float(best_quote["decimal_odds"]) - 1.90),
                  -abs(line - float(form.get("average_l10") or line))),
    }


def build_props_board(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # One displayed line per player + event + market. Alternative sportsbook lines
    # are compared and only the strongest available side/line is retained.
    groups: dict[tuple[str, str, str], dict[float, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for offer in offers:
        form = offer.get("form") or {}
        if not isinstance(form.get("recent_values"), list) or len(form["recent_values"]) < MIN_HISTORY:
            continue
        try:
            line = float(offer.get("line"))
        except (TypeError, ValueError):
            continue
        event = str(offer.get("event_id") or "")
        player = str(offer.get("player_id") or offer.get("player") or "").casefold()
        market = str(offer.get("market") or "")
        if event and player and market:
            groups[(event, player, market)][line].append(offer)

    board = []
    for alternatives in groups.values():
        candidates = [_build_line_entry(line, rows) for line, rows in alternatives.items()]
        candidates = [candidate for candidate in candidates if candidate]
        if candidates:
            selected = max(candidates, key=lambda row: row["_rank"])
            selected.pop("_rank", None)
            board.append(selected)
    board.sort(key=lambda row: (
        max(row["over_rate"] if row["over_quote"] else 0,
            row["under_rate"] if row["under_quote"] else 0),
        row["sample_size"]), reverse=True)
    return board

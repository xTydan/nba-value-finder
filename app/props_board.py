"""Build a recent-form board from real pregame player-prop quotes."""
from __future__ import annotations
from collections import defaultdict
from typing import Any


def _best_quote(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [r for r in rows if isinstance(r.get("decimal_odds"), (int, float))]
    return max(valid, key=lambda r: float(r["decimal_odds"])) if valid else None


def build_props_board(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for offer in offers:
        form = offer.get("form") or {}
        values = form.get("recent_values")
        if not isinstance(values, list) or len(values) < 5:
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
        sample = next((r for r in rows if (r.get("form") or {}).get("recent_values")), None)
        if not sample:
            continue
        form = sample["form"]
        values = [float(v) for v in form["recent_values"]]
        over_hits = sum(v > line for v in values)
        under_hits = sum(v < line for v in values)
        pushes = sum(v == line for v in values)
        over_quote = _best_quote([r for r in rows if str(r.get("side", "")).lower() == "over"])
        under_quote = _best_quote([r for r in rows if str(r.get("side", "")).lower() == "under"])
        base = over_quote or under_quote or sample
        board.append({
            "event_id": base.get("event_id"), "player": base.get("player"),
            "market": market, "line": line, "home_team": base.get("home_team"),
            "away_team": base.get("away_team"), "commence_time": base.get("commence_time"),
            "sample_size": len(values), "over_hits": over_hits, "under_hits": under_hits,
            "pushes": pushes, "over_rate": round(over_hits / len(values), 4),
            "under_rate": round(under_hits / len(values), 4), "recent_values": values,
            "recent_dates": form.get("recent_dates") or [],
            "average_l10": form.get("average_l10"),
            "average_minutes_l10": form.get("average_minutes_l10"),
            "over_quote": {"odds": over_quote.get("decimal_odds"), "bookmaker": over_quote.get("bookmaker"),
                           "bookmaker_key": over_quote.get("bookmaker_key"), "age_seconds": over_quote.get("age_seconds")} if over_quote else None,
            "under_quote": {"odds": under_quote.get("decimal_odds"), "bookmaker": under_quote.get("bookmaker"),
                            "bookmaker_key": under_quote.get("bookmaker_key"), "age_seconds": under_quote.get("age_seconds")} if under_quote else None,
            "analysis_key": base.get("analysis_key") or sample.get("analysis_key"),
        })
    board.sort(key=lambda x: (max(x["over_rate"], x["under_rate"]), x["sample_size"]), reverse=True)
    return board

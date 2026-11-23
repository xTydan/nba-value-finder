"""Conservative market-relative value screening for NBA player props.

This is line-shopping value, not a calibrated outcome prediction model.
A bookmaker's quote is compared with a no-vig consensus built only from
other bookmakers, avoiding use of the candidate quote in its own benchmark.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

MIN_REFERENCE_BOOKS = 2
MIN_TOTAL_BOOKS = MIN_REFERENCE_BOOKS + 1
MIN_ODDS = 1.60
MAX_ODDS = 2.20
MIN_EDGE = 0.025
MIN_EV = 0.04
MIN_RECENT_GAMES = 8


def _valid_odds(value: Any) -> float | None:
    try:
        odds = float(value)
    except (TypeError, ValueError):
        return None
    return odds if 1.01 <= odds <= 100 else None


def _no_vig_pair(over: float, under: float) -> tuple[float, float]:
    over_raw, under_raw = 1 / over, 1 / under
    total = over_raw + under_raw
    return over_raw / total, under_raw / total


def find_value_picks(
    offers: list[dict[str, Any]],
    min_edge: float = MIN_EDGE,
    min_ev: float = MIN_EV,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return best sportsbook quotes with independent no-vig market support."""
    groups: dict[tuple[str, str, str, float], dict[str, dict[str, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for offer in offers:
        try:
            line = float(offer.get("line"))
        except (TypeError, ValueError):
            continue
        side = str(offer.get("side") or "").title()
        book = str(offer.get("bookmaker_key") or offer.get("bookmaker") or "").strip().lower()
        player = str(offer.get("player") or "").strip()
        event = str(offer.get("event_id") or "").strip()
        market = str(offer.get("market") or "").strip()
        odds = _valid_odds(offer.get("decimal_odds"))
        if not all((player, event, market, book)) or side not in {"Over", "Under"} or odds is None:
            continue
        key = (event, player.casefold(), market, line)
        # Keep the freshest quote if duplicate rows occur for the same book/side.
        previous = groups[key][book].get(side)
        if previous is None or int(offer.get("age_seconds") or 0) < int(previous.get("age_seconds") or 0):
            groups[key][book][side] = offer

    picks: list[dict[str, Any]] = []
    complete_groups = 0
    for key, books in groups.items():
        complete = {
            book: pair for book, pair in books.items()
            if "Over" in pair and "Under" in pair
        }
        if len(complete) < MIN_TOTAL_BOOKS:
            continue
        complete_groups += 1
        for candidate_book, pair in complete.items():
            for side in ("Over", "Under"):
                quote = pair[side]
                odds = _valid_odds(quote.get("decimal_odds"))
                if odds is None or not MIN_ODDS <= odds <= MAX_ODDS:
                    continue
                reference_probabilities = []
                for reference_book, reference_pair in complete.items():
                    if reference_book == candidate_book:
                        continue
                    over_odds = _valid_odds(reference_pair["Over"].get("decimal_odds"))
                    under_odds = _valid_odds(reference_pair["Under"].get("decimal_odds"))
                    if over_odds is None or under_odds is None:
                        continue
                    probs = _no_vig_pair(over_odds, under_odds)
                    reference_probabilities.append(probs[0 if side == "Over" else 1])
                if len(reference_probabilities) < MIN_REFERENCE_BOOKS:
                    continue
                fair_probability = median(reference_probabilities)
                implied_probability = 1 / odds
                edge = fair_probability - implied_probability
                ev = fair_probability * odds - 1
                if edge < min_edge or ev < min_ev:
                    continue
                form = quote.get("form") or {}
                l10 = form.get("l10") or {}
                if int(form.get("sample_size") or 0) < MIN_RECENT_GAMES:
                    continue
                picks.append({
                    **quote,
                    "fair_probability": round(fair_probability, 4),
                    "implied_probability": round(implied_probability, 4),
                    "edge": round(edge, 4),
                    "ev": round(ev, 4),
                    "reference_books": len(reference_probabilities),
                    "reference_method": "median_no_vig_leave_one_bookmaker_out",
                    "l10": l10,
                    "value_type": "market_price_discrepancy",
                })

    # Deduplicate multiple eligible quotes for the same exact prop side by EV,
    # preserving the bookmaker with the best expected return.
    best: dict[tuple[str, str, str, float, str], dict[str, Any]] = {}
    for pick in picks:
        key = (
            str(pick.get("event_id")), str(pick.get("player", "")).casefold(),
            str(pick.get("market")), float(pick.get("line")), str(pick.get("side")),
        )
        if key not in best or pick["ev"] > best[key]["ev"]:
            best[key] = pick
    result = sorted(best.values(), key=lambda item: (item["ev"], item["edge"]), reverse=True)
    summary = {
        "method": "leave-one-bookmaker-out no-vig consensus",
        "minimum_reference_books": MIN_REFERENCE_BOOKS,
        "minimum_total_books": MIN_TOTAL_BOOKS,
        "minimum_odds": MIN_ODDS,
        "maximum_odds": MAX_ODDS,
        "minimum_edge": min_edge,
        "minimum_ev": min_ev,
        "minimum_recent_games": MIN_RECENT_GAMES,
        "complete_market_groups": complete_groups,
        "qualified_picks": len(result),
        "calibrated_prediction_model": False,
    }
    return result, summary

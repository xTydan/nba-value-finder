from app.value_model import find_value_picks


def make_offer(book, side, odds, age=20):
    return {
        "event_id": "game-1", "player": "Player One", "market": "player_points",
        "line": 24.5, "side": side, "decimal_odds": odds,
        "bookmaker_key": book, "bookmaker": book.title(), "age_seconds": age,
        "commence_time": "2026-11-25T01:00:00+00:00",
        "home_team": "Home", "away_team": "Away",
        "form": {"sample_size": 10, "l10": {"hits": 7, "decided": 10}},
    }


def test_value_pick_uses_two_other_books_and_excludes_candidate_book_from_fair_price():
    offers = [
        make_offer("book_a", "Over", 2.10), make_offer("book_a", "Under", 1.75),
        make_offer("book_b", "Over", 1.80), make_offer("book_b", "Under", 2.00),
        make_offer("book_c", "Over", 1.78), make_offer("book_c", "Under", 2.02),
    ]
    picks, summary = find_value_picks(offers)
    over = next(p for p in picks if p["side"] == "Over")
    assert over["bookmaker_key"] == "book_a"
    assert over["reference_books"] == 2
    assert over["ev"] > 0.04
    assert summary["calibrated_prediction_model"] is False


def test_no_pick_without_two_independent_reference_books():
    offers = [
        make_offer("book_a", "Over", 2.10), make_offer("book_a", "Under", 1.75),
        make_offer("book_b", "Over", 1.80), make_offer("book_b", "Under", 2.00),
    ]
    picks, _ = find_value_picks(offers)
    assert picks == []


def test_no_pick_when_recent_history_is_too_small():
    offers = [
        make_offer("book_a", "Over", 2.10), make_offer("book_a", "Under", 1.75),
        make_offer("book_b", "Over", 1.80), make_offer("book_b", "Under", 2.00),
        make_offer("book_c", "Over", 1.78), make_offer("book_c", "Under", 2.02),
    ]
    for offer in offers:
        offer["form"]["sample_size"] = 5
    picks, _ = find_value_picks(offers)
    assert picks == []

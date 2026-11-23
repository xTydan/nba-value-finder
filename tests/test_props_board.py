from app.props_board import build_props_board


def test_board_ranks_recent_coverage_and_keeps_both_sides_prices():
    base = {
        "event_id": "g1", "player": "Player One", "market": "player_points",
        "line": 20.5, "home_team": "Home", "away_team": "Away",
        "commence_time": "2026-11-24T00:00:00+00:00",
        "analysis_key": "p1:player_points",
        "form": {"sample_size": 10, "recent_values": [25, 22, 19, 30, 21, 18, 27, 24, 16, 23],
                 "recent_dates": [], "average_l10": 22.5, "average_minutes_l10": 33.2},
    }
    offers = [
        {**base, "side": "Over", "decimal_odds": 1.91, "bookmaker": "Book A"},
        {**base, "side": "Under", "decimal_odds": 1.95, "bookmaker": "Book B"},
    ]
    rows = build_props_board(offers)
    assert len(rows) == 1
    assert rows[0]["over_hits"] == 7
    assert rows[0]["under_hits"] == 3
    assert rows[0]["over_quote"]["odds"] == 1.91
    assert rows[0]["under_quote"]["bookmaker"] == "Book B"
    assert rows[0]["sample_size"] == 10

from app.props_board import build_props_board


def _offer(side, odds, line=20.5):
    return {
        "event_id": "g1", "player": "Player One", "market": "player_points",
        "line": line, "home_team": "Home", "away_team": "Away",
        "commence_time": "2026-11-24T00:00:00+00:00",
        "analysis_key": "p1:player_points", "side": side, "decimal_odds": odds,
        "bookmaker": "Book",
        "form": {"sample_size": 10, "recent_values": [25, 22, 19, 30, 21, 18, 27, 24, 16, 23],
                 "recent_dates": [], "average_l10": 22.5, "average_minutes_l10": 33.2},
    }


def test_board_keeps_only_sides_priced_160_to_220():
    rows = build_props_board([
        _offer("Over", 1.20), _offer("Under", 1.58),
        _offer("Over", 1.60), _offer("Under", 2.20),
        _offer("Over", 2.21),
    ])
    assert len(rows) == 1
    assert rows[0]["over_quote"]["odds"] == 1.60
    assert rows[0]["under_quote"]["odds"] == 2.20


def test_board_drops_line_when_both_prices_outside_band():
    rows = build_props_board([_offer("Over", 1.35), _offer("Under", 1.55)])
    assert rows == []


def test_board_keeps_real_line_and_recent_coverage():
    rows = build_props_board([_offer("Over", 1.91), _offer("Under", 1.95)])
    assert len(rows) == 1
    assert rows[0]["over_hits"] == 7
    assert rows[0]["under_hits"] == 3
    assert rows[0]["sample_size"] == 10

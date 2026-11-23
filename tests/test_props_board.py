from app.props_board import build_props_board


def _offer(side, odds, line=20.5, form=None):
    return {
        "event_id": "g1", "player": "Player One", "market": "player_points",
        "line": line, "home_team": "Home", "away_team": "Away",
        "commence_time": "2026-11-24T00:00:00+00:00",
        "analysis_key": "p1:player_points", "side": side, "decimal_odds": odds,
        "bookmaker": "Book",
        "form": form or {
            "sample_size": 10, "recent_values": [25, 22, 19, 30, 21, 18, 27, 24, 16, 23],
            "recent_dates": ["2026-11-20"] * 10,
            "recent_games": [{"date": "2026-11-20", "game_id": "002", "matchup": "AAA vs BBB"}] * 10,
            "average_l10": 22.5, "average_minutes_l10": 33.2,
        },
    }


def test_board_keeps_nonstandard_prices_and_marks_preferred_band():
    rows = build_props_board([
        _offer("Over", 1.20), _offer("Under", 1.58),
        _offer("Over", 1.60), _offer("Under", 2.20),
        _offer("Over", 2.25),
    ])
    assert len(rows) == 1
    assert rows[0]["over_quote"]["odds"] == 2.25
    assert rows[0]["under_quote"]["odds"] == 2.20
    assert rows[0]["recent_games"][0]["matchup"] == "AAA vs BBB"
    assert rows[0]["recent_games"][0]["date"] == "2026-11-20"


def test_board_drops_only_invalid_or_missing_prices():
    rows = build_props_board([_offer("Over", 1.0), _offer("Under", None)])
    assert rows == []


def test_board_keeps_real_line_and_recent_coverage():
    rows = build_props_board([_offer("Over", 1.91), _offer("Under", 1.95)])
    assert len(rows) == 1
    assert rows[0]["over_hits"] == 7
    assert rows[0]["under_hits"] == 3
    assert rows[0]["sample_size"] == 10

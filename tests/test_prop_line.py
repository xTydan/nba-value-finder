from datetime import datetime, timezone, timedelta

from app.prop_line import _decimal_odds, _parse_events


def test_american_odds_to_decimal():
    assert _decimal_odds(-110) == 1.9091
    assert _decimal_odds(150) == 2.5
    assert _decimal_odds(0) is None


def test_parse_only_fresh_pregame_two_way_props():
    now = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(seconds=30)).isoformat()
    future = (now + timedelta(hours=2)).isoformat()
    payload = [{
        "id": "game-1", "home_team": "Boston Celtics", "away_team": "Chicago Bulls",
        "commence_time": future, "live": False,
        "bookmakers": [{
            "key": "unibet", "title": "Unibet",
            "markets": [{
                "key": "player_points", "last_update": fresh,
                "outcomes": [
                    {"name": "Over", "description": "Jayson Tatum", "point": 27.5, "price": -110},
                    {"name": "Under", "description": "Jayson Tatum", "point": 27.5, "price": -105},
                ],
            }],
        }],
    }]
    rows = _parse_events(payload, now, 900)
    assert len(rows) == 2
    assert rows[0]["player"] == "Jayson Tatum"
    assert rows[0]["line"] == 27.5
    assert rows[0]["decimal_odds"] == 1.9091
    assert rows[0]["bookmaker"] == "Unibet"


def test_parse_rejects_live_stale_and_dfs_prices():
    now = datetime(2026, 11, 23, 18, 0, tzinfo=timezone.utc)
    future = (now + timedelta(hours=1)).isoformat()
    stale = (now - timedelta(hours=1)).isoformat()
    payload = [
        {"id": "live", "commence_time": future, "live": True, "bookmakers": []},
        {"id": "pregame", "commence_time": future, "bookmakers": [
            {"key": "prizepicks", "title": "PrizePicks", "markets": [
                {"key": "player_points", "last_update": (now - timedelta(seconds=5)).isoformat(),
                 "outcomes": [{"name": "Over", "description": "Player", "point": 20.5, "price": 100}]}
            ]},
            {"key": "unibet", "title": "Unibet", "markets": [
                {"key": "player_points", "last_update": stale,
                 "outcomes": [{"name": "Over", "description": "Player", "point": 20.5, "price": 100}]}
            ]},
        ]},
    ]
    assert _parse_events(payload, now, 900) == []

from app import espn


def test_scoreboard_normalizes_event(monkeypatch):
    monkeypatch.setattr(espn, "_get_json", lambda *args, **kwargs: {
        "events": [{
            "id": "123", "name": "Boston Celtics at New York Knicks",
            "shortName": "BOS @ NYK", "date": "2026-11-23T00:00Z",
            "competitions": [{
                "status": {"type": {"description": "Scheduled", "state": "pre"}},
                "venue": {"fullName": "Madison Square Garden"},
                "competitors": [
                    {"homeAway": "away", "team": {"id": "2", "displayName": "Boston Celtics", "abbreviation": "BOS"}},
                    {"homeAway": "home", "team": {"id": "18", "displayName": "New York Knicks", "abbreviation": "NYK"}},
                ],
            }],
        }]
    })
    result = espn.get_scoreboard("20261123")
    assert result["count"] == 1
    assert result["events"][0]["competitors"][0]["abbreviation"] == "BOS"
    assert result["events"][0]["status_state"] == "pre"


def test_injury_team_name_is_always_a_string(monkeypatch):
    monkeypatch.setattr(espn, "_get_json", lambda *args, **kwargs: {
        "teams": [{
            "team": {"id": "1", "name": {"displayName": "Los Angeles Lakers"}},
            "injuries": [{
                "athlete": {"id": "2", "displayName": "Player Name"},
                "status": {"description": "Out"},
            }],
        }]
    })
    result = espn.get_injuries()
    assert result["players"][0]["team"] == "Los Angeles Lakers"
    assert isinstance(result["players"][0]["team"], str)
    assert result["players"][0]["status"] == "Out"


def test_boxscore_parser_normalizes_player_stats_and_dnp():
    event = {"id": "game-1", "date": "2026-11-25T00:00:00Z"}
    payload = {"boxscore": {"players": [{
        "team": {"id": "1", "abbreviation": "BOS"},
        "statistics": [{"names": ["MIN", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "PTS"],
            "athletes": [
                {"athlete": {"id": "123", "displayName": "Player One"},
                 "stats": ["32:10", "8-15", "2-5", "4-4", "7", "6", "2", "1", "0", "22"]},
                {"athlete": {"id": "456", "displayName": "Player Two"},
                 "stats": ["DNP - Coach's Decision"]},
            ]}]
    }]}}
    rows = espn._boxscore_player_rows(payload, event)
    assert rows[0]["game_date"] == "2026-11-24"
    assert rows[0]["pts"] == "22"
    assert rows[0]["fg3m"] == "2"
    assert rows[0]["tov"] == "2"
    assert rows[0]["_source"] == "ESPN box score"
    assert rows[1]["min"] == "0:00"


def test_boxscore_fetch_skips_non_final_events(monkeypatch):
    calls = []
    monkeypatch.setattr(espn, "_get_json", lambda *args, **kwargs: calls.append(args) or {})
    logs, meta = espn.get_boxscore_player_logs([
        {"id": "scheduled", "status_state": "pre", "date": "2026-11-25T00:00:00Z"}
    ])
    assert logs == []
    assert calls == []
    assert meta["finalized_events_checked"] == 0

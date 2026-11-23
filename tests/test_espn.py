from app import espn


def test_scoreboard_normalizes_event(monkeypatch):
    monkeypatch.setattr(espn, "_get_json", lambda *args, **kwargs: {
        "events": [{
            "id": "123",
            "name": "Boston Celtics at New York Knicks",
            "shortName": "BOS @ NYK",
            "date": "2026-11-23T00:00Z",
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


def test_player_gamelog_keeps_source_values(monkeypatch):
    monkeypatch.setattr(espn, "_get_json", lambda *args, **kwargs: {
        "labels": ["MIN", "REB", "AST", "PTS"],
        "names": ["minutes", "rebounds", "assists", "points"],
        "events": [{
            "id": "game1",
            "date": "2026-11-20T00:00Z",
            "opponent": {"displayName": "Chicago Bulls"},
            "gameResult": "W",
            "stats": ["34", "8", "6", "22"],
        }],
    })
    result = espn.get_player_gamelog("1234", 2027)
    assert result["count"] == 1
    assert result["games"][0]["stats"]["points"] == "22"
    assert result["games"][0]["opponent"] == "Chicago Bulls"

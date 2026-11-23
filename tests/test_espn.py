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

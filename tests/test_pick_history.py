from datetime import datetime, timezone
import json

from app.pick_history import update_pick_history


def _board():
    return [{
        "event_id": "event-1",
        "player_id": "123",
        "player": "Keaton Wagler",
        "market": "player_points_rebounds_assists",
        "line": 13.5,
        "home_team": "Home",
        "away_team": "Away",
        "commence_time": "2026-11-25T01:00:00+00:00",
        "sample_size": 10,
        "over_hits": 9,
        "under_hits": 1,
        "over_quotes": [{"odds": 1.90, "bookmaker": "Book A"}, {"odds": 1.55, "bookmaker": "Book B"}],
        "under_quotes": [{"odds": 1.90, "bookmaker": "Book A"}],
    }]


def test_capture_daily_picks_and_settle_from_official_player_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    first_run = datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc)
    result = update_pick_history(_board(), [], site_data, first_run)
    assert result["today_picks"] == 1

    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    pick = saved["days"]["2026-11-24"]["picks"][0]
    assert pick["player"] == "Keaton Wagler"
    assert pick["side"] == "OVER"
    assert pick["odds"] == 1.90
    assert pick["result"] == "PENDING"

    logs = [{
        "player_id": "123",
        "player_name": "Keaton Wagler",
        "game_date": "2026-11-24",
        "pts": "10",
        "reb": "5",
        "ast": "5",
        "min": "30:00",
    }]
    second_run = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
    update_pick_history([], logs, site_data, second_run)
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    settled = saved["days"]["2026-11-24"]["picks"][0]
    assert settled["actual"] == 20.0
    assert settled["result"] == "WIN"


def test_history_uses_only_default_odds_band_and_requires_eight_hits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    board = _board()
    board[0]["over_quotes"] = [{"odds": 1.55, "bookmaker": "Outside"}]
    board[0]["under_quotes"] = [{"odds": 2.30, "bookmaker": "Outside"}]
    result = update_pick_history(board, [], tmp_path / "site" / "data",
                                 datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc))
    assert result["today_picks"] == 0

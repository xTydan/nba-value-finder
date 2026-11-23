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
        "commence_time": "2026-11-24T00:00:00Z",
        "sample_size": 10,
        "over_hits": 9,
        "under_hits": 1,
        "over_quotes": [{"odds": 1.90, "bookmaker": "Book A"}, {"odds": 1.55, "bookmaker": "Book B"}],
        "under_quotes": [{"odds": 1.90, "bookmaker": "Book A"}],
    }]


def _games():
    return [{"id": "event-1", "date": "2026-11-24T00:00:00Z", "status_state": "pre"}]


def test_does_not_capture_before_first_tipoff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    before_tipoff = datetime(2026, 11, 23, 23, 45, tzinfo=timezone.utc)
    result = update_pick_history(_board(), [], site_data, before_tipoff, games=_games())
    assert result["today_picks"] == 0
    assert result["capture_day"] is None
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"] == {}


def test_capture_daily_picks_only_at_first_tipoff_and_settle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    first_run = datetime(2026, 11, 24, 0, 7, tzinfo=timezone.utc)
    result = update_pick_history(_board(), [], site_data, first_run, games=_games())
    assert result["today_picks"] == 1
    assert result["capture_day"] == "2026-11-24"

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
    update_pick_history([], logs, site_data, second_run, games=[])
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    settled = saved["days"]["2026-11-24"]["picks"][0]
    assert settled["actual"] == 20.0
    assert settled["result"] == "WIN"


def test_history_uses_only_default_odds_band_and_requires_eight_hits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    board = _board()
    board[0]["over_quotes"] = [{"odds": 1.55, "bookmaker": "Outside"}]
    board[0]["under_quotes"] = [{"odds": 2.30, "bookmaker": "Outside"}]
    result = update_pick_history(
        board, [], tmp_path / "site" / "data",
        datetime(2026, 11, 24, 0, 7, tzinfo=timezone.utc), games=_games()
    )
    assert result["today_picks"] == 0


def test_dnp_box_score_row_is_void_even_when_stats_are_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    first_run = datetime(2026, 11, 24, 0, 7, tzinfo=timezone.utc)
    update_pick_history(_board(), [], site_data, first_run, games=_games())
    logs = [{
        "player_id": "123",
        "player_name": "Keaton Wagler",
        "game_date": "2026-11-24",
        "pts": "0",
        "reb": "0",
        "ast": "0",
        "min": "0:00",
    }]
    update_pick_history([], logs, site_data,
                        datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc), games=[])
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"]["2026-11-24"]["picks"][0]["result"] == "VOID"

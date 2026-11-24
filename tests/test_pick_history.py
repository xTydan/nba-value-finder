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


def _finalized():
    return {("2026-11-23", "home", "away")}


def test_captures_before_first_tipoff_when_valid_picks_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    before_tipoff = datetime(2026, 11, 23, 23, 45, tzinfo=timezone.utc)
    result = update_pick_history(_board(), [], site_data, before_tipoff, games=_games())
    assert result["today_picks"] == 1
    assert result["capture_day"] == "2026-11-24"
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert len(saved["days"]["2026-11-24"]["picks"]) == 1



def test_game_at_warsaw_midnight_is_archived_under_new_local_day(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    board = _board()
    board[0]["commence_time"] = "2026-11-23T23:00:00Z"
    games = [{"id": "event-1", "date": "2026-11-23T23:00:00Z", "status_state": "pre"}]

    before_midnight = datetime(2026, 11, 23, 22, 59, tzinfo=timezone.utc)
    result = update_pick_history(board, [], site_data, before_midnight, games=games)
    assert result["capture_day"] == "2026-11-24"
    assert result["today_picks"] == 1

    # Once frozen before local midnight, the next build cannot replace it.
    after_midnight = datetime(2026, 11, 23, 23, 7, tzinfo=timezone.utc)
    changed_board = _board()
    changed_board[0]["line"] = 99.5
    result = update_pick_history(changed_board, [], site_data, after_midnight, games=games)
    assert result["capture_day"] is None
    assert result["today_picks"] == 1
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert "2026-11-24" in saved["days"]
    assert saved["days"]["2026-11-24"]["picks"][0]["line"] == 13.5


def test_capture_retries_after_delayed_workflow_without_90_minute_cutoff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    delayed_run = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
    result = update_pick_history(_board(), [], site_data, delayed_run, games=_games())
    assert result["today_picks"] == 1
    assert result["capture_day"] == "2026-11-24"
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"]["2026-11-24"]["picks"][0]["result"] == "PENDING"


def test_capture_daily_picks_only_once_and_settle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    first_run = datetime(2026, 11, 24, 0, 7, tzinfo=timezone.utc)
    result = update_pick_history(_board(), [], site_data, first_run, games=_games())
    assert result["today_picks"] == 1
    assert result["capture_day"] == "2026-11-24"

    # A later board must not overwrite the frozen first snapshot.
    changed_board = _board()
    changed_board[0]["line"] = 99.5
    later_run = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
    update_pick_history(changed_board, [], site_data, later_run, games=_games())
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    pick = saved["days"]["2026-11-24"]["picks"][0]
    assert pick["line"] == 13.5
    assert pick["player"] == "Keaton Wagler"
    assert pick["side"] == "OVER"
    assert pick["odds"] == 1.90
    assert pick["result"] == "PENDING"

    logs = [{
        "player_id": "123",
        "player_name": "Keaton Wagler",
        "game_date": "2026-11-23",
        "pts": "10",
        "reb": "5",
        "ast": "5",
        "min": "30:00",
    }]
    second_run = datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc)
    # A player row by itself must not settle a pick while ESPN has not confirmed Final.
    update_pick_history([], logs, site_data, second_run, games=[], finalized_games=set())
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"]["2026-11-24"]["picks"][0]["result"] == "PENDING"

    update_pick_history([], logs, site_data, second_run, games=[], finalized_games=_finalized())
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
        "game_date": "2026-11-23",
        "pts": "0",
        "reb": "0",
        "ast": "0",
        "min": "0:00",
    }]
    update_pick_history([], logs, site_data,
                        datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc), games=[], finalized_games=_finalized())
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"]["2026-11-24"]["picks"][0]["result"] == "VOID"



def test_archive_matches_props_to_espn_by_matchup_not_provider_event_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    board = _board()
    board[0]["event_id"] = "prop-line-event-999"
    games = [{
        "id": "espn-event-123",
        "date": "2026-11-24T00:00:00Z",
        "status_state": "pre",
        "competitors": [
            {"home_away": "home", "name": "Home"},
            {"home_away": "away", "name": "Away"},
        ],
    }]
    result = update_pick_history(
        board, [], tmp_path / "site" / "data",
        datetime(2026, 11, 23, 23, 45, tzinfo=timezone.utc), games=games
    )
    assert result["today_picks"] == 1
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"]["2026-11-24"]["picks"][0]["event_id"] == "prop-line-event-999"


def test_archives_multiple_upcoming_slate_days_in_one_build(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = _board()[0]
    second = dict(first)
    second.update({
        "event_id": "event-2",
        "player_id": "456",
        "player": "Another Player",
        "home_team": "Home 2",
        "away_team": "Away 2",
        "commence_time": "2026-11-25T01:00:00Z",
    })
    games = [
        {"id": "espn-1", "date": "2026-11-24T00:00:00Z", "status_state": "pre",
         "competitors": [{"home_away": "home", "name": "Home"}, {"home_away": "away", "name": "Away"}]},
        {"id": "espn-2", "date": "2026-11-25T01:00:00Z", "status_state": "pre",
         "competitors": [{"home_away": "home", "name": "Home 2"}, {"home_away": "away", "name": "Away 2"}]},
    ]
    update_pick_history(
        [first, second], [], tmp_path / "site" / "data",
        datetime(2026, 11, 23, 23, 45, tzinfo=timezone.utc), games=games
    )
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert set(saved["days"]) == {"2026-11-24", "2026-11-25"}
    assert saved["days"]["2026-11-24"]["picks"][0]["player"] == "Keaton Wagler"
    assert saved["days"]["2026-11-25"]["picks"][0]["player"] == "Another Player"



def test_team_key_normalizes_espn_la_clippers_alias():
    from app.pick_history import _team_key
    assert _team_key("LA Clippers") == _team_key("Los Angeles Clippers") == "clippers"


def test_settlement_falls_back_to_normalized_player_name_when_id_differs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    update_pick_history(_board(), [], site_data,
                        datetime(2026, 11, 24, 0, 7, tzinfo=timezone.utc), games=_games())
    logs = [{
        "player_id": "different-provider-id",
        "player_name": "Keaton  Wagler",
        "game_date": "2026-11-23",
        "team_abbreviation": "HOME",
        "pts": "10",
        "reb": "5",
        "ast": "5",
        "min": "30:00",
    }]
    update_pick_history([], logs, site_data,
                        datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc),
                        games=[], finalized_games=_finalized())
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    pick = saved["days"]["2026-11-24"]["picks"][0]
    assert pick["actual"] == 20.0
    assert pick["result"] == "WIN"


def test_settlement_uses_minutes_fallback_for_dnp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    site_data = tmp_path / "site" / "data"
    update_pick_history(_board(), [], site_data,
                        datetime(2026, 11, 24, 0, 7, tzinfo=timezone.utc), games=_games())
    logs = [{
        "player_id": "123",
        "player_name": "Keaton Wagler",
        "game_date": "2026-11-23",
        "pts": "0",
        "reb": "0",
        "ast": "0",
        "minutes": "0:00",
    }]
    update_pick_history([], logs, site_data,
                        datetime(2026, 11, 25, 16, 0, tzinfo=timezone.utc),
                        games=[], finalized_games=_finalized())
    saved = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    assert saved["days"]["2026-11-24"]["picks"][0]["result"] == "VOID"


def test_separate_all_archive_captures_each_eligible_side_from_nov_25(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    board = _board()
    board[0]["commence_time"] = "2026-11-25T00:00:00Z"
    board[0]["under_hits"] = 8
    board[0]["under_quotes"] = [{"odds": 1.85, "bookmaker": "Book Under"}]
    games = [{
        "id": "espn-event-1",
        "date": "2026-11-25T00:00:00Z",
        "status_state": "pre",
        "competitors": [
            {"home_away": "home", "name": "Home"},
            {"home_away": "away", "name": "Away"},
        ],
    }]
    update_pick_history(
        board, [], tmp_path / "site" / "data",
        datetime(2026, 11, 24, 23, 45, tzinfo=timezone.utc), games=games
    )
    daily = json.loads((tmp_path / "data" / "pick_history.json").read_text())
    all_history = json.loads((tmp_path / "data" / "all_pick_history.json").read_text())
    assert len(daily["days"]["2026-11-25"]["picks"]) == 1
    all_picks = all_history["days"]["2026-11-25"]["picks"]
    assert {pick["side"] for pick in all_picks} == {"OVER", "UNDER"}
    assert len(all_picks) == 2
    assert {pick["bookmaker"] for pick in all_picks} == {"Book A", "Book Under"}


def test_all_archive_is_settled_by_same_official_finalized_game_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    board = _board()
    board[0]["commence_time"] = "2026-11-25T00:00:00Z"
    board[0]["under_hits"] = 8
    board[0]["under_quotes"] = [{"odds": 1.85, "bookmaker": "Book Under"}]
    games = [{
        "id": "espn-event-1",
        "date": "2026-11-25T00:00:00Z",
        "status_state": "pre",
        "competitors": [
            {"home_away": "home", "name": "Home"},
            {"home_away": "away", "name": "Away"},
        ],
    }]
    site_data = tmp_path / "site" / "data"
    first_run = datetime(2026, 11, 24, 23, 45, tzinfo=timezone.utc)
    update_pick_history(board, [], site_data, first_run, games=games)
    logs = [{
        "player_id": "123",
        "player_name": "Keaton Wagler",
        "game_date": "2026-11-24",
        "pts": "10",
        "reb": "5",
        "ast": "5",
        "min": "30:00",
    }]
    finalized = {("2026-11-24", "home", "away")}
    update_pick_history(
        [], logs, site_data, datetime(2026, 11, 26, 16, 0, tzinfo=timezone.utc),
        games=[], finalized_games=finalized
    )
    all_history = json.loads((tmp_path / "data" / "all_pick_history.json").read_text())
    results = {pick["side"]: pick["result"] for pick in all_history["days"]["2026-11-25"]["picks"]}
    assert results == {"OVER": "WIN", "UNDER": "LOSS"}
    assert all(pick["actual"] == 20 for pick in all_history["days"]["2026-11-25"]["picks"])


def test_all_archive_does_not_capture_before_nov_25(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    update_pick_history(
        _board(), [], tmp_path / "site" / "data",
        datetime(2026, 11, 23, 23, 45, tzinfo=timezone.utc), games=_games()
    )
    all_history = json.loads((tmp_path / "data" / "all_pick_history.json").read_text())
    assert all_history["days"] == {}

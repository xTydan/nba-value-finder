from app.sportsdataverse import _hit_summary, _latest_injury_rows, enrich_player_props, normalize_name


def test_normalize_player_names():
    assert normalize_name("Nikola Jokić") == "nikolajokic"
    assert normalize_name("Jayson Tatum Jr.") == "jaysontatumjr"


def test_hit_summary_handles_pushes():
    result = _hit_summary([20, 25, 25, 30], 25, "Over")
    assert result == {"hits": 1, "games": 4, "pushes": 2, "decided": 2, "rate": 0.5}


def test_latest_injury_row_uses_latest_report_per_game_player():
    rows = [
        {"game_id": "g1", "person_id": "p1", "report_datetime": "2026-11-01 12:00", "current_status": "Questionable"},
        {"game_id": "g1", "person_id": "p1", "report_datetime": "2026-11-01 16:00", "current_status": "Out"},
    ]
    latest = _latest_injury_rows(rows)
    assert latest[("g1", "p1")]["current_status"] == "Out"


def test_enrichment_computes_l10_and_explicit_teammate_absence_split():
    logs, injuries = [], []
    for i, (day, status, played) in enumerate([
        ("2026-11-01", "Available", True), ("2026-11-03", "Out", False),
        ("2026-11-05", "Available", True), ("2026-11-07", "Out", False),
    ]):
        game = f"g{i}"
        logs.append({"player_id": "p1", "player_name": "Player One", "game_id": game,
                     "game_date": day, "team_id": "10", "min": "35",
                     "pts": str(20 + i * 5), "reb": "5", "ast": "4"})
        if status == "Out":
            injuries.append({"game_id": game, "person_id": "p2", "team_id": "10",
                             "report_datetime": day + " 12:00", "current_status": status,
                             "report_player_name": "Two, Player"})
        if played:
            logs.append({"player_id": "p2", "player_name": "Player Two", "game_id": game,
                         "game_date": day, "team_id": "10", "min": "30",
                         "pts": "10", "reb": "3", "ast": "3"})
    offer = {"player": "Player One", "player_id": None, "market": "player_points",
             "line": 27.5, "side": "Over"}
    enriched, summary, analysis = enrich_player_props([offer], logs, injuries)
    assert enriched[0]["form"]["sample_size"] == 4
    assert enriched[0]["form"]["l10"]["hits"] == 2
    split = analysis[enriched[0]["analysis_key"]]["teammate_splits"][0]
    assert split["teammate"] == "Player Two"
    assert split["active_games"] == 2 and split["out_games"] == 2
    assert split["average_with_out"] > split["average_with_active"]
    assert summary["offers_enriched"] == 1


def test_only_reports_from_before_game_date_are_used():
    from app.sportsdataverse import _keep_pregame_reports
    injuries = [
        {"game_id": "g1", "game_date": "2026-11-02", "person_id": "p1",
         "report_datetime": "2026-11-01 18:00:00", "current_status": "Questionable"},
        {"game_id": "g1", "game_date": "2026-11-02", "person_id": "p1",
         "report_datetime": "2026-11-02 09:00:00", "current_status": "Out"},
    ]
    kept = _keep_pregame_reports(injuries)
    assert len(kept) == 1
    assert kept[0]["current_status"] == "Questionable"


def test_combined_prop_markets_are_derived_from_box_score_components():
    from app.sportsdataverse import _stat_value
    row = {"pts": "21", "reb": "7", "ast": "5"}
    assert _stat_value(row, "player_points_rebounds") == 28
    assert _stat_value(row, "player_points_assists") == 26
    assert _stat_value(row, "player_rebounds_assists") == 12


def test_injury_filter_keeps_starters_and_core_rotation_only():
    from app.sportsdataverse import filter_impact_injuries

    logs = [
        {"player_id": "p1", "player_name": "Starter One", "game_date": f"2026-11-{i:02d}",
         "min": "31", "start_position": "PG"}
        for i in range(1, 7)
    ] + [
        {"player_id": "p2", "player_name": "Bench One", "game_date": f"2026-11-{i:02d}",
         "min": "8", "start_position": ""}
        for i in range(1, 7)
    ] + [
        {"player_id": "p3", "player_name": "Sixth Player", "game_date": f"2026-11-{i:02d}",
         "min": "27", "start_position": ""}
        for i in range(1, 7)
    ]
    injuries = [
        {"player_id": "p1", "player": "Starter One", "team": "Team", "status": "Out"},
        {"player_id": "p2", "player": "Bench One", "team": "Team", "status": "Out"},
        {"player_id": "p3", "player": "Sixth Player", "team": "Team", "status": "Questionable"},
    ]
    result = filter_impact_injuries(injuries, logs)
    assert [row["player"] for row in result] == ["Starter One", "Sixth Player"]
    assert result[0]["rotation_role"] == "Starter"
    assert result[1]["rotation_role"] == "Ważna rotacja"

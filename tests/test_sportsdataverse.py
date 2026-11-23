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
    logs = []
    injuries = []
    # Player p1 played 4 games; teammate p2 was out twice and played twice.
    for i, (date, p2_status, p2_played) in enumerate([
        ("2026-11-01", "Available", True),
        ("2026-11-03", "Out", False),
        ("2026-11-05", "Available", True),
        ("2026-11-07", "Out", False),
    ]):
        game = f"g{i}"
        logs.append({
            "player_id": "p1", "player_name": "Player One", "game_id": game,
            "game_date": date, "team_id": "10", "min": "35",
            "pts": str(20 + i * 5), "reb": "5", "ast": "4",
        })
        injuries.append({
            "game_id": game, "person_id": "p2", "team_id": "10",
            "report_datetime": date + " 12:00", "current_status": p2_status,
            "report_player_name": "Two, Player",
        })
        if p2_played:
            logs.append({
                "player_id": "p2", "player_name": "Player Two", "game_id": game,
                "game_date": date, "team_id": "10", "min": "30",
                "pts": "10", "reb": "3", "ast": "3",
            })
    offer = {"player": "Player One", "player_id": None, "market": "player_points",
             "line": 22.5, "side": "Over"}
    enriched, summary = enrich_player_props([offer], logs, injuries)
    form = enriched[0]["form"]
    assert form["sample_size"] == 4
    assert form["l10"]["hits"] == 2
    split = enriched[0]["teammate_splits"][0]
    assert split["teammate"] == "Player Two"
    assert split["active_games"] == 2
    assert split["out_games"] == 2
    assert split["average_with_out"] > split["average_with_active"]
    assert summary["offers_enriched"] == 1

from app.matchup_context import build_matchup_context


def _team_row(game, day, team_id, abbreviation, points, fga, fta, oreb, tov, reb, ast):
    return {
        "game_id": game, "game_date": day, "team_id": team_id,
        "team_abbreviation": abbreviation, "min": "30",
        "pts": str(points), "fga": str(fga), "fta": str(fta),
        "oreb": str(oreb), "tov": str(tov), "reb": str(reb),
        "ast": str(ast), "fg3m": "10", "stl": "5", "blk": "4",
    }


def test_matchup_context_aggregates_team_logs_and_excludes_same_day():
    logs = []
    for i in range(6):
        day = f"2026-11-{i + 1:02d}"
        logs.extend([
            _team_row(f"g{i}", day, "1", "BOS", 110, 90, 20, 10, 12, 45, 25),
            _team_row(f"g{i}", day, "2", "NYK", 100, 88, 18, 8, 14, 40, 20),
        ])
    # A same-day game must not leak into the pregame sample.
    logs.extend([
        _team_row("today", "2026-11-07", "1", "BOS", 140, 100, 30, 12, 10, 50, 30),
        _team_row("today", "2026-11-07", "2", "NYK", 90, 80, 15, 6, 12, 35, 18),
    ])
    offers = [{
        "home_team": "Boston Celtics", "away_team": "New York Knicks",
        "commence_time": "2026-11-07T23:00:00Z", "market": "player_points",
    }]
    enriched, summary = build_matchup_context(offers, logs)
    context = enriched[0]["matchup_context"]
    assert context["available"] is True
    assert context["home_team"] == "BOS"
    assert context["away_team"] == "NYK"
    assert context["sample_games"] == 6
    assert context["home_offensive_rating"] is not None
    assert context["away_defensive_rating"] is not None
    assert context["home_opponent_market_allowed"] == 100
    assert context["home_possessions_per_game"] is not None
    assert context["home_points_allowed"] == 100
    assert context["away_points_allowed"] == 110
    assert context["league_points_allowed"] is not None
    assert context["home_pace"] is not None
    assert context["away_pace"] is not None
    assert context["league_pace"] is not None
    assert context["league_average_minutes"] is not None
    assert summary["offers_with_matchup_context"] == 1


def test_missing_possession_components_do_not_fabricate_ratings():
    logs = []
    for i in range(5):
        day = f"2026-11-{i + 1:02d}"
        for team_id, abbr in (("1", "BOS"), ("2", "NYK")):
            logs.append({
                "game_id": f"g{i}", "game_date": day, "team_id": team_id,
                "team_abbreviation": abbr, "min": "30", "pts": "100",
                "reb": "40", "ast": "20",
            })
    enriched, _ = build_matchup_context([{
        "home_team": "Boston Celtics", "away_team": "New York Knicks",
        "commence_time": "2026-11-07T23:00:00Z", "market": "player_points",
    }], logs)
    context = enriched[0]["matchup_context"]
    assert context["available"] is True
    assert context["home_offensive_rating"] is None
    assert context["home_defensive_rating"] is None
    assert context["home_possessions_per_game"] is None

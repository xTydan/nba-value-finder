"""Conservative pre-game team matchup context derived from player game logs.

This module is intentionally read-only with respect to pick selection and settlement.
It aggregates player box scores into team-game totals and never substitutes missing
box-score components with estimates.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.sportsdataverse import _number, normalize_name

ET = ZoneInfo("America/New_York")
MIN_TEAM_GAMES = 5
POSSESSION_FIELDS = ("fga", "oreb", "tov", "fta", "pts")
MARKET_TOTAL_FIELDS = {
    "player_points": ("pts",),
    "player_rebounds": ("reb",),
    "player_assists": ("ast",),
    "player_threes": ("fg3m",),
    "player_steals": ("stl",),
    "player_blocks": ("blk",),
    "player_turnovers": ("tov",),
    "player_points_rebounds": ("pts", "reb"),
    "player_points_assists": ("pts", "ast"),
    "player_rebounds_assists": ("reb", "ast"),
    "player_points_rebounds_assists": ("pts", "reb", "ast"),
    "player_blocks_steals": ("blk", "stl"),
}
TEAM_ALIASES = {
    "ATL": ("atlanta hawks",), "BOS": ("boston celtics",),
    "BKN": ("brooklyn nets",), "CHA": ("charlotte hornets",),
    "CHI": ("chicago bulls",), "CLE": ("cleveland cavaliers",),
    "DAL": ("dallas mavericks",), "DEN": ("denver nuggets",),
    "DET": ("detroit pistons",), "GSW": ("golden state warriors",),
    "HOU": ("houston rockets",), "IND": ("indiana pacers",),
    "LAC": ("los angeles clippers", "la clippers"),
    "LAL": ("los angeles lakers", "la lakers"),
    "MEM": ("memphis grizzlies",), "MIA": ("miami heat",),
    "MIL": ("milwaukee bucks",), "MIN": ("minnesota timberwolves",),
    "NOP": ("new orleans pelicans",), "NYK": ("new york knicks",),
    "OKC": ("oklahoma city thunder",), "ORL": ("orlando magic",),
    "PHI": ("philadelphia 76ers",), "PHX": ("phoenix suns",),
    "POR": ("portland trail blazers",), "SAC": ("sacramento kings",),
    "SAS": ("san antonio spurs",), "TOR": ("toronto raptors",),
    "UTA": ("utah jazz",), "WAS": ("washington wizards",),
}


def _game_day(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo:
            return parsed.astimezone(ET).date().isoformat()
        return parsed.date().isoformat()
    except ValueError:
        return raw[:10]


def _cutoff_day(commence_time: Any) -> str | None:
    if not commence_time:
        return None
    try:
        parsed = datetime.fromisoformat(str(commence_time).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(ET)
        return parsed.date().isoformat()
    except ValueError:
        return None


def _team_key(value: Any) -> str:
    return normalize_name(value)


def _market_value(row: dict[str, Any], market: str) -> float | None:
    fields = MARKET_TOTAL_FIELDS.get(market)
    if not fields:
        return None
    values = [_number(row, field) for field in fields]
    if any(value is None for value in values):
        return None
    return sum(values)


def _team_games(logs: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, set[str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    aliases: dict[str, set[str]] = defaultdict(set)
    for row in logs:
        game_id = str(row.get("game_id") or "").strip()
        team_id = str(row.get("team_id") or "").strip()
        if not game_id or not team_id:
            continue
        minutes = _number(row, "min")
        if minutes is None:
            minutes = _number(row, "minutes")
        if minutes is None or minutes <= 0:
            continue
        grouped[(game_id, team_id)].append(row)
        for field in ("team_abbreviation", "team_name", "team"):
            value = str(row.get(field) or "").strip()
            if value:
                aliases[_team_key(value)].add(str(row.get("team_abbreviation") or team_id).upper())

    games = []
    for (game_id, team_id), rows in grouped.items():
        first = rows[0]
        totals: dict[str, float] = {}
        for field in ("pts", "fga", "fta", "oreb", "dreb", "reb", "ast", "fg3m", "stl", "blk", "tov"):
            values = [_number(row, field) for row in rows]
            if values and all(value is not None for value in values):
                totals[field] = sum(values)
        games.append({
            "game_id": game_id,
            "team_id": team_id,
            "team_abbreviation": str(first.get("team_abbreviation") or team_id).upper(),
            "team_name": str(first.get("team_name") or first.get("team") or ""),
            "date": _game_day(first.get("game_date")),
            "totals": totals,
            "team_minutes": sum((_number(row, "min") if _number(row, "min") is not None else (_number(row, "minutes") or 0.0)) for row in rows),
        })
    return games, aliases


def _possessions(totals: dict[str, float]) -> float | None:
    if any(field not in totals for field in POSSESSION_FIELDS):
        return None
    value = totals["fga"] - totals["oreb"] + totals["tov"] + 0.44 * totals["fta"]
    return value if value > 0 else None


def build_matchup_context(
    offers: list[dict[str, Any]], logs: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach pre-game opponent team context without changing offer ranking."""
    team_games, aliases = _team_games(logs)
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in team_games:
        by_game[row["game_id"]].append(row)

    # Index every team game with its opponent. A game is accepted only when
    # exactly two team records exist, avoiding accidental partial/multi-team data.
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game_id, sides in by_game.items():
        if len(sides) != 2:
            continue
        a, b = sides
        for own, opponent in ((a, b), (b, a)):
            records[own["team_abbreviation"]].append({
                "date": own["date"], "own": own["totals"],
                "opponent": opponent["totals"],
                "own_possessions": _possessions(own["totals"]),
                "opponent_possessions": _possessions(opponent["totals"]),
                "own_minutes": own.get("team_minutes"),
            })

    # Resolve full sportsbook team names using the team's own labels in logs
    # plus a conservative standard NBA abbreviation dictionary.
    for abbreviation, names in TEAM_ALIASES.items():
        for name in names:
            aliases[_team_key(name)].add(abbreviation)
        aliases[_team_key(abbreviation)].add(abbreviation)

    def resolve(value: Any) -> str | None:
        matches = aliases.get(_team_key(value), set())
        return next(iter(matches)) if len(matches) == 1 else None

    enriched = []
    attached = 0
    for offer in offers:
        item = dict(offer)
        home = resolve(offer.get("home_team"))
        away = resolve(offer.get("away_team"))
        cutoff = _cutoff_day(offer.get("commence_time"))
        market = str(offer.get("market") or "")
        context = {
            "available": False,
            "home_team": home,
            "away_team": away,
            "sample_games": 0,
            "min_sample_games": MIN_TEAM_GAMES,
            "offensive_rating": None,
            "defensive_rating": None,
            "net_rating": None,
            "pace": None,
            "opponent_market_allowed": None,
            "note": "Brak wystarczających, dopasowanych danych drużynowych.",
        }
        if home and away and cutoff:
            # The matchup's defense is the opposing team. The context is computed
            # separately for both sides so cards can display the relevant defense.
            home_rows = [r for r in records.get(home, []) if r["date"] and r["date"] < cutoff]
            away_rows = [r for r in records.get(away, []) if r["date"] and r["date"] < cutoff]
            home_rows.sort(key=lambda r: r["date"], reverse=True)
            away_rows.sort(key=lambda r: r["date"], reverse=True)
            sample = min(len(home_rows), len(away_rows))
            if sample >= MIN_TEAM_GAMES:
                home_rows, away_rows = home_rows[:10], away_rows[:10]
                home_or, home_dr, home_poss, home_allowed = [], [], [], []
                away_or, away_dr, away_poss, away_allowed = [], [], [], []
                home_points_allowed, away_points_allowed, league_points = [], [], []
                home_paces, away_paces, league_paces = [], [], []
                for team_records in records.values():
                    eligible = sorted((r for r in team_records if r["date"] and r["date"] < cutoff), key=lambda r: r["date"], reverse=True)
                    for record in eligible[:10]:
                        opponent_points = record["opponent"].get("pts")
                        if opponent_points is not None:
                            league_points.append(opponent_points)
                        own_poss, opp_poss = record["own_possessions"], record["opponent_possessions"]
                        duration = (record.get("own_minutes") or 0.0) / 5.0
                        if own_poss is not None and opp_poss is not None and 45.0 <= duration <= 70.0:
                            league_paces.append(((own_poss + opp_poss) / 2.0) / duration * 48.0)
                for row in home_rows:
                    own_poss, opp_poss = row["own_possessions"], row["opponent_possessions"]
                    if own_poss and opp_poss and "pts" in row["own"] and "pts" in row["opponent"]:
                        home_or.append(row["own"]["pts"] / own_poss * 100)
                        home_dr.append(row["opponent"]["pts"] / opp_poss * 100)
                        home_poss.append((own_poss + opp_poss) / 2)
                    val = _market_value(row["opponent"], market)
                    if val is not None:
                        home_allowed.append(val)
                    if row["opponent"].get("pts") is not None:
                        home_points_allowed.append(row["opponent"]["pts"])
                    duration = (row.get("own_minutes") or 0.0) / 5.0
                    if row["own_possessions"] is not None and row["opponent_possessions"] is not None and 45.0 <= duration <= 70.0:
                        home_paces.append(((row["own_possessions"] + row["opponent_possessions"]) / 2.0) / duration * 48.0)
                for row in away_rows:
                    own_poss, opp_poss = row["own_possessions"], row["opponent_possessions"]
                    if own_poss and opp_poss and "pts" in row["own"] and "pts" in row["opponent"]:
                        away_or.append(row["own"]["pts"] / own_poss * 100)
                        away_dr.append(row["opponent"]["pts"] / opp_poss * 100)
                        away_poss.append((own_poss + opp_poss) / 2)
                    val = _market_value(row["opponent"], market)
                    if val is not None:
                        away_allowed.append(val)
                    if row["opponent"].get("pts") is not None:
                        away_points_allowed.append(row["opponent"]["pts"])
                    duration = (row.get("own_minutes") or 0.0) / 5.0
                    if row["own_possessions"] is not None and row["opponent_possessions"] is not None and 45.0 <= duration <= 70.0:
                        away_paces.append(((row["own_possessions"] + row["opponent_possessions"]) / 2.0) / duration * 48.0)
                # Home team offense vs away defense; away offense vs home defense.
                def avg(values: list[float]) -> float | None:
                    return round(statistics.mean(values), 1) if len(values) >= MIN_TEAM_GAMES else None
                context = {
                    "available": True,
                    "home_team": home,
                    "away_team": away,
                    "sample_games": sample,
                    "min_sample_games": MIN_TEAM_GAMES,
                    "home_offensive_rating": avg(home_or),
                    "home_defensive_rating": avg(home_dr),
                    "home_net_rating": round(avg(home_or) - avg(home_dr), 1) if avg(home_or) is not None and avg(home_dr) is not None else None,
                    "away_offensive_rating": avg(away_or),
                    "away_defensive_rating": avg(away_dr),
                    "away_net_rating": round(avg(away_or) - avg(away_dr), 1) if avg(away_or) is not None and avg(away_dr) is not None else None,
                    "home_possessions_per_game": avg(home_poss),
                    "away_possessions_per_game": avg(away_poss),
                    "home_points_allowed": avg(home_points_allowed),
                    "away_points_allowed": avg(away_points_allowed),
                    "league_points_allowed": avg(league_points),
                    "home_pace": avg(home_paces), "away_pace": avg(away_paces),
                    "league_pace": avg(league_paces),
                    "league_average_minutes": None,
                    "home_opponent_market_allowed": avg(home_allowed),
                    "away_opponent_market_allowed": avg(away_allowed),
                    "opponent_market": market,
                    "note": "Punkty rywali i Pace z maks. 10 wcześniejszych meczów. Średnia ligi liczona z tego samego okresu.",
                }
                attached += 1
        if cutoff:
            minutes_by_player: dict[str, list[float]] = defaultdict(list)
            for log in logs:
                log_day = _game_day(log.get("game_date"))
                if not log_day or log_day >= cutoff:
                    continue
                pid = str(log.get("player_id") or "").strip()
                mins = _number(log, "min")
                if mins is None:
                    mins = _number(log, "minutes")
                if pid and mins is not None and mins > 0:
                    minutes_by_player[pid].append((log_day, mins))
            rotation_averages = [
                statistics.mean([minutes for _, minutes in sorted(values, reverse=True)[:10]])
                for values in minutes_by_player.values()
                if len(values) >= 5 and statistics.mean([minutes for _, minutes in sorted(values, reverse=True)[:10]]) >= 20
            ]
            context["league_average_minutes"] = round(statistics.mean(rotation_averages), 1) if rotation_averages else None
        item["matchup_context"] = context
        enriched.append(item)
    return enriched, {
        "offers_with_matchup_context": attached,
        "team_game_rows": len(team_games),
        "teams_with_history": len(records),
        "min_team_games": MIN_TEAM_GAMES,
        "possession_formula": "FGA - OREB + TOV + 0.44 × FTA",
        "pace_status": "calculated_from_possessions_and_team_player_minutes_including_overtime",
        "league_baselines": "same pregame window; minutes baseline includes rotation players averaging at least 20 minutes",
    }

"""Build the static GitHub Pages snapshot. All provider calls happen in Actions."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import espn, prop_line, sportsdataverse
from app.props_board import build_props_board
from app.pick_history import update_pick_history
from app.espn import ESPNError
from app.prop_line import PropLineError

SITE = ROOT / "site"


def safe_call(name, fn):
    try:
        return fn(), {"name": name, "available": True, "error": None}
    except (ESPNError, PropLineError, ValueError, RuntimeError) as exc:
        return None, {"name": name, "available": False, "error": str(exc)}


def main():
    SITE.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    odds, odds_status = safe_call("PropLine NBA player props", prop_line.get_player_props)
    injuries, injury_status = safe_call("ESPN injury report", espn.get_injuries)
    historical_data, stats_status = safe_call(
        "SportsDataverse player game logs + historical NBA injury reports",
        sportsdataverse.load_current_season,
    )

    odds_items = (odds or {}).get("items", [])
    player_analysis = {}
    analysis_summary = {"offers_enriched": 0, "offers_unmatched": len(odds_items)}
    stats_meta = None
    if historical_data:
        logs, historical_injuries, stats_meta = historical_data
        try:
            roster_teams = sportsdataverse.team_abbreviations_for_offers(odds_items, logs)
            positions = espn.get_positions_for_teams(roster_teams)
            odds_items, analysis_summary, player_analysis = sportsdataverse.enrich_player_props(
                odds_items, logs, historical_injuries, positions=positions
            )
            analysis_summary["position_teams_queried"] = len(roster_teams)
            analysis_summary["players_with_positions"] = len({value.get("player_id") for value in positions.values() if value.get("player_id")})
            stats_status["message"] = (
                f"Game logs: {stats_meta['game_log_rows']}; injury-report rows: "
                f"{stats_meta['injury_report_rows']}; last game in stats feed: "
                f"{stats_meta['last_game_date']}; matched offers: "
                f"{analysis_summary['offers_enriched']}; roster teams: {len(roster_teams)}; "
                f"players with positions: {len(positions)}."
            )
        except Exception as exc:
            stats_status.update({
                "available": False,
                "error": f"Historical analysis failed: {type(exc).__name__}",
            })
            player_analysis = {}
    else:
        stats_status["message"] = "Historical game logs and injury reports are unavailable."

    games = []
    game_statuses = []
    for offset in (0, 1):
        date = (now + timedelta(days=offset)).strftime("%Y%m%d")
        day, status = safe_call(f"ESPN scoreboard {date}", lambda d=date: espn.get_scoreboard(d))
        game_statuses.append(status)
        if day:
            games.extend(day.get("events", []))

    raw_injuries = (injuries or {}).get("players", [])
    impact_injuries = (
        sportsdataverse.filter_impact_injuries(raw_injuries, logs)
        if historical_data else []
    )
    if historical_data:
        injury_status["message"] = (
            f"ESPN: {len(raw_injuries)} zgłoszeń; pokazano {len(impact_injuries)} "
            "starterów i graczy ważnej rotacji według ostatnich minut/występów."
        )
    print("Scoreboard date diagnostics:", json.dumps([{"id": g.get("id"), "name": g.get("name"), "date": g.get("date"), "commence_time": g.get("commence_time")} for g in games[:20]], ensure_ascii=False))
    props_board = build_props_board(odds_items)
    history_status = update_pick_history(
        props_board, historical_data[0] if historical_data else [], SITE / "data", now, games=games
    )
    board_status = "Dane historyczne niedostępne — brak pełnego rankingu L10." if not stats_meta else f"Linie z historią co najmniej 5 meczów: {len(props_board)}."

    snapshot = {
        "generated_at": now.isoformat(),
        "refresh_minutes": 30,
        "sources": [odds_status, injury_status, stats_status, *game_statuses],
        "player_analysis": player_analysis,
        "analysis_summary": analysis_summary,
        "stats_meta": stats_meta,
        "odds_count": (odds or {}).get("count", 0),
        "bookmakers": (odds or {}).get("bookmakers", []),
        "injuries": impact_injuries,
        "games": games,
        "props_board": props_board,
        "pick_history": history_status,
        "board_status": board_status,
        "policy": "No synthetic lines or picks. Missing source data stays unavailable.",
    }
    (SITE / "data").mkdir(exist_ok=True)
    (SITE / "data" / "latest.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    static_src = ROOT / "app" / "static"
    static_dst = SITE / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst)
    shutil.copy2(static_src / "index.html", SITE / "index.html")
    if stats_meta:
        print(
            f"Historical stats season={stats_meta['season_end_year']} "
            f"last_game_date={stats_meta['last_game_date']} "
            f"game_log_rows={stats_meta['game_log_rows']} "
            f"injury_report_rows={stats_meta['injury_report_rows']}"
        )
        print(
            f"Player analysis: enriched={analysis_summary['offers_enriched']} "
            f"unmatched={analysis_summary['offers_unmatched']} "
            f"player_market_models={analysis_summary['unique_player_market_models']} "
            f"teammate_split_sets={sum(bool(v['teammate_splits']) for v in player_analysis.values())}"
        )
    print(
        "Built static snapshot:",
        f"odds={snapshot['odds_count']}",
        f"injuries={len(snapshot['injuries'])}",
        f"games={len(games)}",
        f"props_board={len(snapshot['props_board'])}",
        f"enriched={analysis_summary['offers_enriched']}",
        f"player_analysis={len(player_analysis)}",
    )
    print("Pick history:", json.dumps(history_status, ensure_ascii=False, sort_keys=True))
    for status in snapshot["sources"]:
        print(f"{status['name']}: {'OK' if status['available'] else 'UNAVAILABLE'}")
        if status["error"]:
            print(f"  {status['error']}")


if __name__ == "__main__":
    main()

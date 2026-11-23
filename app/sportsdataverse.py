"""Historical NBA game logs and official-report-derived teammate availability.

The current-season files are published by SportsDataverse from NBA data sources.
Unknown availability is never treated as active or out. Injury reports are
restricted to versions published before the calendar day of the game; the
published schedules CSV contains dates but not tip-off timestamps, so same-day
reports are conservatively excluded to prevent post-tip-off leakage.
"""
from __future__ import annotations

import csv
import math
import os
import re
import statistics
import time
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

RELEASE_BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
TIMEOUT = 90.0
DATA_DIR = Path(os.getenv("NBA_DATA_CACHE_DIR", "data_cache"))
MARKET_FIELDS = {
    "player_points": ("pts",), "player_rebounds": ("reb",),
    "player_assists": ("ast",), "player_threes": ("fg3m",),
    "player_steals": ("stl",), "player_blocks": ("blk",),
    "player_turnovers": ("tov",),
    "player_points_rebounds": ("pts", "reb"),
    "player_points_assists": ("pts", "ast"),
    "player_rebounds_assists": ("reb", "ast"),
    "player_points_rebounds_assists": ("pts", "reb", "ast"),
    "player_blocks_steals": ("blk", "stl"),
}


class SportsDataError(RuntimeError):
    pass


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def current_season_end_year(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return now.year + 1 if now.month >= 9 else now.year


def _download(url: str, destination: Path, max_age_hours: int = 24) -> Path:
    if destination.exists():
        age = time.time() - destination.stat().st_mtime
        if age < max_age_hours * 3600 and destination.stat().st_size > 0:
            return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=TIMEOUT,
                          headers={"User-Agent": "NBA-Value-Finder/0.5"}) as response:
            response.raise_for_status()
            with temp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        if temp.stat().st_size < 100:
            raise SportsDataError(f"Dataset asset is unexpectedly small: {destination.name}")
        temp.replace(destination)
    except (httpx.HTTPError, OSError) as exc:
        temp.unlink(missing_ok=True)
        raise SportsDataError(f"Could not download {destination.name}: {type(exc).__name__}") from exc
    return destination


def load_current_season() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    season = current_season_end_year()
    logs_path = _download(
        f"{RELEASE_BASE}/nba_stats_player_game_logs/player_game_logs_{season}.csv",
        DATA_DIR / f"player_game_logs_{season}.csv",
    )
    injury_path = _download(
        f"{RELEASE_BASE}/nba_stats_injury_report/injury_report_{season}.csv",
        DATA_DIR / f"injury_report_{season}.csv",
    )
    try:
        with logs_path.open("r", encoding="utf-8-sig", newline="") as handle:
            logs = list(csv.DictReader(handle))
        with injury_path.open("r", encoding="utf-8-sig", newline="") as handle:
            raw_injuries = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise SportsDataError(f"Could not parse current-season data: {type(exc).__name__}") from exc
    if not logs or not raw_injuries:
        raise SportsDataError("Current-season game logs or injury report dataset is empty")
    required_logs = {"player_id", "player_name", "game_id", "game_date", "team_id", "min"}
    required_injuries = {
        "report_datetime", "game_date", "game_id", "team_id",
        "person_id", "current_status", "report_player_name",
    }
    missing_logs = sorted(required_logs - set(logs[0]))
    missing_injuries = sorted(required_injuries - set(raw_injuries[0]))
    if missing_logs or missing_injuries:
        raise SportsDataError(
            "SportsDataverse CSV schema changed; missing player-log columns="
            f"{missing_logs}; missing injury-report columns={missing_injuries}"
        )
    injuries = _keep_pregame_reports(raw_injuries)
    meta = {
        "provider": "SportsDataverse NBA stats datasets",
        "season_end_year": season,
        "game_log_rows": len(logs),
        "injury_report_rows": len(injuries),
        "raw_injury_report_rows": len(raw_injuries),
        "last_game_date": max((r.get("game_date", "") for r in logs), default=None),
        "files": [logs_path.name, injury_path.name],
        "data_note": (
            "Only injury-report versions published before the game date are used. "
            "Same-day reports are excluded because the published schedules CSV "
            "does not include tip-off timestamps."
        ),
    }
    return logs, injuries, meta


def _keep_pregame_reports(
    injuries: list[dict[str, str]], schedules: list[dict[str, str]] | None = None
) -> list[dict[str, str]]:
    """Keep only reports published before the local calendar date of the game.

    The public schedules release exposes game_date but not a reliable tip-off
    timestamp. Excluding same-day reports is deliberately conservative.
    """
    kept = []
    for row in injuries:
        raw_game_date = str(row.get("game_date") or "").strip()
        report_time = _parse_timestamp(row.get("report_datetime"))
        try:
            game_day = date.fromisoformat(raw_game_date[:10])
        except ValueError:
            continue
        if report_time and report_time.date() < game_day:
            kept.append(row)
    return kept


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        # NBA injury-report timestamps are US/Eastern and naive.
        from zoneinfo import ZoneInfo
        parsed = parsed.replace(tzinfo=ZoneInfo("America/New_York"))
    return parsed


def _number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _stat_value(row: dict[str, Any], market: str) -> float | None:
    fields = MARKET_FIELDS.get(market)
    if not fields:
        return None
    values = [_number(row, field) for field in fields]
    if any(value is None for value in values):
        return None
    return sum(values)


def _hit_summary(values: list[float], line: float, side: str) -> dict[str, Any]:
    pushes = sum(value == line for value in values)
    decisive = [value for value in values if value != line]
    hits = sum(value > line if side == "Over" else value < line for value in decisive)
    return {
        "hits": hits, "games": len(values), "pushes": pushes,
        "decided": len(decisive),
        "rate": round(hits / len(decisive), 4) if decisive else None,
    }


def _latest_injury_rows(injuries: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    latest: dict[tuple[str, str], dict[str, str]] = {}
    for row in injuries:
        game_id = str(row.get("game_id") or "").strip()
        person_id = str(row.get("person_id") or "").strip()
        if not game_id or not person_id:
            continue
        key = (game_id, person_id)
        current = latest.get(key)
        stamp = str(row.get("report_datetime") or "")
        if current is None or stamp > str(current.get("report_datetime") or ""):
            latest[key] = row
    return latest


def team_abbreviations_for_offers(offers: list[dict[str, Any]], logs: list[dict[str, str]]) -> list[str]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_name: dict[str, set[str]] = defaultdict(set)
    for row in logs:
        pid = str(row.get("player_id") or "").strip()
        if pid and (_number(row, "min") or 0) > 0:
            by_id[pid].append(row)
            by_name[normalize_name(row.get("player_name"))].add(pid)
    teams: set[str] = set()
    for offer in offers:
        raw_id = str(offer.get("player_id") or "").strip()
        name_key = normalize_name(offer.get("player"))
        valid_id = raw_id in by_id and normalize_name(by_id[raw_id][0].get("player_name")) == name_key
        ids = {raw_id} if valid_id else by_name.get(name_key, set())
        if len(ids) != 1:
            continue
        rows = sorted(by_id[next(iter(ids))], key=lambda r: str(r.get("game_date") or ""), reverse=True)[:10]
        teams.update(str(row.get("team_abbreviation") or "").strip().upper() for row in rows if row.get("team_abbreviation"))
    return sorted(teams)


def enrich_player_props(
    offers: list[dict[str, Any]],
    logs: list[dict[str, str]],
    injuries: list[dict[str, str]],
    positions: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_name: dict[str, set[str]] = defaultdict(set)
    played: set[tuple[str, str]] = set()
    logs_by_game_team: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in logs:
        pid = str(row.get("player_id") or "").strip()
        game_id = str(row.get("game_id") or "").strip()
        if not pid or not game_id:
            continue
        minutes = _number(row, "min")
        if minutes is None:
            minutes = _number(row, "minutes")
        if minutes is not None and minutes > 0:
            by_id[pid].append(row)
            by_name[normalize_name(row.get("player_name"))].add(pid)
            played.add((game_id, pid))
            logs_by_game_team[(game_id, str(row.get("team_id") or "").strip())].append(row)

    latest_reports = _latest_injury_rows(injuries)
    reports_by_game_team: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in latest_reports.values():
        reports_by_game_team[(str(row.get("game_id") or "").strip(),
                               str(row.get("team_id") or "").strip())].append(row)

    metric_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    enriched: list[dict[str, Any]] = []
    analysis_by_key: dict[str, dict[str, Any]] = {}
    matched = 0
    for offer in offers:
        name_key = normalize_name(offer.get("player"))
        raw_id = str(offer.get("player_id") or "").strip()
        provider_id_matches_name = (
            raw_id in by_id and bool(by_id[raw_id])
            and normalize_name(by_id[raw_id][0].get("player_name")) == name_key
        )
        player_ids = {raw_id} if provider_id_matches_name else by_name.get(name_key, set())
        if len(player_ids) != 1:
            copy = dict(offer)
            copy["form"] = None
            copy["analysis_key"] = None
            copy["analysis_status"] = "player_unmatched" if not player_ids else "player_ambiguous"
            enriched.append(copy)
            continue
        player_id = next(iter(player_ids))
        cache_key = (player_id, str(offer.get("market")))
        if cache_key not in metric_cache:
            player_rows = sorted(by_id[player_id], key=lambda r: str(r.get("game_date") or ""), reverse=True)
            metric = str(offer.get("market"))
            values_rows = [(row, _stat_value(row, metric)) for row in player_rows]
            values_rows = [(row, val) for row, val in values_rows if val is not None]
            last10, last5 = values_rows[:10], values_rows[:5]
            position_data = ((positions or {}).get(player_id)
                             or (positions or {}).get(normalize_name(player_rows[0].get("player_name")))
                             or {})
            metric_cache[cache_key] = {
                "player_id": player_id, "rows": player_rows,
                "l10_values": [val for _, val in last10],
                "l5_values": [val for _, val in last5],
                "l10_dates": [str(row.get("game_date") or "") for row, _ in last10],
                "l10_games": [{
                    "date": str(row.get("game_date") or ""),
                    "game_id": str(row.get("game_id") or ""),
                    "matchup": str(row.get("matchup") or row.get("match_up") or ""),
                    "opponent": str(row.get("opponent_team_name") or row.get("opponent_abbreviation") or row.get("opponent_team_id") or ""),
                    "home_away": str(row.get("home_away") or row.get("location") or ""),
                } for row, _ in last10],
                "l10_minutes": [
                    _number(row, "min") if _number(row, "min") is not None else _number(row, "minutes")
                    for row, _ in last10
                ],
                "teammate_splits": _teammate_splits(
                    player_id, player_rows[:10], metric, logs_by_game_team,
                    reports_by_game_team, played, positions or {},
                ),
                "position": position_data.get("position"),
                "position_name": position_data.get("position_name"),
                "position_source": position_data.get("position_source"),
                "position_confidence": position_data.get("position_confidence", "unknown"),
            } if values_rows else None

        cached = metric_cache[cache_key]
        copy = dict(offer)
        if cached is None:
            copy["form"], copy["analysis_key"] = None, None
            copy["analysis_status"] = "no_player_stats"
            enriched.append(copy)
            continue
        line = _number(offer, "line")
        side = str(offer.get("side") or "")
        l10_values, l5_values = cached["l10_values"], cached["l5_values"]
        minutes = [x for x in cached["l10_minutes"] if x is not None]
        copy["player_position"] = cached.get("position")
        copy["player_position_name"] = cached.get("position_name")
        copy["position_source"] = cached.get("position_source")
        copy["position_confidence"] = cached.get("position_confidence", "unknown")
        copy["form"] = {
            "sample_size": len(l10_values),
            "l5": _hit_summary(l5_values, line, side) if line is not None and side in {"Over", "Under"} else None,
            "l10": _hit_summary(l10_values, line, side) if line is not None and side in {"Over", "Under"} else None,
            "average_l10": round(statistics.mean(l10_values), 2) if l10_values else None,
            "median_l10": statistics.median(l10_values) if l10_values else None,
            "recent_values": l10_values,
            "recent_dates": cached["l10_dates"],
            "recent_games": cached["l10_games"],
            "average_minutes_l10": round(statistics.mean(minutes), 1) if minutes else None,
            "last_game_date": cached["l10_dates"][0] if cached["l10_dates"] else None,
        }
        analysis_key = f"{player_id}:{offer['market']}"
        copy["analysis_key"] = analysis_key
        analysis_by_key.setdefault(analysis_key, {
            "player_id": player_id, "market": offer["market"],
            "teammate_splits": cached["teammate_splits"],
        })
        copy["analysis_status"] = "matched"
        matched += 1
        enriched.append(copy)

    summary = {
        "offers_enriched": matched,
        "offers_unmatched": len(offers) - matched,
        "unique_player_market_models": len(metric_cache),
        "historical_availability": "official_nba_injury_reports_processed_by_sportsdataverse",
    }
    return enriched, summary, analysis_by_key


def _teammate_splits(
    player_id: str,
    player_rows: list[dict[str, str]],
    market: str,
    logs_by_game_team: dict[tuple[str, str], list[dict[str, str]]],
    reports_by_game_team: dict[tuple[str, str], list[dict[str, str]]],
    played: set[tuple[str, str]],
    positions: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    accum: dict[str, dict[str, Any]] = {}
    positions = positions or {}
    player_position = (positions.get(player_id) or positions.get(normalize_name(player_rows[0].get("player_name"))) or {}).get("position")
    for player_row in player_rows:
        game_id = str(player_row.get("game_id") or "").strip()
        team_id = str(player_row.get("team_id") or "").strip()
        target_value = _stat_value(player_row, market)
        target_minutes = _number(player_row, "min")
        if target_minutes is None:
            target_minutes = _number(player_row, "minutes")
        if target_value is None:
            continue
        for teammate_row in logs_by_game_team.get((game_id, team_id), []):
            teammate_id = str(teammate_row.get("player_id") or "").strip()
            if not teammate_id or teammate_id == player_id:
                continue
            entry = accum.setdefault(teammate_id, {
                "name": str(teammate_row.get("player_name") or teammate_id),
                "position": (positions.get(teammate_id) or positions.get(normalize_name(teammate_row.get("player_name"))) or {}).get("position"),
                "active_values": [], "out_values": [],
                "active_minutes": [], "out_minutes": [],
            })
            entry["active_values"].append(target_value)
            if target_minutes is not None:
                entry["active_minutes"].append(target_minutes)
        for report in reports_by_game_team.get((game_id, team_id), []):
            teammate_id = str(report.get("person_id") or "").strip()
            if not teammate_id or teammate_id == player_id:
                continue
            if str(report.get("current_status") or "").strip().lower() != "out":
                continue
            if (game_id, teammate_id) in played:
                continue
            entry = accum.setdefault(teammate_id, {
                "name": _report_name(report.get("report_player_name")) or teammate_id,
                "position": (positions.get(teammate_id) or positions.get(normalize_name(_report_name(report.get("report_player_name")))) or {}).get("position"),
                "active_values": [], "out_values": [],
                "active_minutes": [], "out_minutes": [],
            })
            if not entry.get("name") or entry["name"] == teammate_id:
                entry["name"] = _report_name(report.get("report_player_name")) or teammate_id
            entry["out_values"].append(target_value)
            if target_minutes is not None:
                entry["out_minutes"].append(target_minutes)

    result = []
    for teammate_id, entry in accum.items():
        active, out = entry["active_values"], entry["out_values"]
        # Ignore fringe players: their occasional appearances should not be
        # treated as meaningful lineup/role changes. Use their actual minutes
        # in the target player's last-ten-game sample, not minutes from an
        # unrelated season-wide window.
        teammate_minutes = entry["active_minutes"]
        average_teammate_minutes = statistics.mean(teammate_minutes) if teammate_minutes else 0.0
        if average_teammate_minutes < 15.0:
            continue
        if len(active) < 2 or len(out) < 2:
            continue
        active_avg, out_avg = statistics.mean(active), statistics.mean(out)
        active_min = statistics.mean(entry["active_minutes"]) if entry["active_minutes"] else None
        out_min = statistics.mean(entry["out_minutes"]) if entry["out_minutes"] else None
        result.append({
            "teammate_id": teammate_id, "teammate": entry["name"] or teammate_id,
            "position": entry.get("position"),
            "same_position": bool(player_position and entry.get("position") and player_position == entry.get("position")),
            "average_teammate_minutes": round(average_teammate_minutes, 1),
            "active_games": len(active), "out_games": len(out),
            "average_with_active": round(active_avg, 2),
            "average_with_out": round(out_avg, 2),
            "delta_average": round(out_avg - active_avg, 2),
            "minutes_with_active": round(active_min, 1) if active_min is not None else None,
            "minutes_with_out": round(out_min, 1) if out_min is not None else None,
            "confidence": "small_sample" if min(len(active), len(out)) < 5 else "descriptive",
        })
    result.sort(key=lambda x: (bool(x.get("same_position")), min(x["active_games"], x["out_games"]), abs(x["delta_average"])), reverse=True)
    return result[:5]


def _report_name(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if "," in raw:
        last, first = [part.strip() for part in raw.split(",", 1)]
        return f"{first} {last}".strip()
    return raw


def filter_impact_injuries(
    injury_players: list[dict[str, Any]],
    logs: list[dict[str, str]],
    min_rotation_minutes: float = 24.0,
    recent_games: int = 20,
) -> list[dict[str, Any]]:
    """Keep injured players with evidence of starter/core-rotation usage.

    Prefer explicit starter flags/positions where the feed provides them.
    Otherwise use recent average minutes as a conservative role proxy.
    """
    by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in logs:
        pid = str(row.get("player_id") or "").strip()
        name = normalize_name(row.get("player_name"))
        if pid:
            by_id[pid].append(row)
        if name:
            by_name[name].append(row)

    def started(row: dict[str, str]) -> bool | None:
        for key in ("start_position", "start_pos", "starter_position", "position_started"):
            value = str(row.get(key) or "").strip().upper()
            if value and value not in {"", "NONE", "NULL", "NAN", "0", "FALSE"}:
                return True
        for key in ("starter", "is_starter", "started", "start"):
            value = str(row.get(key) or "").strip().lower()
            if value in {"1", "true", "yes", "y"}:
                return True
            if value in {"0", "false", "no", "n"}:
                return False
        return None

    selected = []
    seen = set()
    for injury in injury_players:
        pid = str(injury.get("player_id") or "").strip()
        rows = by_id.get(pid, []) if pid else []
        if not rows:
            name_rows = by_name.get(normalize_name(injury.get("player")), [])
            # Avoid accidentally assigning another player with the same name.
            if len({str(row.get("player_id") or "") for row in name_rows}) == 1:
                rows = name_rows
        rows = sorted(rows, key=lambda row: str(row.get("game_date") or ""), reverse=True)[:recent_games]
        if not rows:
            continue
        minute_values = []
        start_flags = []
        for row in rows:
            minutes = _number(row, "min")
            if minutes is None:
                minutes = _number(row, "minutes")
            if minutes is not None and minutes > 0:
                minute_values.append(minutes)
            flag = started(row)
            if flag is not None:
                start_flags.append(flag)
        if not minute_values:
            continue
        avg_minutes = round(statistics.mean(minute_values), 1)
        start_rate = round(sum(start_flags) / len(start_flags), 3) if start_flags else None
        # An explicit regular starter is always retained. Without start metadata,
        # require substantial minutes; a 24+ minute player is a core rotation member.
        is_starter = start_rate is not None and start_rate >= 0.50
        if not is_starter and avg_minutes < min_rotation_minutes:
            continue
        key = (normalize_name(injury.get("player")), normalize_name(injury.get("team")))
        if key in seen:
            continue
        seen.add(key)
        enriched = dict(injury)
        enriched["rotation_role"] = "Starter" if is_starter else "Ważna rotacja"
        enriched["average_minutes_recent"] = avg_minutes
        enriched["recent_games_sample"] = len(minute_values)
        enriched["starter_rate_recent"] = start_rate
        selected.append(enriched)

    selected.sort(key=lambda row: (
        0 if row["rotation_role"] == "Starter" else 1,
        -float(row["average_minutes_recent"]),
        str(row.get("player") or "").casefold(),
    ))
    return selected

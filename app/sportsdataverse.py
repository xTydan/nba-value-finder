"""Historical NBA game logs and official-report-derived teammate availability.

The current-season files are published by SportsDataverse from NBA data sources.
All joins are conservative: unknown status is never treated as active or out.
"""
from __future__ import annotations

import csv
import gzip
import math
import os
import re
import statistics
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any

import httpx

RELEASE_BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
TIMEOUT = 90.0
DATA_DIR = Path(os.getenv("NBA_DATA_CACHE_DIR", "data_cache"))
MARKET_FIELDS = {
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
                          headers={"User-Agent": "NBA-Value-Finder/0.4"}) as response:
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
    logs_url = f"{RELEASE_BASE}/nba_stats_player_game_logs/player_game_logs_{season}.csv"
    injury_url = f"{RELEASE_BASE}/nba_stats_injury_report/injury_report_{season}.csv"
    schedule_url = f"{RELEASE_BASE}/nba_stats_schedules/nba_schedule_{season}.csv.gz"
    logs_path = _download(logs_url, DATA_DIR / f"player_game_logs_{season}.csv")
    injury_path = _download(injury_url, DATA_DIR / f"injury_report_{season}.csv")
    schedule_path = _download(schedule_url, DATA_DIR / f"nba_schedule_{season}.csv.gz")
    try:
        with logs_path.open("r", encoding="utf-8-sig", newline="") as handle:
            logs = list(csv.DictReader(handle))
        with injury_path.open("r", encoding="utf-8-sig", newline="") as handle:
            raw_injuries = list(csv.DictReader(handle))
        with gzip.open(schedule_path, "rt", encoding="utf-8-sig", newline="") as handle:
            schedules = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        raise SportsDataError(f"Could not parse current-season data: {type(exc).__name__}") from exc
    if not logs or not raw_injuries or not schedules:
        raise SportsDataError("Current-season game logs, injury report or schedule dataset is empty")
    required_logs = {"player_id", "player_name", "game_id", "game_date"}
    required_injuries = {"report_datetime", "game_id", "team_id", "person_id", "current_status"}
    required_schedules = {"game_id", "game_date_time_utc"}
    if (not required_logs.issubset(logs[0])
            or not required_injuries.issubset(raw_injuries[0])
            or not required_schedules.issubset(schedules[0])):
        raise SportsDataError("SportsDataverse CSV schema changed; refusing unsafe joins")
    injuries = _keep_pregame_reports(raw_injuries, schedules)
    meta = {
        "provider": "SportsDataverse NBA stats datasets",
        "season_end_year": season,
        "game_log_rows": len(logs),
        "injury_report_rows": len(injuries),
        "raw_injury_report_rows": len(raw_injuries),
        "schedule_rows": len(schedules),
        "last_game_date": max((r.get("game_date", "") for r in logs), default=None),
        "files": [logs_path.name, injury_path.name, schedule_path.name],
        "data_note": "Only injury-report versions published before the scheduled tip-off are used.",
    }
    return logs, injuries, meta



def _parse_timestamp(value: Any, naive_timezone) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=naive_timezone)
    return parsed.astimezone(timezone.utc)


def _keep_pregame_reports(
    injuries: list[dict[str, str]], schedules: list[dict[str, str]]
) -> list[dict[str, str]]:
    tipoffs: dict[str, datetime] = {}
    for row in schedules:
        game_id = str(row.get("game_id") or "").strip()
        tipoff = _parse_timestamp(row.get("game_date_time_utc"), timezone.utc)
        if game_id and tipoff:
            tipoffs[game_id] = tipoff

    kept = []
    for row in injuries:
        game_id = str(row.get("game_id") or "").strip()
        tipoff = tipoffs.get(game_id)
        report_time = _parse_timestamp(row.get("report_datetime"), ZoneInfo("America/New_York"))
        if tipoff and report_time and report_time < tipoff:
            kept.append(row)
    return kept


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
        "hits": hits,
        "games": len(values),
        "pushes": pushes,
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


def enrich_player_props(
    offers: list[dict[str, Any]],
    logs: list[dict[str, str]],
    injuries: list[dict[str, str]],
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
            raw_id in by_id
            and bool(by_id[raw_id])
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
            last10 = values_rows[:10]
            last5 = last10[:5]
            metric_cache[cache_key] = {
                "player_id": player_id,
                "rows": player_rows,
                "l10_values": [val for _, val in last10],
                "l5_values": [val for _, val in last5],
                "l10_dates": [str(row.get("game_date") or "") for row, _ in last10],
                "l10_minutes": [(_number(row, "min") if _number(row, "min") is not None else _number(row, "minutes")) for row, _ in last10],
                "all_values": [val for _, val in values_rows[:30]],
                "teammate_splits": _teammate_splits(
                    player_id, player_rows[:30], metric, logs_by_game_team,
                    reports_by_game_team, played,
                ),
            } if values_rows else None

        cached = metric_cache[cache_key]
        copy = dict(offer)
        if cached is None:
            copy["form"] = None
            copy["analysis_key"] = None
            copy["analysis_status"] = "no_player_stats"
            enriched.append(copy)
            continue

        line = _number(offer, "line")
        side = str(offer.get("side") or "")
        l10_values = cached["l10_values"]
        l5_values = cached["l5_values"]
        minutes = [x for x in cached["l10_minutes"] if x is not None]
        copy["form"] = {
            "sample_size": len(l10_values),
            "l5": _hit_summary(l5_values, line, side) if line is not None and side in {"Over", "Under"} else None,
            "l10": _hit_summary(l10_values, line, side) if line is not None and side in {"Over", "Under"} else None,
            "average_l10": round(statistics.mean(l10_values), 2) if l10_values else None,
            "median_l10": statistics.median(l10_values) if l10_values else None,
            "average_minutes_l10": round(statistics.mean(minutes), 1) if minutes else None,
            "last_game_date": cached["l10_dates"][0] if cached["l10_dates"] else None,
        }
        analysis_key = f"{player_id}:{offer['market']}"
        copy["analysis_key"] = analysis_key
        analysis_by_key.setdefault(analysis_key, {
            "player_id": player_id,
            "market": offer["market"],
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
) -> list[dict[str, Any]]:
    accum: dict[str, dict[str, Any]] = {}
    for player_row in player_rows:
        game_id = str(player_row.get("game_id") or "").strip()
        team_id = str(player_row.get("team_id") or "").strip()
        target_value = _stat_value(player_row, market)
        target_minutes = _number(player_row, "min")
        if target_minutes is None:
            target_minutes = _number(player_row, "minutes")
        if target_value is None:
            continue
        # Anyone who actually logged minutes is confirmed present, even if
        # they were not listed on the injury report.
        for teammate_row in logs_by_game_team.get((game_id, team_id), []):
            teammate_id = str(teammate_row.get("player_id") or "").strip()
            if not teammate_id or teammate_id == player_id:
                continue
            entry = accum.setdefault(teammate_id, {
                "name": str(teammate_row.get("player_name") or teammate_id),
                "active_values": [], "out_values": [],
                "active_minutes": [], "out_minutes": [],
            })
            entry["active_values"].append(target_value)
            if target_minutes is not None:
                entry["active_minutes"].append(target_minutes)

        # Absence is counted only when the latest pregame report explicitly
        # says OUT and the player did not appear in the box score.
        for report in reports_by_game_team.get((game_id, team_id), []):
            teammate_id = str(report.get("person_id") or "").strip()
            if not teammate_id or teammate_id == player_id:
                continue
            status = str(report.get("current_status") or "").strip().lower()
            if status != "out" or (game_id, teammate_id) in played:
                continue
            entry = accum.setdefault(teammate_id, {
                "name": _report_name(report.get("report_player_name")) or teammate_id,
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
        active = entry["active_values"]
        out = entry["out_values"]
        if len(active) < 2 or len(out) < 2:
            continue
        active_avg = statistics.mean(active)
        out_avg = statistics.mean(out)
        active_min = statistics.mean(entry["active_minutes"]) if entry["active_minutes"] else None
        out_min = statistics.mean(entry["out_minutes"]) if entry["out_minutes"] else None
        result.append({
            "teammate_id": teammate_id,
            "teammate": entry["name"] or teammate_id,
            "active_games": len(active),
            "out_games": len(out),
            "average_with_active": round(active_avg, 2),
            "average_with_out": round(out_avg, 2),
            "delta_average": round(out_avg - active_avg, 2),
            "minutes_with_active": round(active_min, 1) if active_min is not None else None,
            "minutes_with_out": round(out_min, 1) if out_min is not None else None,
            "confidence": "small_sample" if min(len(active), len(out)) < 5 else "descriptive",
        })
    result.sort(key=lambda x: (min(x["active_games"], x["out_games"]), abs(x["delta_average"])), reverse=True)
    return result[:5]


def _report_name(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if "," in raw:
        last, first = [part.strip() for part in raw.split(",", 1)]
        return f"{first} {last}".strip()
    return raw

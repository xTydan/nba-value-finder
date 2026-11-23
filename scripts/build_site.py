"""Build the static GitHub Pages snapshot. All provider calls happen in Actions."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import espn, prop_line
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

    games = []
    game_statuses = []
    for offset in (0, 1):
        date = (now + timedelta(days=offset)).strftime("%Y%m%d")
        day, status = safe_call(f"ESPN scoreboard {date}", lambda d=date: espn.get_scoreboard(d))
        game_statuses.append(status)
        if day:
            games.extend(day.get("events", []))

    snapshot = {
        "generated_at": now.isoformat(),
        "refresh_minutes": 30,
        "sources": [odds_status, injury_status, *game_statuses],
        "odds": (odds or {}).get("items", []),
        "odds_count": (odds or {}).get("count", 0),
        "bookmakers": (odds or {}).get("bookmakers", []),
        "injuries": (injuries or {}).get("players", []),
        "games": games,
        "picks": [],
        "picks_status": "Model is not enabled: no calibrated probability estimates are published yet.",
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
    print(
        "Built static snapshot:",
        f"odds={snapshot['odds_count']}",
        f"injuries={len(snapshot['injuries'])}",
        f"games={len(games)}",
        f"picks={len(snapshot['picks'])}",
    )
    for status in snapshot["sources"]:
        print(f"{status['name']}: {'OK' if status['available'] else 'UNAVAILABLE'}")
        if status["error"]:
            print(f"  {status['error']}")


if __name__ == "__main__":
    main()

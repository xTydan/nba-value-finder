from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import espn
from app.espn import ESPNError
from app.providers import UnconfiguredProvider
from app.storage import init_db

app = FastAPI(title="NBA Value Finder", version="0.2.0")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    try:
        scoreboard = espn.get_scoreboard()
        stats_provider = {
            "provider": "ESPN public NBA API",
            "available": True,
            "checked_at": scoreboard["fetched_at"],
            "message": "Terminarz i wyniki NBA są dostępne.",
        }
    except (ESPNError, ValueError) as exc:
        stats_provider = {
            "provider": "ESPN public NBA API",
            "available": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "message": str(exc),
        }

    try:
        injury_feed = espn.get_injuries()
        injury_provider = {
            "provider": "ESPN NBA injury report",
            "available": True,
            "checked_at": injury_feed["fetched_at"],
            "message": f"Raport ESPN dostępny; wpisów: {injury_feed['count']}. Historia statusów zawodników wymaga osobnego źródła.",
        }
    except ESPNError as exc:
        injury_provider = {
            "provider": "ESPN NBA injury report",
            "available": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "message": str(exc),
        }

    providers = [
        stats_provider,
        injury_provider,
        UnconfiguredProvider(
            "Historical player availability",
            "Historical ACTIVE / OUT status by player and game",
        ).status().__dict__,
        UnconfiguredProvider(
            "Player props odds",
            "Superbet / STS / Fortuna player props",
        ).status().__dict__,
    ]
    return {
        "app": "NBA Value Finder",
        "version": app.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_minutes": 15,
        "providers": providers,
        "verified_picks": 0,
        "notice": "Statystyki terminarza ESPN są podłączone. Kursy i historyczna dostępność zawodników nie są jeszcze podłączone; brak fikcyjnych typów.",
    }


@app.get("/api/games")
def games(date: str | None = Query(default=None, pattern=r"^\d{8}$")):
    try:
        return espn.get_scoreboard(date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ESPNError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/injuries")
def injuries():
    try:
        return espn.get_injuries()
    except ESPNError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/players/{player_id}/gamelog")
def player_gamelog(player_id: str, season: int | None = Query(default=None, ge=2000, le=2100)):
    if not player_id.isdigit():
        raise HTTPException(status_code=400, detail="player_id must be numeric")
    try:
        return espn.get_player_gamelog(player_id, season)
    except ESPNError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/picks")
def picks():
    return {
        "items": [],
        "count": 0,
        "message": "Brak zweryfikowanego źródła kursów. Nie generujemy typów bez rzeczywistych linii.",
    }

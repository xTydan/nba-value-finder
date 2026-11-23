from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.providers import UnconfiguredProvider
from app.storage import init_db

app = FastAPI(title="NBA Value Finder", version="0.1.0")
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
    providers = [
        UnconfiguredProvider("NBA stats / game logs", "Player game logs and box scores").status(),
        UnconfiguredProvider("Injuries / historical availability", "Official injury reports and historical player availability").status(),
        UnconfiguredProvider("Player props odds", "Superbet / STS / Fortuna player props").status(),
    ]
    return {"app":"NBA Value Finder", "generated_at":datetime.now(timezone.utc).isoformat(),
            "refresh_minutes":15, "providers":[p.__dict__ for p in providers],
            "verified_picks":0,
            "notice":"No verified feeds connected. The app intentionally displays no fabricated picks."}

@app.get("/api/picks")
def picks():
    return {"items":[], "count":0, "message":"No verified odds feed connected."}

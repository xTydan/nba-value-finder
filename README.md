# NBA Value Finder — starter

Public-web-app foundation for discovering NBA player-prop opportunities.

## Run locally (Windows)
1. Install Python 3.11+.
2. Clone or download this repository.
3. In the project directory run:
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   uvicorn app.main:app --reload
   ```
4. Open http://127.0.0.1:8000

## Current status
This is a working application foundation: FastAPI backend, responsive dashboard, SQLite schema, analysis primitives, and tests. It deliberately shows **zero verified picks** until real odds/injury/stat providers are configured. It does not invent bookmaker lines, injury reports, or player results.

## Next integration work
- Implement and validate a live NBA stats/game-log provider.
- Implement injury report and historical player availability provider.
- Implement a legal, reliable odds feed for Superbet, STS and Fortuna (or other free source).
- Store timestamped snapshots, run scheduled refresh every 15 minutes, and settle predictions.
- Deploy to a public host with persistent PostgreSQL.

A public URL cannot be created from this source package alone; hosting credentials and provider access are required.

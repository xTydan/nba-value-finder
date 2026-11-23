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

## Connected data source\n- ESPN public NBA endpoints: daily scoreboard, league injury report, and athlete game logs. No API key is required. These endpoints are undocumented and may change; failures are reported instead of replaced with sample data.\n- API routes: `/api/games`, `/api/injuries`, `/api/players/{player_id}/gamelog`, and `/api/status`.\n\n## Data policy
- The scanner fetches current source data on demand; no permanent historical database is required for its initial operation. A short in-memory cache may reduce repeated requests.
- Player-prop odds are taken only from verified live sources. Superbet Poland and STS Poland are preferred when their player markets are actually available; other bookmakers may be used when needed, but the real bookmaker name is always shown and never substituted.
- See [Live data policy](docs/LIVE_DATA_POLICY.md) for source selection, freshness checks and limitations.

## Next integration work
- Implement and validate a live NBA stats/game-log provider.
- Implement injury report and historical player availability provider.
- Validate live PropLine player-prop coverage and then build the probability/value model; Superbet/STS player props are not confirmed in this feed.
- Store timestamped snapshots, run scheduled refresh every 15 minutes, and settle predictions.
- Deploy to a public host with persistent PostgreSQL.

A public URL cannot be created from this source package alone; hosting credentials and provider access are required.

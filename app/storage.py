import os, sqlite3
from pathlib import Path
DB_PATH = Path(os.getenv("DB_PATH", "nba_value_finder.db"))
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS odds_snapshots (
          id INTEGER PRIMARY KEY, event_id TEXT NOT NULL, player_id TEXT NOT NULL,
          market TEXT NOT NULL, line REAL NOT NULL, side TEXT NOT NULL,
          decimal_odds REAL NOT NULL, bookmaker TEXT NOT NULL, captured_at TEXT NOT NULL,
          raw_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_odds_event ON odds_snapshots(event_id);
        CREATE TABLE IF NOT EXISTS injury_snapshots (
          id INTEGER PRIMARY KEY, captured_at TEXT NOT NULL, player_id TEXT NOT NULL,
          team_id TEXT NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL, raw_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS predictions (
          id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, event_id TEXT NOT NULL,
          player_id TEXT NOT NULL, market TEXT NOT NULL, line REAL NOT NULL, side TEXT NOT NULL,
          odds REAL NOT NULL, model_probability REAL NOT NULL, expected_value REAL NOT NULL,
          features_json TEXT NOT NULL, result TEXT, settled_value REAL);
        """)

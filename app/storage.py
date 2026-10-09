"""Локальный кэш матчей в SQLite, чтобы не ходить на flashscore на каждый запрос."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .flashscore import Match

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "matches.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    league TEXT NOT NULL,
    season TEXT NOT NULL,
    round TEXT,
    start TEXT NOT NULL,
    home TEXT NOT NULL,
    away TEXT NOT NULL,
    home_goals INTEGER NOT NULL,
    away_goals INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS updates (
    league TEXT NOT NULL,
    season TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (league, season)
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def save(league: str, season: str, matches: list[Match]) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM matches WHERE league = ? AND season = ?", (league, season))
        conn.executemany(
            "INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(m.id, m.league, m.season, m.round, m.start.isoformat(), m.home, m.away,
              m.home_goals, m.away_goals) for m in matches],
        )
        conn.execute(
            "INSERT OR REPLACE INTO updates VALUES (?, ?, ?)",
            (league, season, datetime.now().isoformat(timespec="seconds")),
        )


def load(league: str, season: str) -> list[Match]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, league, season, round, start, home, away, home_goals, away_goals "
            "FROM matches WHERE league = ? AND season = ? ORDER BY start",
            (league, season),
        ).fetchall()
    return [Match(r[0], r[1], r[2], r[3], datetime.fromisoformat(r[4]), *r[5:]) for r in rows]


def updated_at(league: str, season: str) -> str | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT updated_at FROM updates WHERE league = ? AND season = ?", (league, season)
        ).fetchone()
    return row[0] if row else None

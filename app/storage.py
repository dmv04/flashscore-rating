"""Локальный кэш матчей в SQLite, чтобы не ходить на flashscore на каждый запрос."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .flashscore import Match

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "matches.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id TEXT NOT NULL,
    tournament TEXT NOT NULL,
    season TEXT NOT NULL,
    round TEXT,
    start TEXT NOT NULL,
    home_id TEXT NOT NULL,
    home TEXT NOT NULL,
    away_id TEXT NOT NULL,
    away TEXT NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    PRIMARY KEY (tournament, id)
);
CREATE TABLE IF NOT EXISTS updates (
    tournament TEXT NOT NULL,
    season TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tournament, season)
);
"""
COLUMNS = "id, tournament, season, round, start, home_id, home, away_id, away, home_goals, away_goals"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    if "home_id" not in {r[1] for r in conn.execute("PRAGMA table_info(matches)")}:
        conn.executescript("DROP TABLE IF EXISTS matches; DROP TABLE IF EXISTS updates;")
    conn.executescript(SCHEMA)
    return conn


def save(tournament: str, season: str, matches: list[Match]) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM matches WHERE tournament = ? AND season = ?", (tournament, season))
        conn.executemany(
            f"INSERT INTO matches ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(m.id, m.tournament, m.season, m.round, m.start.isoformat(), m.home_id, m.home,
              m.away_id, m.away, m.home_goals, m.away_goals) for m in matches],
        )
        conn.execute(
            "INSERT OR REPLACE INTO updates VALUES (?, ?, ?)",
            (tournament, season, datetime.now().isoformat(timespec="seconds")),
        )


def load(tournaments: list[str], season: str) -> list[Match]:
    marks = ",".join("?" * len(tournaments))
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT {COLUMNS} FROM matches WHERE tournament IN ({marks}) AND season = ? ORDER BY start",
            (*tournaments, season),
        ).fetchall()
    return [Match(*r[:4], datetime.fromisoformat(r[4]), *r[5:]) for r in rows]


def updated(season: str) -> dict[str, str]:
    with _conn() as conn:
        return dict(conn.execute("SELECT tournament, updated_at FROM updates WHERE season = ?", (season,)))

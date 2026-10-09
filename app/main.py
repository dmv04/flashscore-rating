from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from . import flashscore, rating, storage

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Flashscore rating")


def _check(league: str, season: str) -> None:
    if league not in flashscore.LEAGUES:
        raise HTTPException(404, f"Неизвестная лига: {league}")
    if season not in flashscore.SEASONS:
        raise HTTPException(404, f"Неизвестный сезон: {season}")


def _round_no(r: str) -> int | None:
    m = re.search(r"\d+", r or "")
    return int(m.group()) if m else None


def _matches(league: str, season: str) -> list[flashscore.Match]:
    matches = storage.load(league, season)
    if not matches:
        matches = flashscore.fetch_league(league, season)
        storage.save(league, season, matches)
    return matches


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/leagues")
def leagues():
    return {
        "leagues": [{"id": k, "name": v["name"]} for k, v in flashscore.LEAGUES.items()],
        "seasons": flashscore.SEASONS,
    }


@app.post("/api/refresh")
def refresh(league: str, season: str = flashscore.SEASONS[0]):
    _check(league, season)
    matches = flashscore.fetch_league(league, season)
    storage.save(league, season, matches)
    return {"matches": len(matches), "updated_at": storage.updated_at(league, season)}


@app.get("/api/rating")
def get_rating(
    league: str,
    season: str = flashscore.SEASONS[0],
    last_n: int | None = Query(None, ge=1, description="Учитывать последние N матчей команды"),
    upto_round: int | None = Query(None, ge=1, description="Учитывать туры до N включительно"),
    avg: float = Query(rating.RT_AVG, description="Средний рейтинг турнира"),
):
    _check(league, season)
    matches = _matches(league, season)
    max_round = max((_round_no(m.round) or 0 for m in matches), default=0)
    if upto_round:
        matches = [m for m in matches if (_round_no(m.round) or 0) <= upto_round]

    table = rating.compute(matches, last_n=last_n, avg=avg)
    goals = sum(m.home_goals + m.away_goals for m in matches)
    return {
        "league": league,
        "season": season,
        "updated_at": storage.updated_at(league, season),
        "matches": len(matches),
        "max_round": max_round,
        "avg_goals": goals / len(matches) if matches else 0,
        "table": [
            {
                "team": r.team,
                "rating": round(r.rating, 1),
                "played": r.played,
                "scored": r.scored,
                "conceded": r.conceded,
                "goal_diff": r.goal_diff,
                "balance": round(r.balance, 4),
            }
            for r in table
        ],
    }


@app.get("/api/matches")
def get_matches(league: str, season: str = flashscore.SEASONS[0]):
    _check(league, season)
    return [
        {
            "round": m.round,
            "start": m.start.isoformat(),
            "home": m.home,
            "away": m.away,
            "score": f"{m.home_goals}:{m.away_goals}",
        }
        for m in _matches(league, season)
    ]

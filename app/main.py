from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from . import service
from .tournaments import ALL

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Flashscore rating")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    return service.meta()


@app.post("/api/refresh")
def refresh(tournament: str | None = None):
    if tournament and tournament not in ALL:
        raise HTTPException(404, f"Неизвестный турнир: {tournament}")
    counts = service.refresh([tournament] if tournament else None)
    return {"matches": counts, **service.meta()}


@app.get("/api/rating")
def rating(
    scope: str = Query(..., description="id лиги или world"),
    last_n: int | None = Query(None, ge=1, description="Учитывать последние N матчей команды"),
):
    try:
        return service.rating_table(scope, last_n)
    except KeyError:
        raise HTTPException(404, f"Неизвестная лига: {scope}")


@app.get("/api/predictions")
def predictions(last_n: int | None = Query(None, ge=1)):
    return service.predictions(last_n)

"""Парсер результатов матчей с flashscore.com.

Страница результатов содержит первую порцию матчей прямо в HTML
(cjs.initialFeeds['results']), остальные подгружаются кнопкой "Show more"
из фида  https://2.flashscore.ninja/2/x/feed/tr_1_{country}_{tournament}_{season}_{page}_3_en_1.
Формат фида: записи разделены "~", поля "¬", ключ/значение "÷".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

BASE = "https://www.flashscore.com"
FEED_HOST = "https://2.flashscore.ninja/2/x/feed"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": BASE + "/",
}
DEFAULT_FSIGN = "SW9D1eZo"
STATUS_FINISHED = "3"

LEAGUES = {
    "epl": {"name": "Англия — Премьер-лига", "path": "/football/england/premier-league-{season}/results/"},
    "laliga": {"name": "Испания — Ла Лига", "path": "/football/spain/laliga-{season}/results/"},
}
SEASONS = ["2025-2026"]


@dataclass
class Match:
    id: str
    league: str
    season: str
    round: str
    start: datetime
    home: str
    away: str
    home_goals: int
    away_goals: int


def _records(feed: str) -> list[dict[str, str]]:
    out = []
    for chunk in feed.split("~"):
        rec = {}
        for field in chunk.split("¬"):
            if "÷" in field:
                k, v = field.split("÷", 1)
                rec[k] = v
        if rec:
            out.append(rec)
    return out


def _parse_matches(feed: str, league: str, season: str) -> list[Match]:
    matches = []
    for r in _records(feed):
        if "AA" not in r or r.get("AB") != STATUS_FINISHED:
            continue
        try:
            hg, ag = int(r["AG"]), int(r["AH"])
        except (KeyError, ValueError):
            continue
        matches.append(Match(
            id=r["AA"],
            league=league,
            season=season,
            round=r.get("ER", ""),
            start=datetime.fromtimestamp(int(r["AD"]), tz=timezone.utc),
            home=r.get("AE", ""),
            away=r.get("AF", ""),
            home_goals=hg,
            away_goals=ag,
        ))
    return matches


def fetch_league(league: str, season: str = SEASONS[0]) -> list[Match]:
    """Скачивает все сыгранные матчи турнира за сезон."""
    url = BASE + LEAGUES[league]["path"].format(season=season)
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        html = client.get(url).raise_for_status().text

        m = re.search(r"initialFeeds\['results'\]\s*=\s*\{\s*data:\s*`(.*?)`,(.*?)\}", html, re.S)
        if not m:
            raise RuntimeError(f"Не найден блок результатов на {url}")
        feed, meta = m.group(1), m.group(2)
        season_id = re.search(r"seasonId:\s*(\d+)", meta).group(1)
        head = next(r for r in _records(feed) if "ZEE" in r)
        country_id, tournament_id = head["ZB"], head["ZEE"]
        sign = re.search(r'feed_sign"\s*:\s*"([^"]+)"', html)
        fsign = sign.group(1) if sign else DEFAULT_FSIGN

        by_id = {mt.id: mt for mt in _parse_matches(feed, league, season)}
        for page in range(1, 50):
            name = f"tr_1_{country_id}_{tournament_id}_{season_id}_{page}_3_en_1"
            resp = client.get(f"{FEED_HOST}/{name}", headers={"x-fsign": fsign})
            resp.raise_for_status()
            chunk = _parse_matches(resp.text, league, season)
            if not chunk:
                break
            by_id.update((mt.id, mt) for mt in chunk)

    return sorted(by_id.values(), key=lambda mt: mt.start)

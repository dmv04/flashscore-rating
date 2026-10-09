"""Парсер матчей с flashscore.com.

Страница результатов турнира содержит в HTML первую порцию сыгранных матчей
(cjs.initialFeeds['results']) и ближайшие предстоящие (initialFeeds['fixtures']).
Остальные результаты подгружаются кнопкой "Show more" из фида
https://2.flashscore.ninja/2/x/feed/tr_1_{country}_{stage}_{season}_{page}_3_en_1.
Формат фидов: записи разделены "~", поля "¬", ключ/значение "÷".
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from .tournaments import SEASON, Tournament

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
FINISHED, SCHEDULED = "3", "1"


@dataclass
class Match:
    id: str
    tournament: str
    season: str
    round: str
    start: datetime
    home_id: str
    home: str
    away_id: str
    away: str
    home_goals: int | None  # None — матч ещё не сыгран
    away_goals: int | None

    @property
    def finished(self) -> bool:
        return self.home_goals is not None


def _records(feed: str) -> list[dict[str, str]]:
    out = []
    for chunk in feed.split("~"):
        rec = dict(f.split("÷", 1) for f in chunk.split("¬") if "÷" in f)
        if rec:
            out.append(rec)
    return out


def _parse(feed: str, tournament: str, season: str) -> list[Match]:
    matches = []
    for r in _records(feed):
        if "AA" not in r or r.get("AB") not in (FINISHED, SCHEDULED):
            continue
        goals: tuple[int | None, int | None] = (None, None)
        if r["AB"] == FINISHED:
            try:
                goals = int(r["AG"]), int(r["AH"])
            except (KeyError, ValueError):
                continue
        matches.append(Match(
            id=r["AA"],
            tournament=tournament,
            season=season,
            round=r.get("ER", ""),
            start=datetime.fromtimestamp(int(r["AD"]), tz=timezone.utc),
            home_id=r.get("PX", r.get("AE", "")),
            home=r.get("AE", ""),
            away_id=r.get("PY", r.get("AF", "")),
            away=r.get("AF", ""),
            home_goals=goals[0],
            away_goals=goals[1],
        ))
    return matches


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    """GET с повторами: соединение до flashscore иногда рвётся на TLS."""
    for attempt in range(5):
        try:
            return client.get(url, **kw).raise_for_status()
        except httpx.TransportError:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def _feed(html: str, name: str) -> tuple[str, str]:
    m = re.search(rf"initialFeeds\['{name}'\]\s*=\s*\{{\s*data:\s*`(.*?)`,(.*?)\}}", html, re.S)
    return (m.group(1), m.group(2)) if m else ("", "")


def fetch_tournament(t: Tournament, season: str = SEASON) -> list[Match]:
    """Сыгранные и предстоящие матчи турнира за сезон."""
    url = f"{BASE}/football/{t.path}-{season}/results/"
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        html = _get(client, url).text

        results, meta = _feed(html, "results")
        fixtures, _ = _feed(html, "fixtures")
        by_id = {m.id: m for m in _parse(results + "~" + fixtures, t.id, season)}

        total = re.search(r"allEventsCount:\s*(\d+)", meta)
        season_id = re.search(r"seasonId:\s*(\d+)", meta)
        head = next((r for r in _records(results) if "ZEE" in r), None)
        finished = sum(m.finished for m in by_id.values())
        if head and season_id and total and finished < int(total.group(1)):
            sign = re.search(r'feed_sign"\s*:\s*"([^"]+)"', html)
            fsign = sign.group(1) if sign else DEFAULT_FSIGN
            for page in range(1, 50):
                name = f"tr_1_{head['ZB']}_{head['ZEE']}_{season_id.group(1)}_{page}_3_en_1"
                chunk = _parse(_get(client, f"{FEED_HOST}/{name}", headers={"x-fsign": fsign}).text, t.id, season)
                if not chunk:
                    break
                by_id.update((m.id, m) for m in chunk)

    return sorted(by_id.values(), key=lambda m: m.start)

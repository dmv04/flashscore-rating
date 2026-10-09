"""Собирает автономную HTML-страницу с встроенными матчами из data/matches.db.

    python -m share.build <output.html>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app import flashscore, storage
from app.main import _round_no

SHORT = {"epl": "Англия", "laliga": "Испания"}


def build(out: Path, season: str = flashscore.SEASONS[0]) -> None:
    leagues, updated = {}, []
    for lg in flashscore.LEAGUES:
        matches = storage.load(lg, season)
        if not matches:
            matches = flashscore.fetch_league(lg, season)
            storage.save(lg, season, matches)
        leagues[lg] = {
            "short": SHORT.get(lg, lg),
            # [тур, хозяева, гости, голы хозяев, голы гостей] в хронологическом порядке
            "matches": [[_round_no(m.round) or 0, m.home, m.away, m.home_goals, m.away_goals] for m in matches],
        }
        updated.append(storage.updated_at(lg, season) or "")
    data = json.dumps({"season": season, "leagues": leagues}, ensure_ascii=False, separators=(",", ":"))
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    html = tpl.replace("__DATA__", data).replace("__UPDATED__", max(updated).replace("T", " ")[:16])
    out.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]))

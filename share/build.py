"""Собирает автономную страницу для шаринга: интерфейс app/static/index.html
со встроенными ответами API (снимок кэша), без сервера.

    python -m share.build <output.html>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from app import service
from app.tournaments import LEAGUES

INDEX = Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"
LAST_N = ["", "5", "8", "10"]


def snapshot() -> dict:
    data = {"/api/meta": service.meta()}
    for n in LAST_N:
        last_n = int(n) if n else None
        suffix = f"&last_n={n}" if n else ""
        for scope in ["world"] + [t.id for t in LEAGUES]:
            data[f"/api/rating?scope={scope}{suffix}"] = service.rating_table(scope, last_n)
        data[f"/api/predictions?{suffix[1:]}"] = service.predictions(last_n)
    return data


def build(out: Path) -> None:
    html = INDEX.read_text(encoding="utf-8")
    # страница публикуется внутрь готового каркаса — убираем свой
    html = re.sub(r"<!doctype html>|</?html[^>]*>|</?head>|</?body>|<meta [^>]*>", "", html, flags=re.I)
    data = json.dumps(snapshot(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("<script>", f"<script>window.STATIC_DATA={data};</script>\n<script>", 1)
    out.write_text(html.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    build(Path(sys.argv[1]))

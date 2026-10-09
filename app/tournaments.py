"""Список турниров. Пути — как в адресах flashscore.com/football/<path>-<season>/results/."""
from __future__ import annotations

from dataclasses import dataclass

SEASON = "2026-2027"
# прошлый сезон нужен только для оценки силы лиг по еврокубкам
PREV_SEASON = "2025-2026"


@dataclass(frozen=True)
class Tournament:
    id: str
    name: str
    path: str
    country: str | None = None  # None — еврокубок
    world: bool = True  # участвует в мировом рейтинге


LEAGUES = [
    Tournament("epl", "Премьер-лига", "england/premier-league", "Англия"),
    Tournament("laliga", "Ла Лига", "spain/laliga", "Испания"),
    Tournament("seriea", "Серия A", "italy/serie-a", "Италия"),
    Tournament("bundesliga", "Бундеслига", "germany/bundesliga", "Германия"),
    Tournament("ligue1", "Лига 1", "france/ligue-1", "Франция"),
    Tournament("portugal", "Лига Португал", "portugal/liga-portugal", "Португалия"),
    Tournament("eredivisie", "Эредивизи", "netherlands/eredivisie", "Нидерланды"),
    Tournament("belgium", "Про Лига", "belgium/jupiler-pro-league", "Бельгия"),
    Tournament("turkey", "Суперлига", "turkey/super-lig", "Турция"),
    Tournament("scotland", "Премьершип", "scotland/premiership", "Шотландия"),
    Tournament("rpl", "РПЛ", "russia/premier-league", "Россия", world=False),
    Tournament("fnl", "ФНЛ", "russia/fnl", "Россия", world=False),
]

CUPS = [
    Tournament("ucl", "Лига чемпионов", "europe/champions-league"),
    Tournament("uel", "Лига Европы", "europe/europa-league"),
    Tournament("uecl", "Лига конференций", "europe/conference-league"),
]

ALL = {t.id: t for t in LEAGUES + CUPS}

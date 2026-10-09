"""Рейтинги и прогнозы поверх кэша матчей."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import flashscore, rating, storage
from .flashscore import Match
from .tournaments import ALL, CUPS, LEAGUES, PREV_SEASON, SEASON

WORLD = "world"
WORLD_LEAGUES = [t.id for t in LEAGUES if t.world]
CUP_IDS = [c.id for c in CUPS]


def refresh(ids: list[str] | None = None, season: str = SEASON) -> dict[str, int]:
    out = {}
    for tid in ids or list(ALL):
        matches = flashscore.fetch_tournament(ALL[tid], season)
        storage.save(tid, season, matches)
        out[tid] = len(matches)
    return out


def _load(ids: list[str], season: str = SEASON) -> list[Match]:
    missing = [t for t in ids if t not in storage.updated(season)]
    if missing:
        refresh(missing, season)
    return storage.load(ids, season)


def _round_no(r: str) -> int | None:
    m = re.fullmatch(r"Round (\d+)", r or "")
    return int(m.group(1)) if m else None


@dataclass
class Table:
    league: str
    ratings: dict[str, rating.TeamRating]  # по id команды
    matches: list[Match]


def national(league: str, season: str = SEASON, last_n: int | None = None) -> Table:
    matches = _load([league], season)
    names = {}
    for m in matches:
        names[m.home_id], names[m.away_id] = m.home, m.away
    table = rating.compute(matches, names, last_n)
    return Table(league, {r.id: r for r in table}, matches)


def _links(season: str, last_n: int | None) -> list[tuple[str, str, float, float, int, int]]:
    """Межлиговые матчи еврокубков сезона с национальными рейтингами команд того же сезона."""
    team = {}
    for lg in WORLD_LEAGUES:
        for tid, r in national(lg, season, last_n if season == SEASON else None).ratings.items():
            team[tid] = (lg, r.rating)
    links = []
    for m in _load(CUP_IDS, season):
        if m.finished and m.home_id in team and m.away_id in team:
            (la, ri), (lb, rj) = team[m.home_id], team[m.away_id]
            links.append((la, lb, ri, rj, m.home_goals, m.away_goals))
    return links


def world(last_n: int | None = None) -> tuple[dict[str, rating.TeamRating], dict[str, str], dict]:
    """Мировой рейтинг: национальный рейтинг текущего сезона + поправка силы лиги.
    Поправки оцениваются по еврокубкам текущего и прошлого сезона."""
    tables = {lg: national(lg, SEASON, last_n) for lg in WORLD_LEAGUES}
    links = _links(SEASON, last_n) + _links(PREV_SEASON, None)
    offsets = rating.league_offsets(links, {lg: len(t.ratings) for lg, t in tables.items()})

    count = Counter()
    for la, lb, *_ in links:
        if la != lb:
            count[la] += 1
            count[lb] += 1

    teams, league_of = {}, {}
    for lg, t in tables.items():
        for tid, r in t.ratings.items():
            teams[tid] = rating.TeamRating(**{**r.__dict__, "rating": r.rating + offsets[lg]})
            league_of[tid] = lg
    info = {lg: {"offset": round(offsets[lg], 1), "links": count[lg]} for lg in WORLD_LEAGUES}
    return teams, league_of, info


def _row(r: rating.TeamRating, league: str) -> dict:
    return {
        "team": r.team,
        "league": league,
        "rating": round(r.rating, 1),
        "played": r.played,
        "scored": r.scored,
        "conceded": r.conceded,
        "goal_diff": r.goal_diff,
        "balance": round(r.balance, 4),
    }


def rating_table(scope: str, last_n: int | None = None) -> dict:
    upd = storage.updated(SEASON)
    if scope == WORLD:
        teams, league_of, info = world(last_n)
        rows = [_row(r, league_of[tid]) for tid, r in teams.items()]
        ids = WORLD_LEAGUES + CUP_IDS
        extra = {"leagues": info}
    elif scope in ALL and ALL[scope].country:
        t = national(scope, SEASON, last_n)
        rows = [_row(r, scope) for r in t.ratings.values()]
        ids = [scope]
        extra = {}
    else:
        raise KeyError(scope)
    rows.sort(key=lambda r: r["rating"], reverse=True)
    return {
        "scope": scope,
        "season": SEASON,
        "updated_at": min((upd.get(t, "") for t in ids), default=""),
        "table": rows,
        **extra,
    }


def next_round(matches: list[Match]) -> tuple[int | None, list[Match]]:
    """Ближайший тур: наименьший номер среди туров, где запланировано хотя бы четверть матчей тура
    (одиночные перенесённые игры прошлых туров не считаются туром)."""
    teams = {t for m in matches for t in (m.home_id, m.away_id)}
    per_round = len(teams) // 2 or 1
    upcoming: dict[int, list[Match]] = defaultdict(list)
    for m in matches:
        n = _round_no(m.round)
        if not m.finished and n is not None:
            upcoming[n].append(m)
    rounds = sorted(n for n, ms in upcoming.items() if len(ms) >= max(1, per_round // 4))
    if not rounds:
        return None, []
    return rounds[0], sorted(upcoming[rounds[0]], key=lambda m: m.start)


def predictions(last_n: int | None = None) -> dict:
    """Прогнозы на ближайший тур всех национальных чемпионатов по национальному рейтингу.
    Мировой рейтинг для матчей внутри лиги дал бы то же самое: поправка силы лиги
    одинакова у обеих команд и сокращается в разнице Rt_i − Rt_j."""
    leagues = []
    for t in LEAGUES:
        nat = national(t.id, SEASON, last_n)
        rnd, fixtures = next_round(nat.matches)
        games = []
        for m in fixtures:
            hi, aj = nat.ratings.get(m.home_id), nat.ratings.get(m.away_id)
            if not hi or not aj:
                continue
            total = (hi.goals_per_match + aj.goals_per_match) / 2
            gh, ga = rating.expected_goals(hi.rating, aj.rating, total)
            w, d, l, score = rating.outcome_probs(gh, ga)
            games.append({
                "start": m.start.isoformat(),
                "home": m.home, "away": m.away,
                "home_rating": round(hi.rating, 1), "away_rating": round(aj.rating, 1),
                "total": round(total, 2),
                "home_goals": round(gh, 2), "away_goals": round(ga, 2),
                "p_home": round(w, 3), "p_draw": round(d, 3), "p_away": round(l, 3),
                "score": score,
            })
        leagues.append({"league": t.id, "country": t.country, "name": t.name, "round": rnd, "games": games})
    return {"season": SEASON, "leagues": leagues}


def meta() -> dict:
    return {
        "season": SEASON,
        "leagues": [{"id": t.id, "name": t.name, "country": t.country, "world": t.world} for t in LEAGUES],
        "cups": [{"id": t.id, "name": t.name} for t in CUPS],
        "updated": storage.updated(SEASON),
    }

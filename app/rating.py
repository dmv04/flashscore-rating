"""Рейтинг команд по балансу забитых/пропущенных — система линейных уравнений.

Для команды i и её матчей m (соперник j(m), забито З_m, пропущено П_m):
    δ_im = (З_m + П_m) / (ΣЗ_i + ΣП_i)        — вес матча
    Δ_i  = (ΣЗ_i − ΣП_i) / (ΣЗ_i + ΣП_i)      — относительный баланс
    Rt_i = Σ_m δ_im · Rt_j(m) + 1000 · Δ_i
    (1/n) · Σ Rt_i = 2200                      — средний рейтинг турнира

Первые n уравнений линейно зависимы (каждая строка матрицы в сумме даёт 0),
поэтому система решается вместе с условием на среднее методом наименьших
квадратов — при совместной системе это точное решение.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .flashscore import Match

RT_AVG = 2200.0
SCALE = 1000.0


@dataclass
class TeamRating:
    team: str
    rating: float
    played: int
    scored: int
    conceded: int
    balance: float  # Δ_i

    @property
    def goal_diff(self) -> int:
        return self.scored - self.conceded


def team_games(matches: list[Match], last_n: int | None = None) -> dict[str, list[tuple[str, int, int]]]:
    """Для каждой команды — список (соперник, забито, пропущено), последние last_n матчей."""
    games: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for m in sorted(matches, key=lambda m: m.start):
        games[m.home].append((m.away, m.home_goals, m.away_goals))
        games[m.away].append((m.home, m.away_goals, m.home_goals))
    if last_n:
        games = {t: g[-last_n:] for t, g in games.items()}
    return dict(games)


def compute(matches: list[Match], last_n: int | None = None, avg: float = RT_AVG) -> list[TeamRating]:
    games = team_games(matches, last_n)
    teams = sorted(games)
    if not teams:
        return []
    idx = {t: k for k, t in enumerate(teams)}
    n = len(teams)

    a = np.zeros((n + 1, n))
    b = np.zeros(n + 1)
    stats = {}
    for t, gl in games.items():
        i = idx[t]
        scored = sum(g for _, g, _ in gl)
        conceded = sum(c for _, _, c in gl)
        total = scored + conceded
        a[i, i] = 1.0
        if total == 0:
            # только нули — рейтинг команды равен среднему
            b[i] = avg
            delta = 0.0
        else:
            for opp, g, c in gl:
                a[i, idx[opp]] -= (g + c) / total
            delta = (scored - conceded) / total
            b[i] = SCALE * delta
        stats[t] = (len(gl), scored, conceded, delta)

    a[n, :] = 1.0 / n
    b[n] = avg
    rt, *_ = np.linalg.lstsq(a, b, rcond=None)

    result = [TeamRating(t, float(rt[idx[t]]), *stats[t]) for t in teams]
    return sorted(result, key=lambda r: r.rating, reverse=True)


def expected_goals(rt_i: float, rt_j: float, total: float) -> tuple[float, float]:
    """Ожидаемые голы команд i и j при общем числе голов total (формула 19)."""
    gi = total * (SCALE + (rt_i - rt_j)) / (2 * SCALE)
    return gi, total - gi

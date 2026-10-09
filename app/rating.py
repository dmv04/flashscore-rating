"""Рейтинг команд по балансу забитых/пропущенных — система линейных уравнений.

Для команды i и её матчей m (соперник j(m), забито З_m, пропущено П_m):
    δ_im = (З_m + П_m) / (ΣЗ_i + ΣП_i)        — вес матча
    Δ_i  = (ΣЗ_i − ΣП_i) / (ΣЗ_i + ΣП_i)      — относительный баланс
    Rt_i = Σ_m δ_im · Rt_j(m) + 1000 · Δ_i
    (1/n) · Σ Rt_i = 2200                      — средний рейтинг турнира

Первые n уравнений линейно зависимы (каждая строка матрицы в сумме даёт 0),
поэтому система решается вместе с условием на среднее методом наименьших
квадратов — при совместной системе это точное решение.

Мировой рейтинг = национальный рейтинг + поправка силы лиги (league_offsets),
которая оценивается по межлиговым матчам еврокубков.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .flashscore import Match

RT_AVG = 2200.0
SCALE = 1000.0


@dataclass
class TeamRating:
    id: str
    team: str
    rating: float
    played: int
    scored: int
    conceded: int
    balance: float  # Δ_i

    @property
    def goal_diff(self) -> int:
        return self.scored - self.conceded

    @property
    def goals_per_match(self) -> float:
        return (self.scored + self.conceded) / self.played if self.played else 0.0


def team_games(matches: list[Match], last_n: int | None = None) -> dict[str, list[tuple[str, int, int]]]:
    """Для каждой команды — список (соперник, забито, пропущено), последние last_n матчей."""
    games: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for m in sorted(matches, key=lambda m: m.start):
        if not m.finished:
            continue
        games[m.home_id].append((m.away_id, m.home_goals, m.away_goals))
        games[m.away_id].append((m.home_id, m.away_goals, m.home_goals))
    if last_n:
        games = {t: g[-last_n:] for t, g in games.items()}
    return dict(games)


def compute(
    matches: list[Match],
    names: dict[str, str],
    last_n: int | None = None,
    avg: float = RT_AVG,
) -> list[TeamRating]:
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
            b[i] = avg  # только нули — рейтинг команды равен среднему
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

    result = [TeamRating(t, names.get(t, t), float(rt[idx[t]]), *stats[t]) for t in teams]
    return sorted(result, key=lambda r: r.rating, reverse=True)


def league_offsets(
    links: list[tuple[str, str, float, float, int, int]],
    sizes: dict[str, int],
) -> dict[str, float]:
    """Поправки силы лиг по межлиговым матчам.

    links: (лига i, лига j, Rt_i, Rt_j, голы i, голы j) — национальные рейтинги команд и счёт матча.
    Для каждого матча то же уравнение, что внутри турнира: (Rt_i + o_A) − (Rt_j + o_B) = 1000·Δ_m,
    с весом З+П. Неизвестные — только поправки лиг o; условие Σ size_L·o_L = 0 сохраняет
    средний мировой рейтинг 2200 (средний национальный в каждой лиге уже 2200).
    """
    leagues = sorted(sizes)
    idx = {lg: k for k, lg in enumerate(leagues)}
    rows, rhs = [], []
    for la, lb, ri, rj, g, c in links:
        if la == lb or g + c == 0:
            continue
        w = math.sqrt(g + c)
        row = np.zeros(len(leagues))
        row[idx[la]], row[idx[lb]] = w, -w
        rows.append(row)
        rhs.append(w * (SCALE * (g - c) / (g + c) - (ri - rj)))
    total = sum(sizes.values())
    # условие на среднее — с большим весом, чтобы выполнялось точно
    rows.append(np.array([1e3 * sizes[lg] / total for lg in leagues]))
    rhs.append(0.0)
    o, *_ = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)
    return {lg: float(o[idx[lg]]) for lg in leagues}


def expected_goals(rt_i: float, rt_j: float, total: float) -> tuple[float, float]:
    """Ожидаемые голы команд i и j при общем числе голов total (формула 19)."""
    share = min(max((SCALE + (rt_i - rt_j)) / (2 * SCALE), 0.0), 1.0)
    return total * share, total * (1 - share)


def outcome_probs(lam_i: float, lam_j: float, max_goals: int = 10) -> tuple[float, float, float, str]:
    """Вероятности П1/Х/П2 и самый вероятный счёт при пуассоновских голах с ожиданиями lam_i, lam_j."""
    pi = [math.exp(-lam_i) * lam_i ** k / math.factorial(k) for k in range(max_goals + 1)]
    pj = [math.exp(-lam_j) * lam_j ** k / math.factorial(k) for k in range(max_goals + 1)]
    win = draw = loss = 0.0
    best, best_p = (0, 0), -1.0
    for x, px in enumerate(pi):
        for y, py in enumerate(pj):
            p = px * py
            if x > y:
                win += p
            elif x == y:
                draw += p
            else:
                loss += p
            if p > best_p:
                best, best_p = (x, y), p
    s = win + draw + loss
    return win / s, draw / s, loss / s, f"{best[0]}:{best[1]}"

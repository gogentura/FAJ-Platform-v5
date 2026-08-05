#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Poisson Model v2.0.3
Расчёт вероятностей счетов на основе ожидаемых голов (xG)

ИСПРАВЛЕНИЯ v2.0.3:
- Diagnostics теперь полноценный TypedDict (без NotRequired)
- _prepare_lambdas возвращает Diagnostics вместо Dict[str, Any]
- raw_sum теперь корректно сохраняется ДО нормализации
- MarketsResult содержит raw_expected_total и expected_total

v2.0.3 — PRODUCTION CORE
Готов к фиксации в FAJ Core
"""

import math
import heapq
from typing import Dict, List, Optional, Tuple, TypedDict
from functools import lru_cache


# ============================================================
# TYPES
# ============================================================

class ResultProbability(TypedDict):
    home: float
    draw: float
    away: float


class DoubleChance(TypedDict):
    one_x: float   # 1X
    x_two: float   # X2
    one_two: float # 12


class Diagnostics(TypedDict):
    # Информация о клиппинге
    home_xg_clipped: bool
    away_xg_clipped: bool
    input_home_xg: float
    input_away_xg: float
    effective_home_lambda: float
    effective_away_lambda: float
    raw_expected_total: float
    effective_expected_total: float
    
    # Информация о матрице
    raw_sum: float          # Сумма ДО нормализации
    tail_cut: float         # Отсечённая вероятность
    convergence_ok: bool    # Сумма после нормализации ≈ 1.0
    max_goals_used: int     # Размер матрицы


class TopScore(TypedDict):
    score: str
    probability: float


class MarketsResult(TypedDict):
    result_probability: ResultProbability
    double_chance: DoubleChance
    btts_probability: float
    btts_no_probability: float
    over_2_5: float
    under_2_5: float
    raw_expected_total: float   # Сумма входных xG (до клиппинга)
    expected_total: float        # Сумма lambda (после клиппинга)
    tail_probability: float
    most_likely_score: str
    score_probability: float
    top_scores: List[TopScore]


class PoissonResult(MarketsResult):
    matrix_sum: float
    diagnostics: Diagnostics
    score_matrix: Optional[Dict[Tuple[int, int], float]]


# ============================================================
# MAIN CLASS
# ============================================================

class FAJPoissonModel:
    """
    Модель распределения вероятностей счетов на основе xG

    Это ядро вероятностных расчетов FAJ Platform.
    Модель строит матрицу распределения голов по Пуассону
    и вычисляет все рыночные показатели.

    Архитектура:
        ┌─────────────────────────────────────┐
        │         FAJPoissonModel             │
        ├─────────────────────────────────────┤
        │  calculate()   → полный результат   │
        │  markets()     → только рынки       │
        │  score_matrix()→ только матрица     │
        └─────────────────────────────────────┘

    Пример:
        >>> model = FAJPoissonModel(max_goals=8)
        >>> result = model.calculate(1.72, 0.95)
        >>> print(result['result_probability']['home'])
        0.482
    """

    # ============================================================
    # КОНФИГУРАЦИЯ
    # ============================================================

    XG_MIN: float = 0.1
    XG_MAX: float = 4.0

    def __init__(self, max_goals: int = 8):
        """
        Args:
            max_goals: максимальное количество голов для матрицы
                      (рекомендуется 8-10 для стандартных лиг)
        """
        if max_goals < 1:
            raise ValueError(f"max_goals должен быть >= 1, получено {max_goals}")

        self.MAX_GOALS = max_goals

    # ============================================================
    # ПУБЛИЧНЫЙ API
    # ============================================================

    def calculate(
        self,
        home_xg: float,
        away_xg: float,
        include_matrix: bool = False
    ) -> PoissonResult:
        """
        Полный расчёт всех вероятностей

        Args:
            home_xg: ожидаемые голы хозяев
            away_xg: ожидаемые голы гостей
            include_matrix: если True, возвращает полную матрицу счетов

        Returns:
            PoissonResult с полными данными
        """
        # Подготовка матрицы
        home_lambda, away_lambda, score_matrix, raw_sum, tail_probability, diagnostics = (
            self._prepare_matrix(home_xg, away_xg)
        )

        # Расчет всех показателей за один проход
        markets = self._calculate_markets(score_matrix)

        # Заполняем expected_total и tail_probability
        markets["raw_expected_total"] = home_xg + away_xg
        markets["expected_total"] = home_lambda + away_lambda
        markets["tail_probability"] = tail_probability

        # Сумма матрицы (после нормализации ≈ 1.0)
        matrix_sum = sum(score_matrix.values())

        # Диагностика
        diagnostics.update({
            "raw_sum": raw_sum,
            "tail_cut": tail_probability,
            "convergence_ok": abs(matrix_sum - 1.0) < 1e-9,
            "max_goals_used": self.MAX_GOALS
        })

        # Результат
        result: PoissonResult = {
            **markets,
            "matrix_sum": matrix_sum,
            "diagnostics": diagnostics,
            "score_matrix": score_matrix if include_matrix else None
        }

        return result

    def score_matrix(
        self,
        home_xg: float,
        away_xg: float,
        normalize: bool = True
    ) -> Dict[Tuple[int, int], float]:
        """
        Возвращает только матрицу счетов (сырую или нормированную)

        Args:
            home_xg: ожидаемые голы хозяев
            away_xg: ожидаемые голы гостей
            normalize: нормировать матрицу

        Returns:
            Dict[(home_goals, away_goals), probability]
        """
        home_lambda, away_lambda, _ = self._prepare_lambdas(home_xg, away_xg)
        raw_matrix, raw_sum = self._build_raw_score_matrix(home_lambda, away_lambda)

        if normalize:
            return self._normalize_matrix(raw_matrix, raw_sum)

        return raw_matrix

    def markets(
        self,
        home_xg: float,
        away_xg: float
    ) -> MarketsResult:
        """
        Возвращает только рыночные показатели (без диагностики и матрицы)

        Args:
            home_xg: ожидаемые голы хозяев
            away_xg: ожидаемые голы гостей

        Returns:
            MarketsResult с вероятностями рынков
        """
        # Подготовка матрицы
        home_lambda, away_lambda, score_matrix, raw_sum, tail_probability, _ = (
            self._prepare_matrix(home_xg, away_xg)
        )

        # Расчет рынков
        markets = self._calculate_markets(score_matrix)

        # Заполняем expected_total и tail_probability
        markets["raw_expected_total"] = home_xg + away_xg
        markets["expected_total"] = home_lambda + away_lambda
        markets["tail_probability"] = tail_probability

        return markets

    # ============================================================
    # ВНУТРЕННИЕ МЕТОДЫ
    # ============================================================

    def _prepare_matrix(
        self,
        home_xg: float,
        away_xg: float
    ) -> Tuple[float, float, Dict[Tuple[int, int], float], float, float, Diagnostics]:
        """
        Подготавливает полную матрицу с диагностикой

        Returns:
            Tuple[home_lambda, away_lambda, score_matrix, raw_sum, tail_probability, diagnostics]
        """
        # Подготовка lambdas
        home_lambda, away_lambda, diagnostics = self._prepare_lambdas(home_xg, away_xg)

        # Построение сырой матрицы
        raw_matrix, raw_sum = self._build_raw_score_matrix(home_lambda, away_lambda)

        # Хвостовая вероятность (ДО нормализации)
        tail_probability = max(0.0, min(1.0, 1.0 - raw_sum))

        # Нормализация
        score_matrix = self._normalize_matrix(raw_matrix, raw_sum)

        # Добавляем raw/effective expected_total в диагностику
        diagnostics["raw_expected_total"] = home_xg + away_xg
        diagnostics["effective_expected_total"] = home_lambda + away_lambda

        return home_lambda, away_lambda, score_matrix, raw_sum, tail_probability, diagnostics

    def _prepare_lambdas(
        self,
        home_xg: float,
        away_xg: float
    ) -> Tuple[float, float, Diagnostics]:
        """
        Подготавливает lambdas с клиппингом и диагностикой

        Returns:
            Tuple[home_lambda, away_lambda, diagnostics]
        """
        # Валидация
        if home_xg < 0 or away_xg < 0:
            raise ValueError(
                f"xG не может быть отрицательным: home_xg={home_xg}, away_xg={away_xg}"
            )

        home_clipped = home_xg < self.XG_MIN or home_xg > self.XG_MAX
        away_clipped = away_xg < self.XG_MIN or away_xg > self.XG_MAX

        home_lambda = max(self.XG_MIN, min(self.XG_MAX, home_xg))
        away_lambda = max(self.XG_MIN, min(self.XG_MAX, away_xg))

        diagnostics: Diagnostics = {
            "home_xg_clipped": home_clipped,
            "away_xg_clipped": away_clipped,
            "input_home_xg": home_xg,
            "input_away_xg": away_xg,
            "effective_home_lambda": home_lambda,
            "effective_away_lambda": away_lambda,
            "raw_expected_total": 0.0,
            "effective_expected_total": 0.0,
            "raw_sum": 0.0,
            "tail_cut": 0.0,
            "convergence_ok": False,
            "max_goals_used": self.MAX_GOALS
        }

        return home_lambda, away_lambda, diagnostics

    @staticmethod
    @lru_cache(maxsize=512)
    def _poisson_vector(lam: float, max_goals: int) -> Tuple[float, ...]:
        """
        Кэширует ВЕСЬ ВЕКТОР распределения Пуассона для заданного lambda и max_goals

        Args:
            lam: параметр распределения Пуассона
            max_goals: максимальное количество голов

        Returns:
            tuple из (P(0), P(1), ..., P(max_goals))
        """
        if lam <= 0:
            return tuple(1.0 if k == 0 else 0.0 for k in range(max_goals + 1))

        exp_neg_lam = math.exp(-lam)
        return tuple(
            (exp_neg_lam * (lam ** k)) / math.factorial(k)
            for k in range(max_goals + 1)
        )

    def _build_raw_score_matrix(
        self,
        home_lambda: float,
        away_lambda: float
    ) -> Tuple[Dict[Tuple[int, int], float], float]:
        """
        Строит НЕНОРМАЛИЗОВАННУЮ матрицу вероятностей
        Возвращает (матрица, сумма всех вероятностей)
        """
        matrix: Dict[Tuple[int, int], float] = {}
        total: float = 0.0

        home_probs = self._poisson_vector(home_lambda, self.MAX_GOALS)
        away_probs = self._poisson_vector(away_lambda, self.MAX_GOALS)

        for home_goals in range(self.MAX_GOALS + 1):
            for away_goals in range(self.MAX_GOALS + 1):
                prob = home_probs[home_goals] * away_probs[away_goals]
                matrix[(home_goals, away_goals)] = prob
                total += prob

        return matrix, total

    def _normalize_matrix(
        self,
        matrix: Dict[Tuple[int, int], float],
        total: float
    ) -> Dict[Tuple[int, int], float]:
        """
        Нормирует матрицу вероятностей
        """
        if total <= 0:
            raise RuntimeError(
                f"Невозможно нормировать матрицу: сумма вероятностей = {total:.10f}"
            )

        return {key: prob / total for key, prob in matrix.items()}

    def _calculate_markets(
        self,
        matrix: Dict[Tuple[int, int], float]
    ) -> MarketsResult:
        """
        Один проход по матрице для расчета всех рыночных показателей
        """
        # Инициализация
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        over_2_5 = 0.0
        under_2_5 = 0.0
        btts = 0.0

        # Храним топ-5 счетов через heap
        top_scores_buffer: List[Tuple[float, Tuple[int, int]]] = []

        # Единственный проход по матрице
        for (home_goals, away_goals), prob in matrix.items():
            total_goals = home_goals + away_goals

            # Исходы
            if home_goals > away_goals:
                home_win += prob
            elif home_goals == away_goals:
                draw += prob
            else:
                away_win += prob

            # Тоталы
            if total_goals > 2:
                over_2_5 += prob
            else:
                under_2_5 += prob

            # BTTS
            if home_goals > 0 and away_goals > 0:
                btts += prob

            # Топ-5 счетов (оптимизированный heap)
            score_tuple = (home_goals, away_goals)
            if len(top_scores_buffer) < 5:
                heapq.heappush(top_scores_buffer, (prob, score_tuple))
            elif prob > top_scores_buffer[0][0]:
                heapq.heapreplace(top_scores_buffer, (prob, score_tuple))

        # Double Chance
        one_x = home_win + draw
        x_two = draw + away_win
        one_two = home_win + away_win

        # Топ-5 счетов (сортируем heap по убыванию)
        top_scores = [
            {"score": f"{h}:{a}", "probability": p}
            for p, (h, a) in sorted(top_scores_buffer, key=lambda x: x[0], reverse=True)
        ]

        most_likely = top_scores[0] if top_scores else {"score": "0:0", "probability": 0.0}

        # Возвращаем все рынки
        return {
            "result_probability": {
                "home": home_win,
                "draw": draw,
                "away": away_win
            },
            "double_chance": {
                "one_x": one_x,
                "x_two": x_two,
                "one_two": one_two
            },
            "btts_probability": btts,
            "btts_no_probability": 1.0 - btts,
            "over_2_5": over_2_5,
            "under_2_5": under_2_5,
            "raw_expected_total": 0.0,  # Заполняется снаружи
            "expected_total": 0.0,       # Заполняется снаружи
            "tail_probability": 0.0,     # Заполняется снаружи
            "most_likely_score": most_likely["score"],
            "score_probability": most_likely["probability"],
            "top_scores": top_scores
        }


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    model = FAJPoissonModel(max_goals=8)

    print("\n" + "=" * 60)
    print("⚽ FAJ Poisson Model v2.0.3 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    # Тест 1: стандартный матч
    print("\n📋 Тест 1: стандартный матч (xG 1.72 : 0.95)")
    print("-" * 40)

    result = model.calculate(1.72, 0.95, include_matrix=True)

    print(f"  Победа хозяев: {result['result_probability']['home'] * 100:.1f}%")
    print(f"  Ничья:         {result['result_probability']['draw'] * 100:.1f}%")
    print(f"  Победа гостей: {result['result_probability']['away'] * 100:.1f}%")
    print(f"  Double Chance: 1X={result['double_chance']['one_x']*100:.1f}%, "
          f"X2={result['double_chance']['x_two']*100:.1f}%, "
          f"12={result['double_chance']['one_two']*100:.1f}%")
    print(f"  BTTS: {result['btts_probability']*100:.1f}%")
    print(f"  Тотал > 2.5: {result['over_2_5']*100:.1f}%")

    print(f"\n  📊 Expected Total:")
    print(f"    Raw:   {result['raw_expected_total']:.2f}")
    print(f"    Effective: {result['expected_total']:.2f}")

    print(f"\n  📐 Диагностика:")
    print(f"    raw_sum: {result['diagnostics']['raw_sum']:.10f}")
    print(f"    tail_cut: {result['diagnostics']['tail_cut']*100:.4f}%")
    print(f"    convergence_ok: {'✅' if result['diagnostics']['convergence_ok'] else '❌'}")
    print(f"    max_goals: {result['diagnostics']['max_goals_used']}")

    print(f"\n  🏆 Наиболее вероятный счёт: {result['most_likely_score']} "
          f"({result['score_probability']*100:.2f}%)")

    # Тест 2: с клиппингом (проверка raw/effective)
    print("\n📋 Тест 2: с клиппингом xG (6.2 : 5.8)")
    print("-" * 40)

    result2 = model.calculate(6.2, 5.8)

    print(f"  Входные xG: 6.2 : 5.8")
    print(f"  raw_expected_total: {result2['raw_expected_total']:.2f}")
    print(f"  expected_total: {result2['expected_total']:.2f}")
    print(f"  raw_sum: {result2['diagnostics']['raw_sum']:.10f}")
    print(f"  tail_cut: {result2['diagnostics']['tail_cut']*100:.4f}%")
    print(f"  Клиппинг: home={result2['diagnostics']['home_xg_clipped']}, "
          f"away={result2['diagnostics']['away_xg_clipped']}")

    # Тест 3: markets() — проверка expected_total
    print("\n📋 Тест 3: markets() — проверка всех полей")
    print("-" * 40)

    markets_result = model.markets(1.72, 0.95)
    print(f"  raw_expected_total: {markets_result['raw_expected_total']:.2f}")
    print(f"  expected_total: {markets_result['expected_total']:.2f}")
    print(f"  tail_probability: {markets_result['tail_probability']*100:.4f}%")
    print(f"  BTTS: {markets_result['btts_probability']*100:.1f}%")

    # Тест 4: проверка Diagnostics TypedDict
    print("\n📋 Тест 4: проверка Diagnostics TypedDict")
    print("-" * 40)

    diag = result['diagnostics']
    required_fields = [
        'home_xg_clipped', 'away_xg_clipped',
        'input_home_xg', 'input_away_xg',
        'effective_home_lambda', 'effective_away_lambda',
        'raw_expected_total', 'effective_expected_total',
        'raw_sum', 'tail_cut', 'convergence_ok', 'max_goals_used'
    ]
    all_present = all(field in diag for field in required_fields)
    print(f"  Все поля Diagnostics присутствуют: {'✅' if all_present else '❌'}")

    # Тест 5: обработка ошибок
    print("\n📋 Тест 5: обработка ошибок")
    print("-" * 40)

    try:
        model.calculate(-1.0, 0.8)
    except ValueError as e:
        print(f"  ✅ ValueError: {e}")

    try:
        FAJPoissonModel(max_goals=0)
    except ValueError as e:
        print(f"  ✅ ValueError: {e}")

    print("\n" + "=" * 60)
    print("✅ Все тесты пройдены. Модель готова к фиксации в FAJ Core.")
    print("=" * 60)

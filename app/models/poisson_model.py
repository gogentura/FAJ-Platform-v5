#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Poisson Model v7.3

РОЛЬ:
    Расчёт вероятностей счетов на основе xG.
    Является частью математического ядра FAJ.

ВХОД:
    home_xg: float — ожидаемые голы хозяев
    away_xg: float — ожидаемые голы гостей
    include_matrix: bool — вернуть полную матрицу

ВЫХОД:
    {
        "result_probability": {"home": float, "draw": float, "away": float},
        "double_chance": {
            "home_or_draw": float,
            "draw_or_away": float,
            "home_or_away": float
        },
        "btts_probability": float,
        "btts_no_probability": float,
        "over_2_5": float,
        "under_2_5": float,
        "most_likely_score": str,
        "score_probability": float,
        "top_scores": [{"score": str, "probability": float}],
        "expected_total": float,
        "tail_probability": float,
        "model_stability": float,
        "score_entropy": float,
        "matrix_sum": float
    }

ИЗМЕНЕНИЯ v7.3:
    - double_chance: "1X" → "home_or_draw", "X2" → "draw_or_away", "12" → "home_or_away"
    - Добавлена model_stability = 1 - tail_probability
    - Добавлена score_entropy для оценки неопределённости
=====================================================
"""

import math
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FAJPoissonModel:
    """
    Poisson Model v7.3
    Расчёт вероятностей счетов на основе xG
    """

    VERSION = "7.3"

    # ============================================================
    # MODEL CONSTANTS
    # ============================================================

    MAX_GOALS = 8
    XG_MIN = 0.1
    XG_MAX = 4.0

    def __init__(self, max_goals: int = 8):
        self.MAX_GOALS = max_goals
        self._poisson_cache = {}
        logger.info(f"Poisson Model v{self.VERSION} initialized (max_goals={max_goals})")

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(
        self,
        home_xg: float,
        away_xg: float,
        include_matrix: bool = False
    ) -> Dict:
        """
        Расчёт вероятностей на основе xG
        """
        # 1. Ограничиваем xG
        home_lambda = max(self.XG_MIN, min(self.XG_MAX, home_xg))
        away_lambda = max(self.XG_MIN, min(self.XG_MAX, away_xg))

        # 2. Строим НЕНОРМАЛИЗОВАННУЮ матрицу
        raw_matrix, raw_sum = self._build_raw_score_matrix(home_lambda, away_lambda)

        # 3. Хвостовая вероятность ДО нормализации
        tail_probability = max(0.0, min(1.0, 1.0 - raw_sum))

        # 4. Нормализация
        score_matrix = self._normalize_matrix(raw_matrix, raw_sum)

        # 5. Расчёт всех показателей за один проход
        result = self._calculate_markets(score_matrix)

        # 6. Добавляем мета-информацию
        result["expected_total"] = home_lambda + away_lambda
        result["tail_probability"] = tail_probability
        result["model_stability"] = 1.0 - tail_probability
        result["matrix_sum"] = sum(score_matrix.values())

        # 7. Энтропия распределения счетов
        result["score_entropy"] = self._calculate_entropy(score_matrix)

        if include_matrix:
            result["score_matrix"] = score_matrix

        return result

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _poisson(self, lam: float, k: int) -> float:
        if lam <= 0:
            return 1.0 if k == 0 else 0.0

        cache_key = f"{lam:.4f}_{k}"
        if cache_key in self._poisson_cache:
            return self._poisson_cache[cache_key]

        result = (math.exp(-lam) * (lam ** k)) / math.factorial(k)
        self._poisson_cache[cache_key] = result
        return result

    def _build_raw_score_matrix(
        self,
        home_lambda: float,
        away_lambda: float
    ) -> Tuple[Dict, float]:
        matrix = {}
        total = 0.0

        home_probs = [self._poisson(home_lambda, k) for k in range(self.MAX_GOALS + 1)]
        away_probs = [self._poisson(away_lambda, k) for k in range(self.MAX_GOALS + 1)]

        for h in range(self.MAX_GOALS + 1):
            for a in range(self.MAX_GOALS + 1):
                prob = home_probs[h] * away_probs[a]
                matrix[(h, a)] = prob
                total += prob

        return matrix, total

    def _normalize_matrix(self, matrix: Dict, total: float) -> Dict:
        if total <= 0:
            raise RuntimeError(
                f"Невозможно нормировать матрицу: сумма = {total:.10f}"
            )
        return {key: prob / total for key, prob in matrix.items()}

    def _calculate_markets(self, matrix: Dict) -> Dict:
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        btts = 0.0
        over_2_5 = 0.0
        under_2_5 = 0.0

        most_likely_score = "0:0"
        max_prob = 0.0
        top_scores = []

        for (h, a), prob in matrix.items():
            total_goals = h + a

            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob

            if h > 0 and a > 0:
                btts += prob

            if total_goals > 2:
                over_2_5 += prob
            else:
                under_2_5 += prob

            if prob > max_prob:
                max_prob = prob
                most_likely_score = f"{h}:{a}"

            top_scores.append({"score": f"{h}:{a}", "probability": prob})

        top_scores = sorted(top_scores, key=lambda x: x["probability"], reverse=True)[:5]

        return {
            "result_probability": {
                "home": round(home_win, 4),
                "draw": round(draw, 4),
                "away": round(away_win, 4)
            },
            "double_chance": {
                "home_or_draw": round(home_win + draw, 4),
                "draw_or_away": round(draw + away_win, 4),
                "home_or_away": round(home_win + away_win, 4)
            },
            "btts_probability": round(btts, 4),
            "btts_no_probability": round(1.0 - btts, 4),
            "over_2_5": round(over_2_5, 4),
            "under_2_5": round(under_2_5, 4),
            "most_likely_score": most_likely_score,
            "score_probability": round(max_prob, 4),
            "top_scores": top_scores
        }

    def _calculate_entropy(self, matrix: Dict) -> float:
        """
        Расчёт энтропии распределения счетов
        Чем выше энтропия, тем выше неопределённость
        """
        entropy = 0.0
        for prob in matrix.values():
            if prob > 0:
                entropy -= prob * math.log2(prob)
        return round(entropy, 3)

    # ============================================================
    # DIAGNOSTICS
    # ============================================================

    def status(self) -> Dict:
        return {
            "model": "Poisson Model",
            "version": self.VERSION,
            "max_goals": self.MAX_GOALS,
            "xg_range": [self.XG_MIN, self.XG_MAX],
            "status": "READY"
        }

    def test(self) -> Dict:
        return self.calculate(1.72, 0.95, include_matrix=True)


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ Poisson Model v7.3 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    model = FAJPoissonModel()

    print("\n📊 Status:")
    print(model.status())

    print("\n📋 Тест: xG 1.72 : 0.95")
    print("-" * 40)

    result = model.test()

    probs = result.get("result_probability", {})
    print(f"\n  📊 Home: {probs.get('home', 0)*100:.1f}%")
    print(f"  📊 Draw: {probs.get('draw', 0)*100:.1f}%")
    print(f"  📊 Away: {probs.get('away', 0)*100:.1f}%")

    dc = result.get("double_chance", {})
    print(f"\n  📊 Double Chance:")
    print(f"    Home or Draw: {dc.get('home_or_draw', 0)*100:.1f}%")
    print(f"    Draw or Away: {dc.get('draw_or_away', 0)*100:.1f}%")
    print(f"    Home or Away: {dc.get('home_or_away', 0)*100:.1f}%")

    print(f"\n  📊 BTTS: {result.get('btts_probability', 0)*100:.1f}%")
    print(f"  📊 Over 2.5: {result.get('over_2_5', 0)*100:.1f}%")
    print(f"  📊 Most likely: {result.get('most_likely_score')} ({result.get('score_probability', 0)*100:.2f}%)")
    print(f"  📊 Expected total: {result.get('expected_total', 0):.2f}")
    print(f"  📊 Tail: {result.get('tail_probability', 0)*100:.4f}%")
    print(f"  📊 Model stability: {result.get('model_stability', 0)*100:.1f}%")
    print(f"  📊 Score entropy: {result.get('score_entropy', 0):.3f}")

    print("\n" + "=" * 60)
    print("✅ Poisson Model v7.3 готов к работе.")
    print("=" * 60)

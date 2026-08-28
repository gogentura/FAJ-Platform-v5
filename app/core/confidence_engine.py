#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Confidence Engine v1.4

РОЛЬ:
    Оценка уверенности в прогнозе.

ФАКТОРЫ (v1.4):
    35% Probability spread (разброс вероятностей)
    20% Passport quality (качество данных / xG)
    15% Monte Carlo stability (стабильность симуляции)
    15% Rating difference (разница xG)
    10% Season phase (фаза сезона)
    5%  Context (травмы, форма, мотивация)

ИЗМЕНЕНИЯ v1.4:
    - Адаптирован под структуру PredictionPipeline
    - quality_score использует xG вместо passport
    - rating_score использует разницу xG
    - mc_stability берёт Monte Carlo из extended
=====================================================
"""

import math
import logging
from typing import Dict, Any, Optional

from app.core.match_context import MatchContext

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """
    Расчёт уверенности прогноза
    """

    VERSION = "1.4"

    # Веса факторов (живут в коде)
    WEIGHTS = {
        "probability_spread": 0.35,
        "passport_quality": 0.20,
        "monte_carlo_stability": 0.15,
        "rating_difference": 0.15,
        "season_phase": 0.10,
        "context": 0.05
    }

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"Confidence Engine v{self.VERSION} initialized")

    def calculate(
        self,
        raw_prediction: Dict[str, Any],
        calibrated: Dict[str, Any],
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        """
        Расчёт уверенности

        Args:
            raw_prediction: сырой прогноз от Pipeline
            calibrated: скорректированные вероятности
            context: контекст матча (MatchContext)

        Returns:
            Dict с уверенностью
        """
        # 1. Probability spread (35%)
        spread_score = self._calculate_spread_score(calibrated)

        # 2. Passport quality (20%) — адаптировано
        quality_score = self._calculate_quality_score(raw_prediction)

        # 3. Monte Carlo stability (15%) — адаптировано
        mc_stability = self._calculate_mc_stability(raw_prediction, calibrated)

        # 4. Rating difference (15%) — адаптировано
        rating_score = self._calculate_rating_score(raw_prediction)

        # 5. Season phase (10%)
        season_score = self._calculate_season_score(raw_prediction)

        # 6. Context (5%)
        context_score = self._calculate_context_score(context)

        # Взвешенная сумма
        overall = (
            spread_score * self.WEIGHTS["probability_spread"] +
            quality_score * self.WEIGHTS["passport_quality"] +
            mc_stability * self.WEIGHTS["monte_carlo_stability"] +
            rating_score * self.WEIGHTS["rating_difference"] +
            season_score * self.WEIGHTS["season_phase"] +
            context_score * self.WEIGHTS["context"]
        )

        overall = round(max(0.0, min(1.0, overall)), 3)

        # Уровень
        if overall >= 0.75:
            level = "HIGH"
        elif overall >= 0.50:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "overall": overall,
            "level": level,
            "components": {
                "spread_score": round(spread_score, 3),
                "quality_score": round(quality_score, 3),
                "mc_stability": round(mc_stability, 3),
                "rating_score": round(rating_score, 3),
                "season_score": round(season_score, 3),
                "context_score": round(context_score, 3)
            }
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _calculate_spread_score(
        self,
        calibrated: Dict[str, Any]
    ) -> float:
        """Оценка на основе разброса вероятностей"""
        home = calibrated.get("home", 0.33)
        draw = calibrated.get("draw", 0.33)
        away = calibrated.get("away", 0.33)

        max_prob = max(home, draw, away)
        # 0.33 → 0.5, 0.5 → 0.8, 0.8 → 1.0
        score = 0.5 + (max_prob - 0.33) * 1.5
        return max(0.0, min(1.0, score))

    def _calculate_quality_score(
        self,
        raw: Dict[str, Any]
    ) -> float:
        """
        Оценка качества данных на основе xG
        
        Адаптировано для PredictionPipeline:
            - использует xG как прокси качества
            - если xG в разумном диапазоне → высокое качество
        """
        xg = raw.get("xg", {})
        home_xg = xg.get("home", 0.0)
        away_xg = xg.get("away", 0.0)
        
        # Проверяем, что xG в разумном диапазоне (0.1–4.0)
        if 0.1 <= home_xg <= 4.0 and 0.1 <= away_xg <= 4.0:
            return 0.8
        elif home_xg > 0 and away_xg > 0:
            return 0.6
        else:
            return 0.4

    def _calculate_mc_stability(
        self,
        raw: Dict[str, Any],
        calibrated: Dict[str, Any]
    ) -> float:
        """
        Оценка на основе стабильности Monte Carlo
        
        Адаптировано для PredictionPipeline:
            - берёт Monte Carlo из extended
            - если нет MC — использует top_scores как прокси
        """
        extended = raw.get("extended", {})
        
        # Monte Carlo может быть в extended
        mc = extended.get("monte_carlo", {})
        
        if not mc or not isinstance(mc, dict):
            # Если нет Monte Carlo — пробуем найти top_scores как прокси
            top_scores = extended.get("top_scores", [])
            if top_scores and len(top_scores) >= 3:
                # Если есть top_scores, стабильность средняя
                return 0.6
            return 0.3

        # Poisson вероятности (из calibrated)
        poisson_home = calibrated.get("home", 0.33)
        poisson_draw = calibrated.get("draw", 0.33)
        poisson_away = calibrated.get("away", 0.33)

        # Monte Carlo вероятности
        mc_home = mc.get("home_win", 0.33)
        mc_draw = mc.get("draw", 0.33)
        mc_away = mc.get("away_win", 0.33)

        # Средняя разница между Poisson и MC
        diff_home = abs(poisson_home - mc_home)
        diff_draw = abs(poisson_draw - mc_draw)
        diff_away = abs(poisson_away - mc_away)
        avg_diff = (diff_home + diff_draw + diff_away) / 3

        # Чем меньше разница, тем выше стабильность
        # 0 → 1.0, 0.1 → 0.8, 0.2 → 0.5, 0.3 → 0.2
        stability = 1.0 - min(avg_diff * 3, 1.0)
        return max(0.0, min(1.0, stability))

    def _calculate_rating_score(
        self,
        raw: Dict[str, Any]
    ) -> float:
        """
        Оценка на основе разницы xG (прокси силы команд)
        
        Адаптировано для PredictionPipeline:
            - использует разницу xG вместо рейтингов
        """
        xg = raw.get("xg", {})
        home_xg = xg.get("home", 0.0)
        away_xg = xg.get("away", 0.0)
        
        diff = abs(home_xg - away_xg)
        # diff 0 → 0.5, diff 1.0 → 0.7, diff 2.0 → 0.9, diff 3.0 → 1.0
        score = 0.5 + (diff / 3.0) * 0.5
        return max(0.5, min(1.0, score))

    def _calculate_season_score(
        self,
        raw: Dict[str, Any]
    ) -> float:
        """
        Оценка на основе фазы сезона
        
        Пока заглушка — всегда mid.
        В будущем можно добавить из config.
        """
        # Пока всегда mid
        return 0.85

    def _calculate_context_score(
        self,
        context: Optional[MatchContext]
    ) -> float:
        """Оценка на основе контекста матча"""
        if not context:
            # Нет данных = штраф
            return 0.4

        # Преобразуем в словарь если нужно
        if hasattr(context, "to_dict"):
            ctx = context.to_dict()
        else:
            ctx = context

        squad_stability = ctx.get("squad_stability", 0.7)
        injuries = ctx.get("injuries", 0.0)
        fatigue = ctx.get("fatigue", 0.0)
        coach_factor = ctx.get("coach_factor", 0.7)
        motivation = ctx.get("motivation", 0.7)

        # Чем выше injuries/fatigue, тем ниже уверенность
        penalty = (injuries * 0.5 + fatigue * 0.3)

        score = (
            squad_stability * 0.3 +
            coach_factor * 0.25 +
            motivation * 0.25 +
            (1 - min(penalty, 1.0)) * 0.2
        )

        return max(0.0, min(1.0, score))


if __name__ == "__main__":
    engine = ConfidenceEngine()
    print(f"Confidence Engine v{engine.VERSION}")
    print(f"Weights: {engine.WEIGHTS}")

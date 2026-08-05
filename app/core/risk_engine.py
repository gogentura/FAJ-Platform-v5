#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Risk Engine v1.3

РОЛЬ:
    Оценка риска прогноза для принятия решения.
    Риск = "Можно ли доверять ставочному решению?"

ОТЛИЧИЕ ОТ CONFIDENCE:
    Confidence = "Модель уверена?"
    Risk = "Насколько опасно доверять этому прогнозу?"

ФАКТОРЫ РИСКА (v1.3):
    25% Data Quality (качество данных)
    20% Squad uncertainty (неопределённость состава)
    20% Match volatility (нестабильность матча)
    15% Upset probability (вероятность сенсации)
    10% Confidence (уверенность модели)
    10% Context (травмы, мотивация)

ИЗМЕНЕНИЯ v1.3:
    - Upset risk: использует второй по вероятности исход
    - Добавлен коэффициент ничейной неопределённости
    - Исправлена логика расчёта сенсации
=====================================================
"""

import logging
from typing import Dict, Any, Optional

from app.core.match_context import MatchContext

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Оценка риска прогноза
    """

    VERSION = "1.3"

    # Пороги риска
    THRESHOLDS = {
        "HIGH": 60,
        "MEDIUM": 35,
        "LOW": 0
    }

    # Веса факторов
    WEIGHTS = {
        "data_quality": 0.25,
        "squad_uncertainty": 0.20,
        "match_volatility": 0.20,
        "upset_probability": 0.15,
        "confidence": 0.10,
        "context": 0.10
    }

    # Порог ничейной неопределённости
    DRAW_THRESHOLD = 0.30
    DRAW_PENALTY = 15.0

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"Risk Engine v{self.VERSION} initialized")

    def calculate(
        self,
        raw_prediction: Dict[str, Any],
        calibrated: Dict[str, Any],
        confidence: Dict[str, Any],
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        """
        Расчёт риска

        Args:
            raw_prediction: сырой прогноз
            calibrated: скорректированные вероятности
            confidence: результат Confidence Engine
            context: контекст матча (MatchContext)

        Returns:
            Dict с уровнем риска
        """
        # 1. Data Quality (25%)
        data_quality_risk = self._calculate_data_quality_risk(raw_prediction)

        # 2. Squad Uncertainty (20%)
        squad_risk = self._calculate_squad_risk(context)

        # 3. Match Volatility (20%)
        volatility_risk = self._calculate_volatility_risk(calibrated)

        # 4. Upset Probability (15%)
        upset_risk = self._calculate_upset_risk(calibrated, context)

        # 5. Confidence (10%)
        confidence_risk = self._calculate_confidence_risk(confidence)

        # 6. Context (10%)
        context_risk = self._calculate_context_risk(context)

        # Итоговый риск
        risk_score = (
            data_quality_risk * self.WEIGHTS["data_quality"] +
            squad_risk * self.WEIGHTS["squad_uncertainty"] +
            volatility_risk * self.WEIGHTS["match_volatility"] +
            upset_risk * self.WEIGHTS["upset_probability"] +
            confidence_risk * self.WEIGHTS["confidence"] +
            context_risk * self.WEIGHTS["context"]
        )

        # Дополнительный штраф за высокую вероятность ничьей
        draw_prob = calibrated.get("draw", 0.0)
        if draw_prob >= self.DRAW_THRESHOLD:
            risk_score += self.DRAW_PENALTY * (draw_prob - self.DRAW_THRESHOLD) / 0.2

        risk_score = round(max(0.0, min(100.0, risk_score)), 1)

        # Уровень
        if risk_score >= self.THRESHOLDS["HIGH"]:
            level = "HIGH"
        elif risk_score >= self.THRESHOLDS["MEDIUM"]:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "score": risk_score,
            "level": level,
            "components": {
                "data_quality_risk": round(data_quality_risk, 1),
                "squad_risk": round(squad_risk, 1),
                "volatility_risk": round(volatility_risk, 1),
                "upset_risk": round(upset_risk, 1),
                "confidence_risk": round(confidence_risk, 1),
                "context_risk": round(context_risk, 1),
                "draw_penalty": round(max(0.0, self.DRAW_PENALTY * (calibrated.get("draw", 0) - self.DRAW_THRESHOLD) / 0.2), 1)
            }
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _calculate_data_quality_risk(
        self,
        raw: Dict[str, Any]
    ) -> float:
        """Риск на основе качества данных"""
        home_q = raw.get("passport", {}).get("home_quality", 0)
        away_q = raw.get("passport", {}).get("away_quality", 0)
        avg = (home_q + away_q) / 2

        # 0 → 100, 0.5 → 50, 1 → 0
        risk = (1 - avg) * 100
        return max(0.0, min(100.0, risk))

    def _calculate_squad_risk(
        self,
        context: Optional[MatchContext]
    ) -> float:
        """Риск на основе неопределённости состава"""
        if not context:
            return 50.0

        if hasattr(context, "to_dict"):
            ctx = context.to_dict()
        else:
            ctx = context

        injuries = ctx.get("injuries", 0.0)
        fatigue = ctx.get("fatigue", 0.0)
        squad_stability = ctx.get("squad_stability", 0.7)

        # Чем больше травм и усталости, тем выше риск
        risk = (injuries * 40 + fatigue * 20 + (1 - squad_stability) * 40)
        return max(0.0, min(100.0, risk))

    def _calculate_volatility_risk(
        self,
        calibrated: Dict[str, Any]
    ) -> float:
        """Риск на основе нестабильности матча"""
        home = calibrated.get("home", 0.33)
        draw = calibrated.get("draw", 0.33)
        away = calibrated.get("away", 0.33)

        max_prob = max(home, draw, away)

        # Чем ближе к 0.33, тем выше риск
        # 0.33 → 100, 0.5 → 50, 0.8 → 10
        risk = 100 - (max_prob - 0.33) * 250
        return max(0.0, min(100.0, risk))

    def _calculate_upset_risk(
        self,
        calibrated: Dict[str, Any],
        context: Optional[MatchContext]
    ) -> float:
        """
        Риск на основе вероятности сенсации
        Использует второй по вероятности исход
        """
        home = calibrated.get("home", 0.33)
        draw = calibrated.get("draw", 0.33)
        away = calibrated.get("away", 0.33)

        # Сортируем вероятности по убыванию
        probs = sorted([home, draw, away], reverse=True)

        # Второй по вероятности исход = потенциал сенсации
        upset_base = probs[1]  # второй по величине

        # Базовый риск
        risk = upset_base * 100

        # Корректировка на контекст
        if context:
            if hasattr(context, "to_dict"):
                ctx = context.to_dict()
            else:
                ctx = context

            motivation = ctx.get("motivation", 0.5)
            cup_match = ctx.get("cup_match", False)

            if cup_match:
                risk *= 1.3
            if motivation > 0.7:
                risk *= 1.2

        return max(0.0, min(100.0, risk))

    def _calculate_confidence_risk(
        self,
        confidence: Dict[str, Any]
    ) -> float:
        """Риск на основе уверенности модели"""
        overall = confidence.get("overall", 0.5)

        # 0 → 100, 0.5 → 50, 1 → 0
        risk = (1 - overall) * 100
        return max(0.0, min(100.0, risk))

    def _calculate_context_risk(
        self,
        context: Optional[MatchContext]
    ) -> float:
        """Риск на основе контекста матча"""
        if not context:
            return 50.0

        if hasattr(context, "to_dict"):
            ctx = context.to_dict()
        else:
            ctx = context

        coach_factor = ctx.get("coach_factor", 0.7)
        motivation = ctx.get("motivation", 0.7)

        # Низкий coach_factor или мотивация = высокий риск
        risk = (1 - coach_factor) * 50 + (1 - motivation) * 50
        return max(0.0, min(100.0, risk))


if __name__ == "__main__":
    engine = RiskEngine()
    print(f"Risk Engine v{engine.VERSION}")
    print(f"Thresholds: {engine.THRESHOLDS}")
    print(f"Weights: {engine.WEIGHTS}")
    print(f"Draw threshold: {engine.DRAW_THRESHOLD}")
    print(f"Draw penalty: {engine.DRAW_PENALTY}")

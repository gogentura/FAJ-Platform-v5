#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ Core Engine v7.3

РОЛЬ:
    Тонкий фасад над Prediction Pipeline.
    Единая точка входа для всей платформы.

ИЗМЕНЕНИЯ v7.3:
    - Добавлен параметр match_type
    - Обновлён вызов pipeline.run()
=====================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import config
from app.core.prediction_pipeline import PredictionPipeline
from app.core.match_context import MatchContext

logger = logging.getLogger(__name__)


class FAJCore:
    VERSION = config.CORE_VERSION
    PLATFORM_VERSION = config.PLATFORM_VERSION

    def __init__(self, pipeline: Optional[PredictionPipeline] = None):
        self.version = self.VERSION
        self.platform_version = self.PLATFORM_VERSION
        self.pipeline = pipeline or PredictionPipeline()
        logger.info(f"FAJ Core v{self.VERSION} initialized")

    def predict(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        match_type: str = "league",
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        """Алиас для predict_match"""
        return self.predict_match(home_team, away_team, league, match_type, context)

    def predict_match(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        match_type: str = "league",
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        """
        Полный прогноз матча

        Args:
            home_team: название команды хозяев
            away_team: название команды гостей
            league: лига (RPL, EPL, La Liga, UCL)
            match_type: тип матча (league, cup, ucl_group, ucl_playoff, friendly)
            context: контекст матча (MatchContext)

        Returns:
            Dict с полным прогнозом
        """
        # Проверка pipeline
        if self.pipeline is None:
            logger.error("PredictionPipeline not initialized")
            return {
                "status": "error",
                "message": "PredictionPipeline not initialized",
                "timestamp": datetime.now().isoformat()
            }

        try:
            logger.info(
                "Prediction requested: %s vs %s (%s, %s)",
                home_team,
                away_team,
                league,
                match_type
            )
            result = self.pipeline.run(
                home_team,
                away_team,
                league,
                match_type,
                context
            )

            if result.get("status") == "error":
                logger.warning(
                    "Prediction failed: %s vs %s (%s, %s) - %s",
                    home_team,
                    away_team,
                    league,
                    match_type,
                    result.get("message", "Unknown error")
                )
            else:
                logger.info(
                    "Prediction completed: %s vs %s (%s, %s) - ID: %s",
                    home_team,
                    away_team,
                    league,
                    match_type,
                    result.get("prediction_id", "unknown")
                )

            return result

        except Exception as e:
            logger.exception(
                "Prediction exception: %s vs %s (%s, %s)",
                home_team,
                away_team,
                league,
                match_type
            )
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def status(self) -> Dict[str, Any]:
        """Статус Core и Pipeline"""
        pipeline_status = self.pipeline.status() if hasattr(self.pipeline, "status") else {}

        return {
            "core": "FAJ Core Engine",
            "core_version": self.VERSION,
            "platform_version": self.PLATFORM_VERSION,
            "pipeline_version": pipeline_status.get("version", "unknown"),
            "status": pipeline_status.get("status", "UNKNOWN"),
            "models": pipeline_status.get("models", {}),
            "modules": pipeline_status.get("modules", {}),
            "tournaments": pipeline_status.get("tournaments", []),
            "match_types": pipeline_status.get("match_types", [])
        }

    def test(
        self,
        home_team: str = "Зенит",
        away_team: str = "Спартак",
        league: str = "RPL",
        match_type: str = "league"
    ) -> Dict[str, Any]:
        """Тестовый прогноз с возможностью указать команды"""
        return self.predict_match(home_team, away_team, league, match_type)


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ FAJ Core Engine v7.3 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    core = FAJCore()

    print("\n📊 Status:")
    print(core.status())

    print("\n📋 Тест: Зенит vs Спартак (РПЛ, league)")
    print("-" * 40)

    result = core.test()

    if result.get("status") == "error":
        print(f"\n  ❌ {result.get('message')}")
    else:
        print(f"\n  ✅ Прогноз получен")
        print(f"  📊 Prediction ID: {result.get('prediction_id')}")

        summary = result.get("summary", {})
        print(f"  📊 Match: {summary.get('home', '?')} vs {summary.get('away', '?')}")
        print(f"  📊 Score: {summary.get('score', 'N/A')}")
        print(f"  📊 Home: {summary.get('home_win', 0)*100:.1f}%")
        print(f"  📊 Draw: {summary.get('draw', 0)*100:.1f}%")
        print(f"  📊 Away: {summary.get('away_win', 0)*100:.1f}%")

        confidence = result.get("confidence", {})
        print(f"  📊 Confidence: {confidence.get('level', 'N/A')} ({confidence.get('overall', 0)*100:.1f}%)")

        risk = result.get("risk", {})
        print(f"  📊 Risk: {risk.get('level', 'N/A')} ({risk.get('score', 0)})")

        metadata = result.get("metadata", {})
        print(f"  ⏱️  Processing: {metadata.get('processing_time_ms', 'N/A')} ms")
        print(f"  📦 Core: v{core.VERSION}")
        print(f"  📦 Pipeline: {metadata.get('pipeline_version', 'N/A')}")
        print(f"  📋 Passport Status: {metadata.get('passport_status', {})}")

    print("\n" + "=" * 60)
    print("✅ FAJ Core v7.3 готов к работе.")
    print("=" * 60)

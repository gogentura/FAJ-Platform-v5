#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ Core Engine v7.4

РОЛЬ:
    Тонкий фасад.
    Единая точка входа для всей платформы.

ВСЯ ЛОГИКА В PREDICTION MANAGER
=====================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import config
from app.core.match_context import MatchContext
from app.core.prediction_manager import get_prediction_manager

logger = logging.getLogger(__name__)


class FAJCore:
    """
    FAJ Core Engine v7.4
    Тонкий фасад FAJ Platform
    """

    VERSION = config.CORE_VERSION
    PLATFORM_VERSION = config.PLATFORM_VERSION

    def __init__(self):
        self.version = self.VERSION
        self.platform_version = self.PLATFORM_VERSION

        # Prediction Manager (дирижёр)
        self.manager = get_prediction_manager()

        logger.info(f"FAJ Core v{self.VERSION} initialized")

    # ============================================================
    # MAIN API
    # ============================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        match_type: str = "league",
        context: Optional[MatchContext] = None,
        season_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Алиас для predict_match"""
        return self.predict_match(
            home_team, away_team, league, match_type, context, season_id
        )

    def predict_match(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        match_type: str = "league",
        context: Optional[MatchContext] = None,
        season_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Полный прогноз матча

        Args:
            home_team: название команды хозяев
            away_team: название команды гостей
            league: лига (RPL, EPL, La Liga, UCL)
            match_type: тип матча
            context: контекст матча (MatchContext)
            season_id: ID сезона (опционально)

        Returns:
            Dict с полным прогнозом
        """
        try:
            logger.info(
                "Prediction requested: %s vs %s (%s)",
                home_team, away_team, league
            )

            # ВСЯ ЛОГИКА В MANAGER
            result = self.manager.predict(
                home_team=home_team,
                away_team=away_team,
                league=league,
                match_type=match_type,
                context=context,
                season_id=season_id
            )

            if result.get("status") == "error":
                logger.warning(
                    "Prediction failed: %s vs %s - %s",
                    home_team, away_team,
                    result.get("message", "Unknown error")
                )
            else:
                logger.info(
                    "Prediction completed: %s vs %s - ID: %s",
                    home_team, away_team,
                    result.get("prediction_id", "unknown")
                )

            return result

        except Exception as e:
            logger.exception(
                "Prediction exception: %s vs %s",
                home_team, away_team
            )
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }

    # ============================================================
    # DIAGNOSTICS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """Статус Core и Manager"""
        manager_status = self.manager.status() if hasattr(self.manager, "status") else {}

        return {
            "core": "FAJ Core Engine",
            "core_version": self.VERSION,
            "platform_version": self.PLATFORM_VERSION,
            "manager": manager_status,
            "status": "READY"
        }

    def test(
        self,
        home_team: str = "Зенит",
        away_team: str = "Спартак",
        league: str = "RPL",
        match_type: str = "league"
    ) -> Dict[str, Any]:
        """Тестовый прогноз"""
        return self.predict_match(home_team, away_team, league, match_type)


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ FAJ Core Engine v7.4 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    core = FAJCore()

    print("\n📊 Status:")
    print(core.status())

    print("\n📋 Тест: Зенит vs Спартак")
    print("-" * 40)

    result = core.test()

    if result.get("status") == "error":
        print(f"\n  ❌ {result.get('message')}")
    else:
        print(f"\n  ✅ Прогноз получен")
        print(f"  📊 Match: {result.get('home_team', '?')} vs {result.get('away_team', '?')}")

        prediction = result.get("prediction", {})
        print(f"  📊 Score: {prediction.get('score', 'N/A')}")

        xg = prediction.get("xg", {})
        print(f"  📊 XG: {xg.get('home', 0):.2f} : {xg.get('away', 0):.2f}")

        probs = prediction.get("probability", {})
        print(f"  📊 Home: {probs.get('home', 0)*100:.1f}%")
        print(f"  📊 Draw: {probs.get('draw', 0)*100:.1f}%")
        print(f"  📊 Away: {probs.get('away', 0)*100:.1f}%")

        confidence = prediction.get("confidence", {})
        print(f"  📊 Confidence: {confidence.get('level', 'N/A')} ({confidence.get('overall', 0)*100:.1f}%)")

        risk = prediction.get("risk", {})
        print(f"  📊 Risk: {risk.get('level', 'N/A')} ({risk.get('score', 0)})")

        exec_info = prediction.get("execution_info", {})
        print(f"  ⏱️  Processing: {exec_info.get('processing_time_ms', 'N/A')} ms")
        print(f"  📦 Core: v{core.VERSION}")

    print("\n" + "=" * 60)
    print("✅ FAJ Core v7.4 готов к работе.")
    print("=" * 60)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Manager v1.6 (ДИРИЖЁР)

РОЛЬ:
    Организует процесс прогнозирования.
    НЕ СОДЕРЖИТ МАТЕМАТИКИ.
    НЕ РАБОТАЕТ НАПРЯМУЮ С БД (через Database).

ОТВЕТСТВЕННОСТЬ:
    1. Получить паспорта команд (через PassportManager)
    2. Получить FAJ Rating
    3. Передать данные в PredictionPipeline
    4. Сохранить результат (через Database)

НЕ ОТВЕЧАЕТ:
    - За расчёт xG, Poisson, Monte Carlo
    - За Confidence, Risk
    - За SQL
    - За работу с паспортами (только запрос)
=====================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.prediction_pipeline import PredictionPipeline, get_prediction_pipeline
from app.passports.passport_manager import PassportManager, get_passport_manager
from app.database import FAJDatabase

logger = logging.getLogger(__name__)


class PredictionManager:
    """
    Prediction Manager v1.6 (ДИРИЖЁР)
    """

    VERSION = "1.6"

    def __init__(
        self,
        pipeline: Optional[PredictionPipeline] = None,
        passport_manager: Optional[PassportManager] = None,
        db: Optional[FAJDatabase] = None
    ):
        self.version = self.VERSION
        self.pipeline = pipeline or get_prediction_pipeline()
        self.passport_manager = passport_manager or get_passport_manager()
        self.db = db or FAJDatabase()

        logger.info(f"Prediction Manager v{self.VERSION} initialized")

    # ============================================================
    # MAIN API
    # ============================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        season_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Полный прогноз матча

        Args:
            home_team: название команды хозяев
            away_team: название команды гостей
            league: лига (для журнала, по умолчанию "RPL")
            season_id: ID сезона (опционально)

        Returns:
            Dict с прогнозом
        """
        logger.info(f"Prediction requested: {home_team} vs {away_team} ({league})")

        try:
            # 1. Загрузка паспортов с рейтингом
            home_data = self._get_passport_with_rating(home_team, season_id)
            away_data = self._get_passport_with_rating(away_team, season_id)

            if not home_data or not away_data:
                missing = []
                if not home_data:
                    missing.append(home_team)
                if not away_data:
                    missing.append(away_team)
                return {
                    "status": "error",
                    "message": f"Паспорт не найден: {', '.join(missing)}"
                }

            # 2. Вызов Pipeline (ВСЯ МАТЕМАТИКА)
            result = self.pipeline.run(
                home_passport=home_data["passport"],
                away_passport=away_data["passport"],
                home_rating=home_data["rating"],
                away_rating=away_data["rating"],
                home_team=home_team,
                away_team=away_team,
                league=league
            )

            if result.get("status") == "error":
                return result

            # 3. Сохранение результата
            self._save_prediction(result, home_team, away_team, league)

            return result

        except Exception as e:
            logger.exception(f"Prediction exception: {home_team} vs {away_team}")
            return {"status": "error", "message": str(e)}

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _get_passport_with_rating(
        self,
        team_name: str,
        season_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Получение паспорта с FAJ Rating"""
        if season_id:
            passport = self.passport_manager.get_current_passport_by_name(team_name, season_id)
        else:
            passport = self.passport_manager.get_current_passport_by_name(team_name)

        if not passport:
            return None

        return {
            "passport": passport,
            "rating": self.passport_manager.calculate_rating(passport)
        }

    def _save_prediction(self, result: Dict[str, Any], home_team: str, away_team: str, league: str) -> None:
        """Сохранение прогноза в БД (через Database)"""
        try:
            self.db.save_prediction(
                prediction_id=result.get("prediction_id", ""),
                home_team=home_team,
                away_team=away_team,
                league=league,
                xg_home=result.get("xg", {}).get("home", 0),
                xg_away=result.get("xg", {}).get("away", 0),
                home_win=result.get("probability", {}).get("home", 0),
                draw=result.get("probability", {}).get("draw", 0),
                away_win=result.get("probability", {}).get("away", 0),
                faj_score=result.get("score", "0:0"),
                confidence=result.get("confidence", {}).get("overall", 0.5),
                risk_level=result.get("risk", {}).get("level", "MEDIUM"),
                model_agreement=result.get("model_agreement", {}).get("score", 0.7),
                pipeline_version=self.version
            )
            logger.info(f"Prediction saved: {result.get('prediction_id')}")

        except Exception as e:
            logger.error(f"Save prediction error: {e}")

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        return {
            "manager": "Prediction Manager",
            "version": self.VERSION,
            "status": "READY"
        }


# ============================================================
# SINGLETON
# ============================================================

_default_manager: Optional[PredictionManager] = None


def get_prediction_manager() -> PredictionManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PredictionManager()
    return _default_manager

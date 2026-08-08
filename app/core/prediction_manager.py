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
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.prediction_pipeline import PredictionPipeline, get_prediction_pipeline
from app.core.match_context import MatchContext
from app.passports.passport_manager import PassportManager, get_passport_manager
from app.database import FAJDatabase
from app.config import config

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
        match_type: str = "league",
        context: Optional[MatchContext] = None,
        season_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Полный прогноз матча

        Args:
            home_team: название команды хозяев
            away_team: название команды гостей
            league: лига (для журнала, по умолчанию "RPL")
            match_type: тип матча
            context: контекст матча
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

    def predict_by_match_id(self, match_id: int) -> Dict[str, Any]:
        """
        Прогноз по ID матча из БД

        Args:
            match_id: ID матча

        Returns:
            Dict с прогнозом
        """
        match = self._get_match(match_id)

        if not match:
            return {
                "status": "error",
                "message": f"Матч с ID {match_id} не найден"
            }

        context = MatchContext(
            season=match.get("season"),
            round=match.get("round_number"),
            tournament=match.get("competition")
        )

        return self.predict(
            home_team=match.get("home_team"),
            away_team=match.get("away_team"),
            league=match.get("competition", "RPL"),
            match_type=match.get("match_type", "league"),
            context=context,
            season_id=match.get("season_id")
        )

    def predict_round(self, round_id: int) -> List[Dict[str, Any]]:
        """
        Прогноз всех матчей тура

        Args:
            round_id: ID тура

        Returns:
            List[Dict] с прогнозами
        """
        matches = self._get_round_matches(round_id)
        results = []

        for match in matches:
            try:
                result = self.predict_by_match_id(match["id"])
                results.append(result)
            except Exception as e:
                logger.error(f"Prediction error for match {match['id']}: {e}")
                results.append({
                    "status": "error",
                    "match_id": match["id"],
                    "message": str(e)
                })

        return results

    def predict_batch(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Прогноз нескольких матчей по списку

        Args:
            matches: список словарей с данными матчей

        Returns:
            List[Dict] с прогнозами
        """
        results = []
        for match in matches:
            try:
                result = self.predict(
                    home_team=match.get("home_team"),
                    away_team=match.get("away_team"),
                    league=match.get("league", "RPL"),
                    match_type=match.get("match_type", "league"),
                    context=match.get("context")
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch prediction error: {e}")
                results.append({
                    "status": "error",
                    "match": match,
                    "message": str(e)
                })

        return results

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Получение матча из БД"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.*,
                   th.name as home_team,
                   ta.name as away_team,
                   r.season_id,
                   r.round_number,
                   s.name as season
            FROM matches m
            LEFT JOIN teams th ON m.home_team_id = th.id
            LEFT JOIN teams ta ON m.away_team_id = ta.id
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN seasons s ON r.season_id = s.id
            WHERE m.id = ?
        """, (match_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def _get_round_matches(self, round_id: int) -> List[Dict[str, Any]]:
        """Получение матчей тура"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT m.id,
                   th.name as home_team,
                   ta.name as away_team,
                   m.competition,
                   r.season_id
            FROM matches m
            LEFT JOIN teams th ON m.home_team_id = th.id
            LEFT JOIN teams ta ON m.away_team_id = ta.id
            LEFT JOIN rounds r ON m.round_id = r.id
            WHERE m.round_id = ?
        """, (round_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ============================================================
    # GET PASSPORT WITH RATING (ЗАМЕНЕНО)
    # ============================================================

    def _get_passport_with_rating(
        self,
        team_name: str,
        season_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Получение паспорта команды с FAJ Rating.
        
        Задача метода:
            1. Получить актуальный паспорт.
            2. Проверить, что паспорт реально загружен.
            3. Вывести диагностическую информацию о структуре.
            4. Рассчитать FAJ Rating.
        
        ВАЖНО:
            Метод НЕ изменяет паспорт.
            Метод НЕ содержит математическую модель.
            Метод НЕ подставляет значения по умолчанию.
        """
        # =========================================================
        # 1. ЗАГРУЗКА ПАСПОРТА
        # =========================================================
        if season_id:
            passport = (
                self.passport_manager
                .get_current_passport_by_name(
                    team_name,
                    season_id
                )
            )
        else:
            passport = (
                self.passport_manager
                .get_current_passport_by_name(
                    team_name
                )
            )
        
        # =========================================================
        # 2. ПАСПОРТ НЕ НАЙДЕН
        # =========================================================
        if not passport:
            logger.error(
                "❌ PASSPORT NOT FOUND | team=%s | season_id=%s",
                team_name,
                season_id
            )
            return None
        
        # =========================================================
        # 3. ДИАГНОСТИКА СТРУКТУРЫ ПАСПОРТА
        # =========================================================
        if not isinstance(passport, dict):
            logger.error(
                "❌ INVALID PASSPORT TYPE | team=%s | type=%s",
                team_name,
                type(passport).__name__
            )
            return None
        
        logger.info(
            "📦 PASSPORT LOADED | team=%s | season_id=%s | keys=%s",
            team_name,
            season_id,
            list(passport.keys())
        )
        
        # =========================================================
        # 4. ПОИСК BASE
        # =========================================================
        base = passport.get("BASE")
        if not isinstance(base, dict):
            base = passport.get("base")
        if not isinstance(base, dict):
            base = passport.get("team_base")
        
        # =========================================================
        # 5. ДИАГНОСТИКА ОСНОВНЫХ ПАРАМЕТРОВ
        # =========================================================
        if isinstance(base, dict):
            logger.info(
                "📊 PASSPORT BASE | team=%s | "
                "attack=%s | defense=%s | control=%s | goalkeeper=%s",
                team_name,
                base.get("attack"),
                base.get("defense"),
                base.get("control"),
                base.get("goalkeeper")
            )
        else:
            logger.info(
                "📊 PASSPORT FLAT | team=%s | "
                "attack=%s | defense=%s | control=%s | goalkeeper=%s",
                team_name,
                passport.get("attack"),
                passport.get("defense"),
                passport.get("control"),
                passport.get("goalkeeper")
            )
        
        # =========================================================
        # 6. ДОПОЛНИТЕЛЬНАЯ ДИАГНОСТИКА FORM
        # =========================================================
        form = passport.get("form")
        if form is None and isinstance(base, dict):
            form = base.get("form")
        
        logger.info(
            "📈 PASSPORT FORM | team=%s | form=%s",
            team_name,
            form
        )
        
        # =========================================================
        # 7. РАСЧЁТ FAJ RATING
        # =========================================================
        try:
            rating = self.passport_manager.calculate_rating(passport)
            logger.info(
                "⭐ FAJ RATING | team=%s | rating=%.2f",
                team_name,
                float(rating)
            )
        except Exception as e:
            logger.exception(
                "❌ RATING CALCULATION ERROR | team=%s",
                team_name
            )
            return None
        
        # =========================================================
        # 8. ВОЗВРАТ
        # =========================================================
        return {
            "passport": passport,
            "rating": rating
        }

    def _save_prediction(self, result: Dict[str, Any], home_team: str, away_team: str, league: str) -> None:
        """Сохранение прогноза в БД (через Database)"""
        # Проверяем, включено ли сохранение
        if not config.SAVE_TO_GOLD_DATASET:
            logger.debug("Prediction saving disabled (SAVE_TO_GOLD_DATASET=False)")
            return

        try:
            self.db.save_prediction_result(
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

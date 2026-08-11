#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Manager v1.7 (ДИРИЖЁР)
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
    Prediction Manager v1.7 (ДИРИЖЁР)
    """

    VERSION = "1.7"

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
        season_id: Optional[int] = None,
        match_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Полный прогноз матча
        """
        logger.info(f"Prediction requested: {home_team} vs {away_team} ({league})")

        # ============================================================
        # АВТОМАТИЧЕСКОЕ ПОЛУЧЕНИЕ SEASON_ID
        # ============================================================
        if season_id is None:
            try:
                conn = self.db._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id
                    FROM seasons
                    WHERE status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                conn.close()
                if row:
                    season_id = row[0]
                    logger.info(f"✅ Auto-detected season_id: {season_id}")
                else:
                    logger.warning("⚠️ No active season found, using season_id=1")
                    season_id = 1
            except Exception as e:
                logger.error(f"Error getting season_id: {e}")
                season_id = 1

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

            # 2. Валидация паспортов ДО Pipeline
            self._validate_passport_for_prediction(
                home_data["passport"],
                home_team
            )
            self._validate_passport_for_prediction(
                away_data["passport"],
                away_team
            )

            # 3. Логирование входных данных
            logger.info(
                "🚀 PREDICTION INPUT | "
                "%s vs %s | "
                "home_rating=%.2f | away_rating=%.2f",
                home_team,
                away_team,
                float(home_data["rating"]),
                float(away_data["rating"])
            )

            logger.info(
                "🚀 PREDICTION PASSPORTS | "
                "HOME keys=%s | AWAY keys=%s",
                list(home_data["passport"].keys()),
                list(away_data["passport"].keys())
            )

            # 4. Вызов Pipeline (ВСЯ МАТЕМАТИКА)
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

            # 5. Сохранение результата
            pred_id = self._save_prediction(
                result,
                home_team,
                away_team,
                league,
                match_id
            )

            if pred_id:
                result["prediction_id"] = pred_id

            return result

        except Exception as e:
            logger.exception(f"Prediction exception: {home_team} vs {away_team}")
            return {"status": "error", "message": str(e)}

    def predict_by_match_id(self, match_id: int) -> Dict[str, Any]:
        """Прогноз по ID матча из БД"""
        match = self._get_match(match_id)

        if not match:
            return {
                "status": "error",
                "message": f"Матч с ID {match_id} не найден"
            }

        context = MatchContext(
            season=match.get("season_name"),
            round=match.get("round_number"),
            tournament=match.get("competition")
        )

        return self.predict(
            home_team=match.get("home_team"),
            away_team=match.get("away_team"),
            league=match.get("competition", "RPL"),
            match_type="league",
            context=context,
            season_id=match.get("season_id"),
            match_id=match_id
        )

    def predict_round(self, round_id: int) -> List[Dict[str, Any]]:
        """Прогноз всех матчей тура"""
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
        """Прогноз нескольких матчей по списку"""
        results = []
        for match in matches:
            try:
                result = self.predict(
                    home_team=match.get("home_team"),
                    away_team=match.get("away_team"),
                    league=match.get("league", "RPL"),
                    match_type=match.get("match_type", "league"),
                    context=match.get("context"),
                    season_id=match.get("season_id"),
                    match_id=match.get("match_id")
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
            SELECT
                m.id,
                m.round_id,
                m.home_team_id,
                m.away_team_id,
                m.date,
                m.competition,
                m.status,
                m.actual_home,
                m.actual_away,
                m.home_xg,
                m.away_xg,
                th.name as home_team,
                ta.name as away_team,
                r.season_id,
                r.round_number,
                s.name as season_name
            FROM matches m
            LEFT JOIN teams th ON m.home_team_id = th.id
            LEFT JOIN teams ta ON m.away_team_id = ta.id
            LEFT JOIN rounds r ON m.round_id = r.id
            LEFT JOIN seasons s ON r.season_id = s.id
            WHERE m.id = ?
        """, (match_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return dict(row)

    def _get_round_matches(self, round_id: int) -> List[Dict[str, Any]]:
        """Получение матчей тура"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                m.id,
                m.home_team_id,
                m.away_team_id,
                m.competition,
                m.date,
                m.status,
                th.name as home_team,
                ta.name as away_team,
                r.season_id,
                r.round_number
            FROM matches m
            LEFT JOIN teams th ON m.home_team_id = th.id
            LEFT JOIN teams ta ON m.away_team_id = ta.id
            LEFT JOIN rounds r ON m.round_id = r.id
            WHERE m.round_id = ?
            ORDER BY m.date, m.id
        """, (round_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def _get_passport_with_rating(
        self,
        team_name: str,
        season_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Получение паспорта команды с FAJ Rating"""
        if season_id:
            passport = self.passport_manager.get_current_passport_by_name(team_name, season_id)
        else:
            passport = self.passport_manager.get_current_passport_by_name(team_name)

        if not passport:
            logger.error(f"❌ PASSPORT NOT FOUND | team={team_name} | season_id={season_id}")
            return None

        if not isinstance(passport, dict):
            logger.error(f"❌ INVALID PASSPORT TYPE | team={team_name} | type={type(passport).__name__}")
            return None

        logger.info(f"📦 PASSPORT LOADED | team={team_name} | season_id={season_id} | keys={list(passport.keys())}")

        stored_rating = passport.get("faj_rating")
        if stored_rating is not None:
            try:
                rating = float(stored_rating)
            except (TypeError, ValueError):
                rating = self.passport_manager.calculate_rating(passport)
        else:
            rating = self.passport_manager.calculate_rating(passport)

        logger.info(f"⭐ FAJ RATING | team={team_name} | rating={rating:.2f}")

        return {"passport": passport, "rating": rating}

    def _validate_passport_for_prediction(self, passport: Dict[str, Any], team_name: str) -> None:
        """Проверка паспорта перед передачей в Pipeline"""
        if not isinstance(passport, dict):
            raise ValueError(f"Invalid passport for {team_name}: expected dict, got {type(passport).__name__}")

        required = ["attack", "defense", "control", "goalkeeper"]
        missing = []

        for field in required:
            if field not in passport or passport.get(field) is None:
                missing.append(field)

        if missing:
            logger.error(f"❌ PASSPORT VALIDATION FAILED | team={team_name} | missing={', '.join(missing)}")
            raise ValueError(f"Passport for {team_name} missing required fields: {', '.join(missing)}")

        logger.info(f"✅ PASSPORT VALIDATED | team={team_name} | required_fields=OK")

    def _save_prediction(
        self,
        result: Dict[str, Any],
        home_team: str,
        away_team: str,
        league: str,
        match_id: Optional[int] = None
    ) -> Optional[int]:
        """Сохранение прогноза в БД"""
        if not getattr(config, 'SAVE_TO_GOLD_DATASET', True):
            logger.debug("Prediction saving disabled")
            return None

        try:
            if match_id is None:
                match_id = self._find_match_by_teams(home_team, away_team)

            if match_id is None:
                logger.warning(f"Cannot save prediction: match not found for {home_team} vs {away_team}")
                return None

            prob = result.get("probability", {})
            confidence_data = result.get("confidence", {})
            confidence_value = confidence_data.get("overall", 0.5)

            pred_id = self.db.save_prediction(
                match_id=match_id,
                model_version=self.VERSION,
                algorithm="FAJ Engine",
                home_win=prob.get("home", 0.0),
                draw=prob.get("draw", 0.0),
                away_win=prob.get("away", 0.0),
                over25=result.get("extended", {}).get("total", {}).get("over_2_5", 0.0),
                over35=result.get("extended", {}).get("total", {}).get("over_3_5", 0.0),
                btts=result.get("extended", {}).get("btts", {}).get("yes", 0.0),
                confidence=int(confidence_value * 100),
                prediction_source="FAJ Engine"
            )

            top_scores = result.get("extended", {}).get("top_scores", [])
            for score_data in top_scores:
                self.db.add_prediction_score(
                    prediction_id=pred_id,
                    score=f"{score_data.get('home', 0)}:{score_data.get('away', 0)}",
                    probability=score_data.get('probability', 0.0),
                    rank=score_data.get('rank', 0)
                )

            distributions = result.get("extended", {}).get("distributions", [])
            for dist in distributions:
                self.db.add_prediction_distribution(
                    prediction_id=pred_id,
                    home_goals=dist.get("home", 0),
                    away_goals=dist.get("away", 0),
                    probability=dist.get("probability", 0.0)
                )

            logger.info(f"Prediction saved: id={pred_id}, match_id={match_id}")
            return pred_id

        except Exception as e:
            logger.error(f"Save prediction error: {e}")
            return None

    def _find_match_by_teams(self, home_team: str, away_team: str) -> Optional[int]:
        """Находит match_id по названиям команд"""
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT m.id
                FROM matches m
                JOIN teams th ON th.id = m.home_team_id
                JOIN teams ta ON ta.id = m.away_team_id
                WHERE th.name = ? AND ta.name = ?
                ORDER BY m.date DESC
                LIMIT 1
            """, (home_team, away_team))

            row = cursor.fetchone()
            conn.close()

            if row:
                return row[0]
            return None

        except Exception as e:
            logger.error(f"Find match error: {e}")
            return None

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

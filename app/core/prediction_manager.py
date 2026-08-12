#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Prediction Manager v1.8
=====================================================

РОЛЬ:
    Дирижёр prediction pipeline.

ЦЕПОЧКА:

    SQLite matches
          ↓
    Team Passport
          ↓
    FAJ Rating
          ↓
    PredictionPipeline
          ↓
    xG / Poisson / Monte Carlo
          ↓
    predictions
          ↓
    prediction_scores
    prediction_distributions

ВАЖНО:

    PredictionManager НЕ загружает календарь.

    Матчи уже находятся в SQLite.

    PredictionManager только:
        - получает матч;
        - получает паспорта;
        - запускает математический pipeline;
        - сохраняет прогноз.
=====================================================
"""

import logging
from typing import Dict, Any, Optional, List

from app.core.prediction_pipeline import (
    PredictionPipeline,
    get_prediction_pipeline,
)

from app.core.match_context import MatchContext

from app.passports.passport_manager import (
    PassportManager,
    get_passport_manager,
)

from app.database import FAJDatabase
from app.config import config


logger = logging.getLogger(__name__)


class PredictionManager:
    """
    Prediction Manager v1.8.

    Управляет полным циклом прогнозирования.
    """

    VERSION = "1.8"

    def __init__(
        self,
        pipeline: Optional[PredictionPipeline] = None,
        passport_manager: Optional[PassportManager] = None,
        db: Optional[FAJDatabase] = None,
    ):
        self.version = self.VERSION

        self.pipeline = (
            pipeline
            or get_prediction_pipeline()
        )

        self.passport_manager = (
            passport_manager
            or get_passport_manager()
        )

        self.db = (
            db
            or FAJDatabase()
        )

        logger.info(
            "Prediction Manager v%s initialized",
            self.VERSION,
        )

    # ============================================================
    # MAIN API
    # ============================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        league: str = "РПЛ",
        match_type: str = "league",
        context: Optional[MatchContext] = None,
        season_id: Optional[int] = None,
        match_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Полный прогноз одного матча.
        """

        logger.info(
            "Prediction requested: %s vs %s",
            home_team,
            away_team,
        )

        try:

            # ====================================================
            # 1. SEASON
            # ====================================================

            if season_id is None:
                season_id = self._get_current_season_id()

            if season_id is None:
                return {
                    "status": "error",
                    "message": "Активный сезон не найден.",
                }

            # ====================================================
            # 2. PASSPORT HOME
            # ====================================================

            home_data = (
                self._get_passport_with_rating(
                    home_team,
                    season_id,
                )
            )

            # ====================================================
            # 3. PASSPORT AWAY
            # ====================================================

            away_data = (
                self._get_passport_with_rating(
                    away_team,
                    season_id,
                )
            )

            if not home_data or not away_data:

                missing = []

                if not home_data:
                    missing.append(home_team)

                if not away_data:
                    missing.append(away_team)

                return {
                    "status": "error",
                    "message": (
                        "Паспорт не найден: "
                        + ", ".join(missing)
                    ),
                }

            # ====================================================
            # 4. VALIDATION
            # ====================================================

            self._validate_passport_for_prediction(
                home_data["passport"],
                home_team,
            )

            self._validate_passport_for_prediction(
                away_data["passport"],
                away_team,
            )

            # ====================================================
            # 5. LOG INPUT
            # ====================================================

            logger.info(
                "PREDICTION INPUT | "
                "%s vs %s | "
                "home_rating=%.2f | "
                "away_rating=%.2f",
                home_team,
                away_team,
                home_data["rating"],
                away_data["rating"],
            )

            # ====================================================
            # 6. PIPELINE
            # ====================================================

            result = self.pipeline.run(
                home_passport=home_data["passport"],
                away_passport=away_data["passport"],
                home_rating=home_data["rating"],
                away_rating=away_data["rating"],
                home_team=home_team,
                away_team=away_team,
                league=league,
            )

            if not isinstance(result, dict):

                return {
                    "status": "error",
                    "message": (
                        "PredictionPipeline "
                        "вернул некорректный результат."
                    ),
                }

            if result.get("status") == "error":
                return result

            # ====================================================
            # 7. ADD MATCH INFO
            # ====================================================

            result["match_id"] = match_id
            result["home_team"] = home_team
            result["away_team"] = away_team
            result["league"] = league

            # ====================================================
            # 8. SAVE
            # ====================================================

            pred_id = self._save_prediction(
                result=result,
                home_team=home_team,
                away_team=away_team,
                league=league,
                match_id=match_id,
            )

            if pred_id is not None:

                result["prediction_id"] = pred_id

            return result

        except Exception as e:

            logger.exception(
                "Prediction exception: %s vs %s",
                home_team,
                away_team,
            )

            return {
                "status": "error",
                "message": str(e),
                "home_team": home_team,
                "away_team": away_team,
                "match_id": match_id,
            }

    # ============================================================
    # PREDICT BY MATCH ID
    # ============================================================

    def predict_by_match_id(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Прогноз непосредственно по match_id.
        """

        match = self._get_match(
            match_id
        )

        if not match:

            return {
                "status": "error",
                "message": (
                    f"Матч с ID {match_id} "
                    "не найден."
                ),
                "match_id": match_id,
            }

        context = MatchContext(
            season=match.get(
                "season_name"
            ),
            round=match.get(
                "round_number"
            ),
            tournament=match.get(
                "competition"
            ),
        )

        return self.predict(
            home_team=match.get(
                "home_team"
            ),
            away_team=match.get(
                "away_team"
            ),
            league=match.get(
                "competition",
                "РПЛ",
            ),
            match_type="league",
            context=context,
            season_id=match.get(
                "season_id"
            ),
            match_id=match_id,
        )

    # ============================================================
    # PREDICT ROUND
    # ============================================================

    def predict_round(
        self,
        round_id: int,
        include_finished: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Прогноз матчей конкретного тура.

        По умолчанию завершённые матчи НЕ прогнозируются.
        """

        matches = self._get_round_matches(
            round_id
        )

        results = []

        for match in matches:

            status = str(
                match.get(
                    "status",
                    ""
                )
            ).lower()

            # ----------------------------------------------------
            # Не прогнозируем завершённые матчи
            # ----------------------------------------------------

            if (
                not include_finished
                and status in {
                    "finished",
                    "completed",
                    "played",
                }
            ):

                logger.info(
                    "Skip finished match: id=%s",
                    match["id"],
                )

                continue

            try:

                result = self.predict_by_match_id(
                    match["id"]
                )

                results.append(result)

            except Exception as e:

                logger.exception(
                    "Prediction error for match %s",
                    match["id"],
                )

                results.append(
                    {
                        "status": "error",
                        "match_id": match["id"],
                        "home_team": match.get(
                            "home_team"
                        ),
                        "away_team": match.get(
                            "away_team"
                        ),
                        "message": str(e),
                    }
                )

        return results

    # ============================================================
    # PREDICT BATCH
    # ============================================================

    def predict_batch(
        self,
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Прогноз списка матчей.
        """

        results = []

        for match in matches:

            try:

                result = self.predict(
                    home_team=match.get(
                        "home_team"
                    ),
                    away_team=match.get(
                        "away_team"
                    ),
                    league=match.get(
                        "league",
                        "РПЛ",
                    ),
                    match_type=match.get(
                        "match_type",
                        "league",
                    ),
                    context=match.get(
                        "context"
                    ),
                    season_id=match.get(
                        "season_id"
                    ),
                    match_id=match.get(
                        "match_id"
                    ),
                )

                results.append(result)

            except Exception as e:

                logger.exception(
                    "Batch prediction error"
                )

                results.append(
                    {
                        "status": "error",
                        "match": match,
                        "message": str(e),
                    }
                )

        return results

    # ============================================================
    # SEASON
    # ============================================================

    def _get_current_season_id(
        self,
    ) -> Optional[int]:
        """
        Получает текущий сезон.

        Сначала ищет сезон 2026-2027.
        Затем fallback по последнему ID.

        Не требует наличия поля status.
        """

        conn = self.db._get_connection()

        try:

            cursor = conn.cursor()

            # ------------------------------------------------
            # Основной вариант
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM seasons
                WHERE (
                    name = ?
                    OR name = ?
                )
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    "РПЛ 2026-2027",
                    "2026-2027",
                ),
            )

            row = cursor.fetchone()

            if row:

                season_id = row[0]

                logger.info(
                    "Season detected: %s",
                    season_id,
                )

                return season_id

            # ------------------------------------------------
            # Fallback
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM seasons
                ORDER BY id DESC
                LIMIT 1
                """
            )

            row = cursor.fetchone()

            if row:

                logger.warning(
                    "Fallback season detected: %s",
                    row[0],
                )

                return row[0]

            return None

        finally:

            conn.close()

    # ============================================================
    # GET MATCH
    # ============================================================

    def _get_match(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получение матча из SQLite.
        """

        conn = self.db._get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
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

                    th.name AS home_team,
                    ta.name AS away_team,

                    r.season_id,
                    r.round_number,

                    s.name AS season_name

                FROM matches m

                LEFT JOIN teams th
                    ON m.home_team_id = th.id

                LEFT JOIN teams ta
                    ON m.away_team_id = ta.id

                LEFT JOIN rounds r
                    ON m.round_id = r.id

                LEFT JOIN seasons s
                    ON r.season_id = s.id

                WHERE m.id = ?
                """,
                (match_id,),
            )

            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)

        finally:

            conn.close()

    # ============================================================
    # GET ROUND MATCHES
    # ============================================================

    def _get_round_matches(
        self,
        round_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Получение матчей тура.
        """

        conn = self.db._get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    m.id,
                    m.home_team_id,
                    m.away_team_id,
                    m.competition,
                    m.date,
                    m.status,

                    th.name AS home_team,
                    ta.name AS away_team,

                    r.season_id,
                    r.round_number

                FROM matches m

                LEFT JOIN teams th
                    ON m.home_team_id = th.id

                LEFT JOIN teams ta
                    ON m.away_team_id = ta.id

                LEFT JOIN rounds r
                    ON m.round_id = r.id

                WHERE m.round_id = ?

                ORDER BY
                    m.date,
                    m.id
                """,
                (round_id,),
            )

            rows = cursor.fetchall()

            return [
                dict(row)
                for row in rows
            ]

        finally:

            conn.close()

    # ============================================================
    # PASSPORT
    # ============================================================

    def _get_passport_with_rating(
        self,
        team_name: str,
        season_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает паспорт и FAJ Rating.
        """

        if season_id is not None:

            passport = (
                self.passport_manager
                .get_current_passport_by_name(
                    team_name,
                    season_id,
                )
            )

        else:

            passport = (
                self.passport_manager
                .get_current_passport_by_name(
                    team_name
                )
            )

        if not passport:

            logger.error(
                "PASSPORT NOT FOUND | team=%s | season=%s",
                team_name,
                season_id,
            )

            return None

        if not isinstance(
            passport,
            dict,
        ):

            logger.error(
                "INVALID PASSPORT TYPE | team=%s",
                team_name,
            )

            return None

        stored_rating = passport.get(
            "faj_rating"
        )

        if stored_rating is not None:

            try:

                rating = float(
                    stored_rating
                )

            except (
                TypeError,
                ValueError,
            ):

                rating = (
                    self.passport_manager
                    .calculate_rating(
                        passport
                    )
                )

        else:

            rating = (
                self.passport_manager
                .calculate_rating(
                    passport
                )
            )

        logger.info(
            "FAJ RATING | team=%s | %.2f",
            team_name,
            rating,
        )

        return {
            "passport": passport,
            "rating": float(rating),
        }

    # ============================================================
    # PASSPORT VALIDATION
    # ============================================================

    def _validate_passport_for_prediction(
        self,
        passport: Dict[str, Any],
        team_name: str,
    ) -> None:
        """
        Проверка минимально необходимых полей.
        """

        if not isinstance(
            passport,
            dict,
        ):

            raise ValueError(
                f"Invalid passport for {team_name}"
            )

        required = [
            "attack",
            "defense",
            "control",
            "goalkeeper",
        ]

        missing = []

        for field in required:

            if (
                field not in passport
                or passport.get(field) is None
            ):

                missing.append(field)

        if missing:

            raise ValueError(
                f"Passport for {team_name} "
                f"missing required fields: "
                f"{', '.join(missing)}"
            )

        logger.info(
            "PASSPORT VALIDATED | team=%s",
            team_name,
        )

    # ============================================================
    # SAVE PREDICTION
    # ============================================================

    def _save_prediction(
        self,
        result: Dict[str, Any],
        home_team: str,
        away_team: str,
        league: str,
        match_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Сохранение прогноза.

        Если match_id не передан,
        пытаемся найти матч по командам.
        """

        if not getattr(
            config,
            "SAVE_TO_GOLD_DATASET",
            True,
        ):

            logger.info(
                "Prediction saving disabled"
            )

            return None

        try:

            if match_id is None:

                match_id = (
                    self._find_match_by_teams(
                        home_team,
                        away_team,
                    )
                )

            if match_id is None:

                logger.warning(
                    "Cannot save prediction: "
                    "match not found | %s vs %s",
                    home_team,
                    away_team,
                )

                return None

            # =================================================
            # PROBABILITIES
            # =================================================

            probability = result.get(
                "probability",
                {},
            )

            confidence_data = result.get(
                "confidence",
                {},
            )

            confidence_value = (
                confidence_data.get(
                    "overall",
                    0.5,
                )
            )

            try:

                confidence_value = float(
                    confidence_value
                )

            except (
                TypeError,
                ValueError,
            ):

                confidence_value = 0.5

            # =================================================
            # SAVE MAIN PREDICTION
            # =================================================

            pred_id = self.db.save_prediction(
                match_id=match_id,
                model_version=self.VERSION,
                algorithm="FAJ Engine",
                home_win=probability.get(
                    "home",
                    0.0,
                ),
                draw=probability.get(
                    "draw",
                    0.0,
                ),
                away_win=probability.get(
                    "away",
                    0.0,
                ),
                over25=(
                    result
                    .get("extended", {})
                    .get("total", {})
                    .get("over_2_5", 0.0)
                ),
                over35=(
                    result
                    .get("extended", {})
                    .get("total", {})
                    .get("over_3_5", 0.0)
                ),
                btts=(
                    result
                    .get("extended", {})
                    .get("btts", {})
                    .get("yes", 0.0)
                ),
                confidence=int(
                    max(
                        0.0,
                        min(
                            confidence_value,
                            1.0,
                        ),
                    )
                    * 100
                ),
                prediction_source="FAJ Engine",
            )

            if not pred_id:

                logger.warning(
                    "Prediction save returned no ID"
                )

                return None

            # =================================================
            # TOP SCORES
            # =================================================

            top_scores = (
                result
                .get("extended", {})
                .get("top_scores", [])
            )

            for score_data in top_scores:

                self.db.add_prediction_score(
                    prediction_id=pred_id,
                    score=(
                        f"{score_data.get('home', 0)}:"
                        f"{score_data.get('away', 0)}"
                    ),
                    probability=score_data.get(
                        "probability",
                        0.0,
                    ),
                    rank=score_data.get(
                        "rank",
                        0,
                    ),
                )

            # =================================================
            # DISTRIBUTIONS
            # =================================================

            distributions = (
                result
                .get("extended", {})
                .get("distributions", [])
            )

            for dist in distributions:

                self.db.add_prediction_distribution(
                    prediction_id=pred_id,
                    home_goals=dist.get(
                        "home",
                        0,
                    ),
                    away_goals=dist.get(
                        "away",
                        0,
                    ),
                    probability=dist.get(
                        "probability",
                        0.0,
                    ),
                )

            logger.info(
                "Prediction saved | "
                "prediction_id=%s | "
                "match_id=%s",
                pred_id,
                match_id,
            )

            return pred_id

        except Exception as e:

            logger.exception(
                "Save prediction error"
            )

            return None

    # ============================================================
    # FIND MATCH
    # ============================================================

    def _find_match_by_teams(
        self,
        home_team: str,
        away_team: str,
    ) -> Optional[int]:
        """
        Находит матч в SQLite.
        """

        conn = self.db._get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT m.id

                FROM matches m

                JOIN teams th
                    ON th.id = m.home_team_id

                JOIN teams ta
                    ON ta.id = m.away_team_id

                WHERE
                    th.name = ?
                    AND ta.name = ?

                ORDER BY
                    m.date DESC,
                    m.id DESC

                LIMIT 1
                """,
                (
                    home_team,
                    away_team,
                ),
            )

            row = cursor.fetchone()

            if row:
                return row[0]

            return None

        finally:

            conn.close()

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:

        return {
            "manager": "Prediction Manager",
            "version": self.VERSION,
            "status": "READY",
        }


# ============================================================
# SINGLETON
# ============================================================

_default_manager: Optional[
    PredictionManager
] = None


def get_prediction_manager() -> PredictionManager:

    global _default_manager

    if _default_manager is None:

        _default_manager = PredictionManager()

    return _default_manager

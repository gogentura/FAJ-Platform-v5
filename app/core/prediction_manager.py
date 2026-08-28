#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Prediction Manager v2.1
=====================================================

РОЛЬ:
    Дирижёр prediction pipeline.

АРХИТЕКТУРА:

    MATCH
      ↓
    TEAM PASSPORT
      ↓
    FAJ CLUB RATING
      ↓
    PREDICTION PIPELINE
      │
      ├── FAJ XG MODEL
      │       ↓
      │    home_xg
      │    away_xg
      │
      ├── POISSON
      │
      └── MONTE CARLO
              ↓
        FINAL PREDICTION
              ↓
        GOLD DATASET

ВАЖНО:

    Prediction Manager НЕ рассчитывает xG.

    Prediction Manager НЕ рассчитывает Poisson.

    Prediction Manager НЕ запускает Monte Carlo
    напрямую.

    Prediction Manager НЕ изменяет Team Passport.

    Prediction Manager НЕ обновляет FAJ Rating.

    Все математические расчёты выполняются
    внутри PredictionPipeline.

    FAJ Rating передаётся в pipeline для
    использования соответствующими слоями
    и диагностики.

    Новый FAJ XG Model НЕ использует Rating
    как множитель xG.

ИЗМЕНЕНИЯ v2.1:

    1. Сохранена архитектура v2.0.
    2. Prediction Manager остаётся orchestration layer.
    3. Усилен prediction_hash.
    4. В hash включаются xG и основные вероятности.
    5. Сохранён memory_state_id.
    6. Snapshot создаётся до prediction.
    7. FAJ Rating берётся из сохранённого
       passport faj_rating.
    8. Не выполняется скрытый пересчёт Rating
       без необходимости.
    9. Сохранён Database-only API.
   10. Сохранён совместимый публичный API.
=====================================================
"""

import hashlib
import json
import logging

from datetime import datetime
from typing import Dict, Any, Optional, List, Set

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
    Prediction Manager v2.1.

    Отвечает только за orchestration:

        MATCH
          ↓
        PASSPORT
          ↓
        RATING
          ↓
        PIPELINE
          ↓
        PREDICTION
          ↓
        DATABASE

    Математические модели находятся
    внутри PredictionPipeline.
    """

    VERSION = "2.1"

    FINISHED_STATUSES: Set[str] = {
        "finished",
        "completed",
        "played",
        "ft",
        "ended",
        "full time",
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

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

        Prediction Manager:

            1. получает сезон;
            2. получает паспорта;
            3. получает FAJ Rating;
            4. валидирует паспорта;
            5. фиксирует snapshot;
            6. запускает PredictionPipeline;
            7. добавляет metadata;
            8. сохраняет prediction.

        Сам Manager математические модели
        не рассчитывает.
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
                season_id = (
                    self._get_current_season_id()
                )

            if season_id is None:

                return {
                    "status": "error",
                    "message": (
                        "Активный сезон не найден."
                    ),
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_id": match_id,
                }

            # ====================================================
            # 2. PASSPORTS + RATING
            # ====================================================

            home_data = (
                self._get_passport_with_rating(
                    home_team,
                    season_id,
                )
            )

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
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_id": match_id,
                }

            # ====================================================
            # 3. PASSPORT VALIDATION
            # ====================================================

            self._validate_passport_for_prediction(
                home_data["passport"],
                home_team,
            )

            self._validate_passport_for_prediction(
                away_data["passport"],
                away_team,
            )

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
            # 4. MEMORY STATE
            # ====================================================

            memory_state_id = (
                self._generate_memory_state_id()
            )

            # ====================================================
            # 5. MATCH SNAPSHOT
            # ====================================================

            if match_id is not None:

                self._record_snapshots(
                    match_id=match_id,
                    home_data=home_data,
                    away_data=away_data,
                    memory_state_id=memory_state_id,
                )

            # ====================================================
            # 6. RUN PREDICTION PIPELINE
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

            # ====================================================
            # 7. PIPELINE VALIDATION
            # ====================================================

            if not isinstance(result, dict):

                return {
                    "status": "error",
                    "message": (
                        "PredictionPipeline "
                        "вернул некорректный результат."
                    ),
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_id": match_id,
                }

            if result.get("status") == "error":
                return result

            # ====================================================
            # 8. METADATA
            # ====================================================

            result["match_id"] = match_id
            result["home_team"] = home_team
            result["away_team"] = away_team
            result["league"] = league
            result["match_type"] = match_type
            result["season_id"] = season_id
            result["memory_state_id"] = (
                memory_state_id
            )

            # ====================================================
            # 9. SAVE PREDICTION
            # ====================================================

            pred_id = self._save_prediction(
                result=result,
                home_team=home_team,
                away_team=away_team,
                league=league,
                match_id=match_id,
                memory_state_id=memory_state_id,
            )

            if pred_id is not None:
                result["prediction_id"] = pred_id

            logger.info(
                "Prediction completed | "
                "%s vs %s | "
                "prediction_id=%s",
                home_team,
                away_team,
                pred_id,
            )

            return result

        except Exception as exc:

            logger.exception(
                "Prediction exception: %s vs %s",
                home_team,
                away_team,
            )

            return {
                "status": "error",
                "message": str(exc),
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
        Прогноз по match_id.

        Основной способ запуска прогноза
        для существующего матча.
        """

        match = self._get_match(match_id)

        if not match:

            return {
                "status": "error",
                "message": (
                    f"Матч с ID {match_id} "
                    f"не найден."
                ),
                "match_id": match_id,
            }

        return self.predict(
            home_team=match.get("home_team"),
            away_team=match.get("away_team"),
            league=match.get(
                "competition",
                "РПЛ",
            ),
            match_type="league",
            context=None,
            season_id=match.get("season_id"),
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
        Прогноз всех матчей тура.
        """

        matches = self._get_round_matches(
            round_id
        )

        results = []

        for match in matches:

            status = str(
                match.get("status", "")
            ).lower()

            if (
                not include_finished
                and status in self.FINISHED_STATUSES
            ):

                logger.info(
                    "Skip finished match: id=%s",
                    match["id"],
                )

                continue

            try:

                results.append(
                    self.predict_by_match_id(
                        match["id"]
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Prediction error for match %s",
                    match["id"],
                )

                results.append({
                    "status": "error",
                    "match_id": match["id"],
                    "home_team": match.get(
                        "home_team"
                    ),
                    "away_team": match.get(
                        "away_team"
                    ),
                    "message": str(exc),
                })

        return results

    # ============================================================
    # PREDICT ROUND BY NUMBER
    # ============================================================

    def predict_round_by_number(
        self,
        round_number: int,
        include_finished: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Прогноз тура по номеру.
        """

        season_id = (
            self._get_current_season_id()
        )

        if not season_id:

            return [{
                "status": "error",
                "message": "Сезон не найден",
            }]

        rounds = self.db.get_rounds(
            season_id
        )

        round_id = None

        for current_round in rounds:

            if (
                current_round["round_number"]
                == round_number
            ):

                round_id = (
                    current_round["id"]
                )

                break

        if round_id is None:

            return [{
                "status": "error",
                "message": (
                    f"Тур {round_number} "
                    f"не найден в БД"
                ),
            }]

        logger.info(
            "Predict round by number | "
            "round_number=%s | "
            "round_id=%s",
            round_number,
            round_id,
        )

        return self.predict_round(
            round_id,
            include_finished,
        )

    # ============================================================
    # SEASON
    # ============================================================

    def _get_current_season_id(
        self,
    ) -> Optional[int]:
        """
        Получение текущего сезона
        исключительно через FAJDatabase.
        """

        seasons = self.db.get_seasons()

        for season in seasons:

            name = str(
                season.get("name", "")
            )

            if (
                "РПЛ 2026-2027" in name
                or "2026-2027" in name
            ):

                logger.info(
                    "Season detected: %s",
                    season["id"],
                )

                return season["id"]

        logger.error(
            "Season 2026-2027 not found "
            "in database"
        )

        return None

    # ============================================================
    # GET MATCH
    # ============================================================

    def _get_match(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получение матча через FAJDatabase.
        """

        all_matches = self.db.get_matches()

        match = None

        for current_match in all_matches:

            if current_match["id"] == match_id:

                match = dict(
                    current_match
                )

                break

        if not match:
            return None

        # --------------------------------------------------------
        # HOME TEAM
        # --------------------------------------------------------

        home = self.db.get_team(
            match["home_team_id"]
        )

        # --------------------------------------------------------
        # AWAY TEAM
        # --------------------------------------------------------

        away = self.db.get_team(
            match["away_team_id"]
        )

        match["home_team"] = (
            home["name"]
            if home
            else None
        )

        match["away_team"] = (
            away["name"]
            if away
            else None
        )

        # --------------------------------------------------------
        # ROUND / SEASON
        # --------------------------------------------------------

        rounds = self.db.get_rounds()

        for current_round in rounds:

            if (
                current_round["id"]
                == match["round_id"]
            ):

                match["round_number"] = (
                    current_round[
                        "round_number"
                    ]
                )

                match["season_id"] = (
                    current_round[
                        "season_id"
                    ]
                )

                break

        return match

    # ============================================================
    # GET ROUND MATCHES
    # ============================================================

    def _get_round_matches(
        self,
        round_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Получение матчей тура через FAJDatabase.
        """

        all_matches = (
            self.db.get_matches(
                round_id
            )
        )

        result = []

        for match in all_matches:

            match_dict = dict(match)

            home = self.db.get_team(
                match["home_team_id"]
            )

            away = self.db.get_team(
                match["away_team_id"]
            )

            match_dict["home_team"] = (
                home["name"]
                if home
                else None
            )

            match_dict["away_team"] = (
                away["name"]
                if away
                else None
            )

            result.append(
                match_dict
            )

        return result

    # ============================================================
    # PASSPORT + RATING
    # ============================================================

    def _get_passport_with_rating(
        self,
        team_name: str,
        season_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает актуальный Team Passport
        и сохранённый FAJ Rating.

        ВАЖНО:

        Prediction Manager не обновляет Rating.

        Если faj_rating отсутствует,
        прогноз считается некорректно подготовленным,
        поскольку Rating является отдельным
        состоянием FAJ и должен быть сформирован
        соответствующим слоем системы.
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
                "PASSPORT NOT FOUND | "
                "team=%s | season=%s",
                team_name,
                season_id,
            )

            return None

        if not isinstance(
            passport,
            dict,
        ):

            logger.error(
                "INVALID PASSPORT TYPE | "
                "team=%s",
                team_name,
            )

            return None

        stored_rating = (
            passport.get("faj_rating")
        )

        # --------------------------------------------------------
        # RATING MUST EXIST
        # --------------------------------------------------------

        if stored_rating is None:

            logger.error(
                "FAJ RATING NOT FOUND | "
                "team=%s | season=%s",
                team_name,
                season_id,
            )

            return None

        try:

            rating = float(
                stored_rating
            )

        except (
            TypeError,
            ValueError,
        ):

            logger.error(
                "INVALID FAJ RATING | "
                "team=%s | value=%r",
                team_name,
                stored_rating,
            )

            return None

        if not (
            config.RATING_MIN
            <= rating
            <= config.RATING_MAX
        ):

            logger.error(
                "FAJ RATING OUT OF RANGE | "
                "team=%s | rating=%.3f",
                team_name,
                rating,
            )

            return None

        logger.info(
            "FAJ RATING LOADED | "
            "team=%s | rating=%.2f",
            team_name,
            rating,
        )

        return {
            "passport": passport,
            "rating": rating,
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
        Минимальная валидация паспорта,
        необходимая Prediction Pipeline.
        """

        if not isinstance(
            passport,
            dict,
        ):

            raise ValueError(
                f"Invalid passport "
                f"for {team_name}"
            )

        required = [
            "attack",
            "defense",
            "control",
            "goalkeeper",
            "form",
        ]

        missing = [
            field
            for field in required
            if (
                field not in passport
                or passport.get(field)
                is None
            )
        ]

        if missing:

            raise ValueError(
                f"Passport for {team_name} "
                f"missing required fields: "
                f"{', '.join(missing)}"
            )

        logger.info(
            "PASSPORT VALIDATED | "
            "team=%s",
            team_name,
        )

    # ============================================================
    # SNAPSHOTS
    # ============================================================

    def _record_snapshots(
        self,
        match_id: int,
        home_data: Dict[str, Any],
        away_data: Dict[str, Any],
        memory_state_id: str,
    ) -> None:
        """
        Фиксирует состояние Team Passport
        непосредственно перед прогнозом.

        Snapshot является исторической фиксацией
        входных данных prediction.
        """

        try:

            home_passport = (
                home_data["passport"]
            )

            away_passport = (
                away_data["passport"]
            )

            # ====================================================
            # HOME SNAPSHOT
            # ====================================================

            self.db.record_match_snapshot(
                match_id=match_id,
                team_id=home_passport.get(
                    "team_id"
                ),
                data={
                    "attack": home_passport.get(
                        "attack"
                    ),
                    "defense": home_passport.get(
                        "defense"
                    ),
                    "control": home_passport.get(
                        "control"
                    ),
                    "press": home_passport.get(
                        "press"
                    ),
                    "tempo": home_passport.get(
                        "tempo"
                    ),
                    "transition": home_passport.get(
                        "transition"
                    ),
                    "finishing": home_passport.get(
                        "finishing"
                    ),
                    "coach_factor": home_passport.get(
                        "coach_factor"
                    ),
                    "squad_quality": home_passport.get(
                        "squad_quality"
                    ),
                    "form": home_passport.get(
                        "form"
                    ),
                    "fitness": home_passport.get(
                        "fitness"
                    ),
                    "fatigue": home_passport.get(
                        "fatigue"
                    ),
                    "morale": home_passport.get(
                        "morale"
                    ),
                    "faj_rating": home_data.get(
                        "rating"
                    ),
                },
                passport_id=home_passport.get(
                    "id"
                ),
                passport_version=home_passport.get(
                    "version"
                ),
                memory_state_id=memory_state_id,
            )

            # ====================================================
            # AWAY SNAPSHOT
            # ====================================================

            self.db.record_match_snapshot(
                match_id=match_id,
                team_id=away_passport.get(
                    "team_id"
                ),
                data={
                    "attack": away_passport.get(
                        "attack"
                    ),
                    "defense": away_passport.get(
                        "defense"
                    ),
                    "control": away_passport.get(
                        "control"
                    ),
                    "press": away_passport.get(
                        "press"
                    ),
                    "tempo": away_passport.get(
                        "tempo"
                    ),
                    "transition": away_passport.get(
                        "transition"
                    ),
                    "finishing": away_passport.get(
                        "finishing"
                    ),
                    "coach_factor": away_passport.get(
                        "coach_factor"
                    ),
                    "squad_quality": away_passport.get(
                        "squad_quality"
                    ),
                    "form": away_passport.get(
                        "form"
                    ),
                    "fitness": away_passport.get(
                        "fitness"
                    ),
                    "fatigue": away_passport.get(
                        "fatigue"
                    ),
                    "morale": away_passport.get(
                        "morale"
                    ),
                    "faj_rating": away_data.get(
                        "rating"
                    ),
                },
                passport_id=away_passport.get(
                    "id"
                ),
                passport_version=away_passport.get(
                    "version"
                ),
                memory_state_id=memory_state_id,
            )

            logger.info(
                "Snapshots recorded | "
                "match_id=%s | "
                "memory_state_id=%s",
                match_id,
                memory_state_id,
            )

        except Exception as exc:

            # Snapshot failure НЕ должен
            # уничтожать сам prediction pipeline.
            #
            # Исторически это диагностическая
            # проблема, которую необходимо видеть
            # в логах.

            logger.warning(
                "Failed to record snapshots "
                "for match %s: %s",
                match_id,
                exc,
            )

    # ============================================================
    # MEMORY STATE ID
    # ============================================================

    def _generate_memory_state_id(
        self,
    ) -> str:
        """
        Идентификатор состояния модели
        на момент prediction.
        """

        timestamp = (
            datetime.now()
            .isoformat()
        )

        return (
            f"FAJ-{self.VERSION}-"
            f"{timestamp}"
        )

    # ============================================================
    # PREDICTION HASH
    # ============================================================

    def _generate_prediction_hash(
        self,
        match_id: int,
        result: Dict[str, Any],
    ) -> str:
        """
        Генерирует детерминированный hash
        prediction.

        Hash фиксирует не только 1X2,
        но и основные параметры прогноза.

        Это позволяет отличать два разных
        состояния prediction для одного матча.
        """

        probability = (
            result.get(
                "probability",
                {}
            )
        )

        data = {
            "match_id": match_id,

            "manager_version": self.VERSION,

            "pipeline_version": (
                result.get(
                    "pipeline_version"
                )
            ),

            "model_version": (
                result.get(
                    "model_version"
                )
            ),

            "home_xg": (
                result.get("home_xg")
            ),

            "away_xg": (
                result.get("away_xg")
            ),

            "home_win": round(
                float(
                    probability.get(
                        "home",
                        0.0
                    )
                ),
                6,
            ),

            "draw": round(
                float(
                    probability.get(
                        "draw",
                        0.0
                    )
                ),
                6,
            ),

            "away_win": round(
                float(
                    probability.get(
                        "away",
                        0.0
                    )
                ),
                6,
            ),
        }

        encoded = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            encoded.encode("utf-8")
        ).hexdigest()

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
        memory_state_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Сохраняет Prediction исключительно
        через FAJDatabase.
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

            # ====================================================
            # 1. MATCH ID
            # ====================================================

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
                    "match not found | "
                    "%s vs %s",
                    home_team,
                    away_team,
                )

                return None

            # ====================================================
            # 2. PROBABILITY
            # ====================================================

            probability = result.get(
                "probability",
                {}
            )

            home_win = float(
                probability.get(
                    "home",
                    0.0,
                )
            )

            draw = float(
                probability.get(
                    "draw",
                    0.0,
                )
            )

            away_win = float(
                probability.get(
                    "away",
                    0.0,
                )
            )

            # ====================================================
            # 3. CONFIDENCE
            # ====================================================

            confidence_data = (
                result.get(
                    "confidence",
                    {}
                )
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

            confidence_value = max(
                0.0,
                min(
                    confidence_value,
                    1.0,
                ),
            )

            # ====================================================
            # 4. PREDICTION HASH
            # ====================================================

            prediction_hash = (
                self._generate_prediction_hash(
                    match_id=match_id,
                    result=result,
                )
            )

            # ====================================================
            # 5. SAVE MAIN PREDICTION
            # ====================================================

            extended = result.get(
                "extended",
                {}
            )

            total_data = extended.get(
                "total",
                {}
            )

            btts_data = extended.get(
                "btts",
                {}
            )

            pred_id = (
                self.db.save_prediction(
                    match_id=match_id,
                    model_version=self.VERSION,
                    algorithm="FAJ Engine",
                    home_win=home_win,
                    draw=draw,
                    away_win=away_win,
                    over25=total_data.get(
                        "over_2_5",
                        0.0,
                    ),
                    over35=total_data.get(
                        "over_3_5",
                        0.0,
                    ),
                    btts=btts_data.get(
                        "yes",
                        0.0,
                    ),
                    confidence=int(
                        confidence_value * 100
                    ),
                    prediction_source="FAJ Engine",
                    prediction_hash=(
                        prediction_hash
                    ),
                    memory_state_id=(
                        memory_state_id
                    ),
                )
            )

            if not pred_id:

                logger.warning(
                    "Prediction save "
                    "returned no ID"
                )

                return None

            # ====================================================
            # 6. TOP SCORES
            # ====================================================

            top_scores = extended.get(
                "top_scores",
                []
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

            # ====================================================
            # 7. DISTRIBUTIONS
            # ====================================================

            distributions = extended.get(
                "distributions",
                []
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
                "match_id=%s | "
                "hash=%s",
                pred_id,
                match_id,
                prediction_hash[:12],
            )

            return pred_id

        except Exception:

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
        Поиск матча по командам
        исключительно через FAJDatabase.
        """

        all_matches = (
            self.db.get_matches()
        )

        for match in all_matches:

            home = self.db.get_team(
                match["home_team_id"]
            )

            away = self.db.get_team(
                match["away_team_id"]
            )

            if not home or not away:
                continue

            if (
                home["name"] == home_team
                and away["name"] == away_team
            ):

                return match["id"]

        return None

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """
        Диагностический статус.
        """

        return {
            "manager": (
                "Prediction Manager"
            ),
            "version": self.VERSION,
            "pipeline": (
                getattr(
                    self.pipeline,
                    "VERSION",
                    None,
                )
            ),
            "status": "READY",
        }


# ================================================================
# SINGLETON
# ================================================================

_default_manager: Optional[
    PredictionManager
] = None


def get_prediction_manager() -> PredictionManager:
    """
    Singleton Prediction Manager.
    """

    global _default_manager

    if _default_manager is None:

        _default_manager = (
            PredictionManager()
        )

    return _default_manager


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":

    manager = PredictionManager()

    print()
    print("=" * 70)
    print(
        "FAJ PREDICTION MANAGER "
        f"v{manager.VERSION}"
    )
    print("=" * 70)

    print()
    print("STATUS")
    print("-" * 70)

    print(
        manager.status()
    )

    print()
    print("=" * 70)

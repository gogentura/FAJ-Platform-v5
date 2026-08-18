#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1 — MEMORY HARDENED
Prediction Manager v2.0
=====================================================

РОЛЬ:
    Дирижёр prediction pipeline.

ИСПРАВЛЕНИЯ v2.0:
    1. Убраны все прямые SQL-запросы — только через FAJDatabase
    2. Добавлен prediction_hash для защиты от дублей
    3. Добавлен memory_state_id для фиксации состояния модели
    4. Добавлен record_match_snapshot() перед прогнозом
    5. _get_current_season_id() — через db.get_seasons()
    6. _get_match() — через db.get_matches() + db.get_team()
    7. _get_round_matches() — через db.get_matches(round_id) + db.get_team()
    8. _find_match_by_teams() — через db.get_matches() с фильтрацией
    9. predict_round_by_number() — через db.get_rounds()
"""

import logging
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Set

from app.core.prediction_pipeline import PredictionPipeline, get_prediction_pipeline
from app.core.match_context import MatchContext
from app.passports.passport_manager import PassportManager, get_passport_manager
from app.database import FAJDatabase
from app.config import config


logger = logging.getLogger(__name__)


class PredictionManager:
    """Prediction Manager v2.0 — Memory Hardened"""

    VERSION = "2.0"

    FINISHED_STATUSES: Set[str] = {
        "finished", "completed", "played", "ft", "ended", "full time"
    }

    def __init__(
        self,
        pipeline: Optional[PredictionPipeline] = None,
        passport_manager: Optional[PassportManager] = None,
        db: Optional[FAJDatabase] = None,
    ):
        self.version = self.VERSION
        self.pipeline = pipeline or get_prediction_pipeline()
        self.passport_manager = passport_manager or get_passport_manager()
        self.db = db or FAJDatabase()

        logger.info("Prediction Manager v%s initialized", self.VERSION)

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
        """Полный прогноз одного матча."""
        logger.info("Prediction requested: %s vs %s", home_team, away_team)

        try:
            if season_id is None:
                season_id = self._get_current_season_id()

            if season_id is None:
                return {"status": "error", "message": "Активный сезон не найден."}

            home_data = self._get_passport_with_rating(home_team, season_id)
            away_data = self._get_passport_with_rating(away_team, season_id)

            if not home_data or not away_data:
                missing = []
                if not home_data:
                    missing.append(home_team)
                if not away_data:
                    missing.append(away_team)
                return {"status": "error", "message": f"Паспорт не найден: {', '.join(missing)}"}

            self._validate_passport_for_prediction(home_data["passport"], home_team)
            self._validate_passport_for_prediction(away_data["passport"], away_team)

            logger.info(
                "PREDICTION INPUT | %s vs %s | home_rating=%.2f | away_rating=%.2f",
                home_team, away_team, home_data["rating"], away_data["rating"]
            )

            # ============================================================
            # RECORD MATCH SNAPSHOT (перед прогнозом)
            # ============================================================

            memory_state_id = self._generate_memory_state_id()

            if match_id:
                self._record_snapshots(match_id, home_data, away_data, memory_state_id)

            # ============================================================
            # RUN PIPELINE
            # ============================================================

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
                return {"status": "error", "message": "PredictionPipeline вернул некорректный результат."}

            if result.get("status") == "error":
                return result

            result["match_id"] = match_id
            result["home_team"] = home_team
            result["away_team"] = away_team
            result["league"] = league

            # ============================================================
            # SAVE PREDICTION с hash и memory_state_id
            # ============================================================

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

            return result

        except Exception as e:
            logger.exception("Prediction exception: %s vs %s", home_team, away_team)
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

    def predict_by_match_id(self, match_id: int) -> Dict[str, Any]:
        """Прогноз непосредственно по match_id. Основной способ вызова."""
        match = self._get_match(match_id)

        if not match:
            return {"status": "error", "message": f"Матч с ID {match_id} не найден.", "match_id": match_id}

        context = None

        return self.predict(
            home_team=match.get("home_team"),
            away_team=match.get("away_team"),
            league=match.get("competition", "РПЛ"),
            match_type="league",
            context=context,
            season_id=match.get("season_id"),
            match_id=match_id,
        )

    # ============================================================
    # PREDICT ROUND
    # ============================================================

    def predict_round(self, round_id: int, include_finished: bool = False) -> List[Dict[str, Any]]:
        matches = self._get_round_matches(round_id)
        results = []

        for match in matches:
            status = str(match.get("status", "")).lower()

            if not include_finished and status in self.FINISHED_STATUSES:
                logger.info("Skip finished match: id=%s", match["id"])
                continue

            try:
                results.append(self.predict_by_match_id(match["id"]))
            except Exception as e:
                logger.exception("Prediction error for match %s", match["id"])
                results.append({
                    "status": "error",
                    "match_id": match["id"],
                    "home_team": match.get("home_team"),
                    "away_team": match.get("away_team"),
                    "message": str(e),
                })

        return results

    # ============================================================
    # PREDICT ROUND BY NUMBER
    # ============================================================

    def predict_round_by_number(self, round_number: int, include_finished: bool = False) -> List[Dict[str, Any]]:
        season_id = self._get_current_season_id()

        if not season_id:
            return [{"status": "error", "message": "Сезон не найден"}]

        # Используем db.get_rounds() вместо прямого SQL
        rounds = self.db.get_rounds(season_id)
        round_id = None

        for r in rounds:
            if r["round_number"] == round_number:
                round_id = r["id"]
                break

        if round_id is None:
            return [{"status": "error", "message": f"Тур {round_number} не найден в БД"}]

        logger.info(
            "Predict round by number | round_number=%s | round_id=%s",
            round_number,
            round_id,
        )

        return self.predict_round(round_id, include_finished)

    # ============================================================
    # SEASON (через FAJDatabase)
    # ============================================================

    def _get_current_season_id(self) -> Optional[int]:
        """Ищет сезон 2026-2027 через FAJDatabase."""
        seasons = self.db.get_seasons()

        for season in seasons:
            name = season.get("name", "")
            if "РПЛ 2026-2027" in name or "2026-2027" in name:
                logger.info("Season detected: %s", season["id"])
                return season["id"]

        logger.error("Season 2026-2027 not found in database")
        return None

    # ============================================================
    # GET MATCH (через FAJDatabase)
    # ============================================================

    def _get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        """Получает матч с данными команд через FAJDatabase."""
        all_matches = self.db.get_matches()
        match = None

        for m in all_matches:
            if m["id"] == match_id:
                match = dict(m)
                break

        if not match:
            return None

        # Добавляем названия команд
        home = self.db.get_team(match["home_team_id"])
        away = self.db.get_team(match["away_team_id"])
        match["home_team"] = home["name"] if home else None
        match["away_team"] = away["name"] if away else None

        # Добавляем данные тура и сезона
        rounds = self.db.get_rounds()
        for r in rounds:
            if r["id"] == match["round_id"]:
                match["round_number"] = r["round_number"]
                match["season_id"] = r["season_id"]
                break

        return match

    def _get_round_matches(self, round_id: int) -> List[Dict[str, Any]]:
        """Получает матчи тура с данными команд через FAJDatabase."""
        all_matches = self.db.get_matches(round_id)
        result = []

        for match in all_matches:
            match_dict = dict(match)

            home = self.db.get_team(match["home_team_id"])
            away = self.db.get_team(match["away_team_id"])
            match_dict["home_team"] = home["name"] if home else None
            match_dict["away_team"] = away["name"] if away else None

            result.append(match_dict)

        return result

    # ============================================================
    # PASSPORT (через PassportManager)
    # ============================================================

    def _get_passport_with_rating(self, team_name: str, season_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        if season_id is not None:
            passport = self.passport_manager.get_current_passport_by_name(team_name, season_id)
        else:
            passport = self.passport_manager.get_current_passport_by_name(team_name)

        if not passport:
            logger.error("PASSPORT NOT FOUND | team=%s | season=%s", team_name, season_id)
            return None

        if not isinstance(passport, dict):
            logger.error("INVALID PASSPORT TYPE | team=%s", team_name)
            return None

        stored_rating = passport.get("faj_rating")

        if stored_rating is not None:
            try:
                rating = float(stored_rating)
            except (TypeError, ValueError):
                rating = self.passport_manager.calculate_rating(passport)
        else:
            rating = self.passport_manager.calculate_rating(passport)

        logger.info("FAJ RATING | team=%s | %.2f", team_name, rating)

        return {"passport": passport, "rating": float(rating)}

    # ============================================================
    # PASSPORT VALIDATION
    # ============================================================

    def _validate_passport_for_prediction(self, passport: Dict[str, Any], team_name: str) -> None:
        if not isinstance(passport, dict):
            raise ValueError(f"Invalid passport for {team_name}")

        required = ["attack", "defense", "control", "goalkeeper", "form"]
        missing = [f for f in required if f not in passport or passport.get(f) is None]

        if missing:
            raise ValueError(f"Passport for {team_name} missing required fields: {', '.join(missing)}")

        logger.info("PASSPORT VALIDATED | team=%s", team_name)

    # ============================================================
    # SNAPSHOTS (НОВОЕ)
    # ============================================================

    def _record_snapshots(self, match_id: int, home_data: Dict[str, Any],
                          away_data: Dict[str, Any], memory_state_id: str) -> None:
        """Записывает снапшоты состояния команд перед прогнозом."""
        try:
            home_passport = home_data["passport"]
            away_passport = away_data["passport"]

            # Home snapshot
            self.db.record_match_snapshot(
                match_id=match_id,
                team_id=home_passport.get("team_id"),
                data={
                    "attack": home_passport.get("attack"),
                    "defense": home_passport.get("defense"),
                    "control": home_passport.get("control"),
                    "press": home_passport.get("press"),
                    "tempo": home_passport.get("tempo"),
                    "transition": home_passport.get("transition"),
                    "finishing": home_passport.get("finishing"),
                    "coach_factor": home_passport.get("coach_factor"),
                    "squad_quality": home_passport.get("squad_quality"),
                    "form": home_passport.get("form"),
                    "fitness": home_passport.get("fitness"),
                    "fatigue": home_passport.get("fatigue"),
                    "morale": home_passport.get("morale"),
                },
                passport_id=home_passport.get("id"),
                passport_version=home_passport.get("version"),
                memory_state_id=memory_state_id,
            )

            # Away snapshot
            self.db.record_match_snapshot(
                match_id=match_id,
                team_id=away_passport.get("team_id"),
                data={
                    "attack": away_passport.get("attack"),
                    "defense": away_passport.get("defense"),
                    "control": away_passport.get("control"),
                    "press": away_passport.get("press"),
                    "tempo": away_passport.get("tempo"),
                    "transition": away_passport.get("transition"),
                    "finishing": away_passport.get("finishing"),
                    "coach_factor": away_passport.get("coach_factor"),
                    "squad_quality": away_passport.get("squad_quality"),
                    "form": away_passport.get("form"),
                    "fitness": away_passport.get("fitness"),
                    "fatigue": away_passport.get("fatigue"),
                    "morale": away_passport.get("morale"),
                },
                passport_id=away_passport.get("id"),
                passport_version=away_passport.get("version"),
                memory_state_id=memory_state_id,
            )

            logger.info("Snapshots recorded for match %s", match_id)

        except Exception as e:
            logger.warning("Failed to record snapshots for match %s: %s", match_id, e)

    # ============================================================
    # MEMORY STATE ID
    # ============================================================

    def _generate_memory_state_id(self) -> str:
        """Генерирует уникальный идентификатор состояния модели."""
        timestamp = datetime.now().isoformat()
        return f"FAJ-{self.VERSION}-{timestamp}"

    # ============================================================
    # PREDICTION HASH
    # ============================================================

    def _generate_prediction_hash(self, match_id: int, home_win: float, draw: float, away_win: float) -> str:
        """Генерирует хеш прогноза для защиты от дублей."""
        data = {
            "match_id": match_id,
            "model_version": self.VERSION,
            "home_win": round(home_win, 6),
            "draw": round(draw, 6),
            "away_win": round(away_win, 6),
        }
        encoded = json.dumps(data, sort_keys=True)
        return hashlib.sha256(encoded.encode()).hexdigest()

    # ============================================================
    # SAVE PREDICTION (с hash и memory_state_id)
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
        if not getattr(config, "SAVE_TO_GOLD_DATASET", True):
            logger.info("Prediction saving disabled")
            return None

        try:
            if match_id is None:
                match_id = self._find_match_by_teams(home_team, away_team)

            if match_id is None:
                logger.warning("Cannot save prediction: match not found | %s vs %s", home_team, away_team)
                return None

            probability = result.get("probability", {})
            confidence_data = result.get("confidence", {})

            home_win = probability.get("home", 0.0)
            draw = probability.get("draw", 0.0)
            away_win = probability.get("away", 0.0)

            confidence_value = confidence_data.get("overall", 0.5)
            try:
                confidence_value = float(confidence_value)
            except (TypeError, ValueError):
                confidence_value = 0.5

            # Генерируем prediction_hash
            prediction_hash = self._generate_prediction_hash(match_id, home_win, draw, away_win)

            pred_id = self.db.save_prediction(
                match_id=match_id,
                model_version=self.VERSION,
                algorithm="FAJ Engine",
                home_win=home_win,
                draw=draw,
                away_win=away_win,
                over25=result.get("extended", {}).get("total", {}).get("over_2_5", 0.0),
                over35=result.get("extended", {}).get("total", {}).get("over_3_5", 0.0),
                btts=result.get("extended", {}).get("btts", {}).get("yes", 0.0),
                confidence=int(max(0.0, min(confidence_value, 1.0)) * 100),
                prediction_source="FAJ Engine",
                prediction_hash=prediction_hash,
                memory_state_id=memory_state_id,
            )

            if not pred_id:
                logger.warning("Prediction save returned no ID")
                return None

            top_scores = result.get("extended", {}).get("top_scores", [])
            for score_data in top_scores:
                self.db.add_prediction_score(
                    prediction_id=pred_id,
                    score=f"{score_data.get('home', 0)}:{score_data.get('away', 0)}",
                    probability=score_data.get("probability", 0.0),
                    rank=score_data.get("rank", 0),
                )

            distributions = result.get("extended", {}).get("distributions", [])
            for dist in distributions:
                self.db.add_prediction_distribution(
                    prediction_id=pred_id,
                    home_goals=dist.get("home", 0),
                    away_goals=dist.get("away", 0),
                    probability=dist.get("probability", 0.0),
                )

            logger.info("Prediction saved | prediction_id=%s | match_id=%s | hash=%s",
                       pred_id, match_id, prediction_hash[:8])
            return pred_id

        except Exception as e:
            logger.exception("Save prediction error")
            return None

    # ============================================================
    # FIND MATCH (через FAJDatabase)
    # ============================================================

    def _find_match_by_teams(self, home_team: str, away_team: str) -> Optional[int]:
        """Находит матч по названиям команд через FAJDatabase."""
        all_matches = self.db.get_matches()

        for match in all_matches:
            home = self.db.get_team(match["home_team_id"])
            away = self.db.get_team(match["away_team_id"])

            if home and away:
                if home["name"] == home_team and away["name"] == away_team:
                    return match["id"]

        return None

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

_default_manager: Optional[PredictionManager] = None


def get_prediction_manager() -> PredictionManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PredictionManager()
    return _default_manager

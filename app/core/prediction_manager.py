#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1 — MEMORY HARDENED
Prediction Manager v2.4
=====================================================

РОЛЬ:
    Дирижёр prediction pipeline.

ПРАВИЛА:
    Manager работает с БД.
    Pipeline с БД НЕ работает.
    Engine с БД НЕ работает.

    Manager:
        1. GET PASSPORT + RATING (ОДИН РАЗ)
        2. GET PARAMETER STATE (ОДИН РАЗ)          ← НОВОЕ v2.4
        3. VALIDATE
        4. BUILD CONTEXT (включая parameters)      ← НОВОЕ v2.4
        5. FREEZE PREDICTION SNAPSHOT (FAIL → STOP)
        6. PIPELINE.run(same passport + same rating + parameters)  ← НОВОЕ v2.4
        7. NORMALIZE DISTRIBUTION ONCE
        8. FINAL_SCORE_ENGINE.calculate(same context + same distribution)
        9. BUILD FINAL PREDICTION
        10. SAVE_PREDICTION (с parameter_revision) ← НОВОЕ v2.4
        11. RETURN

    Prediction и Fact никогда не смешиваются.

ИСПРАВЛЕНИЯ v2.4:
    1. Чтение parameter state через get_current_parameter_state()
    2. Передача parameters в PredictionPipeline
    3. Сохранение parameter_revision в prediction
    4. Добавление parameters_used в результат
    5. Использование get_current_parameter_state() (НЕ legacy get_current_parameters())
"""

import hashlib
import json
import logging

from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Union

from app.core.prediction_pipeline import (
    PredictionPipeline,
    get_prediction_pipeline,
)

from app.core.final_score_engine import (
    FAJFinalScoreEngine,
    get_faj_final_score_engine,
)

from app.passports.passport_manager import (
    PassportManager,
    get_passport_manager,
)

from app.database import FAJDatabase
from app.config import config


logger = logging.getLogger(__name__)


class PredictionContextError(Exception):
    """Ошибка создания/фиксации Prediction Context."""
    pass


class PredictionManager:
    """Prediction Manager v2.4 — Memory Hardened + FAJ Final Score + Parameter State."""

    VERSION = "2.4"

    FINISHED_STATUSES: Set[str] = {
        "finished",
        "completed",
        "played",
        "ft",
        "ended",
        "full time",
    }

    def __init__(
        self,
        pipeline: Optional[PredictionPipeline] = None,
        passport_manager: Optional[PassportManager] = None,
        final_score_engine: Optional[FAJFinalScoreEngine] = None,
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

        self.final_engine = (
            final_score_engine
            or get_faj_final_score_engine()
        )

        self.db = db or FAJDatabase()

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
        context=None,
        season_id: Optional[int] = None,
        match_id: Optional[int] = None,
    ) -> Dict[str, Any]:

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
                season_id = self._get_season_id(league)

            if season_id is None:
                return {
                    "status": "error",
                    "message": f"Активный сезон не найден для лиги: {league}",
                }

            # ====================================================
            # 2. GET PASSPORT + RATING (ОДИН РАЗ)
            # ====================================================

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
                    "message": f"Паспорт не найден: {', '.join(missing)}",
                }

            # ====================================================
            # 3. GET PARAMETER STATE (ОДИН РАЗ — НОВОЕ v2.4)
            # ====================================================

            parameter_state = self.db.get_current_parameter_state()
            parameters = dict(parameter_state.get("parameters", {}))
            parameter_revision = int(parameter_state.get("revision", 0))

            logger.info(
                "PARAMETER STATE | revision=%s | parameters=%s",
                parameter_revision,
                parameters,
            )

            # ====================================================
            # 4. VALIDATE
            # ====================================================

            self._validate_passport_for_prediction(home_data["passport"], home_team)
            self._validate_passport_for_prediction(away_data["passport"], away_team)

            home_passport = home_data["passport"]
            away_passport = away_data["passport"]
            home_rating = home_data["rating"]
            away_rating = away_data["rating"]

            logger.info(
                "PREDICTION INPUT | %s vs %s | home_rating=%.2f | away_rating=%.2f",
                home_team,
                away_team,
                home_rating,
                away_rating,
            )

            # ====================================================
            # 5. MEMORY STATE
            # ====================================================

            memory_state_id = self._generate_memory_state_id()

            # ====================================================
            # 6. BUILD PREDICTION CONTEXT (immutable snapshot)
            # ====================================================

            match_date = self._get_match_date(match_id) if match_id else None

            home_context = self._build_prediction_context(
                team_id=home_passport.get("team_id"),
                season_id=season_id,
                team_name=home_team,
                match_date=match_date,
                passport=home_passport,
                rating=home_rating,
            )

            away_context = self._build_prediction_context(
                team_id=away_passport.get("team_id"),
                season_id=season_id,
                team_name=away_team,
                match_date=match_date,
                passport=away_passport,
                rating=away_rating,
            )

            # ====================================================
            # 7. FREEZE PREDICTION SNAPSHOT (FAIL → STOP)
            # ====================================================

            if match_id is not None:
                self._freeze_prediction_snapshot(
                    match_id=match_id,
                    home_context=home_context,
                    away_context=away_context,
                    memory_state_id=memory_state_id,
                )

            # ====================================================
            # 8. PIPELINE.run (same passport + same rating + parameters) — НОВОЕ v2.4
            # ====================================================

            result = self.pipeline.run(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating,
                home_team=home_team,
                away_team=away_team,
                league=league,
                parameters=parameters,  # ← НОВОЕ v2.4
            )

            if not isinstance(result, dict):
                return {
                    "status": "error",
                    "message": "PredictionPipeline вернул некорректный результат.",
                }

            if result.get("status") == "error":
                return result

            # ====================================================
            # 9. NORMALIZE DISTRIBUTION ONCE
            # ====================================================

            math_distribution = self._extract_math_distribution(result)
            normalized_distribution = self._normalize_distribution(math_distribution)

            # ====================================================
            # 10. FAJ FINAL SCORE ENGINE (same context + same distribution)
            # ====================================================

            faj_result = None

            if normalized_distribution and match_id is not None:
                try:
                    # home_advantage из контекста
                    home_advantage = home_context.get("home_advantage", 1.08)

                    faj_result = self.final_engine.calculate(
                        home_context=home_context,
                        away_context=away_context,
                        math_distribution=normalized_distribution,
                        home_advantage=home_advantage,
                    )

                    if faj_result and faj_result.get("faj_final_score") != "—":
                        logger.info(
                            "FAJ FINAL SCORE | %s vs %s | math=%s (%.2f%%) | faj=%s (%.2f%%)",
                            home_team,
                            away_team,
                            faj_result.get("math_most_likely_score"),
                            faj_result.get("math_probability", 0) * 100,
                            faj_result.get("faj_final_score"),
                            faj_result.get("faj_confidence", 0) * 100,
                        )
                    else:
                        logger.warning("FAJ FINAL SCORE FAILED | %s vs %s", home_team, away_team)
                        faj_result = None

                except Exception as e:
                    logger.exception("FAJ Final Score Engine error | %s vs %s", home_team, away_team)
                    faj_result = None

            # ====================================================
            # 11. MANAGER METADATA
            # ====================================================

            result["match_id"] = match_id
            result["home_team"] = home_team
            result["away_team"] = away_team
            result["league"] = league
            result["memory_state_id"] = memory_state_id
            result["manager_version"] = self.VERSION

            # ====================================================
            # 12. PARAMETER STATE В РЕЗУЛЬТАТ (НОВОЕ v2.4)
            # ====================================================

            result["parameter_revision"] = parameter_revision
            result["parameters_used"] = dict(parameters)

            # ====================================================
            # 13. ОБОГАЩАЕМ РЕЗУЛЬТАТ FAJ-ДАННЫМИ
            # ====================================================

            if faj_result and faj_result.get("faj_final_score") != "—":
                # Math данные
                result["math_most_likely_score"] = faj_result.get("math_most_likely_score")
                result["math_score_probability"] = faj_result.get("math_probability", 0.0)

                # FAJ данные
                result["faj_final_score"] = faj_result.get("faj_final_score")
                result["faj_confidence"] = faj_result.get("faj_confidence", 0.0)
                result["faj_score_ranking"] = faj_result.get("faj_score_ranking", [])

                # Decision factors
                decision_factors = faj_result.get("decision_factors", {})
                result["decision_factors"] = decision_factors
                result["context_availability"] = faj_result.get("context_availability", {})

                # История — из decision_factors["history"]
                history = decision_factors.get("history", {})
                result["history_count"] = history.get("count", 0)
                result["history_weight"] = history.get("weight", 0.0)

                # Engine версия — из self.final_engine
                result["engine_version"] = self.final_engine.VERSION
            else:
                # Если FAJ не сработал — только математика
                result["math_most_likely_score"] = result.get("score")
                result["math_score_probability"] = result.get("score_probability", 0.0)
                result["faj_final_score"] = None
                result["faj_confidence"] = None
                result["faj_score_ranking"] = []
                result["decision_factors"] = {}
                result["context_availability"] = {}
                result["history_count"] = 0
                result["history_weight"] = 0.0
                result["engine_version"] = None

            # ====================================================
            # 14. SAVE PREDICTION (с parameter_revision) — НОВОЕ v2.4
            # ====================================================

            pred_id = self._save_prediction(
                result=result,
                home_team=home_team,
                away_team=away_team,
                league=league,
                match_id=match_id,
                memory_state_id=memory_state_id,
                normalized_distribution=normalized_distribution,
                parameter_revision=parameter_revision,  # ← НОВОЕ v2.4
            )

            if pred_id is not None:
                result["prediction_id"] = pred_id

            return result

        except PredictionContextError as e:
            logger.error("PREDICTION CONTEXT ERROR | %s", str(e))
            return {
                "status": "error",
                "message": f"Ошибка фиксации контекста: {str(e)}",
                "home_team": home_team,
                "away_team": away_team,
                "match_id": match_id,
            }

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
    # BUILD PREDICTION CONTEXT
    # ============================================================

    def _build_prediction_context(
        self,
        team_id: Optional[int],
        season_id: Optional[int],
        team_name: str,
        match_date: Optional[str],
        passport: Dict[str, Any],
        rating: float,
    ) -> Dict[str, Any]:
        """
        Строит ЕДИНЫЙ контекст для PredictionPipeline и FinalScoreEngine.

        ВАЖНО:
            - passport и rating НЕ ЗАМЕНЯЮТСЯ историей
            - история добавляется как дополнительный контекст
            - если история недоступна — используется пустой контекст
        """
        context = {
            "team_id": team_id,
            "season_id": season_id,
            "team_name": team_name,
            "rating": rating,
            "passport": passport,  # НЕ ЗАМЕНЯЕТСЯ
            "home_advantage": 1.08,
            "last_match": None,
            "recent_matches": [],
            "form": None,
            "availability": {
                "rating": rating is not None,
                "passport": bool(passport),
                "base": False,
                "last_match": False,
                "recent_matches": False,
            }
        }

        # Добавляем историю, если есть данные
        if team_id is not None and season_id is not None and match_date is not None:
            try:
                db_context = self.db.get_team_recent_context(
                    team_id=team_id,
                    season_id=season_id,
                    match_date=match_date,
                    limit=5,
                )

                if db_context:
                    # ТОЛЬКО ДОБАВЛЯЕМ историю, НЕ ЗАМЕНЯЕМ passport/rating
                    context["last_match"] = db_context.get("last_match")
                    context["recent_matches"] = db_context.get("recent_matches", [])
                    context["form"] = db_context.get("form")
                    context["home_advantage"] = db_context.get("base", {}).get("home_advantage", 1.08)
                    context["availability"] = db_context.get("availability", context["availability"])

                    logger.info(
                        "CONTEXT BUILT | team=%s | rating=%.2f | matches=%s",
                        team_name,
                        rating,
                        len(context["recent_matches"]),
                    )

            except Exception as e:
                logger.warning("Failed to build context for %s: %s", team_name, e)

        return context

    # ============================================================
    # FREEZE PREDICTION SNAPSHOT (FAIL → STOP)
    # ============================================================

    def _freeze_prediction_snapshot(
        self,
        match_id: int,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
        memory_state_id: str,
    ) -> None:
        """
        Фиксирует snapshot состояния ДО prediction.

        ВАЖНО:
            - любая ошибка → PredictionContextError → prediction НЕ сохраняется
            - snapshot является обязательным для воспроизводимости
        """
        try:
            home_passport = home_context.get("passport", {})
            away_passport = away_context.get("passport", {})

            home_snapshot = {
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
            }

            away_snapshot = {
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
            }

            self.db.record_match_snapshot(
                match_id=match_id,
                team_id=home_context.get("team_id"),
                data=home_snapshot,
                passport_id=home_passport.get("id"),
                passport_version=home_passport.get("version"),
                memory_state_id=memory_state_id,
            )

            self.db.record_match_snapshot(
                match_id=match_id,
                team_id=away_context.get("team_id"),
                data=away_snapshot,
                passport_id=away_passport.get("id"),
                passport_version=away_passport.get("version"),
                memory_state_id=memory_state_id,
            )

            logger.info("SNAPSHOT FROZEN | match_id=%s | memory_state=%s", match_id, memory_state_id[:8])

        except Exception as e:
            logger.error("SNAPSHOT FAILED | match_id=%s | error=%s", match_id, str(e))
            raise PredictionContextError(f"Не удалось зафиксировать snapshot: {str(e)}")

    # ============================================================
    # EXTRACT MATH DISTRIBUTION
    # ============================================================

    def _extract_math_distribution(
        self,
        result: Dict[str, Any],
    ) -> Optional[Union[Dict[str, float], List[Dict[str, Any]]]]:
        """Извлекает math_distribution из результата Pipeline."""
        extended = result.get("extended", {})
        if not isinstance(extended, dict):
            return None

        # 1. distributions (приоритет)
        if "distributions" in extended:
            distributions = extended.get("distributions")
            if isinstance(distributions, list) and distributions:
                return distributions

        # 2. score_matrix
        if "score_matrix" in extended:
            score_matrix = extended.get("score_matrix")
            if isinstance(score_matrix, dict) and score_matrix:
                return score_matrix

        # 3. top_scores → преобразование
        top_scores = extended.get("top_scores", [])
        if isinstance(top_scores, list) and top_scores:
            result_list = []
            for item in top_scores:
                if isinstance(item, dict):
                    home = item.get("home")
                    away = item.get("away")
                    prob = item.get("probability")
                    if home is not None and away is not None and prob is not None:
                        try:
                            result_list.append({
                                "home": int(home),
                                "away": int(away),
                                "probability": float(prob),
                            })
                        except (TypeError, ValueError):
                            continue
            if result_list:
                return result_list

        return None

    # ============================================================
    # NORMALIZE DISTRIBUTION ONCE
    # ============================================================

    def _normalize_distribution(
        self,
        distribution: Optional[Union[Dict[str, float], List[Dict[str, Any]]]],
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Нормализует distribution ОДИН раз.

        Вход:
            - { "1:1": 0.128, "2:1": 0.109, ... }
            - [{"home": 1, "away": 1, "probability": 0.128}, ...]

        Выход:
            - [{"home": 1, "away": 1, "probability": 0.128}, ...]
            - probability нормализованы (сумма = 1.0)
            - пустые/некорректные элементы отброшены
        """
        if not distribution:
            return None

        items = []

        if isinstance(distribution, dict):
            for score_str, prob in distribution.items():
                try:
                    prob = float(prob)
                    if prob <= 0:
                        continue
                    if ":" in score_str:
                        parts = score_str.split(":", 1)
                        home = int(parts[0])
                        away = int(parts[1])
                        if home >= 0 and away >= 0:
                            items.append({"home": home, "away": away, "probability": prob})
                except (TypeError, ValueError):
                    continue

        elif isinstance(distribution, list):
            for item in distribution:
                if not isinstance(item, dict):
                    continue
                home = item.get("home")
                away = item.get("away")
                prob = item.get("probability")
                try:
                    home = int(home)
                    away = int(away)
                    prob = float(prob)
                    if home >= 0 and away >= 0 and prob > 0:
                        items.append({"home": home, "away": away, "probability": prob})
                except (TypeError, ValueError):
                    continue

        if not items:
            return None

        # Нормализация
        total = sum(item["probability"] for item in items)
        if total <= 0:
            return None

        for item in items:
            item["probability"] = round(item["probability"] / total, 6)

        # Сортировка по убыванию вероятности
        items.sort(key=lambda x: x["probability"], reverse=True)

        return items

    # ============================================================
    # SEASON
    # ============================================================

    def _get_season_id(self, league: str) -> Optional[int]:
        """Возвращает ID активного сезона для указанной лиги."""
        seasons = self.db.get_seasons()

        for season in seasons:
            season_league = season.get("league", "")
            status = season.get("status", "")

            if season_league == league and status == "active":
                logger.info("Season detected | league=%s | id=%s", league, season["id"])
                return season["id"]

        # Fallback: ищем по названию
        for season in seasons:
            name = season.get("name", "")
            season_league = season.get("league", "")
            if season_league == league and ("2026-2027" in name or "2026/27" in name):
                logger.info("Season detected (fallback) | league=%s | id=%s", league, season["id"])
                return season["id"]

        logger.error("Season not found | league=%s", league)
        return None

    # ============================================================
    # GET MATCH DATE
    # ============================================================

    def _get_match_date(self, match_id: int) -> Optional[str]:
        """Получает дату матча из БД."""
        try:
            match = self._get_match(match_id)
            if match:
                return match.get("date")
        except Exception as e:
            logger.warning("Failed to get match date for %s: %s", match_id, e)
        return None

    # ============================================================
    # PREDICT BY MATCH ID
    # ============================================================

    def predict_by_match_id(self, match_id: int) -> Dict[str, Any]:
        match = self._get_match(match_id)

        if not match:
            return {
                "status": "error",
                "message": f"Матч с ID {match_id} не найден.",
                "match_id": match_id,
            }

        return self.predict(
            home_team=match.get("home_team"),
            away_team=match.get("away_team"),
            league=match.get("competition", "РПЛ"),
            match_type="league",
            context=None,
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
            status = str(match.get("status", "")).strip().lower()

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
        season_id = self._get_season_id("РПЛ")

        if not season_id:
            return [{"status": "error", "message": "Сезон не найден"}]

        rounds = self.db.get_rounds(season_id)
        round_id = None

        for current_round in rounds:
            if current_round["round_number"] == round_number:
                round_id = current_round["id"]
                break

        if round_id is None:
            return [{"status": "error", "message": f"Тур {round_number} не найден в БД"}]

        logger.info("Predict round by number | round_number=%s | round_id=%s", round_number, round_id)
        return self.predict_round(round_id, include_finished)

    # ============================================================
    # GET MATCH
    # ============================================================

    def _get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        all_matches = self.db.get_matches()
        match = None

        for current_match in all_matches:
            if current_match["id"] == match_id:
                match = dict(current_match)
                break

        if not match:
            return None

        home = self.db.get_team(match["home_team_id"])
        away = self.db.get_team(match["away_team_id"])

        match["home_team"] = home["name"] if home else None
        match["away_team"] = away["name"] if away else None

        rounds = self.db.get_rounds()
        for current_round in rounds:
            if current_round["id"] == match["round_id"]:
                match["round_number"] = current_round["round_number"]
                match["season_id"] = current_round["season_id"]
                break

        return match

    # ============================================================
    # GET ROUND MATCHES
    # ============================================================

    def _get_round_matches(self, round_id: int) -> List[Dict[str, Any]]:
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
    # PASSPORT + RATING
    # ============================================================

    def _get_passport_with_rating(
        self,
        team_name: str,
        season_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:

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

        if stored_rating is None:
            logger.error("FAJ RATING MISSING | team=%s | season=%s", team_name, season_id)
            return None

        try:
            rating = float(stored_rating)
        except (TypeError, ValueError):
            logger.error("FAJ RATING INVALID | team=%s | value=%r", team_name, stored_rating)
            return None

        logger.info("FAJ RATING | team=%s | %.2f", team_name, rating)

        return {"passport": passport, "rating": rating}

    # ============================================================
    # PASSPORT VALIDATION
    # ============================================================

    def _validate_passport_for_prediction(self, passport: Dict[str, Any], team_name: str) -> None:
        if not isinstance(passport, dict):
            raise ValueError(f"Invalid passport for {team_name}")

        required = ["attack", "defense", "control", "goalkeeper", "form"]
        missing = [field for field in required if field not in passport or passport.get(field) is None]

        if missing:
            raise ValueError(f"Passport for {team_name} missing required fields: {', '.join(missing)}")

        logger.info("PASSPORT VALIDATED | team=%s", team_name)

    # ============================================================
    # MEMORY STATE ID
    # ============================================================

    def _generate_memory_state_id(self) -> str:
        timestamp = datetime.utcnow().isoformat(timespec="microseconds")
        return f"FAJ-MEM-{self.pipeline.VERSION}-{timestamp}"

    # ============================================================
    # PREDICTION HASH
    # ============================================================

    def _generate_prediction_hash(
        self,
        match_id: int,
        home_win: float,
        draw: float,
        away_win: float,
        faj_final_score: Optional[str] = None,
    ) -> str:
        data = {
            "match_id": match_id,
            "pipeline_version": self.pipeline.VERSION,
            "home_win": round(float(home_win), 6),
            "draw": round(float(draw), 6),
            "away_win": round(float(away_win), 6),
            "faj_final_score": faj_final_score,
            "parameter_revision": self._parameter_revision_snapshot,  # ← НОВОЕ v2.4
        }
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    # ============================================================
    # FIND MATCH (с учётом season_id)
    # ============================================================

    def _find_match_by_teams(
        self,
        home_team: str,
        away_team: str,
        season_id: Optional[int] = None,
        league: Optional[str] = None,
    ) -> Optional[int]:
        all_matches = self.db.get_matches()

        for match in all_matches:
            home = self.db.get_team(match["home_team_id"])
            away = self.db.get_team(match["away_team_id"])

            if not home or not away:
                continue

            if home["name"] != home_team or away["name"] != away_team:
                continue

            if season_id is not None:
                # Проверяем season_id через rounds
                rounds = self.db.get_rounds()
                for round_item in rounds:
                    if round_item["id"] == match["round_id"] and round_item["season_id"] == season_id:
                        return match["id"]

            if league is not None:
                if match.get("competition") == league:
                    return match["id"]

            # Если нет фильтров — возвращаем первый найденный
            if season_id is None and league is None:
                return match["id"]

        return None

    # ============================================================
    # SAVE PREDICTION (с parameter_revision) — НОВОЕ v2.4
    # ============================================================

    def _save_prediction(
        self,
        result: Dict[str, Any],
        home_team: str,
        away_team: str,
        league: str,
        match_id: Optional[int] = None,
        memory_state_id: Optional[str] = None,
        normalized_distribution: Optional[List[Dict[str, Any]]] = None,
        parameter_revision: Optional[int] = None,  # ← НОВОЕ v2.4
    ) -> Optional[int]:

        if not getattr(config, "SAVE_PREDICTIONS", True):
            logger.info("Prediction saving disabled")
            return None

        try:
            if match_id is None:
                match_id = self._find_match_by_teams(home_team, away_team, season_id=None, league=league)

            if match_id is None:
                logger.warning("Cannot save prediction: match not found | %s vs %s", home_team, away_team)
                return None

            probability = result.get("probability", {})
            home_win = float(probability.get("home", 0.0))
            draw = float(probability.get("draw", 0.0))
            away_win = float(probability.get("away", 0.0))

            confidence_data = result.get("confidence", {})
            try:
                confidence_value = float(confidence_data.get("overall", 0.5))
            except (TypeError, ValueError):
                confidence_value = 0.5
            confidence_value = max(0.0, min(1.0, confidence_value))

            # FAJ данные
            faj_final_score = result.get("faj_final_score")
            faj_confidence = result.get("faj_confidence")
            decision_factors = result.get("decision_factors", {})
            math_most_likely_score = result.get("math_most_likely_score")

            # HASH с parameter_revision (НОВОЕ v2.4)
            prediction_hash = self._generate_prediction_hash(
                match_id=match_id,
                home_win=home_win,
                draw=draw,
                away_win=away_win,
                faj_final_score=faj_final_score,
            )

            model_version = result.get("version", self.pipeline.VERSION)
            extended = result.get("extended", {})
            total = extended.get("total", {})
            btts = extended.get("btts", {})

            # Преобразуем parameter_revision в строку для БД
            parameter_revision_str = str(parameter_revision) if parameter_revision is not None else None

            # SAVE MAIN PREDICTION с parameter_revision (НОВОЕ v2.4)
            pred_id = self.db.save_prediction(
                match_id=match_id,
                model_version=model_version,
                algorithm="FAJ Engine",
                home_win=home_win,
                draw=draw,
                away_win=away_win,
                over25=total.get("over_2_5", result.get("over_2_5", 0.0)),
                over35=total.get("over_3_5", 0.0),
                btts=btts.get("yes", result.get("btts", 0.0)),
                confidence=int(confidence_value * 100),
                prediction_source="FAJ Engine",
                prediction_hash=prediction_hash,
                memory_state_id=memory_state_id,
                faj_final_score=faj_final_score,
                faj_confidence=int(faj_confidence * 100) if faj_confidence is not None else None,
                decision_factors=json.dumps(decision_factors) if decision_factors else None,
                parameter_revision=parameter_revision_str,  # ← НОВОЕ v2.4
            )

            if not pred_id:
                logger.warning("Prediction save returned no ID")
                return None

            # TOP SCORES — MATH
            top_scores = extended.get("top_scores", [])
            for score_data in top_scores:
                self.db.add_prediction_score(
                    prediction_id=pred_id,
                    score=f"{score_data.get('home', 0)}:{score_data.get('away', 0)}",
                    probability=score_data.get("probability", 0.0),
                    rank=score_data.get("rank", 0),
                    score_type="math",
                )

            # TOP SCORES — FAJ (используем faj_score)
            faj_ranking = result.get("faj_score_ranking", [])
            for item in faj_ranking:
                self.db.add_prediction_score(
                    prediction_id=pred_id,
                    score=item.get("score", "0:0"),
                    probability=item.get("faj_score", 0.0),
                    rank=item.get("rank", 0),
                    score_type="faj",
                )

            # DISTRIBUTION — используем нормализованную
            distributions_to_save = normalized_distribution or extended.get("distributions", [])
            for dist in distributions_to_save:
                self.db.add_prediction_distribution(
                    prediction_id=pred_id,
                    home_goals=dist.get("home", 0),
                    away_goals=dist.get("away", 0),
                    probability=dist.get("probability", 0.0),
                )

            logger.info(
                "Prediction saved | prediction_id=%s | match_id=%s | model_version=%s | hash=%s | math=%s | faj=%s | parameter_revision=%s",
                pred_id,
                match_id,
                model_version,
                prediction_hash[:8],
                math_most_likely_score,
                faj_final_score,
                parameter_revision,
            )

            return pred_id

        except Exception:
            logger.exception("Save prediction error")
            return None

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        return {
            "manager": "Prediction Manager",
            "version": self.VERSION,
            "pipeline_version": self.pipeline.VERSION,
            "engine_version": self.final_engine.VERSION,
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
FAJ Cycle — Main Orchestrator
===========================================================

Назначение:
    Безопасная оркестрация полного жизненного цикла FAJ.

Цепочка:

    BOOTSTRAP
        ↓
    SYSTEM STATUS
        ↓
    TEAMS / PASSPORTS
        ↓
    CALENDAR
        ↓
    HISTORICAL RESULTS
        ↓
    LEARNING
        ↓
    NEXT ROUND
        ↓
    PREDICTIONS

ВАЖНЫЕ ПРИНЦИПЫ:

    - SQLite only
    - Никаких DELETE
    - Никаких DROP
    - Не пересоздаём существующие rounds
    - Не пересоздаём существующие matches
    - Не запускаем sync_teams() автоматически
    - Парсеры не должны напрямую менять БД
    - Каждый этап имеет собственный результат
    - При критической ошибке цикл останавливается
    - Сначала диагностика, затем запись
===========================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

# ============================================================
# IMPORTS
# ============================================================

from app.database import FAJDatabase

from app.bootstrap import bootstrap_faj
from app.sync_engine import SyncEngine

from app.parsers.rpl_fixtures_parser import RPLFixturesParser
from app.parsers.rpl_results_parser import RPLResultsParser

from app.loaders.rpl_historical_importer import (
    import_historical_results,
)

from app.learning_engine import run_learning

from app.core.prediction_manager import PredictionManager


# ============================================================
# CONFIG
# ============================================================

CYCLE_VERSION = "12.1"

LEAGUE = "РПЛ"
SEASON_YEAR = "2026-2027"

EXPECTED_TEAMS = 16
EXPECTED_ROUNDS = 30
EXPECTED_MATCHES = 240

DEFAULT_RESULTS_ROUNDS = (1, 3)

MIN_MATCHES_FOR_LEARNING = 8


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | FAJ CYCLE | %(levelname)s | %(message)s",
    )


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _phase_result(
    phase: str,
    success: bool,
    **kwargs: Any,
) -> Dict[str, Any]:

    result = {
        "phase": phase,
        "success": success,
        "timestamp": _now(),
    }

    result.update(kwargs)

    return result


def _stop(
    phase: str,
    reason: str,
    **kwargs: Any,
) -> Dict[str, Any]:

    result = {
        "success": False,
        "cycle_version": CYCLE_VERSION,
        "phase": phase,
        "reason": reason,
        "timestamp": _now(),
    }

    result.update(kwargs)

    logger.error(
        "FAJ Cycle STOP | phase=%s | reason=%s",
        phase,
        reason,
    )

    return result


# ============================================================
# DATABASE STATUS
# ============================================================

def _get_database_status(db: FAJDatabase) -> Dict[str, Any]:
    """
    Безопасная диагностика БД.

    Ничего не изменяет.
    """

    try:
        status = db.get_status()

        return {
            "success": True,
            "status": status,
        }

    except Exception as exc:

        logger.exception("Ошибка получения статуса БД")

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# TEAM / PASSPORT STATUS
# ============================================================

def _get_team_status(db: FAJDatabase) -> Dict[str, Any]:
    """
    Проверка команд и паспортов.

    ВАЖНО:
        Здесь НИЧЕГО не создаётся автоматически.
    """

    try:

        teams = db.get_teams(league=LEAGUE)

        team_count = len(teams)

        passport_count = 0

        try:

            season_id = db.get_season_id(
                LEAGUE,
                SEASON_YEAR,
                "league",
            )

            if season_id:

                for team in teams:

                    passport = db.get_team_passport(
                        team["id"],
                        season_id,
                    )

                    if passport:
                        passport_count += 1

        except Exception as exc:

            logger.warning(
                "Не удалось полностью проверить паспорта: %s",
                exc,
            )

        return {
            "success": True,
            "teams": team_count,
            "passports": passport_count,
            "expected_teams": EXPECTED_TEAMS,
            "expected_passports": EXPECTED_TEAMS,
            "ready": (
                team_count >= EXPECTED_TEAMS
                and passport_count >= EXPECTED_TEAMS
            ),
        }

    except Exception as exc:

        logger.exception("Ошибка проверки команд")

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# SEASON STATUS
# ============================================================

def _get_season_status(db: FAJDatabase) -> Dict[str, Any]:

    try:

        season_id = db.get_season_id(
            LEAGUE,
            SEASON_YEAR,
            "league",
        )

        return {
            "success": True,
            "exists": season_id is not None,
            "season_id": season_id,
        }

    except Exception as exc:

        logger.exception("Ошибка проверки сезона")

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# ROUND STATUS
# ============================================================

def _get_round_status(
    db: FAJDatabase,
    season_id: int,
) -> Dict[str, Any]:

    try:

        rounds = db.get_rounds(season_id)

        round_numbers = []

        for row in rounds:

            if isinstance(row, dict):

                number = row.get("round_number")

            else:

                number = row["round_number"]

            if number is not None:
                round_numbers.append(int(number))

        round_numbers = sorted(set(round_numbers))

        return {
            "success": True,
            "rounds": len(round_numbers),
            "expected_rounds": EXPECTED_ROUNDS,
            "round_numbers": round_numbers,
            "complete": len(round_numbers) >= EXPECTED_ROUNDS,
        }

    except Exception as exc:

        logger.exception("Ошибка проверки туров")

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# MATCH STATUS
# ============================================================

def _get_match_status(
    db: FAJDatabase,
    season_id: int,
) -> Dict[str, Any]:

    try:

        rounds = db.get_rounds(season_id)

        total_matches = 0
        finished_matches = 0

        round_status = {}

        for round_row in rounds:

            if isinstance(round_row, dict):
                round_id = round_row["id"]
                round_number = round_row["round_number"]
            else:
                round_id = round_row["id"]
                round_number = round_row["round_number"]

            matches = db.get_matches(round_id)

            count = len(matches)

            finished = 0

            for match in matches:

                status = match.get("status")

                actual_home = match.get("actual_home")
                actual_away = match.get("actual_away")

                if (
                    status == "finished"
                    or (
                        actual_home is not None
                        and actual_away is not None
                    )
                ):
                    finished += 1

            total_matches += count
            finished_matches += finished

            round_status[int(round_number)] = {
                "round_id": round_id,
                "matches": count,
                "finished": finished,
            }

        return {
            "success": True,
            "matches": total_matches,
            "finished_matches": finished_matches,
            "expected_matches": EXPECTED_MATCHES,
            "complete": total_matches >= EXPECTED_MATCHES,
            "rounds": round_status,
        }

    except Exception as exc:

        logger.exception("Ошибка проверки матчей")

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# NEXT ROUND
# ============================================================

def _find_next_round_without_predictions(
    db: FAJDatabase,
    season_id: int,
) -> Optional[int]:
    """
    Находит первый тур, где существуют матчи без прогнозов.

    Уже сыгранные матчи не выбираются.
    """

    rounds = db.get_rounds(season_id)

    for round_row in sorted(
        rounds,
        key=lambda x: int(x["round_number"]),
    ):

        round_id = round_row["id"]
        round_number = int(round_row["round_number"])

        matches = db.get_matches(round_id)

        pending = False

        for match in matches:

            status = match.get("status")

            actual_home = match.get("actual_home")
            actual_away = match.get("actual_away")

            # Уже сыгранный матч пропускаем.
            if (
                status == "finished"
                or (
                    actual_home is not None
                    and actual_away is not None
                )
            ):
                continue

            match_id = match["id"]

            prediction = db.get_match_prediction(match_id)

            if not prediction:
                pending = True
                break

        if pending:
            return round_number

    return None


# ============================================================
# CALENDAR
# ============================================================

def _validate_calendar(
    db: FAJDatabase,
    season_id: int,
) -> Dict[str, Any]:
    """
    Проверяет существующий календарь.

    ВАЖНО:
        Эта функция НЕ создаёт rounds/matches.
    """

    try:

        round_status = _get_round_status(
            db,
            season_id,
        )

        if not round_status["success"]:
            return round_status

        match_status = _get_match_status(
            db,
            season_id,
        )

        if not match_status["success"]:
            return match_status

        errors = []

        if round_status["rounds"] != EXPECTED_ROUNDS:

            errors.append(
                f"Ожидалось {EXPECTED_ROUNDS} туров, "
                f"получено {round_status['rounds']}"
            )

        if match_status["matches"] != EXPECTED_MATCHES:

            errors.append(
                f"Ожидалось {EXPECTED_MATCHES} матчей, "
                f"получено {match_status['matches']}"
            )

        for round_number, data in match_status["rounds"].items():

            if data["matches"] != 8:

                errors.append(
                    f"Тур {round_number}: "
                    f"{data['matches']} матчей вместо 8"
                )

        return {
            "success": len(errors) == 0,
            "calendar_valid": len(errors) == 0,
            "rounds": round_status,
            "matches": match_status,
            "validation_errors": errors,
        }

    except Exception as exc:

        logger.exception("Ошибка проверки календаря")

        return {
            "success": False,
            "calendar_valid": False,
            "error": str(exc),
        }


# ============================================================
# PARSER DIAGNOSTIC
# ============================================================

def _inspect_fixture_parser() -> Dict[str, Any]:
    """
    Проверяет доступность parser API.

    Парсер здесь НЕ записывает данные в БД.
    """

    try:

        parser = RPLFixturesParser()

        if not hasattr(parser, "parse"):
            return {
                "success": False,
                "error": (
                    "RPLFixturesParser не содержит метода parse()"
                ),
            }

        return {
            "success": True,
            "parser": "RPLFixturesParser",
            "method": "parse",
            "available": True,
        }

    except Exception as exc:

        logger.exception("Ошибка инициализации fixture parser")

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# HISTORICAL RESULTS
# ============================================================

def _import_historical_results() -> Dict[str, Any]:

    try:

        result = import_historical_results()

        if not isinstance(result, dict):

            return {
                "success": False,
                "error": (
                    "Historical importer вернул "
                    "не Dict"
                ),
            }

        return result

    except Exception as exc:

        logger.exception(
            "Ошибка исторического импорта"
        )

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# LEARNING
# ============================================================

def _run_learning(
    force: bool = False,
) -> Dict[str, Any]:

    try:

        result = run_learning(
            force=force,
        )

        if not isinstance(result, dict):

            return {
                "success": False,
                "error": (
                    "Learning Engine вернул "
                    "не Dict"
                ),
            }

        return result

    except Exception as exc:

        logger.exception(
            "Ошибка Learning Engine"
        )

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# PREDICTION
# ============================================================

def _run_prediction(
    db: FAJDatabase,
    season_id: int,
    prediction_round: Optional[int] = None,
) -> Dict[str, Any]:

    try:

        manager = PredictionManager()

        if prediction_round is None:

            prediction_round = (
                _find_next_round_without_predictions(
                    db,
                    season_id,
                )
            )

        if prediction_round is None:

            return {
                "success": True,
                "predictions_created": 0,
                "round": None,
                "message": (
                    "Нет тура с матчами без прогнозов."
                ),
            }

        rounds = db.get_rounds(season_id)

        round_id = None

        for row in rounds:

            if int(row["round_number"]) == int(
                prediction_round
            ):
                round_id = row["id"]
                break

        if round_id is None:

            return {
                "success": False,
                "error": (
                    f"Тур {prediction_round} "
                    "не найден в БД."
                ),
            }

        # Проверяем наличие API PredictionManager.
        if not hasattr(manager, "predict_round"):

            return {
                "success": False,
                "error": (
                    "PredictionManager не содержит "
                    "метода predict_round()."
                ),
            }

        predictions = manager.predict_round(
            round_id,
            include_finished=False,
        )

        if predictions is None:
            predictions = []

        return {
            "success": True,
            "round": prediction_round,
            "round_id": round_id,
            "predictions_created": len(predictions),
            "predictions": predictions,
        }

    except Exception as exc:

        logger.exception(
            "Ошибка PredictionManager"
        )

        return {
            "success": False,
            "error": str(exc),
        }


# ============================================================
# MAIN CYCLE
# ============================================================

def run_faj_cycle(
    db_path: Optional[str] = None,
    results_rounds: Tuple[int, int] = DEFAULT_RESULTS_ROUNDS,
    force_learning: bool = False,
    prediction_round: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Полный цикл FAJ.

    Параметры:

        db_path:
            Зарезервировано для совместимости.
            FAJDatabase использует собственный DB_FILE.

        results_rounds:
            Диапазон исторических результатов.

        force_learning:
            Принудительный запуск обучения.

        prediction_round:
            Конкретный тур для прогноза.
            Если None — определяется автоматически.

        dry_run:
            True  = только диагностика.
            False = разрешить операции записи.

    ВАЖНО:

        Первый запуск рекомендуется делать:

            dry_run=True

        После проверки состояния:

            dry_run=False
    """

    started_at = _now()

    logger.info("=" * 70)
    logger.info(
        "FAJ CYCLE v%s START",
        CYCLE_VERSION,
    )
    logger.info(
        "dry_run=%s",
        dry_run,
    )
    logger.info("=" * 70)

    result: Dict[str, Any] = {
        "success": False,
        "cycle_version": CYCLE_VERSION,
        "started_at": started_at,
        "finished_at": None,
        "dry_run": dry_run,
        "phase": None,
        "bootstrap": None,
        "database": None,
        "system": None,
        "teams": None,
        "season": None,
        "calendar": None,
        "results": None,
        "learning": None,
        "predictions": None,
        "errors": [],
        "warnings": [],
    }

    # ========================================================
    # 1. DATABASE
    # ========================================================

    result["phase"] = "database"

    try:

        db = FAJDatabase()

        database_status = _get_database_status(db)

        result["database"] = database_status

        if not database_status["success"]:

            return _stop(
                "database",
                "Не удалось получить статус БД.",
                **result,
            )

    except Exception as exc:

        logger.exception(
            "Критическая ошибка БД"
        )

        return _stop(
            "database",
            str(exc),
            **result,
        )

    # ========================================================
    # 2. BOOTSTRAP
    # ========================================================

    result["phase"] = "bootstrap"

    try:

        bootstrap = bootstrap_faj()

        result["bootstrap"] = bootstrap

        if not bootstrap.get("ready", False):

            return _stop(
                "bootstrap",
                "Bootstrap сообщил, что система не готова.",
                **result,
            )

    except Exception as exc:

        logger.exception(
            "Ошибка bootstrap"
        )

        return _stop(
            "bootstrap",
            str(exc),
            **result,
        )

    # ========================================================
    # 3. TEAMS / PASSPORTS
    # ========================================================

    result["phase"] = "teams"

    team_status = _get_team_status(db)

    result["teams"] = team_status

    if not team_status["success"]:

        return _stop(
            "teams",
            "Не удалось проверить команды/паспорта.",
            **result,
        )

    if not team_status["ready"]:

        return _stop(
            "teams",
            (
                "Недостаточно команд или паспортов. "
                "Автоматическая синхронизация отключена "
                "для безопасности."
            ),
            **result,
        )

    # ========================================================
    # 4. SEASON
    # ========================================================

    result["phase"] = "season"

    season_status = _get_season_status(db)

    result["season"] = season_status

    if not season_status["success"]:

        return _stop(
            "season",
            "Ошибка проверки сезона.",
            **result,
        )

    if not season_status["exists"]:

        return _stop(
            "season",
            (
                f"Сезон {LEAGUE} "
                f"{SEASON_YEAR} не найден."
            ),
            **result,
        )

    season_id = season_status["season_id"]

    # ========================================================
    # 5. CALENDAR
    # ========================================================

    result["phase"] = "calendar"

    calendar = _validate_calendar(
        db,
        season_id,
    )

    result["calendar"] = calendar

    if not calendar.get(
        "calendar_valid",
        False,
    ):

        # Проверяем parser API только для диагностики.
        parser_status = _inspect_fixture_parser()

        result["calendar"]["parser"] = parser_status

        return _stop(
            "calendar",
            (
                "Существующий календарь "
                "не прошёл валидацию. "
                "Оркестратор ничего не пересоздаёт."
            ),
            **result,
        )

    # ========================================================
    # 6. DRY RUN
    # ========================================================

    if dry_run:

        result["phase"] = "dry_run"

        next_round = (
            _find_next_round_without_predictions(
                db,
                season_id,
            )
        )

        result["predictions"] = {
            "success": True,
            "dry_run": True,
            "next_round": next_round,
            "message": (
                "Диагностический режим. "
                "Запись результатов, обучение "
                "и прогнозирование не выполнялись."
            ),
        }

        result["success"] = True
        result["phase"] = "dry_run_complete"
        result["finished_at"] = _now()

        logger.info(
            "FAJ CYCLE DRY RUN COMPLETE"
        )

        return result

    # ========================================================
    # 7. HISTORICAL RESULTS
    # ========================================================

    result["phase"] = "results"

    logger.info(
        "Импорт исторических результатов..."
    )

    historical = _import_historical_results()

    result["results"] = historical

    if not historical.get("success", False):

        return _stop(
            "results",
            "Исторический импорт завершился ошибкой.",
            **result,
        )

    # ========================================================
    # 8. LEARNING
    # ========================================================

    result["phase"] = "learning"

    logger.info(
        "Запуск Learning Engine..."
    )

    learning = _run_learning(
        force=force_learning,
    )

    result["learning"] = learning

    if not learning.get("success", False):

        return _stop(
            "learning",
            "Learning Engine завершился ошибкой.",
            **result,
        )

    # ========================================================
    # 9. PREDICTIONS
    # ========================================================

    result["phase"] = "predictions"

    logger.info(
        "Запуск Prediction Manager..."
    )

    predictions = _run_prediction(
        db=db,
        season_id=season_id,
        prediction_round=prediction_round,
    )

    result["predictions"] = predictions

    if not predictions.get("success", False):

        return _stop(
            "predictions",
            "Prediction Manager завершился ошибкой.",
            **result,
        )

    # ========================================================
    # 10. COMPLETE
    # ========================================================

    result["success"] = True
    result["phase"] = "completed"
    result["finished_at"] = _now()

    logger.info("=" * 70)
    logger.info(
        "FAJ CYCLE v%s COMPLETE",
        CYCLE_VERSION,
    )
    logger.info("=" * 70)

    return result


# ============================================================
# CONVENIENCE API
# ============================================================

def run_cycle(
    dry_run: bool = True,
    force_learning: bool = False,
    prediction_round: Optional[int] = None,
) -> Dict[str, Any]:

    return run_faj_cycle(
        dry_run=dry_run,
        force_learning=force_learning,
        prediction_round=prediction_round,
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("FAJ PLATFORM v12.1")
    print("FAJ CYCLE")
    print("=" * 70)
    print()
    print(
        "Режим: DRY RUN"
    )
    print(
        "База данных НЕ изменяется."
    )
    print()

    cycle_result = run_faj_cycle(
        dry_run=True,
    )

    print()
    print("=" * 70)
    print("FAJ CYCLE RESULT")
    print("=" * 70)

    print(
        f"Success: {cycle_result.get('success')}"
    )

    print(
        f"Phase: {cycle_result.get('phase')}"
    )

    if cycle_result.get("teams"):

        teams = cycle_result["teams"]

        print(
            f"Teams: "
            f"{teams.get('teams', 0)}"
        )

        print(
            f"Passports: "
            f"{teams.get('passports', 0)}"
        )

    if cycle_result.get("season"):

        season = cycle_result["season"]

        print(
            f"Season: "
            f"{season.get('exists')}"
        )

    if cycle_result.get("calendar"):

        calendar = cycle_result["calendar"]

        if calendar.get("rounds"):

            print(
                f"Rounds: "
                f"{calendar['rounds'].get('rounds', 0)}"
            )

        if calendar.get("matches"):

            print(
                f"Matches: "
                f"{calendar['matches'].get('matches', 0)}"
            )

            print(
                f"Finished: "
                f"{calendar['matches'].get('finished_matches', 0)}"
            )

    if cycle_result.get("predictions"):

        print(
            f"Next round: "
            f"{cycle_result['predictions'].get('next_round')}"
        )

    if cycle_result.get("errors"):

        print()
        print("ERRORS:")

        for error in cycle_result["errors"]:

            print(
                f"  - {error}"
            )

    print()
    print("=" * 70)

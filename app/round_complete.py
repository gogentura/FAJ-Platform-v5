#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================
FAJ Platform v12.1
Round Complete Manager v3.0
===========================================================
НАЗНАЧЕНИЕ:
    Контроль завершения футбольного тура.
ЦЕПОЧКА:
    tour_manager
         ↓
    predict_round
         ↓
    import_facts
         ↓
    round_complete
         ↓
    learning_engine
         ↓
    следующий тур
ОТВЕТСТВЕННОСТЬ:
    1. Проверить существование тура.
    2. Проверить наличие матчей.
    3. Проверить наличие фактических результатов.
    4. Проверить наличие прогнозов FAJ.
    5. Проверить наличие экспертных прогнозов.
    6. Проверить, что результаты не заблокированы некорректно.
    7. Вернуть диагностический отчёт.
    8. При явной команде завершить тур.
    9. При явной команде передать управление обучению.
ВАЖНО:
    - SQLite only.
    - БД не удаляется.
    - DELETE не используется.
    - DROP не используется.
    - Исторические факты не изменяются.
    - Прогнозы не удаляются.
    - Календарь не изменяется.
    - Обучение не выполняется автоматически при простой проверке.
===========================================================
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)
# ============================================================
# RESULT OBJECT
# ============================================================
@dataclass
class RoundCheckResult:
    """
    Результат проверки тура.
    """
    success: bool = False
    round_number: Optional[int] = None
    total_matches: int = 0
    results_count: int = 0
    faj_predictions_count: int = 0
    expert_predictions_count: int = 0
    missing_results: List[int] = field(
        default_factory=list
    )
    missing_faj_predictions: List[int] = field(
        default_factory=list
    )
    missing_expert_predictions: List[int] = field(
        default_factory=list
    )
    locked_results: List[int] = field(
        default_factory=list
    )
    errors: List[str] = field(
        default_factory=list
    )
    warnings: List[str] = field(
        default_factory=list
    )
    message: str = ""
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "round_number": self.round_number,
            "total_matches": self.total_matches,
            "results_count": self.results_count,
            "faj_predictions_count": (
                self.faj_predictions_count
            ),
            "expert_predictions_count": (
                self.expert_predictions_count
            ),
            "missing_results": list(
                self.missing_results
            ),
            "missing_faj_predictions": list(
                self.missing_faj_predictions
            ),
            "missing_expert_predictions": list(
                self.missing_expert_predictions
            ),
            "locked_results": list(
                self.locked_results
            ),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "message": self.message,
        }
# ============================================================
# ROUND COMPLETE MANAGER
# ============================================================
class RoundCompleteManager:
    """
    Контроллер проверки и завершения тура.
    Не содержит бизнес-логику прогнозной модели.
    Не рассчитывает:
        - xG
        - Poisson
        - Monte Carlo
        - рейтинги
        - Team Passport
    Он только контролирует состояние тура.
    """
    VERSION = "3.0"
    def __init__(
        self,
        db: Any = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.db = db
        self.db_path = db_path
        if self.db is None:
            self.db = self._create_database()
    # ========================================================
    # DATABASE
    # ========================================================
    def _create_database(self) -> Any:
        """
        Создаёт объект database.py.
        Поддерживает несколько возможных API
        без изменения database.py.
        """
        try:
            from app.database import Database
        except ImportError as exc:
            logger.error(
                "Не удалось импортировать Database: %s",
                exc,
            )
            raise
        if self.db_path is not None:
            try:
                return Database(
                    db_path=self.db_path
                )
            except TypeError:
                pass
            try:
                return Database(
                    self.db_path
                )
            except TypeError:
                pass
        return Database()
    # ========================================================
    # PUBLIC API
    # ========================================================
    def check_round(
        self,
        round_number: int,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
    ) -> RoundCheckResult:
        """
        Полная проверка готовности тура.
        Ничего не изменяет в БД.
        """
        result = RoundCheckResult(
            round_number=int(round_number)
        )
        try:
            matches = self._get_round_matches(
                round_number=round_number,
                league=league,
                season_id=season_id,
            )
        except Exception as exc:
            result.errors.append(
                f"Ошибка получения матчей: {exc}"
            )
            result.message = (
                "Не удалось получить матчи тура."
            )
            return result
        if not matches:
            result.errors.append(
                "Матчи тура не найдены."
            )
            result.message = (
                f"Тур {round_number}: "
                "матчи не найдены."
            )
            return result
        result.total_matches = len(matches)
        for match in matches:
            match_id = self._match_id(match)
            if match_id is None:
                result.errors.append(
                    "Обнаружен матч без match_id."
                )
                continue
            # ------------------------------------------------
            # ФАКТ
            # ------------------------------------------------
            fact = self._get_match_result(
                match_id
            )
            if self._has_valid_result(fact):
                result.results_count += 1
            else:
                result.missing_results.append(
                    match_id
                )
            # ------------------------------------------------
            # FAJ ПРОГНОЗ
            # ------------------------------------------------
            faj_prediction = (
                self._get_latest_prediction(
                    match_id
                )
            )
            if faj_prediction:
                result.faj_predictions_count += 1
            else:
                result.missing_faj_predictions.append(
                    match_id
                )
            # ------------------------------------------------
            # ЭКСПЕРТ
            # ------------------------------------------------
            expert_predictions = (
                self._get_expert_predictions(
                    match_id
                )
            )
            if expert_predictions:
                result.expert_predictions_count += 1
            else:
                result.missing_expert_predictions.append(
                    match_id
                )
            # ------------------------------------------------
            # LOCK
            # ------------------------------------------------
            if self._is_result_locked(match_id):
                result.locked_results.append(
                    match_id
                )
        # ====================================================
        # FINAL DECISION
        # ====================================================
        if result.missing_results:
            result.errors.append(
                "Не все матчи имеют фактический результат."
            )
        if result.missing_faj_predictions:
            result.warnings.append(
                "Не для всех матчей найден прогноз FAJ."
            )
        if result.missing_expert_predictions:
            result.warnings.append(
                "Не для всех матчей найден прогноз эксперта."
            )
        # Для завершения тура обязательны факты.
        # Экспертный прогноз может отсутствовать,
        # если он не был введён.
        result.success = (
            result.total_matches > 0
            and not result.missing_results
        )
        if result.success:
            if result.missing_faj_predictions:
                result.message = (
                    f"Тур {round_number} имеет "
                    "все фактические результаты, "
                    "но часть прогнозов FAJ отсутствует."
                )
            elif result.missing_expert_predictions:
                result.message = (
                    f"Тур {round_number} готов "
                    "по фактам и FAJ. "
                    "Часть экспертных прогнозов отсутствует."
                )
            else:
                result.message = (
                    f"Тур {round_number} полностью готов."
                )
        else:
            result.message = (
                f"Тур {round_number} НЕ готов "
                "к завершению."
            )
        logger.info(
            "Round %s check: success=%s",
            round_number,
            result.success,
        )
        return result
    # ========================================================
    # COMPLETE
    # ========================================================
    def complete_round(
        self,
        round_number: int,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
        lock_results: bool = True,
    ) -> RoundCheckResult:
        """
        Завершает тур.
        Алгоритм:
            1. Проверка.
            2. Если факты неполные — остановка.
            3. Если всё готово — LOCK результатов.
            4. Возвращает отчёт.
        Обучение здесь НЕ запускается.
        """
        result = self.check_round(
            round_number=round_number,
            league=league,
            season_id=season_id,
        )
        if not result.success:
            logger.warning(
                "Тур %s не завершён: %s",
                round_number,
                result.message,
            )
            return result
        if lock_results:
            self._lock_round_results(
                round_number=round_number,
                league=league,
                season_id=season_id,
            )
            # Повторная проверка состояния.
            result = self.check_round(
                round_number=round_number,
                league=league,
                season_id=season_id,
            )
        if result.success:
            result.message = (
                f"Тур {round_number} завершён. "
                "Факты зафиксированы."
            )
        return result
    # ========================================================
    # LEARNING
    # ========================================================
    def run_learning(
        self,
        round_number: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Передаёт управление learning_engine.
        Сам алгоритм обучения здесь НЕ реализуется.
        Важно:
            метод вызывается явно.
        """
        try:
            from app.learning_engine import (
                run_learning,
            )
        except ImportError as exc:
            return {
                "success": False,
                "error": (
                    "Не удалось импортировать "
                    f"learning_engine: {exc}"
                ),
            }
        try:
            kwargs: Dict[str, Any] = {
                "force": force,
            }
            if self.db_path is not None:
                kwargs["db_path"] = self.db_path
            if round_number is not None:
                kwargs["round_number"] = (
                    round_number
                )
            try:
                learning_result = run_learning(
                    **kwargs
                )
            except TypeError:
                # Совместимость со старым API.
                if self.db_path is not None:
                    learning_result = run_learning(
                        db_path=self.db_path,
                        force=force,
                    )
                else:
                    learning_result = run_learning(
                        force=force
                    )
            return {
                "success": True,
                "result": learning_result,
            }
        except Exception as exc:
            logger.exception(
                "Ошибка обучения"
            )
            return {
                "success": False,
                "error": str(exc),
            }
    # ========================================================
    # FULL CYCLE
    # ========================================================
    def complete_and_learn(
        self,
        round_number: int,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
        lock_results: bool = True,
        run_learning: bool = True,
        force_learning: bool = False,
    ) -> Dict[str, Any]:
        """
        Полный контролируемый переход:
            check
              ↓
            complete
              ↓
            learning
        Если тур не готов:
            обучение НЕ запускается.
        """
        check = self.complete_round(
            round_number=round_number,
            league=league,
            season_id=season_id,
            lock_results=lock_results,
        )
        if not check.success:
            return {
                "success": False,
                "round_check": check.to_dict(),
                "learning": None,
                "message": (
                    "Тур не готов. "
                    "Обучение не запускалось."
                ),
            }
        if not run_learning:
            return {
                "success": True,
                "round_check": check.to_dict(),
                "learning": None,
                "message": (
                    "Тур завершён. "
                    "Обучение отключено."
                ),
            }
        learning = self.run_learning(
            round_number=round_number,
            force=force_learning,
        )
        if not learning.get("success"):
            return {
                "success": False,
                "round_check": check.to_dict(),
                "learning": learning,
                "message": (
                    "Тур завершён, "
                    "но обучение завершилось ошибкой."
                ),
            }
        return {
            "success": True,
            "round_check": check.to_dict(),
            "learning": learning,
            "message": (
                f"Тур {round_number} завершён "
                "и передан в обучение."
            ),
        }
    # ========================================================
    # MATCHES
    # ========================================================
    def _get_round_matches(
        self,
        round_number: int,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
    ) -> List[Any]:
        """
        Получает матчи тура.
        Поддерживает несколько вариантов API database.py.
        """
        round_number = int(round_number)
        # ----------------------------------------------------
        # Специализированный метод
        # ----------------------------------------------------
        for method_name in (
            "get_matches_by_round",
            "get_round_matches",
            "get_matches_for_round",
        ):
            method = getattr(
                self.db,
                method_name,
                None,
            )
            if not callable(method):
                continue
            attempts = [
                {
                    "round_number": round_number,
                    "league": league,
                    "season_id": season_id,
                },
                {
                    "round_number": round_number,
                },
                {
                    "round": round_number,
                },
            ]
            for kwargs in attempts:
                kwargs = {
                    key: value
                    for key, value in kwargs.items()
                    if value is not None
                }
                try:
                    matches = method(
                        **kwargs
                    )
                    if matches is None:
                        return []
                    return list(matches)
                except TypeError:
                    continue
        # ----------------------------------------------------
        # Через round ID
        # ----------------------------------------------------
        get_round = getattr(
            self.db,
            "get_round",
            None,
        )
        if callable(get_round):
            try:
                round_row = get_round(
                    round_number
                )
                if round_row:
                    round_id = self._row_value(
                        round_row,
                        "id",
                    )
                    if round_id is not None:
                        for method_name in (
                            "get_matches_by_round_id",
                            "get_matches",
                        ):
                            method = getattr(
                                self.db,
                                method_name,
                                None,
                            )
                            if not callable(method):
                                continue
                            try:
                                matches = method(
                                    round_id
                                )
                                if matches is not None:
                                    return list(
                                        matches
                                    )
                            except TypeError:
                                pass
            except Exception:
                pass
        # ----------------------------------------------------
        # Прямой SQL fallback.
        #
        # SELECT только.
        # ----------------------------------------------------
        return self._sql_get_round_matches(
            round_number
        )
    def _sql_get_round_matches(
        self,
        round_number: int,
    ) -> List[Any]:
        connection = self._get_connection()
        if connection is None:
            return []
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT *
                FROM matches
                WHERE round_id IN (
                    SELECT id
                    FROM rounds
                    WHERE round_number = ?
                )
                ORDER BY id
                """,
                (int(round_number),),
            )
            return cursor.fetchall()
        except Exception as exc:
            logger.error(
                "SQL ошибка получения матчей тура: %s",
                exc,
            )
            return []
        finally:
            try:
                connection.close()
            except Exception:
                pass
    # ========================================================
    # RESULT
    # ========================================================
    def _get_match_result(
        self,
        match_id: int,
    ) -> Any:
        method = getattr(
            self.db,
            "get_match_result",
            None,
        )
        if callable(method):
            try:
                return method(match_id)
            except Exception:
                return None
        return None
    @staticmethod
    def _has_valid_result(
        result: Any,
    ) -> bool:
        if result is None:
            return False
        home_goals = RoundCompleteManager._row_value(
            result,
            "home_goals",
        )
        away_goals = RoundCompleteManager._row_value(
            result,
            "away_goals",
        )
        if home_goals is None or away_goals is None:
            return False
        try:
            int(home_goals)
            int(away_goals)
            return (
                int(home_goals) >= 0
                and int(away_goals) >= 0
            )
        except (
            TypeError,
            ValueError,
        ):
            return False
    # ========================================================
    # FAJ PREDICTION
    # ========================================================
    def _get_latest_prediction(
        self,
        match_id: int,
    ) -> Any:
        method = getattr(
            self.db,
            "get_latest_prediction",
            None,
        )
        if not callable(method):
            return None
        try:
            return method(match_id)
        except Exception:
            return None
    # ========================================================
    # EXPERT PREDICTION
    # ========================================================
    def _get_expert_predictions(
        self,
        match_id: int,
    ) -> Any:
        method = getattr(
            self.db,
            "get_expert_predictions",
            None,
        )
        if callable(method):
            try:
                return method(match_id)
            except Exception:
                return None
        # ----------------------------------------------------
        # SQL fallback.
        # ----------------------------------------------------
        connection = self._get_connection()
        if connection is None:
            return None
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT *
                FROM expert_predictions
                WHERE match_id = ?
                ORDER BY created_at DESC
                """,
                (match_id,),
            )
            return cursor.fetchall()
        except Exception as exc:
            logger.error(
                "Ошибка expert_predictions: %s",
                exc,
            )
            return None
        finally:
            try:
                connection.close()
            except Exception:
                pass
    # ========================================================
    # LOCK CHECK
    # ========================================================
    def _is_result_locked(
        self,
        match_id: int,
    ) -> bool:
        method = getattr(
            self.db,
            "is_result_locked",
            None,
        )
        if not callable(method):
            return False
        try:
            return bool(
                method(match_id)
            )
        except Exception:
            return False
    # ========================================================
    # LOCK ROUND
    # ========================================================
    def _lock_round_results(
        self,
        round_number: int,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
    ) -> None:
        """
        Блокирует результаты всех матчей тура.
        Уже заблокированные результаты
        повторно не изменяются.
        """
        matches = self._get_round_matches(
            round_number=round_number,
            league=league,
            season_id=season_id,
        )
        lock_method = getattr(
            self.db,
            "lock_match_result",
            None,
        )
        if not callable(lock_method):
            logger.warning(
                "database.py не содержит "
                "lock_match_result()"
            )
            return
        for match in matches:
            match_id = self._match_id(match)
            if match_id is None:
                continue
            if self._is_result_locked(match_id):
                continue
            try:
                lock_method(match_id)
                logger.info(
                    "Результат матча %s заблокирован.",
                    match_id,
                )
            except Exception as exc:
                logger.error(
                    "Не удалось заблокировать "
                    "матч %s: %s",
                    match_id,
                    exc,
                )
    # ========================================================
    # CONNECTION
    # ========================================================
    def _get_connection(self) -> Any:
        for method_name in (
            "get_connection",
            "_get_connection",
            "connect",
        ):
            method = getattr(
                self.db,
                method_name,
                None,
            )
            if callable(method):
                try:
                    return method()
                except Exception:
                    continue
        return None
    # ========================================================
    # ROW HELPERS
    # ========================================================
    @staticmethod
    def _row_value(
        row: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        if row is None:
            return default
        if isinstance(row, dict):
            return row.get(
                key,
                default,
            )
        try:
            return row[key]
        except (
            KeyError,
            IndexError,
            TypeError,
        ):
            pass
        try:
            if hasattr(row, key):
                return getattr(
                    row,
                    key,
                )
        except Exception:
            pass
        return default
    @staticmethod
    def _match_id(
        match: Any,
    ) -> Optional[int]:
        value = (
            RoundCompleteManager._row_value(
                match,
                "id",
            )
        )
        if value is None:
            value = (
                RoundCompleteManager._row_value(
                    match,
                    "match_id",
                )
            )
        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return None
# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================
def check_round(
    round_number: int,
    db: Any = None,
    db_path: Optional[str] = None,
    league: Optional[str] = None,
    season_id: Optional[int] = None,
) -> RoundCheckResult:
    """
    Удобная функция проверки тура.
    """
    manager = RoundCompleteManager(
        db=db,
        db_path=db_path,
    )
    return manager.check_round(
        round_number=round_number,
        league=league,
        season_id=season_id,
    )
def complete_round(
    round_number: int,
    db: Any = None,
    db_path: Optional[str] = None,
    league: Optional[str] = None,
    season_id: Optional[int] = None,
    lock_results: bool = True,
) -> RoundCheckResult:
    """
    Удобная функция завершения тура.
    """
    manager = RoundCompleteManager(
        db=db,
        db_path=db_path,
    )
    return manager.complete_round(
        round_number=round_number,
        league=league,
        season_id=season_id,
        lock_results=lock_results,
    )
def complete_and_learn(
    round_number: int,
    db: Any = None,
    db_path: Optional[str] = None,
    league: Optional[str] = None,
    season_id: Optional[int] = None,
    lock_results: bool = True,
    run_learning: bool = True,
    force_learning: bool = False,
) -> Dict[str, Any]:
    """
    Удобная функция:
        завершить тур
             ↓
        запустить обучение
    """
    manager = RoundCompleteManager(
        db=db,
        db_path=db_path,
    )
    return manager.complete_and_learn(
        round_number=round_number,
        league=league,
        season_id=season_id,
        lock_results=lock_results,
        run_learning=run_learning,
        force_learning=force_learning,
    )
# ============================================================
# LOCAL DIAGNOSTIC
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )
    print("=" * 70)
    print("FAJ Platform v12.1")
    print("Round Complete Manager v3.0")
    print("=" * 70)
    manager = RoundCompleteManager()
    # --------------------------------------------------------
    # ВАЖНО:
    #
    # Локальный запуск только проверяет тур.
    # Он НЕ запускает обучение.
    # --------------------------------------------------------
    report = manager.check_round(
        round_number=1,
        league="РПЛ",
    )
    print()
    print(
        f"Тур: {report.round_number}"
    )
    print(
        f"Матчей: {report.total_matches}"
    )
    print(
        f"Фактов: {report.results_count}"
    )
    print(
        f"FAJ прогнозов: "
        f"{report.faj_predictions_count}"
    )
    print(
        f"Экспертных прогнозов: "
        f"{report.expert_predictions_count}"
    )
    if report.missing_results:
        print(
            "Нет результатов:",
            report.missing_results,
        )
    if report.missing_faj_predictions:
        print(
            "Нет прогнозов FAJ:",
            report.missing_faj_predictions,
        )
    if report.missing_expert_predictions:
        print(
            "Нет экспертных прогнозов:",
            report.missing_expert_predictions,
        )
    if report.errors:
        print()
        print("ОШИБКИ:")
        for error in report.errors:
            print(
                f" - {error}"
            )
    if report.warnings:
        print()
        print("ПРЕДУПРЕЖДЕНИЯ:")
        for warning in report.warnings:
            print(
                f" - {warning}"
            )
    print()
    print(
        "СТАТУС:",
        "ГОТОВ" if report.success else "НЕ ГОТОВ",
    )
    print()
    print(report.message)
    print("=" * 70)

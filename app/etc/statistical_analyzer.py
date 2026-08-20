#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Statistical Analyzer v1.0
============================================================

НАЗНАЧЕНИЕ:

    Статистический анализ завершённых матчей
    для Evolution Training Center.

Роль модуля:

    FACTS
      ↓
    MATCH STATISTICS
      ↓
    STATISTICAL ANALYZER
      ↓
    объективные показатели
      ↓
    ETC
      ↓
    LEARNING

ВАЖНЫЕ ПРИНЦИПЫ:

    1. Только анализ фактов.
    2. Никакого изменения исторических данных.
    3. Никакого изменения FAJ Rating.
    4. Никакого изменения model_parameters.
    5. Никакого обучения внутри этого модуля.
    6. Никакого DELETE.
    7. database.py не изменяется.
    8. Все результаты возвращаются вызывающему ETC.
    9. Observed xG берётся из match_statistics.xg.
   10. Счёт берётся из match_results.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


from app.database import FAJDatabase


logger = logging.getLogger(__name__)


ANALYZER_VERSION = "1.0"
ANALYZER_NAME = "FAJ ETC Statistical Analyzer v1.0"


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _average(values: List[float]) -> Optional[float]:
    if not values:
        return None

    return sum(values) / len(values)


def _round(
    value: Optional[float],
    digits: int = 4,
) -> Optional[float]:
    if value is None:
        return None

    return round(value, digits)


# ============================================================
# MAIN CLASS
# ============================================================

class StatisticalAnalyzer:
    """
    Статистический анализатор ETC.

    Отвечает за преобразование сырых фактов матчей
    в агрегированные статистические показатели.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC
    # ========================================================

    def analyze_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Анализирует переданный набор завершённых матчей.
        """

        result = {
            "success": False,
            "version": ANALYZER_VERSION,
            "engine": ANALYZER_NAME,

            "matches_analyzed": 0,
            "teams_analyzed": 0,

            "league_statistics": {},
            "team_statistics": [],

            "errors": [],
        }

        try:

            if not matches:
                result["errors"].append(
                    "Нет матчей для статистического анализа."
                )
                return result

            team_data: Dict[int, Dict[str, Any]] = {}

            valid_matches = 0

            for match in matches:

                analyzed = self._analyze_match(match)

                if analyzed is None:
                    continue

                valid_matches += 1

                self._add_match_to_team_statistics(
                    team_data,
                    analyzed,
                    home=True,
                )

                self._add_match_to_team_statistics(
                    team_data,
                    analyzed,
                    home=False,
                )

            result["matches_analyzed"] = valid_matches

            result["league_statistics"] = (
                self._build_league_statistics(matches)
            )

            result["team_statistics"] = (
                self._finalize_team_statistics(team_data)
            )

            result["teams_analyzed"] = len(
                result["team_statistics"]
            )

            result["success"] = True

            logger.info(
                "Statistical analysis completed: "
                "matches=%s teams=%s",
                result["matches_analyzed"],
                result["teams_analyzed"],
            )

            return result

        except Exception as exc:

            logger.exception(
                "Statistical Analyzer error"
            )

            result["errors"].append(str(exc))

            return result

    # ========================================================
    # SINGLE MATCH
    # ========================================================

    def analyze_match(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Анализ одного завершённого матча.
        """

        result = {
            "success": False,
            "version": ANALYZER_VERSION,
            "engine": ANALYZER_NAME,
            "match_id": match_id,
            "statistics": None,
            "errors": [],
        }

        try:

            matches = self.db.get_matches()

            match = next(
                (
                    item
                    for item in matches
                    if _safe_int(item.get("id")) == match_id
                ),
                None,
            )

            if not match:
                result["errors"].append(
                    f"Матч {match_id} не найден."
                )
                return result

            analyzed = self._analyze_match(match)

            if analyzed is None:
                result["errors"].append(
                    f"Недостаточно статистики для матча {match_id}."
                )
                return result

            result["statistics"] = analyzed
            result["success"] = True

            return result

        except Exception as exc:

            logger.exception(
                "Statistical analysis failed for match %s",
                match_id,
            )

            result["errors"].append(str(exc))

            return result

    # ========================================================
    # MATCH ANALYSIS
    # ========================================================

    def _analyze_match(
        self,
        match: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Собирает статистику одного матча.

        Основной источник:

            match_statistics

        Результат:

            match_results
        """

        match_id = _safe_int(match.get("id"))

        home_team_id = _safe_int(
            match.get("home_team_id")
        )

        away_team_id = _safe_int(
            match.get("away_team_id")
        )

        if not match_id:
            return None

        home_stats = self._get_team_match_statistics(
            match_id,
            home_team_id,
        )

        away_stats = self._get_team_match_statistics(
            match_id,
            away_team_id,
        )

        if not home_stats and not away_stats:
            return None

        match_result = self.db.get_match_result(
            match_id
        )

        if not match_result:
            return None

        home_goals = _safe_int(
            match_result.get("home_goals")
        )

        away_goals = _safe_int(
            match_result.get("away_goals")
        )

        return {
            "match_id": match_id,

            "home_team_id": home_team_id,
            "away_team_id": away_team_id,

            "home_goals": home_goals,
            "away_goals": away_goals,

            "home_result": self._result(
                home_goals,
                away_goals,
            ),

            "away_result": self._result(
                away_goals,
                home_goals,
            ),

            "home": self._calculate_team_match_metrics(
                home_stats,
                home_goals,
            ),

            "away": self._calculate_team_match_metrics(
                away_stats,
                away_goals,
            ),
        }

    # ========================================================
    # RAW MATCH STATISTICS
    # ========================================================

    def _get_team_match_statistics(
        self,
        match_id: int,
        team_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает фактическую статистику команды
        в конкретном матче.

        Источник:

            match_statistics
        """

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM match_statistics
                WHERE match_id = ?
                  AND team_id = ?
                LIMIT 1
                """,
                (
                    match_id,
                    team_id,
                ),
            )

            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)

        finally:
            conn.close()

    # ========================================================
    # MATCH METRICS
    # ========================================================

    def _calculate_team_match_metrics(
        self,
        stats: Optional[Dict[str, Any]],
        goals: int,
    ) -> Dict[str, Any]:
        """
        Рассчитывает производные показатели команды
        в одном матче.
        """

        if not stats:
            return {
                "available": False,
            }

        xg = _safe_float(
            stats.get("xg")
        )

        shots = _safe_int(
            stats.get("shots")
        )

        shots_on_target = _safe_int(
            stats.get("shots_on_target")
        )

        possession = _safe_float(
            stats.get("possession")
        )

        corners = _safe_int(
            stats.get("corners")
        )

        passes = _safe_int(
            stats.get("passes")
        )

        pass_accuracy = _safe_float(
            stats.get("pass_accuracy")
        )

        # ----------------------------------------------------
        # Реализация
        # ----------------------------------------------------

        if xg is not None and xg > 0:
            xg_conversion = goals / xg
        else:
            xg_conversion = None

        # ----------------------------------------------------
        # Удары → голы
        # ----------------------------------------------------

        if shots > 0:
            shot_conversion = goals / shots
        else:
            shot_conversion = None

        # ----------------------------------------------------
        # Удары в створ → голы
        # ----------------------------------------------------

        if shots_on_target > 0:
            shot_on_target_conversion = (
                goals / shots_on_target
            )
        else:
            shot_on_target_conversion = None

        # ----------------------------------------------------
        # xG → голы
        #
        # Положительное значение:
        # забили больше ожидаемого.
        #
        # Отрицательное:
        # забили меньше ожидаемого.
        # ----------------------------------------------------

        if xg is not None:
            finishing_overperformance = goals - xg
        else:
            finishing_overperformance = None

        return {
            "available": True,

            "xg": _round(xg),

            "goals": goals,

            "possession": _round(
                possession,
                2,
            ),

            "shots": shots,

            "shots_on_target": shots_on_target,

            "corners": corners,

            "fouls": _safe_int(
                stats.get("fouls")
            ),

            "yellow_cards": _safe_int(
                stats.get("yellow_cards")
            ),

            "red_cards": _safe_int(
                stats.get("red_cards")
            ),

            "big_chances": _safe_int(
                stats.get("big_chances")
            ),

            "saves": _safe_int(
                stats.get("saves")
            ),

            "passes": passes,

            "pass_accuracy": _round(
                pass_accuracy,
                2,
            ),

            "xg_conversion": _round(
                xg_conversion,
            ),

            "shot_conversion": _round(
                shot_conversion,
            ),

            "shot_on_target_conversion": _round(
                shot_on_target_conversion,
            ),

            "finishing_overperformance": _round(
                finishing_overperformance,
            ),
        }

    # ========================================================
    # TEAM AGGREGATION
    # ========================================================

    def _add_match_to_team_statistics(
        self,
        team_data: Dict[int, Dict[str, Any]],
        analyzed: Dict[str, Any],
        home: bool,
    ) -> None:
        """
        Добавляет один матч в накопительную статистику команды.
        """

        if home:

            team_id = analyzed["home_team_id"]
            metrics = analyzed["home"]

            opponent_goals = analyzed["away_goals"]

        else:

            team_id = analyzed["away_team_id"]
            metrics = analyzed["away"]

            opponent_goals = analyzed["home_goals"]

        if not metrics.get("available"):
            return

        if team_id not in team_data:

            team_data[team_id] = {
                "team_id": team_id,

                "matches": 0,

                "wins": 0,
                "draws": 0,
                "losses": 0,

                "goals_for": [],
                "goals_against": [],

                "xg": [],
                "possession": [],
                "shots": [],
                "shots_on_target": [],
                "corners": [],
                "fouls": [],
                "yellow_cards": [],
                "red_cards": [],
                "passes": [],
                "pass_accuracy": [],

                "xg_conversion": [],
                "shot_conversion": [],
                "shot_on_target_conversion": [],

                "finishing_overperformance": [],
            }

        data = team_data[team_id]

        data["matches"] += 1

        goals = _safe_int(
            metrics.get("goals")
        )

        data["goals_for"].append(
            goals
        )

        data["goals_against"].append(
            opponent_goals
        )

        if goals > opponent_goals:
            data["wins"] += 1

        elif goals < opponent_goals:
            data["losses"] += 1

        else:
            data["draws"] += 1

        self._append_if_number(
            data["xg"],
            metrics.get("xg"),
        )

        self._append_if_number(
            data["possession"],
            metrics.get("possession"),
        )

        self._append_if_number(
            data["shots"],
            metrics.get("shots"),
        )

        self._append_if_number(
            data["shots_on_target"],
            metrics.get("shots_on_target"),
        )

        self._append_if_number(
            data["corners"],
            metrics.get("corners"),
        )

        self._append_if_number(
            data["fouls"],
            metrics.get("fouls"),
        )

        self._append_if_number(
            data["yellow_cards"],
            metrics.get("yellow_cards"),
        )

        self._append_if_number(
            data["red_cards"],
            metrics.get("red_cards"),
        )

        self._append_if_number(
            data["passes"],
            metrics.get("passes"),
        )

        self._append_if_number(
            data["pass_accuracy"],
            metrics.get("pass_accuracy"),
        )

        self._append_if_number(
            data["xg_conversion"],
            metrics.get("xg_conversion"),
        )

        self._append_if_number(
            data["shot_conversion"],
            metrics.get("shot_conversion"),
        )

        self._append_if_number(
            data["shot_on_target_conversion"],
            metrics.get(
                "shot_on_target_conversion"
            ),
        )

        self._append_if_number(
            data["finishing_overperformance"],
            metrics.get(
                "finishing_overperformance"
            ),
        )

    @staticmethod
    def _append_if_number(
        target: List[float],
        value: Any,
    ) -> None:

        numeric = _safe_float(value)

        if numeric is not None:
            target.append(numeric)

    # ========================================================
    # FINAL TEAM STATISTICS
    # ========================================================

    def _finalize_team_statistics(
        self,
        team_data: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        result = []

        for team_id, data in team_data.items():

            matches = max(
                1,
                data["matches"],
            )

            goals_for_avg = (
                sum(data["goals_for"])
                / matches
            )

            goals_against_avg = (
                sum(data["goals_against"])
                / matches
            )

            points = (
                data["wins"] * 3
                + data["draws"]
            )

            result.append(
                {
                    "team_id": team_id,

                    "matches": data["matches"],

                    "wins": data["wins"],
                    "draws": data["draws"],
                    "losses": data["losses"],

                    "points": points,

                    "points_per_match": round(
                        points / matches,
                        4,
                    ),

                    "win_rate": round(
                        data["wins"] / matches,
                        4,
                    ),

                    "draw_rate": round(
                        data["draws"] / matches,
                        4,
                    ),

                    "loss_rate": round(
                        data["losses"] / matches,
                        4,
                    ),

                    "goals_for_avg": round(
                        goals_for_avg,
                        4,
                    ),

                    "goals_against_avg": round(
                        goals_against_avg,
                        4,
                    ),

                    "xg_avg": _round(
                        _average(data["xg"])
                    ),

                    "possession_avg": _round(
                        _average(data["possession"]),
                        2,
                    ),

                    "shots_avg": _round(
                        _average(data["shots"])
                    ),

                    "shots_on_target_avg": _round(
                        _average(
                            data["shots_on_target"]
                        )
                    ),

                    "corners_avg": _round(
                        _average(data["corners"])
                    ),

                    "fouls_avg": _round(
                        _average(data["fouls"])
                    ),

                    "yellow_cards_avg": _round(
                        _average(
                            data["yellow_cards"]
                        )
                    ),

                    "red_cards_avg": _round(
                        _average(
                            data["red_cards"]
                        )
                    ),

                    "passes_avg": _round(
                        _average(data["passes"])
                    ),

                    "pass_accuracy_avg": _round(
                        _average(
                            data["pass_accuracy"]
                        ),
                        2,
                    ),

                    "xg_conversion_avg": _round(
                        _average(
                            data["xg_conversion"]
                        )
                    ),

                    "shot_conversion_avg": _round(
                        _average(
                            data["shot_conversion"]
                        )
                    ),

                    "shot_on_target_conversion_avg": _round(
                        _average(
                            data[
                                "shot_on_target_conversion"
                            ]
                        )
                    ),

                    "finishing_overperformance_avg": _round(
                        _average(
                            data[
                                "finishing_overperformance"
                            ]
                        )
                    ),
                }
            )

        result.sort(
            key=lambda item: item["points"],
            reverse=True,
        )

        return result

    # ========================================================
    # LEAGUE STATISTICS
    # ========================================================

    def _build_league_statistics(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Рассчитывает общие показатели по батчу матчей.
        """

        total_matches = 0

        total_goals = 0

        home_wins = 0
        draws = 0
        away_wins = 0

        xg_values: List[float] = []

        shots_values: List[float] = []
        shots_on_target_values: List[float] = []

        possession_values: List[float] = []

        corners_values: List[float] = []

        btts_count = 0

        over25_count = 0

        over35_count = 0

        for match in matches:

            match_id = _safe_int(
                match.get("id")
            )

            result = self.db.get_match_result(
                match_id
            )

            if not result:
                continue

            home_goals = _safe_int(
                result.get("home_goals")
            )

            away_goals = _safe_int(
                result.get("away_goals")
            )

            total_matches += 1

            total_goals += (
                home_goals
                + away_goals
            )

            if home_goals > away_goals:
                home_wins += 1

            elif home_goals < away_goals:
                away_wins += 1

            else:
                draws += 1

            if (
                home_goals > 0
                and away_goals > 0
            ):
                btts_count += 1

            total = (
                home_goals
                + away_goals
            )

            if total > 2:
                over25_count += 1

            if total > 3:
                over35_count += 1

            home_team_id = _safe_int(
                match.get("home_team_id")
            )

            away_team_id = _safe_int(
                match.get("away_team_id")
            )

            home_stats = (
                self._get_team_match_statistics(
                    match_id,
                    home_team_id,
                )
            )

            away_stats = (
                self._get_team_match_statistics(
                    match_id,
                    away_team_id,
                )
            )

            for stats in (
                home_stats,
                away_stats,
            ):

                if not stats:
                    continue

                xg = _safe_float(
                    stats.get("xg")
                )

                shots = _safe_float(
                    stats.get("shots")
                )

                shots_on_target = _safe_float(
                    stats.get("shots_on_target")
                )

                possession = _safe_float(
                    stats.get("possession")
                )

                corners = _safe_float(
                    stats.get("corners")
                )

                if xg is not None:
                    xg_values.append(xg)

                if shots is not None:
                    shots_values.append(shots)

                if shots_on_target is not None:
                    shots_on_target_values.append(
                        shots_on_target
                    )

                if possession is not None:
                    possession_values.append(
                        possession
                    )

                if corners is not None:
                    corners_values.append(
                        corners
                    )

        if total_matches == 0:
            return {}

        return {
            "matches": total_matches,

            "goals_total": total_goals,

            "goals_per_match": round(
                total_goals / total_matches,
                4,
            ),

            "home_win_rate": round(
                home_wins / total_matches,
                4,
            ),

            "draw_rate": round(
                draws / total_matches,
                4,
            ),

            "away_win_rate": round(
                away_wins / total_matches,
                4,
            ),

            "btts_rate": round(
                btts_count / total_matches,
                4,
            ),

            "over25_rate": round(
                over25_count / total_matches,
                4,
            ),

            "over35_rate": round(
                over35_count / total_matches,
                4,
            ),

            "observed_xg_per_team_avg": _round(
                _average(xg_values)
            ),

            "shots_per_team_avg": _round(
                _average(shots_values)
            ),

            "shots_on_target_per_team_avg": _round(
                _average(
                    shots_on_target_values
                )
            ),

            "possession_per_team_avg": _round(
                _average(
                    possession_values
                ),
                2,
            ),

            "corners_per_team_avg": _round(
                _average(corners_values)
            ),
        }

    # ========================================================
    # RESULT
    # ========================================================

    @staticmethod
    def _result(
        goals_for: int,
        goals_against: int,
    ) -> str:

        if goals_for > goals_against:
            return "W"

        if goals_for < goals_against:
            return "L"

        return "D"


# ============================================================
# PUBLIC API
# ============================================================

def analyze_statistics(
    matches: List[Dict[str, Any]],
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API статистического анализатора.
    """

    analyzer = StatisticalAnalyzer(
        db=db
    )

    return analyzer.analyze_matches(
        matches
    )


def analyze_match_statistics(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Анализ одного матча.
    """

    analyzer = StatisticalAnalyzer(
        db=db
    )

    return analyzer.analyze_match(
        match_id
    )


# ============================================================
# CLI
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

    db = FAJDatabase()

    matches = db.get_matches()

    analyzer = StatisticalAnalyzer(
        db=db
    )

    result = analyzer.analyze_matches(
        matches
    )

    print("=" * 70)
    print("FAJ ETC — STATISTICAL ANALYZER v1.0")
    print("=" * 70)

    print(
        f"Успех: {result['success']}"
    )

    print(
        f"Матчей: {result['matches_analyzed']}"
    )

    print(
        f"Команд: {result['teams_analyzed']}"
    )

    print()

    league = result["league_statistics"]

    if league:

        print("LEAGUE STATISTICS")
        print("-" * 70)

        print(
            f"Голов/матч: "
            f"{league.get('goals_per_match')}"
        )

        print(
            f"BTTS: "
            f"{league.get('btts_rate')}"
        )

        print(
            f"Over 2.5: "
            f"{league.get('over25_rate')}"
        )

        print(
            f"Over 3.5: "
            f"{league.get('over35_rate')}"
        )

        print(
            f"Observed xG: "
            f"{league.get('observed_xg_per_team_avg')}"
        )

        print()

    print("TEAM STATISTICS")
    print("-" * 70)

    for team in result["team_statistics"]:

        print(
            f"Team {team['team_id']} | "
            f"MP={team['matches']} | "
            f"PPM={team['points_per_match']:.3f} | "
            f"xG={team['xg_avg']} | "
            f"GF={team['goals_for_avg']:.3f} | "
            f"GA={team['goals_against_avg']:.3f}"
        )

    if result["errors"]:

        print()

        for error in result["errors"]:
            print(
                f"❌ {error}"
            )

    print("=" * 70)

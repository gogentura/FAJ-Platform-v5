#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
RPL HISTORICAL IMPORTER
===========================================================

Назначение:
    Однократный контролируемый импорт исторических
    результатов РПЛ 2026/27.

Источник исходного набора:
    manual historical dataset.

ВАЖНО:

    NB-Bet НЕ является постоянным источником данных.

    Этот модуль:
        - не парсит NB-Bet;
        - не удаляет данные;
        - не очищает таблицы;
        - не создаёт матчи;
        - не создаёт паспорта;
        - не запускает обучение;
        - не рассчитывает прогнозы.

    Он только:

        1. берёт заранее проверенный набор результатов;
        2. ищет соответствующий матч в matches;
        3. проверяет round + home_team + away_team;
        4. записывает результат;
        5. сохраняет источник как historical/manual_import;
        6. безопасно повторяется.

===========================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.database import Database


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

SEASON_YEAR = "2026-2027"
LEAGUE = "РПЛ"

SOURCE = "historical/manual_import"
PARSER_VERSION = "rpl_historical_importer_v1.0"

EXPECTED_MATCHES = 24


# ============================================================
# HISTORICAL DATASET
# ============================================================
#
# ВАЖНО:
# Здесь находятся НЕ URL и НЕ парсер.
#
# Это зафиксированный исторический набор.
#
# Формат:
#
# {
#     "round": 1,
#     "date": "2026-07-24",
#     "home_team": "ЦСКА",
#     "away_team": "Балтика",
#     "home_goals": 2,
#     "away_goals": 1,
# }
#
# Счёт каждого матча должен быть проверен ДО внесения сюда.
#
# ============================================================

HISTORICAL_RESULTS: List[Dict[str, Any]] = [

    # --------------------------------------------------------
    # TOUR 1
    # --------------------------------------------------------

    {
        "round": 1,
        "date": "2026-07-24",
        "home_team": "ЦСКА",
        "away_team": "Балтика",
        "home_goals": 2,
        "away_goals": 1,
    },

    {
        "round": 1,
        "date": "2026-07-25",
        "home_team": "Рубин",
        "away_team": "Краснодар",
        "home_goals": 1,
        "away_goals": 3,
    },

    {
        "round": 1,
        "date": "2026-07-25",
        "home_team": "Спартак",
        "away_team": "Родина",
        "home_goals": 3,
        "away_goals": 0,
    },

    {
        "round": 1,
        "date": "2026-07-25",
        "home_team": "Акрон",
        "away_team": "Зенит",
        "home_goals": 0,
        "away_goals": 5,
    },

    {
        "round": 1,
        "date": "2026-07-25",
        "home_team": "Динамо Москва",
        "away_team": "Крылья Советов",
        "home_goals": 0,
        "away_goals": 0,
    },

    {
        "round": 1,
        "date": "2026-07-25",
        "home_team": "Факел",
        "away_team": "Динамо Махачкала",
        "home_goals": 1,
        "away_goals": 2,
    },

    {
        "round": 1,
        "date": "2026-07-26",
        "home_team": "Оренбург",
        "away_team": "Ростов",
        "home_goals": 2,
        "away_goals": 1,
    },

    {
        "round": 1,
        "date": "2026-07-26",
        "home_team": "Локомотив",
        "away_team": "Ахмат",
        "home_goals": 1,
        "away_goals": 1,
    },


    # --------------------------------------------------------
    # TOUR 2
    # --------------------------------------------------------

    {
        "round": 2,
        "date": "2026-07-31",
        "home_team": "Ахмат",
        "away_team": "Спартак",
        "home_goals": 1,
        "away_goals": 2,
    },

    {
        "round": 2,
        "date": "2026-08-02",
        "home_team": "Краснодар",
        "away_team": "Факел",
        "home_goals": 3,
        "away_goals": 2,
    },

    {
        "round": 2,
        "date": "2026-08-02",
        "home_team": "Оренбург",
        "away_team": "Зенит",
        "home_goals": 0,
        "away_goals": 3,
    },

    {
        "round": 2,
        "date": "2026-08-01",
        "home_team": "Балтика",
        "away_team": "Динамо Москва",
        "home_goals": 2,
        "away_goals": 1,
    },

    {
        "round": 2,
        "date": "2026-08-01",
        "home_team": "Динамо Махачкала",
        "away_team": "Локомотив",
        "home_goals": 2,
        "away_goals": 1,
    },

    {
        "round": 2,
        "date": "2026-08-01",
        "home_team": "ЦСКА",
        "away_team": "Крылья Советов",
        "home_goals": 1,
        "away_goals": 1,
    },

    {
        "round": 2,
        "date": "2026-08-01",
        "home_team": "Акрон",
        "away_team": "Рубин",
        "home_goals": 1,
        "away_goals": 2,
    },

    {
        "round": 2,
        "date": "2026-07-31",
        "home_team": "Родина",
        "away_team": "Ростов",
        "home_goals": 2,
        "away_goals": 4,
    },


    # --------------------------------------------------------
    # TOUR 3
    # --------------------------------------------------------
    #
    # В ЭТОМ БЛОКЕ СЧЁТЫ ДОЛЖНЫ БЫТЬ ВСТАВЛЕНЫ
    # ИЗ ПРОВЕРЕННОГО ИСТОРИЧЕСКОГО НАБОРА.
    #
    # НЕ ЗАПОЛНЯЕМ ИХ ДОГАДКАМИ.
    #
    # --------------------------------------------------------

    {
        "round": 3,
        "date": "2026-08-08",
        "home_team": "Локомотив",
        "away_team": "Акрон",
        "home_goals": None,
        "away_goals": None,
    },

    {
        "round": 3,
        "date": "2026-08-08",
        "home_team": "Крылья Советов",
        "away_team": "Балтика",
        "home_goals": None,
        "away_goals": None,
    },

    {
        "round": 3,
        "date": "2026-08-08",
        "home_team": "Ростов",
        "away_team": "ЦСКА",
        "home_goals": None,
        "away_goals": None,
    },

    {
        "round": 3,
        "date": "2026-08-09",
        "home_team": "Динамо Москва",
        "away_team": "Динамо Махачкала",
        "home_goals": None,
        "away_goals": None,
    },

    {
        "round": 3,
        "date": "2026-08-09",
        "home_team": "Зенит",
        "away_team": "Родина",
        "home_goals": 1,
        "away_goals": 2,
    },

    {
        "round": 3,
        "date": "2026-08-09",
        "home_team": "Спартак",
        "away_team": "Краснодар",
        "home_goals": 1,
        "away_goals": 2,
    },

    {
        "round": 3,
        "date": "2026-08-09",
        "home_team": "Рубин",
        "away_team": "Оренбург",
        "home_goals": 1,
        "away_goals": 1,
    },

    {
        "round": 3,
        "date": "2026-08-10",
        "home_team": "Факел",
        "away_team": "Ахмат",
        "home_goals": 0,
        "away_goals": 0,
    },
]


# ============================================================
# RESULT
# ============================================================

def _result() -> Dict[str, Any]:
    return {
        "source": SOURCE,
        "parser": PARSER_VERSION,
        "season": SEASON_YEAR,
        "league": LEAGUE,

        "found": 0,
        "inserted": 0,
        "updated": 0,
        "already_exists": 0,

        "skipped": 0,
        "errors": 0,

        "matches_without_db_record": 0,

        "rounds_updated": [],

        "details": [],

        "started_at": datetime.now().isoformat(),
        "finished_at": None,
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_dataset() -> None:
    """
    Проверяет сам исторический набор ДО обращения к БД.
    """

    if len(HISTORICAL_RESULTS) != EXPECTED_MATCHES:
        raise ValueError(
            f"Исторический набор содержит "
            f"{len(HISTORICAL_RESULTS)} матчей, "
            f"ожидалось {EXPECTED_MATCHES}"
        )

    for index, item in enumerate(
        HISTORICAL_RESULTS,
        start=1,
    ):

        required = (
            "round",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
        )

        for field in required:

            if field not in item:
                raise ValueError(
                    f"Матч #{index}: "
                    f"отсутствует {field}"
                )

        if item["home_team"] == item["away_team"]:
            raise ValueError(
                f"Матч #{index}: "
                "одинаковые команды"
            )

        if not (
            1 <= int(item["round"]) <= 30
        ):
            raise ValueError(
                f"Матч #{index}: "
                f"некорректный тур {item['round']}"
            )

        # Нельзя импортировать непроверенный счёт.
        if (
            item["home_goals"] is None
            or item["away_goals"] is None
        ):
            raise ValueError(
                f"Матч #{index}: "
                f"{item['home_team']} — "
                f"{item['away_team']} "
                "не имеет проверенного счёта"
            )


# ============================================================
# IMPORTER
# ============================================================

class RPLHistoricalImporter:

    def __init__(
        self,
        db: Optional[Database] = None,
    ) -> None:

        self.db = db or Database()

    # ========================================================
    # PUBLIC
    # ========================================================

    def import_results(
        self,
        rounds: Optional[List[int]] = None,
    ) -> Dict[str, Any]:

        result = _result()

        started = datetime.now()

        try:

            validate_dataset()

        except Exception as exc:

            result["errors"] = 1
            result["details"].append(
                {
                    "status": "error",
                    "stage": "dataset_validation",
                    "message": str(exc),
                }
            )

            result["finished_at"] = (
                datetime.now().isoformat()
            )

            return result

        if rounds is None:
            selected_rounds = {1, 2, 3}
        else:
            selected_rounds = {
                int(value)
                for value in rounds
            }

        dataset = [
            item
            for item in HISTORICAL_RESULTS
            if int(item["round"])
            in selected_rounds
        ]

        result["found"] = len(dataset)

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            for item in dataset:

                self._import_one(
                    cursor=cursor,
                    item=item,
                    result=result,
                )

            conn.commit()

        except Exception:

            conn.rollback()
            raise

        finally:

            conn.close()

        result["rounds_updated"] = sorted(
            {
                int(item["round"])
                for item in dataset
                if item["round"]
            }
        )

        result["finished_at"] = (
            datetime.now().isoformat()
        )

        elapsed = (
            datetime.now() - started
        ).total_seconds()

        logger.info(
            "Historical import completed: "
            "found=%s inserted=%s updated=%s "
            "existing=%s errors=%s elapsed=%.2fs",
            result["found"],
            result["inserted"],
            result["updated"],
            result["already_exists"],
            result["errors"],
            elapsed,
        )

        return result

    # ========================================================
    # ONE MATCH
    # ========================================================

    def _import_one(
        self,
        cursor,
        item: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:

        round_number = int(
            item["round"]
        )

        home_team = item[
            "home_team"
        ]

        away_team = item[
            "away_team"
        ]

        # ----------------------------------------------------
        # Ищем матч только по:
        #
        # round + home_team + away_team
        #
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                m.id,
                m.actual_home,
                m.actual_away,
                m.status
            FROM matches m

            JOIN rounds r
                ON r.id = m.round_id

            JOIN teams ht
                ON ht.id = m.home_team_id

            JOIN teams at
                ON at.id = m.away_team_id

            WHERE
                r.round_number = ?
                AND ht.name = ?
                AND at.name = ?

            LIMIT 1
            """,
            (
                round_number,
                home_team,
                away_team,
            ),
        )

        match = cursor.fetchone()

        if not match:

            result[
                "matches_without_db_record"
            ] += 1

            result["skipped"] += 1

            result["details"].append(
                {
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "status": "missing_match",
                }
            )

            return

        match_id = match["id"]

        home_goals = int(
            item["home_goals"]
        )

        away_goals = int(
            item["away_goals"]
        )

        # ----------------------------------------------------
        # Проверяем существующий результат
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                home_goals,
                away_goals
            FROM match_results
            WHERE match_id = ?
            LIMIT 1
            """,
            (match_id,),
        )

        existing_result = (
            cursor.fetchone()
        )

        # ----------------------------------------------------
        # Результат уже есть
        # ----------------------------------------------------

        if existing_result:

            same_score = (
                int(
                    existing_result[
                        "home_goals"
                    ]
                )
                == home_goals
                and
                int(
                    existing_result[
                        "away_goals"
                    ]
                )
                == away_goals
            )

            if same_score:

                result[
                    "already_exists"
                ] += 1

                result["details"].append(
                    {
                        "match_id": match_id,
                        "round": round_number,
                        "home_team": home_team,
                        "away_team": away_team,
                        "status": "already_exists",
                    }
                )

                return

            # ------------------------------------------------
            # Результат существует, но отличается.
            #
            # Не перетираем молча.
            # ------------------------------------------------

            result["errors"] += 1

            result["details"].append(
                {
                    "match_id": match_id,
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "status": "score_conflict",
                    "database_score": (
                        existing_result[
                            "home_goals"
                        ],
                        existing_result[
                            "away_goals"
                        ],
                    ),
                    "import_score": (
                        home_goals,
                        away_goals,
                    ),
                }
            )

            return

        # ----------------------------------------------------
        # INSERT RESULT
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT OR IGNORE INTO match_results (
                match_id,
                home_goals,
                away_goals,
                home_penalty_goals,
                away_penalty_goals
            )
            VALUES (?, ?, ?, 0, 0)
            """,
            (
                match_id,
                home_goals,
                away_goals,
            ),
        )

        inserted = (
            cursor.rowcount
        )

        # ----------------------------------------------------
        # UPDATE MATCH
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE matches
            SET
                actual_home = ?,
                actual_away = ?,
                status = 'finished',
                updated_at = ?
            WHERE id = ?
            """,
            (
                home_goals,
                away_goals,
                datetime.now().isoformat(),
                match_id,
            ),
        )

        if inserted:

            result["inserted"] += 1

            result["details"].append(
                {
                    "match_id": match_id,
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": (
                        f"{home_goals}:"
                        f"{away_goals}"
                    ),
                    "status": "inserted",
                    "source": SOURCE,
                }
            )

        else:

            result["already_exists"] += 1


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def import_rpl_historical_results(
    rounds: Optional[List[int]] = None,
) -> Dict[str, Any]:

    importer = RPLHistoricalImporter()

    return importer.import_results(
        rounds=rounds
    )


# ============================================================
# LOCAL TEST
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

    result = (
        import_rpl_historical_results(
            rounds=[1, 2, 3]
        )
    )

    print()
    print("=" * 70)
    print(
        "FAJ RPL HISTORICAL IMPORT"
    )
    print("=" * 70)

    for key in (
        "found",
        "inserted",
        "updated",
        "already_exists",
        "skipped",
        "errors",
        "matches_without_db_record",
    ):
        print(
            f"{key}: {result[key]}"
        )

    print()

    for item in result[
        "details"
    ]:

        print(item)

    print("=" * 70)

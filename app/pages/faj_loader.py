#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v13.0
FAJ Loader — загрузка фактических результатов и статистики РПЛ

Загружает:
    - 24 матча
    - 3 тура
    - фактический счет
    - xG
    - удары
    - удары в створ
    - владение
    - угловые
    - желтые карточки
    - точность передач

ВАЖНО:
    Никаких искусственных 0 для отсутствующей статистики.
    Если показатель реально не найден — записывается NULL/не записывается.
"""

import os
import sqlite3
import streamlit as st


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

DB_PATH = os.path.join(BASE_DIR, "data", "faj.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# ============================================================
# 24 ФАКТИЧЕСКИХ МАТЧА РПЛ
# ============================================================
#
# Формат:
#
# (
#     тур,
#     хозяева,
#     гости,
#     голы хозяев,
#     голы гостей,
#     xG хозяев,
#     xG гостей,
#     удары хозяев,
#     удары гостей,
#     удары в створ хозяев,
#     удары в створ гостей,
#     владение хозяев,
#     владение гостей,
#     угловые хозяев,
#     угловые гостей,
#     ЖК хозяев,
#     ЖК гостей,
#     точность передач хозяев,
#     точность передач гостей
# )
#
# None = показатель не найден.
# НИКАКИХ ФИКТИВНЫХ НУЛЕЙ.
#

MATCH_DATA = [

    # ========================================================
    # ТУР 1
    # ========================================================

    (
        1,
        "ЦСКА",
        "Балтика",
        2, 1,
        2.25, 1.52,
        18, 14,
        5, 3,
        65, 35,
        6, 2,
        1, 1,
        83, 66
    ),

    (
        1,
        "Рубин",
        "Краснодар",
        1, 3,
        0.61, 2.76,
        5, 19,
        3, 8,
        28, 72,
        2, 4,
        0, 3,
        53, 85
    ),

    (
        1,
        "Спартак",
        "Родина",
        3, 0,
        2.50, 0.55,
        25, 7,
        9, 4,
        60, 40,
        12, 4,
        0, 3,
        87, 78
    ),

    (
        1,
        "Акрон",
        "Зенит",
        0, 5,
        0.69, 2.52,
        11, 20,
        4, 10,
        52, 48,
        9, 5,
        3, 2,
        84, 86
    ),

    (
        1,
        "Динамо",
        "Крылья Советов",
        0, 0,
        1.25, 1.23,
        21, 12,
        5, 4,
        66, 34,
        6, 2,
        None, None,
        84, 68
    ),

    (
        1,
        "Факел",
        "Динамо Мх",
        1, 2,
        1.16, 0.85,
        13, 11,
        3, 4,
        57, 43,
        8, 2,
        0, 1,
        83, 75
    ),

    (
        1,
        "Оренбург",
        "Ростов",
        2, 1,
        0.82, 0.69,
        9, 14,
        3, 5,
        42, 58,
        3, 6,
        3, 6,
        60, 72
    ),

    (
        1,
        "Локомотив",
        "Ахмат",
        1, 1,
        1.27, 1.24,
        16, 21,
        2, 7,
        47, 53,
        2, 5,
        3, 0,
        79, 80
    ),


    # ========================================================
    # ТУР 2
    # ========================================================

    (
        2,
        "Родина",
        "Ростов",
        2, 4,
        0.59, 2.05,
        8, 24,
        2, 10,
        49, 51,
        2, 9,
        2, 1,
        64, 69
    ),

    (
        2,
        "Акрон",
        "Рубин",
        1, 2,
        0.63, 1.59,
        9, 16,
        4, 5,
        64, 36,
        5, 3,
        1, 2,
        83, 75
    ),

    (
        2,
        "ЦСКА",
        "Крылья Советов",
        1, 1,
        1.87, 0.52,
        18, 11,
        6, 5,
        55, 45,
        2, 5,
        0, 3,
        86, 79
    ),

    (
        2,
        "Динамо Мх",
        "Локомотив",
        2, 1,
        2.24, 1.73,
        12, 13,
        5, 5,
        41, 59,
        1, 9,
        1, 2,
        73, 80
    ),

    (
        2,
        "Балтика",
        "Динамо",
        2, 1,
        1.34, 0.76,
        8, 14,
        4, 4,
        28, 72,
        2, 8,
        2, 0,
        54, 80
    ),

    (
        2,
        "Оренбург",
        "Зенит",
        0, 3,
        1.02, 0.80,
        13, 12,
        2, 5,
        31, 69,
        5, 2,
        3, 1,
        78, 90
    ),

    (
        2,
        "Краснодар",
        "Факел",
        3, 2,
        0.83, 2.10,
        11, 13,
        5, 3,
        56, 44,
        2, 4,
        4, 0,
        85, 76
    ),

    (
        2,
        "Ахмат",
        "Спартак",
        1, 2,
        0.93, 0.55,
        4, 11,
        3, 4,
        27, 73,
        1, 5,
        1, 2,
        62, 87
    ),


    # ========================================================
    # ТУР 3
    # ========================================================

    (
        3,
        "Локомотив",
        "Акрон",
        0, 0,
        1.79, 1.05,
        23, 15,
        3, 3,
        58, 42,
        2, 6,
        4, 1,
        85, 79
    ),

    (
        3,
        "Крылья Советов",
        "Балтика",
        0, 2,
        0.43, 1.15,
        5, 13,
        1, 5,
        67, 33,
        2, 5,
        1, 0,
        83, 70
    ),

    (
        3,
        "Динамо",
        "Динамо Мх",
        3, 1,
        1.08, 1.14,
        11, 8,
        6, 2,
        67, 33,
        4, 2,
        3, 3,
        81, 64
    ),

    (
        3,
        "ЦСКА",
        "Ростов",
        0, 0,
        0.83, 0.84,
        13, 13,
        3, 4,
        56, 44,
        1, 3,
        1, 2,
        78, 71
    ),

    (
        3,
        "Зенит",
        "Родина",
        1, 2,
        1.59, 0.76,
        22, 7,
        6, 3,
        66, 34,
        11, 3,
        1, 1,
        87, 77
    ),

    (
        3,
        "Спартак",
        "Краснодар",
        1, 2,
        1.32, 1.08,
        16, 16,
        3, 4,
        63, 37,
        6, 7,
        1, 3,
        78, 71
    ),

    (
        3,
        "Рубин",
        "Оренбург",
        1, 1,
        0.64, 0.86,
        10, 13,
        1, 3,
        62, 38,
        7, 1,
        2, 1,
        74, 65
    ),

    (
        3,
        "Факел",
        "Ахмат",
        0, 0,
        1.58, 0.35,
        16, 9,
        3, 2,
        54, 46,
        10, 4,
        2, 1,
        74, 76
    ),
]


# ============================================================
# TEAM NAME NORMALIZATION
# ============================================================

TEAM_ALIASES = {
    "Акрон Тольятти": "Акрон",
    "Спартак Москва": "Спартак",
    "Динамо Москва": "Динамо",
    "Динамо Махачкала": "Динамо Мх",
    "Локомотив Москва": "Локомотив",
}


def normalize_team_name(name):
    return TEAM_ALIASES.get(name, name)


# ============================================================
# FIND TEAM
# ============================================================

def get_team_id(cursor, team_name):

    team_name = normalize_team_name(team_name)

    cursor.execute(
        "SELECT id FROM teams WHERE name = ?",
        (team_name,)
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    return None


# ============================================================
# FIND MATCH
# ============================================================

def get_match_id(cursor, season_id, round_number, home_id, away_id):

    cursor.execute(
        """
        SELECT m.id
        FROM matches m
        JOIN rounds r
            ON r.id = m.round_id
        WHERE r.season_id = ?
          AND r.round_number = ?
          AND m.home_team_id = ?
          AND m.away_team_id = ?
        LIMIT 1
        """,
        (
            season_id,
            round_number,
            home_id,
            away_id
        )
    )

    row = cursor.fetchone()

    return row[0] if row else None


# ============================================================
# SAVE MATCH STATISTICS
# ============================================================

def save_statistics(
    cursor,
    match_id,
    team_id,
    possession,
    shots,
    shots_on_target,
    corners,
    yellow_cards,
    xg,
    pass_accuracy
):

    # Удаляем старую запись этого матча/команды,
    # чтобы повторная загрузка не создавала дубликаты.

    cursor.execute(
        """
        DELETE FROM match_statistics
        WHERE match_id = ?
          AND team_id = ?
        """,
        (
            match_id,
            team_id
        )
    )

    columns = [
        "match_id",
        "team_id",
        "possession",
        "shots",
        "shots_on_target",
        "corners",
        "yellow_cards",
        "xg",
        "pass_accuracy"
    ]

    values = [
        match_id,
        team_id,
        possession,
        shots,
        shots_on_target,
        corners,
        yellow_cards,
        xg,
        pass_accuracy
    ]

    # Если значение None — не вставляем его как фальшивый 0.
    # Формируем INSERT только для реально имеющихся данных.

    valid_columns = []
    valid_values = []

    for column, value in zip(columns, values):

        if value is not None:
            valid_columns.append(column)
            valid_values.append(value)

    placeholders = ", ".join(["?"] * len(valid_values))
    column_sql = ", ".join(valid_columns)

    cursor.execute(
        f"""
        INSERT INTO match_statistics
        ({column_sql})
        VALUES ({placeholders})
        """,
        valid_values
    )


# ============================================================
# MAIN
# ============================================================

def main():

    st.set_page_config(
        page_title="FAJ Loader",
        layout="wide"
    )

    st.title("📥 FAJ Loader")
    st.subheader("РПЛ 2026/27 — загрузка 24 фактических матчей")

    st.info(
        "Будут загружены фактические результаты и статистика "
        "1–3 туров РПЛ. Всего 24 матча."
    )

    st.metric(
        "Матчей к загрузке",
        len(MATCH_DATA)
    )

    if st.button(
        "🔥 ЗАГРУЗИТЬ ВСЕ 24 МАТЧА",
        type="primary",
        use_container_width=True
    ):

        conn = None

        try:

            conn = get_connection()
            cursor = conn.cursor()

            # ====================================================
            # SEASON
            # ====================================================

            cursor.execute(
                """
                SELECT id
                FROM seasons
                WHERE name = ?
                LIMIT 1
                """,
                ("2026-2027",)
            )

            season_row = cursor.fetchone()

            if not season_row:

                cursor.execute(
                    """
                    INSERT INTO seasons (name)
                    VALUES (?)
                    """,
                    ("2026-2027",)
                )

                season_id = cursor.lastrowid

            else:

                season_id = season_row[0]

            # ====================================================
            # LOAD
            # ====================================================

            loaded = 0
            skipped = []

            progress = st.progress(0)
            status = st.empty()

            for index, row in enumerate(MATCH_DATA):

                (
                    round_number,
                    home_name,
                    away_name,
                    home_goals,
                    away_goals,
                    home_xg,
                    away_xg,
                    home_shots,
                    away_shots,
                    home_sot,
                    away_sot,
                    home_possession,
                    away_possession,
                    home_corners,
                    away_corners,
                    home_yellow,
                    away_yellow,
                    home_pass_accuracy,
                    away_pass_accuracy
                ) = row

                home_name = normalize_team_name(home_name)
                away_name = normalize_team_name(away_name)

                status.text(
                    f"Загрузка {index + 1}/{len(MATCH_DATA)}: "
                    f"{home_name} — {away_name}"
                )

                # ----------------------------------------------
                # TEAM IDS
                # ----------------------------------------------

                home_id = get_team_id(
                    cursor,
                    home_name
                )

                away_id = get_team_id(
                    cursor,
                    away_name
                )

                if not home_id or not away_id:

                    skipped.append(
                        f"Тур {round_number}: "
                        f"{home_name} — {away_name} "
                        f"(команда не найдена)"
                    )

                    progress.progress(
                        (index + 1) / len(MATCH_DATA)
                    )

                    continue

                # ----------------------------------------------
                # MATCH ID
                # ----------------------------------------------

                match_id = get_match_id(
                    cursor,
                    season_id,
                    round_number,
                    home_id,
                    away_id
                )

                if not match_id:

                    skipped.append(
                        f"Тур {round_number}: "
                        f"{home_name} — {away_name} "
                        f"(матч не найден в календаре)"
                    )

                    progress.progress(
                        (index + 1) / len(MATCH_DATA)
                    )

                    continue

                # ----------------------------------------------
                # MATCH RESULT
                # ----------------------------------------------

                cursor.execute(
                    """
                    DELETE FROM match_results
                    WHERE match_id = ?
                    """,
                    (match_id,)
                )

                cursor.execute(
                    """
                    INSERT INTO match_results
                    (
                        match_id,
                        home_goals,
                        away_goals
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        match_id,
                        home_goals,
                        away_goals
                    )
                )

                # ----------------------------------------------
                # MATCH STATISTICS — HOME
                # ----------------------------------------------

                save_statistics(
                    cursor,
                    match_id,
                    home_id,
                    home_possession,
                    home_shots,
                    home_sot,
                    home_corners,
                    home_yellow,
                    home_xg,
                    home_pass_accuracy
                )

                # ----------------------------------------------
                # MATCH STATISTICS — AWAY
                # ----------------------------------------------

                save_statistics(
                    cursor,
                    match_id,
                    away_id,
                    away_possession,
                    away_shots,
                    away_sot,
                    away_corners,
                    away_yellow,
                    away_xg,
                    away_pass_accuracy
                )

                # ----------------------------------------------
                # UPDATE MATCH
                # ----------------------------------------------

                cursor.execute(
                    """
                    UPDATE matches
                    SET
                        actual_home = ?,
                        actual_away = ?,
                        home_xg = ?,
                        away_xg = ?,
                        home_possession = ?,
                        away_possession = ?,
                        home_shots = ?,
                        away_shots = ?,
                        home_shots_on_target = ?,
                        away_shots_on_target = ?,
                        status = 'finished'
                    WHERE id = ?
                    """,
                    (
                        home_goals,
                        away_goals,
                        home_xg,
                        away_xg,
                        home_possession,
                        away_possession,
                        home_shots,
                        away_shots,
                        home_sot,
                        away_sot,
                        match_id
                    )
                )

                loaded += 1

                progress.progress(
                    (index + 1) / len(MATCH_DATA)
                )

            # ====================================================
            # COMMIT
            # ====================================================

            conn.commit()

            status.text("✅ Загрузка завершена")

            st.success(
                f"🔥 ЗАГРУЖЕНО: {loaded} из {len(MATCH_DATA)} матчей"
            )

            # ====================================================
            # SKIPPED
            # ====================================================

            if skipped:

                st.warning(
                    f"⚠️ Не загружено: {len(skipped)}"
                )

                with st.expander(
                    "Показать пропущенные матчи"
                ):

                    for item in skipped:
                        st.write(
                            f"• {item}"
                        )

            else:

                st.success(
                    "✅ ВСЕ 24 МАТЧА НАЙДЕНЫ И ЗАГРУЖЕНЫ"
                )

            # ====================================================
            # VERIFICATION
            # ====================================================

            st.divider()

            st.subheader("🔎 Проверка базы")

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM matches
                WHERE status = 'finished'
                """
            )

            finished_count = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM match_results
                """
            )

            results_count = cursor.fetchone()[0]

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM match_statistics
                """
            )

            statistics_count = cursor.fetchone()[0]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Завершённых матчей",
                    finished_count
                )

            with col2:
                st.metric(
                    "Результатов",
                    results_count
                )

            with col3:
                st.metric(
                    "Статистических записей",
                    statistics_count
                )

            st.divider()

            # ====================================================
            # SHOW 24 MATCHES
            # ====================================================

            st.subheader("📋 Загруженные 24 матча")

            cursor.execute(
                """
                SELECT
                    r.round_number,
                    ht.name,
                    at.name,
                    m.actual_home,
                    m.actual_away,
                    m.home_xg,
                    m.away_xg
                FROM matches m
                JOIN rounds r
                    ON r.id = m.round_id
                JOIN teams ht
                    ON ht.id = m.home_team_id
                JOIN teams at
                    ON at.id = m.away_team_id
                WHERE r.season_id = ?
                  AND r.round_number IN (1, 2, 3)
                  AND m.status = 'finished'
                ORDER BY
                    r.round_number,
                    m.id
                """,
                (season_id,)
            )

            rows = cursor.fetchall()

            if rows:

                import pandas as pd

                df = pd.DataFrame(
                    rows,
                    columns=[
                        "Тур",
                        "Хозяева",
                        "Гости",
                        "Голы Х",
                        "Голы Г",
                        "xG Х",
                        "xG Г"
                    ]
                )

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

            st.balloons()

        except Exception as e:

            if conn:
                conn.rollback()

            st.error(
                f"❌ ОШИБКА ЗАГРУЗКИ: {e}"
            )

            import traceback

            st.code(
                traceback.format_exc()
            )

        finally:

            if conn:
                conn.close()


if __name__ == "__main__":
    main()

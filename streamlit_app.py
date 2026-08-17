#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
MAIN APPLICATION
FAJ Match Center — ЕДИНЫЙ ИНТЕРФЕЙС
============================================================

ПРИНЦИПЫ:
    SQLite only
    database.py — единый источник схемы
    Никакого DELETE / DROP
    Не изменяем фактические результаты
    Прогнозы только для НЕСЫГРАННЫХ матчей
    Исправление календаря только home_team_id / away_team_id
    Match Laboratory встроен в Матч-центр
============================================================
"""

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st


# ============================================================
# PATH
# ============================================================

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ============================================================
# CONFIG
# ============================================================

try:
    from app.config import config
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.config: {e}")
    st.stop()


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title=f"FAJ Platform v{config.PLATFORM_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATABASE
# ============================================================

try:
    from app.database import get_connection, DB_FILE
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.database: {e}")
    st.stop()

DB_PATH = DB_FILE


# ============================================================
# PREDICTION MANAGER
# ============================================================

try:
    from app.core.prediction_manager import get_prediction_manager
except Exception:
    get_prediction_manager = None


# ============================================================
# BOOTSTRAP
# ============================================================

try:
    from app.bootstrap import bootstrap_faj
except Exception:
    bootstrap_faj = None


# ============================================================
# FAJ CYCLE
# ============================================================

try:
    from app.faj_cycle import (
        FAJCycle,
        run_faj_cycle as faj_cycle_runner,
    )
    FAJ_CYCLE_AVAILABLE = True
    FAJ_CYCLE_IMPORT_ERROR = None
except Exception as e:
    FAJCycle = None
    faj_cycle_runner = None
    FAJ_CYCLE_AVAILABLE = False
    FAJ_CYCLE_IMPORT_ERROR = str(e)


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "bootstrap_result" not in st.session_state:
    st.session_state.bootstrap_result = None

if "cycle_result" not in st.session_state:
    st.session_state.cycle_result = None

if "round_predictions" not in st.session_state:
    st.session_state.round_predictions = {}

if "selected_round" not in st.session_state:
    st.session_state.selected_round = None

if "lab_match_id" not in st.session_state:
    st.session_state.lab_match_id = None


# ============================================================
# NAVIGATION
# ============================================================

def navigate(page_name):
    st.session_state.page = page_name
    st.rerun()


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db_connection():
    return get_connection()


def database_exists():
    return os.path.exists(DB_PATH)


def table_exists(table_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            LIMIT 1
            """,
            (table_name,),
        )

        result = cursor.fetchone()
        conn.close()

        return bool(result)

    except Exception:
        return False


# ============================================================
# BOOTSTRAP
# ============================================================

if st.session_state.bootstrap_result is None:

    if bootstrap_faj is not None:

        try:
            with st.spinner("🚀 Проверка FAJ..."):
                st.session_state.bootstrap_result = bootstrap_faj()

        except Exception as e:

            st.session_state.bootstrap_result = {
                "ready": False,
                "messages": [f"❌ Ошибка Bootstrap: {e}"],
            }

    else:

        st.session_state.bootstrap_result = {
            "ready": False,
            "messages": ["⚠️ bootstrap_faj недоступен."],
        }


# ============================================================
# SEASON
# ============================================================

def get_active_season():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, league, name
            FROM seasons
            WHERE league = 'РПЛ'
              AND (
                    status = 'active'
                    OR name LIKE '%2026/27%'
                    OR name LIKE '%2026-27%'
                  )
            ORDER BY
                CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "league": row[1],
            "name": row[2],
        }

    except Exception:
        return None


# ============================================================
# ROUNDS
# ============================================================

def get_rounds(season_id):

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, round_number
            FROM rounds
            WHERE season_id = ?
            ORDER BY round_number
            """,
            (season_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "round_number": int(row[1]),
            }
            for row in rows
        ]

    except Exception:
        return []


# ============================================================
# MATCHES
# ============================================================

def get_round_matches(round_id):

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                m.id,
                m.date,
                m.status,
                th.name AS home_team,
                ta.name AS away_team,
                m.is_played,
                mr.home_goals,
                mr.away_goals
            FROM matches m

            LEFT JOIN teams th
                ON m.home_team_id = th.id

            LEFT JOIN teams ta
                ON m.away_team_id = ta.id

            LEFT JOIN match_results mr
                ON mr.match_id = m.id

            WHERE m.round_id = ?

            ORDER BY m.date, m.id
            """,
            (round_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        result = []

        for row in rows:

            result.append(
                {
                    "id": row[0],
                    "date": row[1],
                    "status": row[2],
                    "home_team": row[3],
                    "away_team": row[4],
                    "is_played": (
                        row[5] == 1
                        or row[5] is True
                    ),
                    "home_goals": row[6],
                    "away_goals": row[7],
                }
            )

        return result

    except Exception:
        return []


# ============================================================
# DATABASE COUNTS
# ============================================================

def get_db_counts():

    result = {
        "teams": 0,
        "matches": 0,
        "predictions": 0,
    }

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # ----------------------------
        # Teams
        # ----------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM teams
            WHERE league = 'РПЛ'
            """
        )

        row = cursor.fetchone()

        if row:
            result["teams"] = row[0] or 0

        # ----------------------------
        # Matches
        # ----------------------------

        season = get_active_season()

        if season:

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM matches m
                JOIN rounds r
                    ON m.round_id = r.id
                WHERE r.season_id = ?
                """,
                (season["id"],),
            )

            row = cursor.fetchone()

            if row:
                result["matches"] = row[0] or 0

        # ----------------------------
        # Predictions
        # ----------------------------

        if table_exists("predictions"):

            if season:

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM predictions p

                    LEFT JOIN matches m
                        ON p.match_id = m.id

                    LEFT JOIN rounds r
                        ON m.round_id = r.id

                    WHERE r.season_id = ?
                    """,
                    (season["id"],),
                )

            else:

                cursor.execute(
                    "SELECT COUNT(*) FROM predictions"
                )

            row = cursor.fetchone()

            if row:
                result["predictions"] = row[0] or 0

        conn.close()

    except Exception:
        pass

    return result


# ============================================================
# CANONICAL CALENDAR
# ============================================================

CANONICAL_CALENDAR = [

    # ----------------------------
    # ROUND 1
    # ----------------------------

    (1, "ЦСКА", "Балтика"),
    (1, "Рубин", "Краснодар"),
    (1, "Спартак", "Родина"),
    (1, "Акрон", "Зенит"),
    (1, "Динамо Москва", "Крылья Советов"),
    (1, "Факел", "Динамо Махачкала"),
    (1, "Оренбург", "Ростов"),
    (1, "Локомотив", "Ахмат"),

    # ----------------------------
    # ROUND 2
    # ----------------------------

    (2, "Ахмат", "Спартак"),
    (2, "Краснодар", "Факел"),
    (2, "Оренбург", "Зенит"),
    (2, "Балтика", "Динамо Москва"),
    (2, "Динамо Махачкала", "Локомотив"),
    (2, "ЦСКА", "Крылья Советов"),
    (2, "Акрон", "Рубин"),
    (2, "Родина", "Ростов"),

    # ----------------------------
    # ROUND 3
    # ----------------------------

    (3, "Факел", "Ахмат"),
    (3, "Спартак", "Краснодар"),
    (3, "Рубин", "Оренбург"),
    (3, "Зенит", "Родина"),
    (3, "Динамо Москва", "Динамо Махачкала"),
    (3, "ЦСКА", "Ростов"),
    (3, "Локомотив", "Акрон"),
    (3, "Крылья Советов", "Балтика"),

    # ----------------------------
    # ROUND 4
    # ----------------------------

    (4, "Родина", "Акрон"),
    (4, "Оренбург", "Локомотив"),
    (4, "Балтика", "Спартак"),
    (4, "Крылья Советов", "Динамо Махачкала"),
    (4, "Зенит", "Динамо Москва"),
    (4, "Краснодар", "Ахмат"),
    (4, "Ростов", "Рубин"),
    (4, "ЦСКА", "Факел"),
]


# ============================================================
# CALENDAR DIAGNOSTIC
# ============================================================

def get_calendar_status():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        season = get_active_season()

        if not season:

            conn.close()

            return {
                "error": "Сезон не найден"
            }

        cursor.execute(
            """
            SELECT id, round_number
            FROM rounds
            WHERE season_id = ?
              AND round_number BETWEEN 1 AND 4
            """,
            (season["id"],),
        )

        rounds = {
            int(row[1]): row[0]
            for row in cursor.fetchall()
        }

        actual = {}

        for round_number, round_id in rounds.items():

            cursor.execute(
                """
                SELECT
                    m.id,
                    th.name,
                    ta.name
                FROM matches m

                JOIN teams th
                    ON th.id = m.home_team_id

                JOIN teams ta
                    ON ta.id = m.away_team_id

                WHERE m.round_id = ?
                """,
                (round_id,),
            )

            for row in cursor.fetchall():

                actual[
                    (
                        round_number,
                        row[1],
                        row[2],
                    )
                ] = row[0]

        conn.close()

        canonical = set(CANONICAL_CALENDAR)
        actual_set = set(actual.keys())

        correct = canonical & actual_set

        reversed_matches = []

        for r, home, away in CANONICAL_CALENDAR:

            if (
                r,
                home,
                away
            ) not in actual:

                if (
                    r,
                    away,
                    home
                ) in actual:

                    reversed_matches.append(
                        {
                            "round": r,
                            "home": home,
                            "away": away,
                            "match_id": actual[
                                (r, away, home)
                            ],
                        }
                    )

        missing = []

        for item in canonical:

            if item not in actual:

                reversed_item = (
                    item[0],
                    item[2],
                    item[1],
                )

                if reversed_item not in actual:

                    missing.append(item)

        extra = []

        for item in actual_set:

            if item not in canonical:

                extra.append(item)

        return {
            "total": len(CANONICAL_CALENDAR),
            "correct": len(correct),
            "wrong": len(reversed_matches),
            "missing": len(missing),
            "extra": len(extra),
            "matches": reversed_matches,
            "missing_matches": missing,
            "extra_matches": extra,
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# FIX CALENDAR
# ============================================================

def fix_calendar():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        season = get_active_season()

        if not season:

            conn.close()

            return {
                "success": False,
                "error": "Сезон не найден",
            }

        cursor.execute(
            """
            SELECT id, round_number
            FROM rounds
            WHERE season_id = ?
              AND round_number BETWEEN 1 AND 4
            """,
            (season["id"],),
        )

        rounds = {
            int(row[1]): row[0]
            for row in cursor.fetchall()
        }

        to_fix = []

        for round_number, round_id in rounds.items():

            cursor.execute(
                """
                SELECT
                    m.id,
                    th.name,
                    ta.name
                FROM matches m

                JOIN teams th
                    ON th.id = m.home_team_id

                JOIN teams ta
                    ON ta.id = m.away_team_id

                WHERE m.round_id = ?
                """,
                (round_id,),
            )

            for row in cursor.fetchall():

                match_id = row[0]
                home = row[1]
                away = row[2]

                canonical = (
                    round_number,
                    home,
                    away,
                )

                reversed_key = (
                    round_number,
                    away,
                    home,
                )

                if (
                    canonical not in CANONICAL_CALENDAR
                    and reversed_key in CANONICAL_CALENDAR
                ):

                    to_fix.append(
                        (
                            match_id,
                            away,
                            home,
                        )
                    )

        fixed = 0

        for match_id, home_name, away_name in to_fix:

            cursor.execute(
                """
                SELECT id
                FROM teams
                WHERE name = ?
                  AND league = 'РПЛ'
                LIMIT 1
                """,
                (home_name,),
            )

            home_row = cursor.fetchone()

            cursor.execute(
                """
                SELECT id
                FROM teams
                WHERE name = ?
                  AND league = 'РПЛ'
                LIMIT 1
                """,
                (away_name,),
            )

            away_row = cursor.fetchone()

            if not home_row or not away_row:
                continue

            cursor.execute(
                """
                UPDATE matches
                SET home_team_id = ?,
                    away_team_id = ?
                WHERE id = ?
                """,
                (
                    home_row[0],
                    away_row[0],
                    match_id,
                ),
            )

            fixed += 1

        conn.commit()
        conn.close()

        return {
            "success": True,
            "fixed": fixed,
        }

    except Exception as e:

        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass

        return {
            "success": False,
            "error": str(e),
        }


# ============================================================
# PREDICTION
# ============================================================

def calculate_prediction(match):

    if get_prediction_manager is None:

        return {
            "error": "Prediction Manager недоступен."
        }

    try:

        manager = get_prediction_manager()

        result = manager.predict(
            home_team=match["home_team"],
            away_team=match["away_team"],
            league="РПЛ",
        )

        if isinstance(result, dict):

            if (
                result.get("error")
                or result.get("status") == "error"
            ):

                return {
                    "error": result.get(
                        "message",
                        "Ошибка расчёта",
                    )
                }

        return result

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# FORMAT
# ============================================================

def pct(value):

    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "—"


# ============================================================
# RENDER PREDICTION
# ============================================================

def render_prediction(match, result):

    if not result:

        st.caption("⏳ Прогноз ещё не рассчитан")
        return

    if result.get("error"):

        st.error(result["error"])
        return

    if result.get("status") == "error":

        st.error(
            result.get(
                "message",
                "Ошибка расчёта",
            )
        )

        return

    xg = result.get("xg", {})
    confidence = result.get("confidence", {})
    risk = result.get("risk", {})
    probability = result.get("probability", {})

    col1, col2, col3 = st.columns(
        [1, 1.3, 1]
    )

    with col1:

        st.metric(
            "xG хозяев",
            f'{float(xg.get("home", 0)):.2f}',
        )

    with col2:

        st.metric(
            "FAJ прогноз",
            result.get("score", "—"),
        )

    with col3:

        st.metric(
            "xG гостей",
            f'{float(xg.get("away", 0)):.2f}',
        )

    p1, px, p2 = st.columns(3)

    with p1:
        st.caption("П1")
        st.write(
            f'**{pct(probability.get("home", 0))}**'
        )

    with px:
        st.caption("X")
        st.write(
            f'**{pct(probability.get("draw", 0))}**'
        )

    with p2:
        st.caption("П2")
        st.write(
            f'**{pct(probability.get("away", 0))}**'
        )

    c1, c2 = st.columns(2)

    with c1:

        st.caption("🧠 Confidence")

        st.write(
            f'**{pct(confidence.get("overall", 0))}** '
            f'{confidence.get("level", "")}'
        )

    with c2:

        st.caption("⚠️ Risk")

        st.write(
            f'**{risk.get("level", "—")}**'
        )


# ============================================================
# MATCH LABORATORY — INLINE
# ============================================================

def render_match_laboratory():

    match_id = st.session_state.get(
        "lab_match_id"
    )

    if not match_id:
        return

    st.divider()

    st.subheader(
        "🔬 Match Laboratory"
    )

    try:

        from app.pages.match_analysis import main

        main()

    except Exception as e:

        st.error(
            f"❌ Ошибка Match Laboratory: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):
            st.exception(e)

    if st.button(
        "✖ Закрыть Match Laboratory",
        use_container_width=True,
    ):

        st.session_state.lab_match_id = None
        st.rerun()


# ============================================================
# MATCH CARD
# ============================================================

def render_match_card(match, index):

    match_id = int(match["id"])

    result = (
        st.session_state
        .round_predictions
        .get(match_id)
    )

    with st.container(border=True):

        col1, col2 = st.columns(
            [4, 1]
        )

        with col1:

            st.markdown(
                f"### ⚽ "
                f"{match['home_team']} "
                f"— "
                f"{match['away_team']}"
            )

            if match.get("date"):

                st.caption(
                    f"📅 {match['date']}"
                )

        with col2:

            if match.get("is_played"):

                st.caption(
                    "✅ Сыгран"
                )

            elif (
                result
                and not result.get("error")
                and result.get("status") != "error"
            ):

                st.success("FAJ ✓")

            else:

                st.caption(
                    "⏳ Ожидает"
                )

        # ----------------------------
        # RESULT
        # ----------------------------

        if match.get("is_played"):

            st.caption(
                "📊 Результат: "
                f"{match.get('home_goals', '?')} : "
                f"{match.get('away_goals', '?')}"
            )

        else:

            render_prediction(
                match,
                result,
            )

        # ----------------------------
        # ACTIONS
        # ----------------------------

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "🔬 Детали",
                key=f"details_{match_id}",
                use_container_width=True,
            ):

                st.session_state.lab_match_id = match_id
                st.rerun()

        with col2:

            if (
                not match.get("is_played")
                and (
                    not result
                    or result.get("error")
                    or result.get("status") == "error"
                )
            ):

                if st.button(
                    "🔮 Рассчитать",
                    key=f"predict_{match_id}",
                    use_container_width=True,
                ):

                    with st.spinner(
                        f"FAJ рассчитывает: "
                        f"{match['home_team']} — "
                        f"{match['away_team']}"
                    ):

                        prediction = calculate_prediction(
                            match
                        )

                    st.session_state.round_predictions[
                        match_id
                    ] = prediction

                    st.rerun()


# ============================================================
# CALCULATE ROUND
# ============================================================

def calculate_round(matches):

    upcoming = [
        match
        for match in matches
        if not match.get("is_played")
    ]

    if not upcoming:
        return

    progress = st.progress(
        0,
        text="Подготовка прогнозов...",
    )

    total = len(upcoming)

    for index, match in enumerate(
        upcoming,
        start=1,
    ):

        progress.progress(
            index / total,
            text=(
                f"FAJ: {index}/{total} — "
                f"{match['home_team']} — "
                f"{match['away_team']}"
            ),
        )

        result = calculate_prediction(
            match
        )

        st.session_state.round_predictions[
            int(match["id"])
        ] = result

    progress.empty()


# ============================================================
# FAJ CYCLE
# ============================================================

def run_faj_cycle():
    if not FAJ_CYCLE_AVAILABLE:
        return {
            "success": False,
            "ready": False,
            "message": (
                "FAJ Cycle недоступен."
                + (
                    f" Ошибка импорта: "
                    f"{FAJ_CYCLE_IMPORT_ERROR}"
                    if FAJ_CYCLE_IMPORT_ERROR
                    else ""
                )
            ),
        }
    try:
        # ----------------------------------------------------
        # ЕДИНАЯ ТОЧКА ЗАПУСКА
        # ----------------------------------------------------
        if faj_cycle_runner is not None:
            result = faj_cycle_runner()
        else:
            cycle = FAJCycle()
            result = cycle.run()
        # ----------------------------------------------------
        # Нормализация результата
        # ----------------------------------------------------
        if isinstance(result, dict):
            return result
        return {
            "success": True,
            "ready": True,
            "result": result,
        }
    except Exception as e:
        return {
            "success": False,
            "ready": False,
            "message": str(e),
        }


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("⚽ FAJ")

    st.caption(
        f"Platform v{config.PLATFORM_VERSION}"
    )

    st.divider()

    st.caption("🏠 ОСНОВНОЕ")

    if st.button(
        "🏠 Матч-центр",
        use_container_width=True,
    ):
        navigate("home")

    if st.button(
        "🔮 Прогнозы",
        use_container_width=True,
    ):
        navigate("predictions")

    if st.button(
        "📊 Аналитика",
        use_container_width=True,
    ):
        navigate("analytics")

    if st.button(
        "📚 История",
        use_container_width=True,
    ):
        navigate("history")

    st.divider()

    st.caption("🧠 FAJ")

    if st.button(
        "📋 Паспорта",
        use_container_width=True,
    ):
        navigate("passports")

    st.divider()

    st.caption("⚙️ СИСТЕМА")

    if st.button(
        "⚙️ Система",
        use_container_width=True,
    ):
        navigate("system")

    st.divider()

    if st.button(
        "🔄 Запустить FAJ Cycle",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner(
            "🧠 FAJ Cycle выполняет полный цикл..."
        ):
            st.session_state.cycle_result = run_faj_cycle()
        st.rerun()

    st.divider()

    counts = get_db_counts()

    st.caption("📊 СОСТОЯНИЕ")

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Команды",
            counts["teams"],
        )

    with c2:
        st.metric(
            "Матчи",
            counts["matches"],
        )

    if database_exists():

        st.caption(
            "🟢 SQLite"
        )

    else:

        st.caption(
            "🔴 SQLite отсутствует"
        )


# ============================================================
# HOME — MATCH CENTER
# ============================================================

if st.session_state.page == "home":

    season = get_active_season()

    if not season:

        st.error(
            "❌ Активный сезон РПЛ не найден."
        )

        st.stop()

    rounds = get_rounds(
        season["id"]
    )

    if not rounds:

        st.error(
            "❌ В сезоне нет туров."
        )

        st.stop()

    round_map = {
        r["round_number"]: r["id"]
        for r in rounds
    }

    # ----------------------------
    # Current round
    # ----------------------------

    if 5 in round_map:

        current_round = 5

    else:

        current_round = max(
            round_map.keys()
        )

    # ----------------------------
    # Selected round
    # ----------------------------

    selected_round = (
        st.session_state.selected_round
    )

    if (
        selected_round not in round_map
    ):

        selected_round = current_round
        st.session_state.selected_round = (
            current_round
        )

    # ========================================================
    # CALENDAR STATUS
    # ========================================================

    calendar_status = (
        get_calendar_status()
    )

    if "error" not in calendar_status:

        total = calendar_status["total"]
        correct = calendar_status["correct"]
        wrong = calendar_status["wrong"]
        missing = calendar_status["missing"]
        extra = calendar_status["extra"]

        if (
            wrong == 0
            and missing == 0
            and extra == 0
            and correct == total
        ):

            st.success(
                "✅ Календарь 1–4 туров корректен: "
                f"{correct}/{total} матчей."
            )

        else:

            st.warning(
                "⚠️ Состояние календаря 1–4 туров: "
                f"{correct}/{total} корректно."
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                st.metric(
                    "Перепутано",
                    wrong,
                )

            with c2:
                st.metric(
                    "Отсутствует",
                    missing,
                )

            with c3:
                st.metric(
                    "Лишних",
                    extra,
                )

            if wrong > 0:

                if st.button(
                    "🔧 Исправить календарь "
                    "(только команды)",
                    type="primary",
                    use_container_width=True,
                ):

                    result = fix_calendar()

                    if result.get("success"):

                        st.success(
                            "✅ Исправление завершено. "
                            f"Изменено матчей: "
                            f"{result.get('fixed', 0)}"
                        )

                        st.rerun()

                    else:

                        st.error(
                            "❌ Ошибка исправления: "
                            f"{result.get('error')}"
                        )

            if missing > 0:

                st.info(
                    "ℹ️ Отсутствующие матчи "
                    "автоматически не создаются. "
                    "Календарь должен восстанавливаться "
                    "через штатный loader/parser."
                )

    else:

        st.error(
            "❌ Не удалось проверить календарь: "
            f"{calendar_status['error']}"
        )

    st.divider()

    # ========================================================
    # HEADER
    # ========================================================

    st.markdown(
        "# ⚽ FAJ Match Center"
    )

    st.caption(
        f"РПЛ · 2026/27 · "
        f"{selected_round}-й тур"
    )

    # ========================================================
    # TOP METRICS
    # ========================================================

    counts = get_db_counts()

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "🏟️ Команды",
            counts["teams"],
        )

    with c2:

        st.metric(
            "⚽ Матчи",
            counts["matches"],
        )

    with c3:

        st.metric(
            "🔮 Прогнозы",
            counts["predictions"],
        )

    with c4:

        st.metric(
            "📅 Тур",
            selected_round,
        )

    st.divider()

    # ========================================================
    # ROUND NAVIGATION
    # ========================================================

    available_rounds = sorted(
        round_map.keys()
    )

    left, center, right = st.columns(
        [1, 2, 1]
    )

    with left:

        prev_round = selected_round - 1

        if prev_round in round_map:

            if st.button(
                "← Предыдущий",
                use_container_width=True,
            ):

                st.session_state.selected_round = (
                    prev_round
                )

                st.rerun()

    with center:

        selected_round_ui = st.selectbox(
            "Тур",
            available_rounds,
            index=available_rounds.index(
                selected_round
            ),
            label_visibility="collapsed",
        )

        if (
            selected_round_ui
            != st.session_state.selected_round
        ):

            st.session_state.selected_round = (
                selected_round_ui
            )

            st.rerun()

    with right:

        next_round = selected_round + 1

        if next_round in round_map:

            if st.button(
                "Следующий →",
                use_container_width=True,
            ):

                st.session_state.selected_round = (
                    next_round
                )

                st.rerun()

    # ========================================================
    # MATCHES
    # ========================================================

    round_id = round_map[
        st.session_state.selected_round
    ]

    matches = get_round_matches(
        round_id
    )

    st.markdown(
        f"## {st.session_state.selected_round}-й тур"
    )

    st.caption(
        f"{len(matches)} матчей"
    )

    # ========================================================
    # PREDICTIONS
    # ========================================================

    upcoming = [
        match
        for match in matches
        if not match.get("is_played")
    ]

    calculated = [
        match
        for match in upcoming
        if int(match["id"])
        in st.session_state.round_predictions
    ]

    if not upcoming:

        st.success(
            "🟢 Все матчи этого тура уже сыграны."
        )

    elif len(calculated) < len(upcoming):

        remaining = (
            len(upcoming)
            - len(calculated)
        )

        if st.button(
            f"🔮 Рассчитать прогнозы "
            f"тура ({remaining})",
            type="primary",
            use_container_width=True,
        ):

            calculate_round(matches)
            st.rerun()

    else:

        st.success(
            "🟢 Все прогнозы этого тура рассчитаны."
        )

    st.divider()

    # ========================================================
    # MATCH CARDS
    # ========================================================

    if not matches:

        st.info(
            "В выбранном туре матчей нет."
        )

    else:

        for index, match in enumerate(
            matches
        ):

            render_match_card(
                match,
                index,
            )

            st.write("")

    # ========================================================
    # INLINE MATCH LABORATORY
    # ========================================================

    render_match_laboratory()

    # ========================================================
    # LAST FAJ CYCLE
    # ========================================================

    if st.session_state.cycle_result:
        result = st.session_state.cycle_result
        st.divider()
        st.subheader("🔄 FAJ Cycle")
        # --------------------------------------------------------
        # STATUS
        # --------------------------------------------------------
        if result.get("success") and result.get("ready"):
            st.success(
                "🟢 FAJ Cycle завершён успешно"
            )
        elif result.get("success"):
            st.warning(
                "🟡 FAJ Cycle завершён с предупреждениями"
            )
        else:
            st.error(
                "🔴 FAJ Cycle остановлен с ошибкой"
            )
        # --------------------------------------------------------
        # METRICS
        # --------------------------------------------------------
        historical = result.get(
            "historical",
            {}
        )
        learning = result.get(
            "learning",
            {}
        )
        predictions = result.get(
            "predictions",
            {}
        )
        final = result.get(
            "final",
            {}
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(
                "📥 Новые результаты",
                historical.get(
                    "inserted",
                    0,
                ),
            )
        with c2:
            st.metric(
                "🧠 Learning",
                (
                    "RUN"
                    if learning.get("success")
                    else
                    "SKIP"
                    if learning.get("skipped")
                    else
                    "ERROR"
                ),
            )
        with c3:
            st.metric(
                "🔮 Прогнозы",
                predictions.get(
                    "count",
                    0,
                ),
            )
        with c4:
            st.metric(
                "⏱️ Время",
                f"{result.get('duration_seconds', 0):.2f} с",
            )
        # --------------------------------------------------------
        # STEPS
        # --------------------------------------------------------
        steps = result.get(
            "steps",
            [],
        )
        if steps:
            with st.expander(
                "📋 Этапы FAJ Cycle",
                expanded=False,
            ):
                for step in steps:
                    status = step.get(
                        "status",
                        "",
                    )
                    message = step.get(
                        "message",
                        "",
                    )
                    if status == "success":
                        st.success(message)
                    elif status == "skipped":
                        st.info(message)
                    elif status == "warning":
                        st.warning(message)
                    elif status == "error":
                        st.error(message)
        # --------------------------------------------------------
        # ERRORS
        # --------------------------------------------------------
        errors = result.get(
            "errors",
            [],
        )
        if errors:
            with st.expander(
                "❌ Ошибки FAJ Cycle",
                expanded=True,
            ):
                for error in errors:
                    st.error(str(error))
        # --------------------------------------------------------
        # FINAL DATABASE STATE
        # --------------------------------------------------------
        with st.expander(
            "💾 Состояние базы после Cycle",
            expanded=False,
        ):
            fc1, fc2, fc3, fc4, fc5 = st.columns(5)
            with fc1:
                st.metric(
                    "Команды",
                    final.get(
                        "teams",
                        0,
                    ),
                )
            with fc2:
                st.metric(
                    "Результаты",
                    final.get(
                        "match_results",
                        0,
                    ),
                )
            with fc3:
                st.metric(
                    "Прогнозы",
                    final.get(
                        "predictions",
                        0,
                    ),
                )
            with fc4:
                st.metric(
                    "Learning",
                    final.get(
                        "learning_memory",
                        0,
                    ),
                )
            with fc5:
                st.metric(
                    "Parameters",
                    final.get(
                        "model_parameters",
                        0,
                    ),
                )


# ============================================================
# PREDICTIONS
# ============================================================

elif st.session_state.page == "predictions":

    try:

        from app.pages.predictions import main

        main()

    except Exception as e:

        st.error(
            f"❌ Ошибка страницы прогнозов: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(e)


# ============================================================
# PASSPORTS
# ============================================================

elif st.session_state.page == "passports":

    st.title(
        "📋 Паспорта команд"
    )

    try:

        conn = get_db_connection()

        passport_df = pd.read_sql_query(
            """
            SELECT
                t.name AS team_name,
                tp.attack,
                tp.defense,
                tp.control,
                tp.goalkeeper,
                tp.faj_rating

            FROM teams t

            LEFT JOIN team_passports tp
                ON t.id = tp.team_id

            WHERE t.league = 'РПЛ'

            ORDER BY t.name
            """,
            conn,
        )

        conn.close()

        if passport_df.empty:

            st.info(
                "Паспорта не найдены."
            )

        else:

            display_df = (
                passport_df.rename(
                    columns={
                        "team_name": "Команда",
                        "attack": "Атака",
                        "defense": "Защита",
                        "control": "Контроль",
                        "goalkeeper": "Вратарь",
                        "faj_rating": "FAJ Rating",
                    }
                )
            )

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as e:

        st.error(
            f"❌ Ошибка паспортов: {e}"
        )


# ============================================================
# ANALYTICS
# ============================================================

elif st.session_state.page == "analytics":

    st.title(
        "📊 Аналитика"
    )

    st.info(
        "Аналитический слой FAJ."
    )

    counts = get_db_counts()

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Матчи",
            counts["matches"],
        )

    with c2:
        st.metric(
            "Прогнозы",
            counts["predictions"],
        )

    with c3:
        st.metric(
            "Команды",
            counts["teams"],
        )


# ============================================================
# HISTORY
# ============================================================

elif st.session_state.page == "history":

    st.title(
        "📚 История FAJ"
    )

    st.info(
        "История прогнозов и фактических результатов."
    )

    counts = get_db_counts()

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "Матчи",
            counts["matches"],
        )

    with c2:

        st.metric(
            "Прогнозы",
            counts["predictions"],
        )


# ============================================================
# SYSTEM
# ============================================================

elif st.session_state.page == "system":

    st.title(
        "⚙️ Система"
    )

    st.caption(
        "Техническое состояние FAJ Platform"
    )

    st.divider()

    counts = get_db_counts()

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Platform",
            f"v{config.PLATFORM_VERSION}",
        )

    with c2:

        st.metric(
            "Core",
            f"v{config.CORE_VERSION}",
        )

    with c3:

        st.metric(
            "Pipeline",
            f"v{config.PIPELINE_VERSION}",
        )

    st.divider()

    st.subheader(
        "💾 SQLite"
    )

    if database_exists():

        st.success(
            "🟢 SQLite доступна"
        )

        try:

            size_mb = (
                os.path.getsize(DB_PATH)
                / 1024
                / 1024
            )

            st.metric(
                "Размер БД",
                f"{size_mb:.2f} MB",
            )

        except Exception:
            pass

    else:

        st.error(
            "🔴 faj.db не найден"
        )

    st.divider()

    st.subheader(
        "🔍 Состояние"
    )

    summary_df = pd.DataFrame(
        [
            {
                "Показатель": "Команды РПЛ",
                "Количество": counts["teams"],
            },
            {
                "Показатель": (
                    "Матчи активного сезона"
                ),
                "Количество": counts["matches"],
            },
            {
                "Показатель": "Прогнозы",
                "Количество": counts["predictions"],
            },
        ]
    )

    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"⚽ FAJ Platform v{config.PLATFORM_VERSION} · "
    f"Core v{config.CORE_VERSION} · "
    f"Pipeline v{config.PIPELINE_VERSION} · "
    f"SQLite · "
    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
)

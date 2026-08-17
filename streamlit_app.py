#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
MAIN APPLICATION

FAJ Match Center
Главная страница — рабочий интерфейс FAJ.

ВАЖНО:
    Streamlit = UI.
    SQLite = источник данных.
    PredictionManager = расчёт прогнозов.
    FAJ Cycle = оркестратор.
    Match Laboratory = детальная диагностика.

Никаких:
    DELETE
    DROP
    очистки БД
    изменения схемы
    генерации календаря
"""

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st


# ============================================================
# PATH
# ============================================================

ROOT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

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
    from app.database import (
        get_connection,
        FAJDatabase,
        DB_FILE,
    )
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.database: {e}")
    st.stop()


DB_PATH = DB_FILE


# ============================================================
# PREDICTION MANAGER
# ============================================================

try:
    from app.core.prediction_manager import (
        get_prediction_manager,
    )
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
    from app.faj_cycle import FAJCycle

    FAJ_CYCLE_AVAILABLE = True

except Exception:
    FAJCycle = None
    FAJ_CYCLE_AVAILABLE = False


# ============================================================
# GITHUB
# ============================================================

try:
    from app.github_db_sync import save_database_to_github
except Exception:
    save_database_to_github = None


# ============================================================
# SESSION
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "bootstrap_result" not in st.session_state:
    st.session_state.bootstrap_result = None

if "cycle_result" not in st.session_state:
    st.session_state.cycle_result = None

if "round_predictions" not in st.session_state:
    st.session_state.round_predictions = {}

if "prediction_loading" not in st.session_state:
    st.session_state.prediction_loading = False


# ============================================================
# NAVIGATION
# ============================================================

def navigate(page_name):
    st.session_state.page = page_name
    st.rerun()


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    return get_connection()


def database_exists():
    return os.path.exists(DB_PATH)


# ============================================================
# BOOTSTRAP
# ============================================================

if st.session_state.bootstrap_result is None:

    if bootstrap_faj is not None:

        try:
            with st.spinner("🚀 Проверка FAJ..."):
                st.session_state.bootstrap_result = (
                    bootstrap_faj()
                )

        except Exception as e:

            st.session_state.bootstrap_result = {
                "ready": False,
                "messages": [
                    f"❌ Ошибка Bootstrap: {e}"
                ],
            }

    else:

        st.session_state.bootstrap_result = {
            "ready": False,
            "messages": [
                "⚠️ bootstrap_faj недоступен."
            ],
        }


# ============================================================
# SAFE SQL HELPERS
# ============================================================

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


def get_table_columns(table_name):

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info([{table_name}])"
        )

        rows = cursor.fetchall()

        conn.close()

        return [row[1] for row in rows]

    except Exception:

        return []


# ============================================================
# FAJ CURRENT SEASON
# ============================================================

def get_active_season():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, league, name
            FROM seasons
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if not row:

            cursor.execute(
                """
                SELECT id, league, name
                FROM seasons
                WHERE league = 'РПЛ'
                ORDER BY id DESC
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
# ROUND HELPERS
# ============================================================

def get_rounds(season_id):

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                round_number
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


def get_current_round(rounds):

    if not rounds:
        return None

    round_numbers = [
        r["round_number"]
        for r in rounds
    ]

    # Текущий рабочий тур для FAJ.
    # Если 5-й тур существует — используем его.
    if 5 in round_numbers:
        return 5

    return max(round_numbers)


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
                m.competition,
                th.name AS home_team,
                ta.name AS away_team

            FROM matches m

            LEFT JOIN teams th
                ON m.home_team_id = th.id

            LEFT JOIN teams ta
                ON m.away_team_id = ta.id

            WHERE m.round_id = ?

            ORDER BY
                m.date,
                m.id
            """,
            (round_id,),
        )

        rows = cursor.fetchall()

        conn.close()

        return [
            {
                "id": row[0],
                "date": row[1],
                "status": row[2],
                "competition": row[3],
                "home_team": row[4],
                "away_team": row[5],
            }
            for row in rows
        ]

    except Exception as e:

        st.error(
            f"❌ Ошибка чтения матчей: {e}"
        )

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

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # MATCHES
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # PREDICTIONS
        # ----------------------------------------------------

        if table_exists("predictions"):

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM predictions
                """
            )

            row = cursor.fetchone()

            if row:
                result["predictions"] = row[0] or 0

        conn.close()

    except Exception:

        pass

    return result


# ============================================================
# PREDICTION
# ============================================================

def calculate_prediction(match):

    if get_prediction_manager is None:

        return {
            "status": "error",
            "message": (
                "Prediction Manager недоступен."
            ),
        }

    try:

        manager = get_prediction_manager()

        result = manager.predict_by_match_id(
            int(match["id"])
        )

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================
# FORMATTERS
# ============================================================

def pct(value):

    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "—"


def get_probability(result, key):

    probability = result.get(
        "probability",
        {},
    )

    return probability.get(
        key,
        0,
    )


def render_prediction(match, result):

    if not result:

        st.caption(
            "⏳ Прогноз ещё не рассчитан"
        )

        return

    if result.get("status") != "success":

        st.error(
            result.get(
                "message",
                "Ошибка расчёта прогноза.",
            )
        )

        return

    xg = result.get(
        "xg",
        {},
    )

    confidence = result.get(
        "confidence",
        {},
    )

    risk = result.get(
        "risk",
        {},
    )

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
            result.get(
                "score",
                "—",
            ),
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
            f"**{pct(get_probability(result, 'home'))}**"
        )

    with px:

        st.caption("X")
        st.write(
            f"**{pct(get_probability(result, 'draw'))}**"
        )

    with p2:

        st.caption("П2")
        st.write(
            f"**{pct(get_probability(result, 'away'))}**"
        )

    c1, c2 = st.columns(2)

    with c1:

        st.caption(
            "🧠 Confidence"
        )

        st.write(
            f"**{pct(confidence.get('overall', 0))}** "
            f"{confidence.get('level', '')}"
        )

    with c2:

        st.caption(
            "⚠️ Risk"
        )

        st.write(
            f"**{risk.get('level', '—')}**"
        )


# ============================================================
# MATCH CARD
# ============================================================

def render_match_card(match, index):

    result = st.session_state.round_predictions.get(
        int(match["id"])
    )

    with st.container(border=True):

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        col1, col2 = st.columns(
            [4, 1]
        )

        with col1:

            st.markdown(
                f"### ⚽ {match['home_team']}  —  "
                f"{match['away_team']}"
            )

            if match.get("date"):

                st.caption(
                    f"📅 {match['date']}"
                )

        with col2:

            if result and result.get("status") == "success":

                st.success("FAJ ✓")

            else:

                st.caption(
                    "Прогноз ожидает"
                )

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        render_prediction(
            match,
            result,
        )

        # ----------------------------------------------------
        # ACTION
        # ----------------------------------------------------

        col1, col2 = st.columns(
            [1, 1]
        )

        with col1:

            if st.button(
                "🔬 Детали",
                key=f"details_{match['id']}",
                use_container_width=True,
            ):

                st.session_state.lab_match_id = (
                    int(match["id"])
                )

                navigate("match_analysis")

        with col2:

            if not result or result.get("status") != "success":

                if st.button(
                    "🔮 Рассчитать",
                    key=f"predict_{match['id']}",
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
                        int(match["id"])
                    ] = prediction

                    st.rerun()


# ============================================================
# RUN FULL ROUND
# ============================================================

def calculate_round(matches):

    if not matches:
        return

    progress = st.progress(
        0,
        text="Подготовка прогнозов..."
    )

    total = len(matches)

    for index, match in enumerate(
        matches,
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
            "message": "FAJ Cycle недоступен.",
        }

    try:

        cycle = FAJCycle()

        if hasattr(cycle, "run"):
            result = cycle.run()

        elif hasattr(cycle, "run_cycle"):
            result = cycle.run_cycle()

        elif hasattr(cycle, "execute"):
            result = cycle.execute()

        else:

            return {
                "success": False,
                "message": (
                    "FAJCycle не имеет "
                    "run/run_cycle/execute."
                ),
            }

        if isinstance(result, dict):
            return result

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:

        return {
            "success": False,
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

    if st.button(
        "🔬 Match Laboratory",
        use_container_width=True,
    ):

        navigate("match_analysis")

    st.divider()

    st.caption("⚙️ СИСТЕМА")

    if st.button(
        "⚙️ Система",
        use_container_width=True,
    ):

        navigate("system")

    if st.button(
        "🧬 System Trace",
        use_container_width=True,
    ):

        navigate("system_trace")

    st.divider()

    if st.button(
        "🔄 Обновить FAJ",
        type="primary",
        use_container_width=True,
    ):

        with st.spinner(
            "🧠 FAJ выполняет цикл..."
        ):

            st.session_state.cycle_result = (
                run_faj_cycle()
            )

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
# HOME
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

    current_round = get_current_round(
        rounds
    )

    round_map = {
        r["round_number"]: r["id"]
        for r in rounds
    }

    round_id = round_map[
        current_round
    ]

    matches = get_round_matches(
        round_id
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    st.markdown(
        "# ⚽ FAJ Match Center"
    )

    st.caption(
        f"РПЛ · 2026/27 · {current_round}-й тур"
    )

    st.divider()

    # --------------------------------------------------------
    # TOP BAR
    # --------------------------------------------------------

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
            len(st.session_state.round_predictions),
        )

    with c4:
        st.metric(
            "📅 Тур",
            current_round,
        )

    st.divider()

    # --------------------------------------------------------
    # ROUND NAVIGATION
    # --------------------------------------------------------

    left, center, right = st.columns(
        [1, 2, 1]
    )

    with left:

        previous_round = current_round - 1

        if previous_round in round_map:

            if st.button(
                "← Предыдущий",
                use_container_width=True,
            ):

                st.session_state.selected_round = (
                    previous_round
                )

                st.rerun()

    with center:

        selected_round = st.selectbox(
            "Тур",
            sorted(round_map.keys()),
            index=sorted(round_map.keys()).index(
                st.session_state.get(
                    "selected_round",
                    current_round,
                )
            ),
            label_visibility="collapsed",
        )

    with right:

        next_round = current_round + 1

        if next_round in round_map:

            if st.button(
                "Следующий →",
                use_container_width=True,
            ):

                st.session_state.selected_round = (
                    next_round
                )

                st.rerun()

    if selected_round != current_round:

        round_id = round_map[
            selected_round
        ]

        matches = get_round_matches(
            round_id
        )

    st.markdown(
        f"## {selected_round}-й тур"
    )

    st.caption(
        f"{len(matches)} матчей"
    )

    # --------------------------------------------------------
    # CALCULATE ROUND
    # --------------------------------------------------------

    missing_predictions = [
        m
        for m in matches
        if int(m["id"])
        not in st.session_state.round_predictions
    ]

    if missing_predictions:

        if st.button(
            f"🔮 Рассчитать прогнозы тура "
            f"({len(missing_predictions)})",
            type="primary",
            use_container_width=True,
        ):

            calculate_round(
                matches
            )

            st.rerun()

    else:

        st.success(
            "🟢 Все прогнозы текущего отображаемого тура рассчитаны."
        )

    st.divider()

    # --------------------------------------------------------
    # MATCHES
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # LAST CYCLE
    # --------------------------------------------------------

    if st.session_state.cycle_result:

        with st.expander(
            "🔄 Последний запуск FAJ Cycle"
        ):

            result = st.session_state.cycle_result

            if result.get("success"):

                st.success(
                    "FAJ Cycle завершён успешно."
                )

            else:

                st.warning(
                    "FAJ Cycle завершён с проблемой."
                )

            st.json(result)


# ============================================================
# PREDICTIONS
# ============================================================

elif st.session_state.page == "predictions":

    from app.pages.predictions import main

    main()


# ============================================================
# MATCH LABORATORY
# ============================================================

elif st.session_state.page == "match_analysis":

    st.title("🔬 Match Laboratory")

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


# ============================================================
# PASSPORTS
# ============================================================

elif st.session_state.page == "passports":

    st.title("📋 Паспорта команд")

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

            display_df = passport_df.rename(
                columns={
                    "team_name": "Команда",
                    "attack": "Атака",
                    "defense": "Защита",
                    "control": "Контроль",
                    "goalkeeper": "Вратарь",
                    "faj_rating": "FAJ Rating",
                }
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

    st.title("📊 Аналитика")

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

    st.title("📚 История FAJ")

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
# SYSTEM TRACE
# ============================================================

elif st.session_state.page == "system_trace":

    from app.pages.system_trace import main

    main()


# ============================================================
# SYSTEM
# ============================================================

elif st.session_state.page == "system":

    st.title("⚙️ Система")

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
        "🔍 Диагностика"
    )

    summary_df = pd.DataFrame(
        [
            {
                "Показатель": "Команды РПЛ",
                "Количество": counts["teams"],
            },
            {
                "Показатель": "Матчи активного сезона",
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

    with st.expander(
        "🩺 SQLite Integrity Check"
    ):

        try:

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "PRAGMA integrity_check"
            )

            row = cursor.fetchone()

            conn.close()

            if row and row[0] == "ok":

                st.success(
                    "✅ SQLite integrity_check: OK"
                )

            else:

                st.error(
                    f"❌ Integrity check: {row}"
                )

        except Exception as e:

            st.error(
                f"❌ Ошибка: {e}"
            )

    st.caption(
        f"Проверка: "
        f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
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

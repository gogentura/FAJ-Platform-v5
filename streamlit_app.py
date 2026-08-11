#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
STREAMLIT MAIN APPLICATION
============================================================

Главная точка входа FAJ Platform.

Принципы:
    - SQLite only
    - database.py — единый источник схемы
    - load_all.py — центр загрузки данных
    - persistent state хранится вне session_state
    - Streamlit rerun не должен обнулять состояние БД
    - никаких DELETE / DROP / очисток исторических данных

Структура:

    streamlit_app.py
        |
        +-- Auto Bootstrap
        |
        +-- Home
        +-- Predictions
        +-- Match Laboratory
        +-- Passports
        +-- Load All
        +-- Load Calendar
        +-- Load Statistics
        +-- System
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

from app.config import config


# ============================================================
# STREAMLIT PAGE CONFIG
# ============================================================
# ВАЖНО:
# set_page_config должен выполняться до остальных st.* вызовов.

st.set_page_config(
    page_title=f"FAJ Platform v{config.PLATFORM_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATABASE / CORE
# ============================================================

from app.database import get_connection, FAJDatabase
from app.core.prediction_manager import get_prediction_manager


# ============================================================
# AUTO BOOTSTRAP
# ============================================================

bootstrap_result = {
    "ready": True,
    "messages": [],
}

try:

    from app.bootstrap import bootstrap_faj

    bootstrap_result = bootstrap_faj()

except Exception as e:

    bootstrap_result = {
        "ready": False,
        "messages": [
            f"Ошибка Auto Bootstrap: {e}"
        ],
    }


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "prediction_result" not in st.session_state:
    st.session_state.prediction_result = None


# ============================================================
# HELPERS
# ============================================================

def go_to_page(page_name: str):
    """
    Единая навигация.
    """

    st.session_state.page = page_name


def get_db_counts():
    """
    Получает базовый статус БД.

    Ничего не изменяет.
    """

    result = {
        "teams": 0,
        "matches": 0,
        "results": 0,
        "stats": 0,
    }

    try:

        conn = get_connection()
        cursor = conn.cursor()

        queries = {
            "teams": "SELECT COUNT(*) FROM teams",
            "matches": "SELECT COUNT(*) FROM matches",
            "results": "SELECT COUNT(*) FROM match_results",
            "stats": "SELECT COUNT(*) FROM match_statistics",
        }

        for key, query in queries.items():

            try:
                cursor.execute(query)
                row = cursor.fetchone()

                if row:
                    result[key] = row[0] or 0

            except Exception:
                result[key] = 0

        conn.close()

    except Exception:
        pass

    return result


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("⚽ FAJ")

    st.caption(
        f"Platform v{config.PLATFORM_VERSION}"
    )

    st.divider()

    # --------------------------------------------------------
    # MAIN
    # --------------------------------------------------------

    if st.button(
        "🏠 Главная",
        use_container_width=True,
        key="menu_home",
    ):

        go_to_page("home")
        st.session_state.prediction_result = None
        st.rerun()

    if st.button(
        "📊 Прогнозы",
        use_container_width=True,
        key="menu_predictions",
    ):

        go_to_page("predictions")
        st.session_state.prediction_result = None
        st.rerun()

    if st.button(
        "🔬 Match Lab",
        use_container_width=True,
        key="menu_match_lab",
    ):

        go_to_page("match_analysis")
        st.session_state.prediction_result = None
        st.rerun()

    if st.button(
        "📋 Паспорта",
        use_container_width=True,
        key="menu_passports",
    ):

        go_to_page("passports")
        st.rerun()

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    st.divider()

    st.caption("📥 ДАННЫЕ")

    if st.button(
        "🚀 Загрузить всё",
        use_container_width=True,
        key="menu_load_all",
    ):

        go_to_page("load_all")
        st.rerun()

    if st.button(
        "📅 Загрузить календарь",
        use_container_width=True,
        key="menu_load_calendar",
    ):

        go_to_page("load_calendar")
        st.rerun()

    if st.button(
        "📊 Загрузить статистику",
        use_container_width=True,
        key="menu_load_stats",
    ):

        go_to_page("load_stats")
        st.rerun()

    # --------------------------------------------------------
    # SYSTEM
    # --------------------------------------------------------

    st.divider()

    if st.button(
        "⚙️ Система",
        use_container_width=True,
        key="menu_system",
    ):

        go_to_page("system")
        st.rerun()

    # --------------------------------------------------------
    # DATABASE STATUS
    # --------------------------------------------------------

    st.divider()

    counts = get_db_counts()

    st.caption("📊 Статус БД")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.caption(
            f"🏟️ {counts['teams']}"
        )

    with c2:
        st.caption(
            f"📋 {counts['matches']}"
        )

    with c3:
        st.caption(
            f"📊 {counts['stats']}"
        )

    st.caption(
        "Команды · Матчи · Статистика"
    )


# ============================================================
# HOME
# ============================================================

if st.session_state.page == "home":

    st.title(
        "🏠 FAJ Platform"
    )

    st.caption(
        f"FAJ Platform v{config.PLATFORM_VERSION} · "
        f"Core v{config.CORE_VERSION} · "
        f"Pipeline v{config.PIPELINE_VERSION}"
    )

    # --------------------------------------------------------
    # BOOTSTRAP STATUS
    # --------------------------------------------------------

    if bootstrap_result.get("ready"):

        st.success(
            "✅ Система готова к работе"
        )

    else:

        st.warning(
            "⚠️ Система требует внимания"
        )

        messages = bootstrap_result.get(
            "messages",
            [],
        )

        if messages:

            with st.expander(
                "📋 Детали Bootstrap"
            ):

                for message in messages:
                    st.text(message)

    st.divider()

    # --------------------------------------------------------
    # DATABASE OVERVIEW
    # --------------------------------------------------------

    counts = get_db_counts()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "🏟️ Команды",
            counts["teams"],
        )

    with c2:
        st.metric(
            "📋 Матчи",
            counts["matches"],
        )

    with c3:
        st.metric(
            "📊 Результаты",
            counts["results"],
        )

    with c4:
        st.metric(
            "📈 Статистика",
            counts["stats"],
        )

    st.divider()

    # --------------------------------------------------------
    # QUICK START
    # --------------------------------------------------------

    st.subheader(
        "🚀 Быстрый старт"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        if st.button(
            "📥 Центр данных",
            use_container_width=True,
            type="primary",
            key="home_load",
        ):

            go_to_page("load_all")
            st.rerun()

    with c2:

        if st.button(
            "📊 Сделать прогноз",
            use_container_width=True,
            key="home_predict",
        ):

            go_to_page("predictions")
            st.rerun()

    with c3:

        if st.button(
            "🔬 Match Laboratory",
            use_container_width=True,
            key="home_lab",
        ):

            go_to_page("match_analysis")
            st.rerun()


# ============================================================
# PREDICTIONS
# ============================================================

elif st.session_state.page == "predictions":

    st.title(
        "📊 Прогнозы матчей"
    )

    st.caption(
        f"FAJ Prediction Engine · "
        f"Pipeline v{config.PIPELINE_VERSION}"
    )

    try:

        conn = get_connection()

        teams_df = pd.read_sql(
            """
            SELECT id, name
            FROM teams
            WHERE league = 'РПЛ'
            ORDER BY name
            """,
            conn,
        )

        conn.close()

    except Exception as e:

        teams_df = pd.DataFrame()

        st.error(
            f"❌ Ошибка чтения команд: {e}"
        )

    if teams_df.empty:

        st.warning(
            "⚠️ В базе нет команд РПЛ."
        )

        if st.button(
            "🚀 Перейти к загрузке данных",
            key="predict_go_load_all",
        ):

            go_to_page("load_all")
            st.rerun()

    else:

        col1, col2 = st.columns(2)

        with col1:

            team1 = st.selectbox(
                "🏠 Хозяева",
                teams_df["name"].tolist(),
                key="team1",
            )

        with col2:

            team2 = st.selectbox(
                "✈️ Гости",
                teams_df["name"].tolist(),
                key="team2",
            )

        if st.button(
            "🔮 Сделать прогноз",
            type="primary",
            use_container_width=True,
            key="do_predict",
        ):

            if team1 == team2:

                st.error(
                    "❌ Команды не могут совпадать."
                )

                st.session_state.prediction_result = None

            else:

                with st.spinner(
                    "🧠 FAJ рассчитывает прогноз..."
                ):

                    try:

                        pm = get_prediction_manager()

                        result = pm.predict(
                            home_team=team1,
                            away_team=team2,
                            league="RPL",
                        )

                        st.session_state.prediction_result = result

                    except Exception as e:

                        st.error(
                            f"❌ Ошибка прогноза: {e}"
                        )

                        st.session_state.prediction_result = None

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        result = (
            st.session_state.prediction_result
        )

        if result:

            if result.get("status") == "error":

                st.error(
                    f"❌ {result.get('message', 'Ошибка')}"
                )

            else:

                st.divider()

                st.subheader(
                    f"📊 "
                    f"{result.get('home_team', '')} "
                    f"vs "
                    f"{result.get('away_team', '')}"
                )

                xg = result.get(
                    "xg",
                    {},
                )

                probability = result.get(
                    "probability",
                    {},
                )

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "🏠 xG хозяев",
                        f"{xg.get('home', 0):.2f}",
                    )

                with c2:

                    st.metric(
                        "🎯 Прогноз",
                        result.get(
                            "score",
                            "0:0",
                        ),
                    )

                    st.caption(
                        "Вероятность: "
                        f"{result.get('score_probability', 0):.1%}"
                    )

                with c3:

                    st.metric(
                        "✈️ xG гостей",
                        f"{xg.get('away', 0):.2f}",
                    )

                # ------------------------------------------------
                # PROBABILITIES
                # ------------------------------------------------

                st.subheader(
                    "📈 Вероятности"
                )

                prob_df = pd.DataFrame(
                    {
                        "Исход": [
                            "Победа хозяев",
                            "Ничья",
                            "Победа гостей",
                        ],
                        "Вероятность": [
                            probability.get(
                                "home",
                                0,
                            ),
                            probability.get(
                                "draw",
                                0,
                            ),
                            probability.get(
                                "away",
                                0,
                            ),
                        ],
                    }
                )

                st.bar_chart(
                    prob_df.set_index(
                        "Исход"
                    )
                )

                # ------------------------------------------------
                # EXTENDED
                # ------------------------------------------------

                extended = result.get(
                    "extended",
                    {},
                )

                if extended:

                    st.subheader(
                        "📋 Расширенные метрики"
                    )

                    c1, c2 = st.columns(2)

                    with c1:

                        st.write(
                            "**⚽ Обе забьют**"
                        )

                        btts = extended.get(
                            "btts",
                            {},
                        )

                        st.metric(
                            "Да",
                            f"{btts.get('yes', 0):.1%}",
                        )

                        st.metric(
                            "Нет",
                            f"{btts.get('no', 0):.1%}",
                        )

                    with c2:

                        st.write(
                            "**📊 Тоталы**"
                        )

                        total = extended.get(
                            "total",
                            {},
                        )

                        st.metric(
                            "Тотал > 2.5",
                            f"{total.get('over_2_5', 0):.1%}",
                        )

                        st.metric(
                            "Тотал > 3.5",
                            f"{total.get('over_3_5', 0):.1%}",
                        )

                    top_scores = extended.get(
                        "top_scores",
                        [],
                    )

                    if top_scores:

                        st.subheader(
                            "🎯 Топ точных счетов"
                        )

                        scores_data = []

                        for score in top_scores:

                            scores_data.append(
                                {
                                    "№": score.get(
                                        "rank",
                                        0,
                                    ),
                                    "Счёт": (
                                        f"{score.get('home', 0)}:"
                                        f"{score.get('away', 0)}"
                                    ),
                                    "Вероятность": score.get(
                                        "prob_percent",
                                        "0%",
                                    ),
                                }
                            )

                        st.dataframe(
                            pd.DataFrame(
                                scores_data
                            ).set_index("№"),
                            use_container_width=True,
                        )

                with st.expander(
                    "📋 Полный результат JSON"
                ):

                    st.json(result)


# ============================================================
# MATCH LABORATORY
# ============================================================

elif st.session_state.page == "match_analysis":

    try:

        from app.pages.match_analysis import (
            main as match_analysis_main
        )

        match_analysis_main()

    except ImportError as e:

        st.error(
            f"❌ Match Laboratory не найден: {e}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка Match Laboratory: {e}"
        )


# ============================================================
# PASSPORTS
# ============================================================

elif st.session_state.page == "passports":

    st.title(
        "📋 Паспорта команд"
    )

    st.caption(
        "FAJ Passport Manager"
    )

    try:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
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
            """
        )

        rows = cursor.fetchall()

        conn.close()

        if not rows:

            st.warning(
                "⚠️ Паспорта пока не загружены."
            )

            if st.button(
                "🚀 Перейти к загрузке",
                key="passports_go_load_all",
            ):

                go_to_page("load_all")
                st.rerun()

        else:

            data = []

            for row in rows:

                try:

                    team_name = row["team_name"]

                    if team_name:

                        data.append(
                            {
                                "Команда": team_name,
                                "Атака": round(
                                    row["attack"] or 50,
                                    1,
                                ),
                                "Защита": round(
                                    row["defense"] or 50,
                                    1,
                                ),
                                "Контроль": round(
                                    row["control"] or 50,
                                    1,
                                ),
                                "Вратарь": round(
                                    row["goalkeeper"] or 50,
                                    1,
                                ),
                                "FAJ Rating": round(
                                    row["faj_rating"] or 0,
                                    1,
                                ),
                            }
                        )

                except Exception:
                    continue

            if data:

                st.dataframe(
                    pd.DataFrame(data),
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    f"📊 Команд: {len(data)}"
                )


    except Exception as e:

        st.error(
            f"❌ Ошибка загрузки паспортов: {e}"
        )


# ============================================================
# LOAD ALL
# ============================================================

elif st.session_state.page == "load_all":

    try:

        from app.pages.load_all import (
            main as load_all_main
        )

        load_all_main()

    except ImportError as e:

        st.error(
            f"❌ Страница 'Загрузить всё' не найдена: {e}"
        )

        st.info(
            "Проверьте наличие файла "
            "app/pages/load_all.py"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка страницы загрузки: {e}"
        )


# ============================================================
# LOAD CALENDAR
# ============================================================

elif st.session_state.page == "load_calendar":

    try:

        from app.pages.load_calendar import (
            main as load_calendar_main
        )

        load_calendar_main()

    except ImportError as e:

        st.error(
            f"❌ Страница календаря не найдена: {e}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка загрузки календаря: {e}"
        )


# ============================================================
# LOAD STATISTICS
# ============================================================

elif st.session_state.page == "load_stats":

    try:

        from app.pages.load_stats import (
            main as load_stats_main
        )

        load_stats_main()

    except ImportError as e:

        st.error(
            f"❌ Страница статистики не найдена: {e}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка загрузки статистики: {e}"
        )


# ============================================================
# SYSTEM
# ============================================================

elif st.session_state.page == "system":

    st.title(
        "⚙️ Система"
    )

    try:

        db = FAJDatabase()

        status_db = db.get_status()

        tables = status_db.get(
            "tables",
            {},
        )

        st.subheader(
            "📊 База данных"
        )

        c1, c2 = st.columns(2)

        with c1:

            st.write(
                "**Основные таблицы**"
            )

            st.write(
                f"- teams: "
                f"{tables.get('teams', 0)}"
            )

            st.write(
                f"- matches: "
                f"{tables.get('matches', 0)}"
            )

            st.write(
                f"- match_results: "
                f"{tables.get('match_results', 0)}"
            )

            st.write(
                f"- match_statistics: "
                f"{tables.get('match_statistics', 0)}"
            )

        with c2:

            st.write(
                "**FAJ**"
            )

            st.write(
                f"- team_passports: "
                f"{tables.get('team_passports', 0)}"
            )

            st.write(
                f"- predictions: "
                f"{tables.get('predictions', 0)}"
            )

            st.write(
                f"- expert_predictions: "
                f"{tables.get('expert_predictions', 0)}"
            )

        st.divider()

        # ----------------------------------------------------
        # DB FILE
        # ----------------------------------------------------

        db_path = os.path.join(
            ROOT_DIR,
            "data",
            "faj.db",
        )

        st.subheader(
            "💾 SQLite"
        )

        st.write(
            f"**Файл:** `{db_path}`"
        )

        if os.path.exists(db_path):

            size = (
                os.path.getsize(db_path)
                / (1024 * 1024)
            )

            st.write(
                f"**Размер:** {size:.2f} MB"
            )

        else:

            st.warning(
                "Файл SQLite пока не найден."
            )

        # ----------------------------------------------------
        # VERSIONS
        # ----------------------------------------------------

        st.divider()

        st.subheader(
            "📌 Версии"
        )

        st.write(
            f"**Platform:** "
            f"v{config.PLATFORM_VERSION}"
        )

        st.write(
            f"**Core:** "
            f"v{config.CORE_VERSION}"
        )

        st.write(
            f"**Pipeline:** "
            f"v{config.PIPELINE_VERSION}"
        )

        st.divider()

        st.caption(
            "Текущее время: "
            f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка системной страницы: {e}"
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"⚽ FAJ Platform v{config.PLATFORM_VERSION} · "
    f"Core v{config.CORE_VERSION} · "
    f"Pipeline v{config.PIPELINE_VERSION} · "
    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
STREAMLIT MAIN APPLICATION
============================================================

Главная точка входа FAJ Platform.

АРХИТЕКТУРА:

    streamlit_app.py
            |
            +-- Auto Bootstrap
            |
            +-- Главная
            |
            +-- Прогнозы
            |      |
            |      +-- PredictionManager
            |              |
            |              +-- PredictionPipeline
            |                      |
            |                      +-- xG
            |                      +-- Poisson
            |                      +-- Monte Carlo
            |
            +-- Match Laboratory
            |
            +-- Паспорта
            |
            +-- System Trace
            |
            +-- Database Diagnostic
            |
            +-- Load All
            +-- Load Calendar
            +-- Load Statistics
            |
            +-- System

ПРИНЦИПЫ:

    - SQLite only
    - database.py — единый источник схемы
    - persistent state хранится в БД
    - Streamlit rerun не должен обнулять БД
    - streamlit_app.py не содержит математическое ядро
    - streamlit_app.py не содержит загрузчики
    - streamlit_app.py не содержит обучение
    - диагностика БД работает только на чтение
    - System Trace работает только на чтение
    - никаких DELETE / DROP / очистки исторических данных
============================================================
"""

import os
import sys
import sqlite3
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
    from app.database import get_connection, FAJDatabase
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.database: {e}")
    st.stop()


# ============================================================
# PREDICTION MANAGER
# ============================================================

try:
    from app.core.prediction_manager import get_prediction_manager
except Exception as e:
    get_prediction_manager = None


# ============================================================
# GITHUB SYNC
# ============================================================

try:
    from app.github_db_sync import save_database_to_github
except Exception as e:
    save_database_to_github = None


# ============================================================
# DATABASE PATH
# ============================================================

DB_PATH = os.path.join(
    ROOT_DIR,
    "data",
    "faj.db",
)


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "prediction_result" not in st.session_state:
    st.session_state.prediction_result = None


# ============================================================
# NAVIGATION
# ============================================================

def go_to_page(page_name):
    """
    Единая навигация приложения.
    """
    st.session_state.page = page_name


def navigate(page_name, clear_prediction=False):
    """
    Переключение страницы.
    """
    st.session_state.page = page_name

    if clear_prediction:
        st.session_state.prediction_result = None

    st.rerun()


# ============================================================
# AUTO BOOTSTRAP
# ============================================================

bootstrap_result = {
    "ready": True,
    "messages": [],
}

try:

    from app.bootstrap import bootstrap_faj

    result = bootstrap_faj()

    if isinstance(result, dict):
        bootstrap_result = result
    else:
        bootstrap_result = {
            "ready": True,
            "messages": [str(result)],
        }

except Exception as e:

    bootstrap_result = {
        "ready": False,
        "messages": [
            f"Ошибка Auto Bootstrap: {e}"
        ],
    }


# ============================================================
# DATABASE HELPERS
# ============================================================

def database_exists():
    """
    Проверяет наличие SQLite-файла.
    Только чтение.
    """
    return os.path.exists(DB_PATH)


def get_db_connection():
    """
    Получает соединение с БД через единый database.py.
    """
    return get_connection()


def get_db_counts():
    """
    Базовые счётчики БД.

    ВАЖНО:
        Функция только читает БД.

    Если конкретной таблицы нет,
    она просто получает значение 0.
    """

    result = {
        "tables": 0,
        "teams": 0,
        "matches": 0,
        "predictions": 0,
    }

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # Количество таблиц
        try:

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
                """
            )

            row = cursor.fetchone()

            if row:
                result["tables"] = row[0] or 0

        except Exception:
            pass

        # Отдельные таблицы
        table_map = {
            "teams": "teams",
            "matches": "matches",
            "predictions": "predictions",
        }

        for key, table in table_map.items():

            try:

                cursor.execute(
                    f"SELECT COUNT(*) FROM {table}"
                )

                row = cursor.fetchone()

                if row:
                    result[key] = row[0] or 0

            except Exception:

                result[key] = 0

        conn.close()

    except Exception:
        pass

    return result


def get_all_tables():
    """
    Возвращает реальные таблицы SQLite.

    Только чтение.
    """

    tables = []

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )

        rows = cursor.fetchall()

        for row in rows:

            try:
                tables.append(row[0])
            except Exception:
                pass

        conn.close()

    except Exception:
        pass

    return tables


def get_table_count(table_name):
    """
    Безопасно получает количество записей в таблице.
    """

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # table_name получен только из sqlite_master
        # и используется исключительно для SELECT.
        cursor.execute(
            f"SELECT COUNT(*) FROM [{table_name}]"
        )

        row = cursor.fetchone()

        conn.close()

        if row:
            return row[0] or 0

    except Exception:
        pass

    return None


def get_table_columns(table_name):
    """
    Получает структуру таблицы SQLite.
    Только чтение.
    """

    columns = []

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info([{table_name}])"
        )

        rows = cursor.fetchall()

        for row in rows:

            columns.append(
                {
                    "cid": row[0],
                    "name": row[1],
                    "type": row[2],
                    "notnull": row[3],
                    "default": row[4],
                    "pk": row[5],
                }
            )

        conn.close()

    except Exception:
        pass

    return columns


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("⚽ FAJ")

    st.caption(
        f"Platform v{config.PLATFORM_VERSION}"
    )

    st.divider()

    # ========================================================
    # MAIN
    # ========================================================

    st.caption("🏠 ОСНОВНОЕ")

    if st.button(
        "🏠 Главная",
        use_container_width=True,
        key="nav_home",
    ):
        navigate("home", clear_prediction=True)

    if st.button(
        "📊 Прогнозы",
        use_container_width=True,
        key="nav_predictions",
    ):
        navigate("predictions")

    if st.button(
        "🔬 Match Laboratory",
        use_container_width=True,
        key="nav_match_lab",
    ):
        navigate("match_analysis")


    if st.button(
        "📋 Паспорта",
        use_container_width=True,
        key="nav_passports",
    ):
        navigate("passports")


    # ========================================================
    # DIAGNOSTICS
    # ========================================================

    st.divider()

    st.caption("🔍 ДИАГНОСТИКА")

    if st.button(
        "🧬 System Trace",
        use_container_width=True,
        key="nav_system_trace",
    ):
        navigate("system_trace")


    if st.button(
        "🔍 Диагностика БД",
        use_container_width=True,
        key="nav_database",
    ):
        navigate("database")


    # ========================================================
    # DATA
    # ========================================================

    st.divider()

    st.caption("📥 ДАННЫЕ")

    if st.button(
        "🚀 Загрузить всё",
        use_container_width=True,
        key="nav_load_all",
    ):
        navigate("load_all")


    if st.button(
        "📅 Календарь",
        use_container_width=True,
        key="nav_calendar",
    ):
        navigate("load_calendar")


    if st.button(
        "📊 Статистика",
        use_container_width=True,
        key="nav_stats",
    ):
        navigate("load_stats")


    # ========================================================
    # GITHUB SYNC
    # ========================================================

    st.divider()

    st.caption("💾 GitHub Sync")

    if st.button(
        "💾 Сохранить БД в GitHub",
        use_container_width=True,
        key="nav_save_db",
    ):
        try:
            if save_database_to_github is None:
                st.error("❌ Модуль github_db_sync не загружен.")
            else:
                with st.spinner("⏳ Сохранение faj.db в GitHub..."):
                    result = save_database_to_github()
                    st.success(
                        f"✅ База данных сохранена в GitHub!\n"
                        f"   Файл: {result['path']}\n"
                        f"   Размер: {result['size'] // 1024} KB\n"
                        f"   SHA: {result['sha'][:8]}..."
                    )
        except FileNotFoundError as e:
            st.error(f"❌ {e}")
        except RuntimeError as e:
            st.error(f"❌ {e}")
        except Exception as e:
            st.error(f"❌ Ошибка сохранения: {e}")
            with st.expander("Техническая ошибка"):
                st.exception(e)


    # ========================================================
    # SYSTEM
    # ========================================================

    st.divider()

    if st.button(
        "⚙️ Система",
        use_container_width=True,
        key="nav_system",
    ):
        navigate("system")


    # ========================================================
    # DATABASE STATUS
    # ========================================================

    st.divider()

    st.caption("📊 БД")

    counts = get_db_counts()

    c1, c2, c3 = st.columns(3)

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

    with c3:
        st.metric(
            "Прогнозы",
            counts["predictions"],
        )

    if database_exists():

        st.caption("🟢 SQLite подключена")

    else:

        st.caption("🔴 faj.db не найден")


# ============================================================
# HOME
# ============================================================

if st.session_state.page == "home":

    st.title("🏠 FAJ Platform")

    st.caption(
        f"FAJ Platform v{config.PLATFORM_VERSION} · "
        f"Core v{config.CORE_VERSION} · "
        f"Pipeline v{config.PIPELINE_VERSION}"
    )

    st.divider()

    # --------------------------------------------------------
    # BOOTSTRAP
    # --------------------------------------------------------

    st.subheader("🚀 Состояние системы")

    if bootstrap_result.get("ready"):

        st.success(
            "✅ Auto Bootstrap: система готова"
        )

    else:

        st.warning(
            "⚠️ Auto Bootstrap сообщает о проблеме"
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
                    st.text(str(message))


    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    st.divider()

    st.subheader("💾 База данных")

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
            "🗄️ Таблицы",
            counts["tables"],
        )


    # --------------------------------------------------------
    # QUICK START
    # --------------------------------------------------------

    st.divider()

    st.subheader("🚀 Быстрый старт")

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        if st.button(
            "📥 Центр данных",
            use_container_width=True,
            type="primary",
            key="home_load_all",
        ):
            navigate("load_all")


    with c2:

        if st.button(
            "📊 Прогноз",
            use_container_width=True,
            key="home_prediction",
        ):
            navigate("predictions")


    with c3:

        if st.button(
            "🔬 Match Lab",
            use_container_width=True,
            key="home_match_lab",
        ):
            navigate("match_analysis")


    with c4:

        if st.button(
            "🧬 System Trace",
            use_container_width=True,
            key="home_trace",
        ):
            navigate("system_trace")


    # --------------------------------------------------------
    # ARCHITECTURE
    # --------------------------------------------------------

    st.divider()

    st.subheader("🧠 Архитектура FAJ v12.1")

    st.code(
        """
Streamlit
    │
    ├── Auto Bootstrap
    │
    ├── Predictions
    │      │
    │      └── PredictionManager
    │              │
    │              └── PredictionPipeline
    │                      │
    │                      ├── xG Model
    │                      ├── Poisson Model
    │                      └── Monte Carlo Model
    │
    ├── Match Laboratory
    │
    ├── Passports
    │
    ├── Data Loaders
    │
    ├── System Trace
    │
    └── SQLite
           │
           └── database.py
        """,
        language="text",
    )


# ============================================================
# PREDICTIONS
# ============================================================

elif st.session_state.page == "predictions":

    st.title("📊 Прогнозы FAJ")

    st.caption(
        "Prediction Manager → Prediction Pipeline → Models"
    )

    st.divider()

    if get_prediction_manager is None:

        st.error(
            "❌ Prediction Manager не удалось загрузить."
        )

        st.stop()


    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    try:

        conn = get_db_connection()

        teams_df = pd.read_sql_query(
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
            "⚠️ В БД пока нет команд РПЛ."
        )

        if st.button(
            "🚀 Перейти в Центр данных",
            type="primary",
            key="prediction_go_data",
        ):
            navigate("load_all")


    else:

        col1, col2 = st.columns(2)

        team_names = teams_df["name"].tolist()

        with col1:

            team1 = st.selectbox(
                "🏠 Хозяева",
                team_names,
                key="prediction_home_team",
            )

        with col2:

            team2 = st.selectbox(
                "✈️ Гости",
                team_names,
                key="prediction_away_team",
            )


        if st.button(
            "🔮 РАССЧИТАТЬ ПРОГНОЗ",
            type="primary",
            use_container_width=True,
            key="calculate_prediction",
        ):

            if team1 == team2:

                st.error(
                    "❌ Хозяева и гости должны быть разными командами."
                )

                st.session_state.prediction_result = None

            else:

                with st.spinner(
                    "🧠 FAJ рассчитывает прогноз..."
                ):

                    try:

                        manager = get_prediction_manager()

                        result = manager.predict(
                            home_team=team1,
                            away_team=team2,
                            league="RPL",
                        )

                        st.session_state.prediction_result = result

                    except Exception as e:

                        st.session_state.prediction_result = None

                        st.error(
                            f"❌ Ошибка Prediction Manager: {e}"
                        )

                        with st.expander(
                            "Техническая информация"
                        ):
                            st.exception(e)


        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        result = st.session_state.prediction_result

        if result:

            if result.get("status") == "error":

                st.error(
                    result.get(
                        "message",
                        "Prediction Engine вернул ошибку.",
                    )
                )

            else:

                st.divider()

                home_team = result.get(
                    "home_team",
                    team1,
                )

                away_team = result.get(
                    "away_team",
                    team2,
                )

                st.subheader(
                    f"⚽ {home_team} — {away_team}"
                )


                xg = result.get(
                    "xg",
                    {},
                )

                probability = result.get(
                    "probability",
                    {},
                )


                # ------------------------------------------------
                # MAIN RESULT
                # ------------------------------------------------

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "🏠 xG хозяев",
                        f"{float(xg.get('home', 0) or 0):.2f}",
                    )

                with c2:

                    st.metric(
                        "🎯 Прогноз",
                        result.get(
                            "score",
                            "—",
                        ),
                    )

                    score_probability = (
                        result.get(
                            "score_probability",
                            0,
                        )
                        or 0
                    )

                    try:

                        st.caption(
                            "Вероятность точного счёта: "
                            f"{float(score_probability):.1%}"
                        )

                    except Exception:

                        pass

                with c3:

                    st.metric(
                        "✈️ xG гостей",
                        f"{float(xg.get('away', 0) or 0):.2f}",
                    )


                # ------------------------------------------------
                # RESULT PROBABILITIES
                # ------------------------------------------------

                st.subheader(
                    "📈 Вероятности исходов"
                )

                prob_home = (
                    probability.get("home", 0)
                    or 0
                )

                prob_draw = (
                    probability.get("draw", 0)
                    or 0
                )

                prob_away = (
                    probability.get("away", 0)
                    or 0
                )

                prob_df = pd.DataFrame(
                    {
                        "Исход": [
                            "Победа хозяев",
                            "Ничья",
                            "Победа гостей",
                        ],
                        "Вероятность": [
                            prob_home,
                            prob_draw,
                            prob_away,
                        ],
                    }
                )

                st.bar_chart(
                    prob_df.set_index("Исход")
                )


                # ------------------------------------------------
                # EXTENDED
                # ------------------------------------------------

                extended = result.get(
                    "extended",
                    {},
                )

                if extended:

                    st.divider()

                    st.subheader(
                        "📋 Расширенные показатели"
                    )

                    c1, c2 = st.columns(2)

                    with c1:

                        st.write(
                            "### ⚽ Обе забьют"
                        )

                        btts = extended.get(
                            "btts",
                            {},
                        )

                        yes_value = (
                            btts.get("yes", 0)
                            or 0
                        )

                        no_value = (
                            btts.get("no", 0)
                            or 0
                        )

                        try:

                            st.metric(
                                "Да",
                                f"{float(yes_value):.1%}",
                            )

                            st.metric(
                                "Нет",
                                f"{float(no_value):.1%}",
                            )

                        except Exception:

                            st.write(btts)


                    with c2:

                        st.write(
                            "### 📊 Тоталы"
                        )

                        total = extended.get(
                            "total",
                            {},
                        )

                        over25 = (
                            total.get(
                                "over_2_5",
                                0,
                            )
                            or 0
                        )

                        over35 = (
                            total.get(
                                "over_3_5",
                                0,
                            )
                            or 0
                        )

                        try:

                            st.metric(
                                "Тотал > 2.5",
                                f"{float(over25):.1%}",
                            )

                            st.metric(
                                "Тотал > 3.5",
                                f"{float(over35):.1%}",
                            )

                        except Exception:

                            st.write(total)


                    # ------------------------------------------------
                    # TOP SCORES
                    # ------------------------------------------------

                    top_scores = extended.get(
                        "top_scores",
                        [],
                    )

                    if top_scores:

                        st.subheader(
                            "🎯 Наиболее вероятные счета"
                        )

                        score_rows = []

                        for score in top_scores:

                            score_rows.append(
                                {
                                    "№": score.get(
                                        "rank",
                                        len(score_rows) + 1,
                                    ),
                                    "Счёт": (
                                        f"{score.get('home', 0)}:"
                                        f"{score.get('away', 0)}"
                                    ),
                                    "Вероятность": score.get(
                                        "prob_percent",
                                        "—",
                                    ),
                                }
                            )

                        if score_rows:

                            st.dataframe(
                                pd.DataFrame(score_rows),
                                use_container_width=True,
                                hide_index=True,
                            )


                # ------------------------------------------------
                # RAW RESULT
                # ------------------------------------------------

                with st.expander(
                    "📋 Полный результат Prediction Manager"
                ):

                    st.json(result)


# ============================================================
# MATCH LABORATORY
# ============================================================

elif st.session_state.page == "match_analysis":

    st.title("🔬 Match Laboratory")

    st.caption(
        "Диагностика прогноза от Team Passport до Monte Carlo"
    )

    try:

        from app.pages.match_analysis import main

        main()

    except ImportError as e:

        st.error(
            f"❌ Match Laboratory не найден: {e}"
        )

        st.info(
            "Проверь файл app/pages/match_analysis.py"
        )

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

    st.caption(
        "Team Passport · FAJ Rating · Team Intelligence"
    )

    st.divider()

    try:

        conn = get_db_connection()

        query = """
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

        passport_df = pd.read_sql_query(
            query,
            conn,
        )

        conn.close()


        if passport_df.empty:

            st.warning(
                "⚠️ Паспорта команд пока не найдены."
            )

            if st.button(
                "🚀 Перейти в Центр данных",
                key="passport_go_data",
            ):
                navigate("load_all")

        else:

            display_df = passport_df.copy()

            display_df = display_df.rename(
                columns={
                    "team_name": "Команда",
                    "attack": "Атака",
                    "defense": "Защита",
                    "control": "Контроль",
                    "goalkeeper": "Вратарь",
                    "faj_rating": "FAJ Rating",
                }
            )

            numeric_columns = [
                "Атака",
                "Защита",
                "Контроль",
                "Вратарь",
                "FAJ Rating",
            ]

            for column in numeric_columns:

                if column in display_df.columns:

                    display_df[column] = pd.to_numeric(
                        display_df[column],
                        errors="coerce",
                    ).round(1)

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                f"📊 Команд в выборке: {len(display_df)}"
            )

    except Exception as e:

        st.error(
            f"❌ Ошибка загрузки паспортов: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):
            st.exception(e)


# ============================================================
# SYSTEM TRACE
# ============================================================

elif st.session_state.page == "system_trace":

    st.title("🧬 System Trace")

    st.caption(
        "Фактическая архитектура FAJ Platform v12.1"
    )

    st.info(
        "System Trace работает в режиме чтения. "
        "Он показывает реальные связи файлов и не изменяет проект."
    )

    try:

        from app.pages.system_trace import main

        main()

    except ImportError as e:

        st.error(
            f"❌ System Trace не найден: {e}"
        )

        st.info(
            "Ожидаемый файл: "
            "app/pages/system_trace.py"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка System Trace: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):
            st.exception(e)


# ============================================================
# DATABASE DIAGNOSTIC
# ============================================================

elif st.session_state.page == "database":

    st.title("🔍 Диагностика базы данных")

    st.caption(
        "FAJ Database Diagnostic · READ ONLY"
    )

    st.info(
        "⚠️ Эта страница ничего не удаляет, "
        "не очищает и не изменяет в базе данных."
    )

    # --------------------------------------------------------
    # DATABASE FILE
    # --------------------------------------------------------

    st.subheader("💾 SQLite")

    c1, c2, c3 = st.columns(3)

    with c1:

        if database_exists():

            st.success("✅ faj.db найден")

        else:

            st.error("❌ faj.db не найден")


    with c2:

        st.write(
            f"**Путь:** `{DB_PATH}`"
        )


    with c3:

        if database_exists():

            size_mb = (
                os.path.getsize(DB_PATH)
                / 1024
                / 1024
            )

            st.metric(
                "Размер",
                f"{size_mb:.2f} MB",
            )


    # --------------------------------------------------------
    # COUNTS
    # --------------------------------------------------------

    st.divider()

    st.subheader("📊 Основные показатели")

    counts = get_db_counts()

    c1, c2, c3, c4 = st.columns(4)

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

    with c3:

        st.metric(
            "Прогнозы",
            counts["predictions"],
        )

    with c4:

        st.metric(
            "Таблицы",
            counts["tables"],
        )


    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    st.divider()

    st.subheader("🗄️ Реальные таблицы БД")

    tables = get_all_tables()

    if not tables:

        st.warning(
            "⚠️ Таблицы не обнаружены."
        )

    else:

        table_rows = []

        for table in tables:

            count = get_table_count(table)

            table_rows.append(
                {
                    "Таблица": table,
                    "Записей": (
                        count
                        if count is not None
                        else "—"
                    ),
                }
            )

        table_df = pd.DataFrame(
            table_rows
        )

        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
        )


    # --------------------------------------------------------
    # TABLE INSPECTOR
    # --------------------------------------------------------

    if tables:

        st.divider()

        st.subheader(
            "🔬 Инспектор таблицы"
        )

        selected_table = st.selectbox(
            "Выберите таблицу",
            tables,
            key="db_selected_table",
        )

        if selected_table:

            columns = get_table_columns(
                selected_table
            )

            if columns:

                st.dataframe(
                    pd.DataFrame(columns),
                    use_container_width=True,
                    hide_index=True,
                )

            else:

                st.warning(
                    "Структура таблицы недоступна."
                )


    # --------------------------------------------------------
    # FOREIGN KEY
    # --------------------------------------------------------

    st.divider()

    st.subheader("🔗 Foreign Key Check")

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "PRAGMA foreign_key_check"
        )

        fk_errors = cursor.fetchall()

        conn.close()

        if not fk_errors:

            st.success(
                "✅ Нарушений FOREIGN KEY не обнаружено."
            )

        else:

            st.error(
                f"❌ Обнаружено нарушений: "
                f"{len(fk_errors)}"
            )

            fk_rows = []

            for row in fk_errors:

                fk_rows.append(
                    {
                        "Таблица": row[0],
                        "Row ID": row[1],
                        "Parent": row[2],
                        "Parent Row": row[3],
                    }
                )

            st.dataframe(
                pd.DataFrame(fk_rows),
                use_container_width=True,
                hide_index=True,
            )

    except Exception as e:

        st.error(
            f"❌ Ошибка FOREIGN KEY check: {e}"
        )


    # --------------------------------------------------------
    # INTEGRITY
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🩺 SQLite Integrity Check"
    )

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "PRAGMA integrity_check"
        )

        row = cursor.fetchone()

        conn.close()

        if row:

            integrity = row[0]

            if integrity == "ok":

                st.success(
                    "✅ SQLite integrity_check: OK"
                )

            else:

                st.error(
                    f"❌ SQLite integrity_check: "
                    f"{integrity}"
                )

    except Exception as e:

        st.error(
            f"❌ Ошибка integrity_check: {e}"
        )


    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    st.divider()

    st.success(
        "🔍 Диагностика завершена. "
        "Режим READ ONLY."
    )


# ============================================================
# LOAD ALL
# ============================================================

elif st.session_state.page == "load_all":

    st.title("🚀 Центр загрузки данных")

    st.caption(
        "FAJ Data Loading Center"
    )

    try:

        from app.pages.load_all import main

        main()

    except ImportError as e:

        st.error(
            f"❌ load_all.py не найден: {e}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка Центра загрузки: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):
            st.exception(e)


# ============================================================
# LOAD CALENDAR
# ============================================================

elif st.session_state.page == "load_calendar":

    st.title("📅 Загрузка календаря")

    st.caption(
        "FAJ Calendar Loader"
    )

    try:

        from app.pages.load_calendar import main

        main()

    except ImportError as e:

        st.error(
            f"❌ load_calendar.py не найден: {e}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка загрузки календаря: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):
            st.exception(e)


# ============================================================
# LOAD STATISTICS
# ============================================================

elif st.session_state.page == "load_stats":

    st.title("📊 Загрузка статистики")

    st.caption(
        "FAJ Statistics Loader"
    )

    try:

        from app.pages.load_stats import main

        main()

    except ImportError as e:

        st.error(
            f"❌ load_stats.py не найден: {e}"
        )

    except Exception as e:

        st.error(
            f"❌ Ошибка загрузки статистики: {e}"
        )

        with st.expander(
            "Техническая ошибка"
        ):
            st.exception(e)


# ============================================================
# SYSTEM
# ============================================================

elif st.session_state.page == "system":

    st.title("⚙️ Система")

    st.caption(
        "FAJ Platform · System Status"
    )

    # --------------------------------------------------------
    # VERSIONS
    # --------------------------------------------------------

    st.subheader("📌 Версии")

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


    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    st.divider()

    st.subheader("💾 SQLite")

    if database_exists():

        size_mb = (
            os.path.getsize(DB_PATH)
            / 1024
            / 1024
        )

        st.success(
            "🟢 База данных доступна"
        )

        st.write(
            f"**Файл:** `{DB_PATH}`"
        )

        st.write(
            f"**Размер:** {size_mb:.2f} MB"
        )

    else:

        st.error(
            "🔴 faj.db не найден"
        )


    # --------------------------------------------------------
    # DATABASE STATUS
    # --------------------------------------------------------

    st.divider()

    try:

        db = FAJDatabase()

        status = db.get_status()

        if isinstance(status, dict):

            st.subheader(
                "📊 Статус database.py"
            )

            status_rows = []

            for key, value in status.items():

                status_rows.append(
                    {
                        "Параметр": key,
                        "Значение": value,
                    }
                )

            if status_rows:

                st.dataframe(
                    pd.DataFrame(status_rows),
                    use_container_width=True,
                    hide_index=True,
                )

    except Exception as e:

        st.warning(
            f"⚠️ Статус БД недоступен: {e}"
        )


    # --------------------------------------------------------
    # TABLE SUMMARY
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🗄️ Краткая статистика БД"
    )

    counts = get_db_counts()

    summary_df = pd.DataFrame(
        [
            {
                "Показатель": "Таблицы",
                "Количество": counts["tables"],
            },
            {
                "Показатель": "Команды",
                "Количество": counts["teams"],
            },
            {
                "Показатель": "Матчи",
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


    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    st.divider()

    st.caption(
        "Текущее время: "
        f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )


# ============================================================
# UNKNOWN PAGE
# ============================================================

else:

    st.session_state.page = "home"

    st.rerun()


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

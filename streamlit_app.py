#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
MAIN APPLICATION — НОВАЯ АРХИТЕКТУРА
============================================================

ПРИНЦИПЫ:
    - SQLite only
    - database.py — единый источник схемы
    - Никакого DELETE / DROP (кроме контролируемой очистки)
    - Календарь создаётся через UI
    - Факты загружаются через ссылки
    - Прогнозы только для НЕСЫГРАННЫХ матчей
    - Обучение только после закрытия тура
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
    st.session_state.page = "tour_manager"  # по умолчанию открываем управление турами

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
# SEASON — ИСПРАВЛЕНО
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
                    OR name LIKE '%2026-2027%'
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
            LEFT JOIN teams th ON m.home_team_id = th.id
            LEFT JOIN teams ta ON m.away_team_id = ta.id
            LEFT JOIN match_results mr ON mr.match_id = m.id
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
                    "is_played": row[5] == 1 or row[5] is True,
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
        cursor.execute("SELECT COUNT(*) FROM teams WHERE league = 'РПЛ'")
        row = cursor.fetchone()
        if row:
            result["teams"] = row[0] or 0
        season = get_active_season()
        if season:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM matches m
                JOIN rounds r ON m.round_id = r.id
                WHERE r.season_id = ?
                """,
                (season["id"],),
            )
            row = cursor.fetchone()
            if row:
                result["matches"] = row[0] or 0
        if table_exists("predictions"):
            cursor.execute("SELECT COUNT(*) FROM predictions")
            row = cursor.fetchone()
            if row:
                result["predictions"] = row[0] or 0
        conn.close()
    except Exception:
        pass
    return result


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("⚽ FAJ")
    st.caption(f"Platform v{config.PLATFORM_VERSION}")
    st.divider()

    st.caption("🏟️ ТУРНИР")
    if st.button("🗓️ Управление турами", use_container_width=True):
        navigate("tour_manager")
    if st.button("📥 Импорт фактов", use_container_width=True):
        navigate("import_facts")
    if st.button("🧠 Прогноз тура", use_container_width=True):
        navigate("predict_round")
    if st.button("🏁 Тур сыгран", use_container_width=True):
        navigate("round_complete")

    st.divider()
    st.caption("📊 АНАЛИТИКА")
    if st.button("📋 Паспорта", use_container_width=True):
        navigate("passports")
    if st.button("📊 Аналитика", use_container_width=True):
        navigate("analytics")
    if st.button("📚 История", use_container_width=True):
        navigate("history")

    st.divider()
    st.caption("⚙️ СИСТЕМА")
    if st.button("⚙️ Система", use_container_width=True):
        navigate("system")
    if st.button("🧹 Очистка данных", use_container_width=True):
        navigate("reset_data")

    st.divider()
    if st.button("🔄 Запустить FAJ Cycle", type="primary", use_container_width=True):
        with st.spinner("🧠 FAJ Cycle выполняет полный цикл..."):
            st.session_state.cycle_result = faj_cycle_runner()  # ИСПРАВЛЕНО
        st.rerun()

    st.divider()
    counts = get_db_counts()
    st.caption("📊 СОСТОЯНИЕ")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Команды", counts["teams"])
    with c2:
        st.metric("Матчи", counts["matches"])
    if database_exists():
        st.caption("🟢 SQLite")
    else:
        st.caption("🔴 SQLite отсутствует")


# ============================================================
# СТРАНИЦЫ
# ============================================================

# ---------- УПРАВЛЕНИЕ ТУРАМИ ----------
if st.session_state.page == "tour_manager":
    try:
        from app.pages.tour_manager import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ---------- ИМПОРТ ФАКТОВ ----------
elif st.session_state.page == "import_facts":
    try:
        from app.pages.import_facts import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ---------- ПРОГНОЗ ТУРА ----------
elif st.session_state.page == "predict_round":
    try:
        from app.pages.predict_round import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ---------- ТУР СЫГРАН ----------
elif st.session_state.page == "round_complete":
    try:
        from app.pages.round_complete import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ---------- ОЧИСТКА ДАННЫХ ----------
elif st.session_state.page == "reset_data":
    try:
        from app.pages.reset_data import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ---------- ПАСПОРТА ----------
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
            LEFT JOIN team_passports tp ON t.id = tp.team_id
            WHERE t.league = 'РПЛ'
            ORDER BY t.name
            """,
            conn,
        )
        conn.close()
        if passport_df.empty:
            st.info("Паспорта не найдены.")
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
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"❌ Ошибка паспортов: {e}")

# ---------- АНАЛИТИКА ----------
elif st.session_state.page == "analytics":
    st.title("📊 Аналитика")
    st.info("Аналитический слой FAJ (в разработке).")
    counts = get_db_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Матчи", counts["matches"])
    with c2:
        st.metric("Прогнозы", counts["predictions"])
    with c3:
        st.metric("Команды", counts["teams"])

# ---------- ИСТОРИЯ ----------
elif st.session_state.page == "history":
    st.title("📚 История FAJ")
    st.info("История прогнозов и фактических результатов (в разработке).")
    counts = get_db_counts()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Матчи", counts["matches"])
    with c2:
        st.metric("Прогнозы", counts["predictions"])

# ---------- СИСТЕМА ----------
elif st.session_state.page == "system":
    st.title("⚙️ Система")
    st.caption("Техническое состояние FAJ Platform")
    st.divider()
    counts = get_db_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Platform", f"v{config.PLATFORM_VERSION}")
    with c2:
        st.metric("Core", f"v{config.CORE_VERSION}")
    with c3:
        st.metric("Pipeline", f"v{config.PIPELINE_VERSION}")
    st.divider()
    st.subheader("💾 SQLite")
    if database_exists():
        st.success("🟢 SQLite доступна")
        try:
            size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
            st.metric("Размер БД", f"{size_mb:.2f} MB")
        except Exception:
            pass
    else:
        st.error("🔴 faj.db не найден")

    # ============================================================
    # ДИАГНОСТИКА БД
    # ============================================================
    st.divider()
    st.subheader("📁 Диагностика БД")
    st.write(f"**Путь к БД:** `{DB_PATH}`")
    st.write(f"**Файл существует:** {os.path.exists(DB_PATH)}")
    if os.path.exists(DB_PATH):
        size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
        st.write(f"**Размер:** {size_mb:.2f} MB")
        import time
        mtime = os.path.getmtime(DB_PATH)
        st.write(f"**Изменён:** {datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S')}")

    st.divider()
    st.subheader("🔍 Состояние")
    summary_df = pd.DataFrame(
        [
            {"Показатель": "Команды РПЛ", "Количество": counts["teams"]},
            {"Показатель": "Матчи активного сезона", "Количество": counts["matches"]},
            {"Показатель": "Прогнозы", "Количество": counts["predictions"]},
        ]
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ---------- ЕСЛИ СТРАНИЦА НЕ НАЙДЕНА ----------
else:
    st.session_state.page = "tour_manager"
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

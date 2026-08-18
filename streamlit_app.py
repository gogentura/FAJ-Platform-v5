#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1 — MEMORY HARDENED
MAIN APPLICATION — ФИНАЛЬНЫЙ ГИБРИД
============================================================

АРХИТЕКТУРА:
    streamlit_app.py
           │
    ┌──────┴──────┐
    │             │
 системный    Round Center
   слой
    │             │
 Bootstrap   tour_manager
 FAJ Cycle   predict_round
 System      import_facts
 Diagnostics round_complete
 Analytics
 History
 Passports
 Diagnostic

ПРИНЦИПЫ:
    - Никакого прямого SQL в streamlit_app.py
    - Все операции через FAJDatabase и менеджеры
    - database.py — единственный источник схемы
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
    from app.database import FAJDatabase, DB_FILE
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.database: {e}")
    st.stop()

DB_PATH = DB_FILE


# ============================================================
# MANAGERS
# ============================================================

try:
    from app.match_manager import MatchManager
except Exception:
    MatchManager = None

try:
    from app.result_manager import ResultManager
except Exception:
    ResultManager = None

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
    from app.faj_cycle import run_faj_cycle as faj_cycle_runner
    FAJ_CYCLE_AVAILABLE = True
except Exception as e:
    faj_cycle_runner = None
    FAJ_CYCLE_AVAILABLE = False
    FAJ_CYCLE_IMPORT_ERROR = str(e)


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "tour_manager"

if "bootstrap_result" not in st.session_state:
    st.session_state.bootstrap_result = None

if "cycle_result" not in st.session_state:
    st.session_state.cycle_result = None


# ============================================================
# NAVIGATION
# ============================================================

def navigate(page_name: str) -> None:
    st.session_state.page = page_name
    st.rerun()


# ============================================================
# DATABASE HELPERS (через FAJDatabase)
# ============================================================

def get_db() -> FAJDatabase:
    return FAJDatabase()


def database_exists() -> bool:
    return os.path.exists(DB_PATH)


def table_exists(table_name: str) -> bool:
    try:
        db = get_db()
        return db.table_exists(table_name)
    except Exception:
        return False


# ============================================================
# GET ACTIVE SEASON (через FAJDatabase)
# ============================================================

def get_active_season():
    try:
        db = get_db()
        seasons = db.get_seasons()

        for season in seasons:
            league = season.get("league", "")
            name = season.get("name", "")
            status = season.get("status", "")

            if league == "РПЛ":
                if (
                    status == "active"
                    or "2026/27" in name
                    or "2026-27" in name
                    or "2026-2027" in name
                ):
                    return {
                        "id": season["id"],
                        "league": league,
                        "name": name,
                    }

        for season in reversed(seasons):
            if season.get("league") == "РПЛ":
                return {
                    "id": season["id"],
                    "league": season["league"],
                    "name": season.get("name", ""),
                }

        return None
    except Exception:
        return None


# ============================================================
# DATABASE COUNTS (через FAJDatabase)
# ============================================================

def get_db_counts():
    result = {
        "teams": 0,
        "matches": 0,
        "predictions": 0,
        "results": 0,
    }
    try:
        db = get_db()

        teams = db.get_teams(league="РПЛ")
        result["teams"] = len(teams)

        season = get_active_season()
        if season:
            matches = db.get_matches()
            count = 0
            for match in matches:
                rounds = db.get_rounds()
                for r in rounds:
                    if r["id"] == match["round_id"] and r["season_id"] == season["id"]:
                        count += 1
                        break
            result["matches"] = count

        if table_exists("predictions"):
            result["predictions"] = db.get_table_count("predictions")

        if table_exists("match_results"):
            result["results"] = db.get_table_count("match_results")

    except Exception:
        pass

    return result


# ============================================================
# PASSPORT DATA (через FAJDatabase)
# ============================================================

def get_passport_data():
    try:
        db = get_db()
        season = get_active_season()

        if not season:
            return []

        teams = db.get_teams(league="РПЛ")
        data = []

        for team in teams:
            passport = db.get_team_passport(team["id"], season["id"])
            if passport:
                data.append({
                    "team_name": team["name"],
                    "attack": passport.get("attack", 0),
                    "defense": passport.get("defense", 0),
                    "control": passport.get("control", 0),
                    "goalkeeper": passport.get("goalkeeper", 0),
                    "faj_rating": passport.get("faj_rating", 0),
                })

        return data
    except Exception:
        return []


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
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("⚽ FAJ")
    st.caption(f"Platform v{config.PLATFORM_VERSION}")
    st.divider()

    # ============================================================
    # ROUND CENTER
    # ============================================================

    st.caption("🏟️ ROUND CENTER")

    if st.button("🗓️ Управление турами", use_container_width=True):
        navigate("tour_manager")

    if st.button("🧠 Прогноз тура", use_container_width=True):
        navigate("predict_round")

    if st.button("📥 Факты тура", use_container_width=True):
        navigate("import_facts")

    if st.button("🏁 Тур сыгран", use_container_width=True):
        navigate("round_complete")

    st.divider()

    # ============================================================
    # SYSTEM LAYER
    # ============================================================

    st.caption("⚙️ СИСТЕМА")

    if st.button("📋 Паспорта", use_container_width=True):
        navigate("passports")

    if st.button("📊 Аналитика", use_container_width=True):
        navigate("analytics")

    if st.button("📚 История", use_container_width=True):
        navigate("history")

    if st.button("⚙️ Система", use_container_width=True):
        navigate("system")

    if st.button("🧹 Очистка данных", use_container_width=True):
        navigate("reset_data")

    if st.button("🔧 Диагностика", use_container_width=True):
        navigate("diagnostic")

    st.divider()

    # ============================================================
    # FAJ CYCLE
    # ============================================================

    if st.button("🔄 Запустить FAJ Cycle", type="primary", use_container_width=True):
        if FAJ_CYCLE_AVAILABLE and faj_cycle_runner:
            with st.spinner("🧠 FAJ Cycle выполняет полный цикл..."):
                try:
                    st.session_state.cycle_result = faj_cycle_runner()
                except Exception as e:
                    st.session_state.cycle_result = {"success": False, "errors": [str(e)]}
            st.rerun()
        else:
            st.error(f"❌ FAJ Cycle недоступен: {FAJ_CYCLE_IMPORT_ERROR if not FAJ_CYCLE_AVAILABLE else 'Ошибка'}")

    st.divider()

    # ============================================================
    # STATUS
    # ============================================================

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
# PAGES ROUTER
# ============================================================

# ---------- ROUND CENTER ----------

if st.session_state.page == "tour_manager":
    try:
        from app.pages.tour_manager import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

elif st.session_state.page == "predict_round":
    try:
        from app.pages.predict_round import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

elif st.session_state.page == "import_facts":
    try:
        from app.pages.import_facts import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

elif st.session_state.page == "round_complete":
    try:
        from app.pages.round_complete import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ---------- SYSTEM LAYER ----------

elif st.session_state.page == "passports":
    st.title("📋 Паспорта команд")

    data = get_passport_data()

    if not data:
        st.info("Паспорта не найдены.")
    else:
        df = pd.DataFrame(data)
        display_df = df.rename(
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

elif st.session_state.page == "analytics":
    st.title("📊 Аналитика")
    st.info("Аналитический слой FAJ (в разработке).")

    counts = get_db_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Команды", counts["teams"])
    with c2:
        st.metric("Матчи", counts["matches"])
    with c3:
        st.metric("Результаты", counts["results"])
    with c4:
        st.metric("Прогнозы", counts["predictions"])

elif st.session_state.page == "history":
    st.title("📚 История FAJ")
    st.info("История прогнозов и фактических результатов (в разработке).")

    counts = get_db_counts()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Матчи", counts["matches"])
    with c2:
        st.metric("Прогнозы", counts["predictions"])

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

    st.divider()

    st.subheader("📁 Диагностика БД")
    st.write(f"**Путь к БД:** `{DB_PATH}`")
    st.write(f"**Файл существует:** {os.path.exists(DB_PATH)}")

    if os.path.exists(DB_PATH):
        size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
        st.write(f"**Размер:** {size_mb:.2f} MB")
        mtime = os.path.getmtime(DB_PATH)
        st.write(f"**Изменён:** {datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S')}")

    st.divider()

    st.subheader("🔍 Состояние")
    summary_df = pd.DataFrame(
        [
            {"Показатель": "Команды РПЛ", "Количество": counts["teams"]},
            {"Показатель": "Матчи активного сезона", "Количество": counts["matches"]},
            {"Показатель": "Результаты", "Количество": counts["results"]},
            {"Показатель": "Прогнозы", "Количество": counts["predictions"]},
        ]
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

elif st.session_state.page == "reset_data":
    try:
        from app.pages.reset_data import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка загрузки страницы: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

elif st.session_state.page == "diagnostic":
    st.title("🔧 Диагностика FAJ Database")

    st.subheader("📁 Путь к БД")
    st.code(DB_PATH)

    st.subheader("📊 Статус файла")
    if os.path.exists(DB_PATH):
        size = os.path.getsize(DB_PATH)
        st.success(f"✅ Файл существует! Размер: {size / 1024:.2f} KB")
    else:
        st.error("❌ Файл НЕ СУЩЕСТВУЕТ")

    st.subheader("📊 Попытка инициализации")
    try:
        db = get_db()
        status = db.get_status()
        st.success(f"✅ Database initialized: {status['status']}")
        st.json(status)
    except Exception as e:
        st.error(f"❌ Ошибка инициализации: {e}")
        st.exception(e)

    st.subheader("📁 Содержимое data/")
    try:
        data_dir = os.path.dirname(DB_PATH)
        files = os.listdir(data_dir) if os.path.exists(data_dir) else []
        st.write(f"Директория: {data_dir}")
        st.write(f"Файлы: {files}")
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")

# ---------- FALLBACK ----------

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
MAIN APPLICATION
============================================================

АРХИТЕКТУРА:

    streamlit_app.py
           │
    ┌──────┴─────────────────────────┐
    │                                │
 ROUND CENTER                    SYSTEM
    │                                │
    ├── tour_manager                ├── passports
    ├── predict_round               ├── analytics
    ├── import_facts                ├── history
    └── round_complete              ├── system
                                     ├── diagnostic
                                     ├── reset_data
                                     └── soccerway_inspector

СИСТЕМА:

    Bootstrap
        ↓
    Round Center
        ↓
    FAJ Cycle
        ↓
    Learning Engine

ПРИНЦИПЫ:

    - SQLite only
    - database.py — единственный источник схемы
    - никакого прямого SQL в Streamlit
    - операции выполняются через FAJDatabase / managers
    - исторические факты не удаляются
    - predictions не смешиваются с results
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
except Exception as exc:
    st.error(f"❌ Не удалось загрузить app.config: {exc}")
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
except Exception as exc:
    st.error(f"❌ Не удалось загрузить app.database: {exc}")
    st.stop()


DB_PATH = DB_FILE


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
    from app.faj_cycle import run_faj_cycle

    FAJ_CYCLE_AVAILABLE = True
    FAJ_CYCLE_IMPORT_ERROR = None

except Exception as exc:
    run_faj_cycle = None
    FAJ_CYCLE_AVAILABLE = False
    FAJ_CYCLE_IMPORT_ERROR = str(exc)


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
# DATABASE HELPER
# ============================================================

def get_db() -> FAJDatabase:
    return FAJDatabase()


def database_exists() -> bool:
    return os.path.exists(DB_PATH)


def table_exists(table_name: str) -> bool:
    try:
        db = get_db()
        return bool(db.table_exists(table_name))
    except Exception:
        return False


# ============================================================
# ACTIVE SEASON
# ============================================================

def get_active_season():
    """
    Возвращает активный сезон РПЛ.
    """

    try:
        db = get_db()
        seasons = db.get_seasons()

        # Сначала ищем явно активный сезон
        for season in seasons:

            data = dict(season)

            league = data.get("league", "")
            name = data.get("name", "")
            status = data.get("status", "")

            if league != "РПЛ":
                continue

            if (
                status == "active"
                or "2026/27" in name
                or "2026-27" in name
                or "2026-2027" in name
            ):
                return {
                    "id": data["id"],
                    "league": league,
                    "name": name,
                }

        # Fallback — последний сезон РПЛ
        for season in reversed(seasons):

            data = dict(season)

            if data.get("league") == "РПЛ":

                return {
                    "id": data["id"],
                    "league": data["league"],
                    "name": data.get("name", ""),
                }

        return None

    except Exception:
        return None


# ============================================================
# DATABASE COUNTS
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

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        try:
            teams = db.get_teams(league="РПЛ")
            result["teams"] = len(teams)
        except Exception:
            result["teams"] = 0

        # ----------------------------------------------------
        # MATCHES
        # ----------------------------------------------------

        season = get_active_season()

        if season:

            try:
                matches = db.get_matches()
                rounds = db.get_rounds()

                round_map = {}

                for round_row in rounds:

                    row = dict(round_row)

                    round_map[row.get("id")] = row

                count = 0

                for match in matches:

                    match_data = dict(match)

                    round_id = match_data.get("round_id")

                    round_data = round_map.get(round_id)

                    if not round_data:
                        continue

                    if round_data.get("season_id") == season["id"]:
                        count += 1

                result["matches"] = count

            except Exception:
                result["matches"] = 0

        # ----------------------------------------------------
        # PREDICTIONS
        # ----------------------------------------------------

        if table_exists("predictions"):

            try:
                result["predictions"] = db.get_table_count(
                    "predictions"
                )
            except Exception:
                result["predictions"] = 0

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        if table_exists("match_results"):

            try:
                result["results"] = db.get_table_count(
                    "match_results"
                )
            except Exception:
                result["results"] = 0

    except Exception:
        pass

    return result


# ============================================================
# PASSPORT DATA
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

            team_data = dict(team)

            passport = db.get_team_passport(
                team_data["id"],
                season["id"],
            )

            if not passport:
                continue

            passport_data = dict(passport)

            data.append(
                {
                    "team_name": team_data["name"],
                    "attack": passport_data.get(
                        "attack",
                        0,
                    ),
                    "defense": passport_data.get(
                        "defense",
                        0,
                    ),
                    "control": passport_data.get(
                        "control",
                        0,
                    ),
                    "goalkeeper": passport_data.get(
                        "goalkeeper",
                        0,
                    ),
                    "faj_rating": passport_data.get(
                        "faj_rating",
                        0,
                    ),
                }
            )

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

                st.session_state.bootstrap_result = (
                    bootstrap_faj()
                )

        except Exception as exc:

            st.session_state.bootstrap_result = {
                "ready": False,
                "messages": [
                    f"❌ Ошибка Bootstrap: {exc}"
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
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("⚽ FAJ")

    st.caption(
        f"Platform v{config.PLATFORM_VERSION}"
    )

    st.divider()

    # ========================================================
    # ROUND CENTER
    # ========================================================

    st.caption("🏟️ ROUND CENTER")

    if st.button(
        "🗓️ Управление турами",
        use_container_width=True,
    ):
        navigate("tour_manager")

    if st.button(
        "🧠 Прогноз тура",
        use_container_width=True,
    ):
        navigate("predict_round")

    if st.button(
        "📥 Факты тура",
        use_container_width=True,
    ):
        navigate("import_facts")

    if st.button(
        "🏁 Тур сыгран",
        use_container_width=True,
    ):
        navigate("round_complete")

    st.divider()

    # ========================================================
    # SYSTEM
    # ========================================================

    st.caption("⚙️ СИСТЕМА")

    if st.button(
        "📋 Паспорта",
        use_container_width=True,
    ):
        navigate("passports")

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

    if st.button(
        "⚙️ Система",
        use_container_width=True,
    ):
        navigate("system")

    if st.button(
        "🧹 Очистка данных",
        use_container_width=True,
    ):
        navigate("reset_data")

    if st.button(
        "🔧 Диагностика",
        use_container_width=True,
    ):
        navigate("diagnostic")

    if st.button(
        "🔎 Инспектор Soccerway",
        use_container_width=True,
    ):
        navigate("soccerway_inspector")

    st.divider()

    # ========================================================
    # FAJ CYCLE
    # ========================================================

    if st.button(
        "🔄 Запустить FAJ Cycle",
        type="primary",
        use_container_width=True,
    ):

        if FAJ_CYCLE_AVAILABLE and run_faj_cycle:

            with st.spinner(
                "🧠 FAJ Cycle выполняет полный цикл..."
            ):

                try:

                    st.session_state.cycle_result = (
                        run_faj_cycle()
                    )

                except Exception as exc:

                    st.session_state.cycle_result = {
                        "success": False,
                        "errors": [str(exc)],
                    }

            st.rerun()

        else:

            st.error(
                "❌ FAJ Cycle недоступен: "
                f"{FAJ_CYCLE_IMPORT_ERROR or 'Ошибка импорта'}"
            )

    st.divider()

    # ========================================================
    # GITHUB STORAGE
    # ========================================================

    st.caption("☁️ ХРАНИЛИЩЕ")

    if st.button(
        "💾 Сохранить базу в GitHub",
        use_container_width=True,
    ):

        try:

            from app.github_db_sync import (
                save_database_to_github
            )

            with st.spinner("Сохранение..."):

                result = save_database_to_github()

            st.success(
                f"✅ База сохранена: "
                f"{result['size']} bytes"
            )

        except Exception as exc:

            st.error(
                f"❌ Ошибка: {exc}"
            )

    if st.button(
        "🔄 Восстановить базу из GitHub",
        use_container_width=True,
    ):

        try:

            from app.github_db_sync import (
                load_database_from_github
            )

            with st.spinner("Восстановление..."):

                result = load_database_from_github()

            if result.get("loaded"):

                st.success(
                    f"✅ База восстановлена: "
                    f"{result['size']} bytes"
                )

            else:

                st.info(
                    f"ℹ️ {result.get('reason', '')}"
                )

            st.rerun()

        except Exception as exc:

            st.error(
                f"❌ Ошибка: {exc}"
            )

    st.divider()

    # ========================================================
    # STATUS
    # ========================================================

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

        st.caption("🟢 SQLite")

    else:

        st.caption("🔴 SQLite отсутствует")


# ============================================================
# PAGE ROUTER
# ============================================================

# ============================================================
# ROUND CENTER
# ============================================================

if st.session_state.page == "tour_manager":

    try:

        from app.pages.tour_manager import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander("Техническая ошибка"):
            st.exception(exc)


elif st.session_state.page == "predict_round":

    try:

        from app.pages.predict_round import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander("Техническая ошибка"):
            st.exception(exc)


elif st.session_state.page == "import_facts":

    try:

        from app.pages.import_facts import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander("Техническая ошибка"):
            st.exception(exc)


elif st.session_state.page == "round_complete":

    try:

        from app.pages.round_complete import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander("Техническая ошибка"):
            st.exception(exc)


# ============================================================
# SYSTEM
# ============================================================

elif st.session_state.page == "passports":

    st.title("📋 Паспорта команд")

    try:

        data = get_passport_data()

        if not data:

            st.info(
                "Паспорта не найдены."
            )

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

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки паспортов: {exc}"
        )

        st.exception(exc)


# ============================================================
# ANALYTICS
# ============================================================

elif st.session_state.page == "analytics":

    st.title("📊 Аналитика")

    st.info(
        "Аналитический слой FAJ."
    )

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
            "Результаты",
            counts["results"],
        )

    with c4:
        st.metric(
            "Прогнозы",
            counts["predictions"],
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

    # --------------------------------------------------------
    # SQLITE
    # --------------------------------------------------------

    st.subheader("💾 SQLite")

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

    # --------------------------------------------------------
    # DATABASE INFO
    # --------------------------------------------------------

    st.subheader("📁 Диагностика БД")

    st.write(
        f"**Путь к БД:** `{DB_PATH}`"
    )

    st.write(
        f"**Файл существует:** "
        f"{os.path.exists(DB_PATH)}"
    )

    if os.path.exists(DB_PATH):

        try:

            size_mb = (
                os.path.getsize(DB_PATH)
                / 1024
                / 1024
            )

            st.write(
                f"**Размер:** {size_mb:.2f} MB"
            )

            mtime = os.path.getmtime(DB_PATH)

            st.write(
                "**Изменён:** "
                f"{datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S')}"
            )

        except Exception:
            pass

    st.divider()

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    st.subheader("🔍 Состояние")

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
                "Показатель": "Результаты",
                "Количество": counts["results"],
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
# RESET DATA
# ============================================================

elif st.session_state.page == "reset_data":

    try:

        from app.pages.reset_data import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander("Техническая ошибка"):
            st.exception(exc)


# ============================================================
# DIAGNOSTIC
# ============================================================

elif st.session_state.page == "diagnostic":

    st.title(
        "🔧 Диагностика FAJ Database"
    )

    # --------------------------------------------------------
    # PATH
    # --------------------------------------------------------

    st.subheader("📁 Путь к БД")

    st.code(DB_PATH)

    # --------------------------------------------------------
    # FILE
    # --------------------------------------------------------

    st.subheader("📊 Статус файла")

    if os.path.exists(DB_PATH):

        size = os.path.getsize(DB_PATH)

        st.success(
            "✅ Файл существует! "
            f"Размер: {size / 1024:.2f} KB"
        )

    else:

        st.error(
            "❌ Файл НЕ СУЩЕСТВУЕТ"
        )

    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    st.subheader(
        "📊 Проверка инициализации"
    )

    try:

        db = get_db()

        status = db.get_status()

        st.success(
            f"✅ Database initialized: "
            f"{status['status']}"
        )

        st.json(status)

    except Exception as exc:

        st.error(
            f"❌ Ошибка инициализации: {exc}"
        )

        st.exception(exc)

    # --------------------------------------------------------
    # DATA DIRECTORY
    # --------------------------------------------------------

    st.subheader(
        "📁 Содержимое data/"
    )

    try:

        data_dir = os.path.dirname(DB_PATH)

        files = (
            os.listdir(data_dir)
            if os.path.exists(data_dir)
            else []
        )

        st.write(
            f"Директория: {data_dir}"
        )

        st.write(
            f"Файлы: {files}"
        )

    except Exception as exc:

        st.error(
            f"❌ Ошибка: {exc}"
        )


# ============================================================
# SOCCERWAY INSPECTOR
# ============================================================

elif st.session_state.page == "soccerway_inspector":

    try:

        from app.pages.soccerway_inspector import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander("Техническая ошибка"):
            st.exception(exc)


# ============================================================
# FALLBACK
# ============================================================

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

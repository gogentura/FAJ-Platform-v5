#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.2
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
    └── round_complete              ├── etc
                                     ├── system
                                     ├── diagnostic
                                     ├── parser_diagnostic
                                     ├── data_audit
                                     └── reset_data

    CLUB RATINGS
           │
           └── app/faj_club_ratings.py
                    │
                    ├── РПЛ
                    ├── Ла Лига
                    ├── АПЛ
                    └── Лига чемпионов

ПРИНЦИПЫ:

    - SQLite только для игровой/исторической БД
    - database.py — единственный источник схемы БД
    - никакого прямого SQL в Streamlit
    - FAJ Club Rating хранится отдельно от SQLite
    - START_RATING является экспертной базой
    - CURRENT_RATING в будущем изменяется через ETC
    - START_RATING никогда не перезаписывается
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

except Exception as exc:

    st.error(
        f"❌ Не удалось загрузить app.config: {exc}"
    )

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
        FAJDatabase,
        DB_FILE,
    )

except Exception as exc:

    st.error(
        f"❌ Не удалось загрузить app.database: {exc}"
    )

    st.stop()


DB_PATH = DB_FILE


# ============================================================
# CLUB RATINGS
# ============================================================

"""
FAJ Club Rating является отдельным слоем.

Архитектура:

    START_RATING
          ↓
    Club Rating Engine
          ↓
       results
          ↓
    CURRENT_RATING
          ↓
       history
          ↓
        marker

START_RATING остаётся неизменным.

Текущий динамический рейтинг в дальнейшем
изменяется через ClubRatingUpdater / ETC.
"""

try:

    from app.faj_club_ratings import (
        FAJ_CLUB_RATINGS,
        get_all_ratings,
        get_league_ratings,
        get_team_rating,
    )

    RATINGS_AVAILABLE = True

except Exception:

    FAJ_CLUB_RATINGS = {}
    RATINGS_AVAILABLE = False

    def get_all_ratings():
        return {}

    def get_league_ratings(league):
        return {}

    def get_team_rating(team_name):
        return None


# ============================================================
# BOOTSTRAP
# ============================================================

try:

    from app.bootstrap import bootstrap_faj

except Exception:

    bootstrap_faj = None


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_PAGE = "tour_manager"

if "page" not in st.session_state:

    st.session_state.page = DEFAULT_PAGE


if "bootstrap_result" not in st.session_state:

    st.session_state.bootstrap_result = None


# ============================================================
# NAVIGATION
# ============================================================

def navigate(page_name: str) -> None:
    """
    Переключение страницы приложения.
    """

    st.session_state.page = page_name

    st.rerun()


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db() -> FAJDatabase:
    """
    Возвращает экземпляр FAJDatabase.

    SQLite остаётся полностью инкапсулированным
    внутри database.py.
    """

    return FAJDatabase()


def database_exists() -> bool:
    """
    Проверяет наличие SQLite-файла.
    """

    return os.path.exists(DB_PATH)


def table_exists(table_name: str) -> bool:
    """
    Безопасная проверка существования таблицы.
    """

    try:

        db = get_db()

        return bool(
            db.table_exists(table_name)
        )

    except Exception:

        return False


# ============================================================
# PAGE LOADER
# ============================================================

def load_page(
    module_name: str,
    page_title: str,
) -> None:
    """
    Унифицированный загрузчик страниц FAJ.

    Пример:

        load_page(
            "app.pages.tour_manager",
            "Управление турами",
        )
    """

    try:

        module = __import__(
            module_name,
            fromlist=["main"],
        )

        main = getattr(
            module,
            "main",
        )

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы "
            f"{page_title}: {exc}"
        )

        with st.expander(
            "Техническая информация"
        ):

            st.exception(exc)


# ============================================================
# ACTIVE SEASON
# ============================================================

def get_active_season():
    """
    Возвращает активный сезон РПЛ.

    Приоритет:

    1. status == active
    2. сезон 2026/27
    3. последний сезон РПЛ
    """

    try:

        db = get_db()

        seasons = db.get_seasons()

        # ----------------------------------------------------
        # Явно активный сезон
        # ----------------------------------------------------

        for season in seasons:

            data = dict(season)

            league = data.get(
                "league",
                "",
            )

            name = data.get(
                "name",
                "",
            )

            status = data.get(
                "status",
                "",
            )

            if league != "РПЛ":

                continue

            if status == "active":

                return {
                    "id": data["id"],
                    "league": league,
                    "name": name,
                }

        # ----------------------------------------------------
        # Текущий сезон
        # ----------------------------------------------------

        for season in seasons:

            data = dict(season)

            league = data.get(
                "league",
                "",
            )

            name = data.get(
                "name",
                "",
            )

            if league != "РПЛ":

                continue

            if any(
                marker in name
                for marker in (
                    "2026/27",
                    "2026-27",
                    "2026-2027",
                )
            ):

                return {
                    "id": data["id"],
                    "league": league,
                    "name": name,
                }

        # ----------------------------------------------------
        # Последний сезон РПЛ
        # ----------------------------------------------------

        for season in reversed(seasons):

            data = dict(season)

            if data.get("league") == "РПЛ":

                return {
                    "id": data["id"],
                    "league": data["league"],
                    "name": data.get(
                        "name",
                        "",
                    ),
                }

        return None

    except Exception:

        return None


# ============================================================
# DATABASE COUNTS
# ============================================================

def get_db_counts():
    """
    Возвращает основные счётчики FAJ.

    Важно:

    matches считаются только для активного сезона РПЛ.
    """

    result = {
        "teams": 0,
        "matches": 0,
        "predictions": 0,
        "results": 0,
    }

    try:

        db = get_db()

        # ====================================================
        # TEAMS
        # ====================================================

        try:

            teams = db.get_teams(
                league="РПЛ"
            )

            result["teams"] = len(teams)

        except Exception:

            result["teams"] = 0

        # ====================================================
        # MATCHES
        # ====================================================

        season = get_active_season()

        if season:

            try:

                rounds = db.get_rounds(
                    season_id=season["id"]
                )

                round_ids = {
                    dict(row).get("id")
                    for row in rounds
                }

                matches = db.get_matches()

                result["matches"] = sum(
                    1
                    for match in matches
                    if dict(match).get(
                        "round_id"
                    ) in round_ids
                )

            except Exception:

                result["matches"] = 0

        # ====================================================
        # PREDICTIONS
        # ====================================================

        if table_exists(
            "predictions"
        ):

            try:

                result["predictions"] = (
                    db.get_table_count(
                        "predictions"
                    )
                )

            except Exception:

                result["predictions"] = 0

        # ====================================================
        # RESULTS
        # ====================================================

        if table_exists(
            "match_results"
        ):

            try:

                result["results"] = (
                    db.get_table_count(
                        "match_results"
                    )
                )

            except Exception:

                result["results"] = 0

        return result

    except Exception:

        return result


# ============================================================
# PASSPORT DATA
# ============================================================

def get_passport_data():
    """
    Загружает паспорта команд РПЛ
    для активного сезона.
    """

    try:

        db = get_db()

        season = get_active_season()

        if not season:

            return []

        teams = db.get_teams(
            league="РПЛ"
        )

        data = []

        for team in teams:

            team_data = dict(team)

            passport = db.get_team_passport(
                team_data["id"],
                season["id"],
            )

            if not passport:

                continue

            passport_data = dict(
                passport
            )

            data.append(
                {
                    "team_name": team_data.get(
                        "name",
                        "",
                    ),
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
# CLUB RATING VIEW
# ============================================================

def render_league_rating(
    league_name: str,
    title: str | None = None,
):
    """
    Отображает рейтинг выбранного турнира.
    """

    if not RATINGS_AVAILABLE:

        st.warning(
            "⚠️ FAJ Club Rating пока не подключён."
        )

        st.info(
            "Проверьте наличие "
            "`app/faj_club_ratings.py`."
        )

        return

    ratings = get_league_ratings(
        league_name
    )

    if not ratings:

        st.warning(
            f"⚠️ Рейтинг для "
            f"{league_name} не найден."
        )

        return

    if title:

        st.subheader(title)

    rows = []

    sorted_ratings = sorted(
        ratings.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    for position, (
        team,
        rating,
    ) in enumerate(
        sorted_ratings,
        start=1,
    ):

        rows.append(
            {
                "№": position,
                "Команда": team,
                "FAJ Rating": rating,
            }
        )

    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# BOOTSTRAP
# ============================================================

def run_bootstrap():
    """
    Однократный запуск bootstrap для текущей сессии.
    """

    if st.session_state.bootstrap_result is not None:

        return

    if bootstrap_faj is None:

        st.session_state.bootstrap_result = {
            "ready": False,
            "messages": [
                "⚠️ bootstrap_faj недоступен."
            ],
        }

        return

    try:

        with st.spinner(
            "🚀 Проверка FAJ..."
        ):

            result = bootstrap_faj()

        if result is None:

            result = {
                "ready": True,
                "messages": [],
            }

        st.session_state.bootstrap_result = result

    except Exception as exc:

        st.session_state.bootstrap_result = {
            "ready": False,
            "messages": [
                f"❌ Ошибка Bootstrap: {exc}"
            ],
        }


run_bootstrap()


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

    st.caption(
        "🏟️ ROUND CENTER"
    )

    if st.button(
        "🗓️ Управление турами",
        use_container_width=True,
        key="nav_tour_manager",
    ):

        navigate(
            "tour_manager"
        )

    if st.button(
        "🧠 Прогноз тура",
        use_container_width=True,
        key="nav_predict_round",
    ):

        navigate(
            "predict_round"
        )

    if st.button(
        "📥 Факты тура",
        use_container_width=True,
        key="nav_import_facts",
    ):

        navigate(
            "import_facts"
        )

    if st.button(
        "🏁 Тур сыгран",
        use_container_width=True,
        key="nav_round_complete",
    ):

        navigate(
            "round_complete"
        )

    st.divider()

    # ========================================================
    # FAJ RATINGS
    # ========================================================

    st.caption(
        "⭐ FAJ RATINGS"
    )

    if st.button(
        "⭐ Рейтинг клубов",
        use_container_width=True,
        key="nav_club_ratings",
    ):

        navigate(
            "club_ratings"
        )

    st.divider()

    # ========================================================
    # SYSTEM
    # ========================================================

    st.caption(
        "⚙️ СИСТЕМА"
    )

    if st.button(
        "📋 Паспорта",
        use_container_width=True,
        key="nav_passports",
    ):

        navigate(
            "passports"
        )

    if st.button(
        "📊 Аналитика",
        use_container_width=True,
        key="nav_analytics",
    ):

        navigate(
            "analytics"
        )

    if st.button(
        "📚 История",
        use_container_width=True,
        key="nav_history",
    ):

        navigate(
            "history"
        )

    if st.button(
        "🧠 ETC",
        use_container_width=True,
        key="nav_etc",
    ):

        navigate(
            "etc"
        )

    if st.button(
        "⚙️ Система",
        use_container_width=True,
        key="nav_system",
    ):

        navigate(
            "system"
        )

    if st.button(
        "🧹 Очистка данных",
        use_container_width=True,
        key="nav_reset_data",
    ):

        navigate(
            "reset_data"
        )

    if st.button(
        "🔧 Диагностика",
        use_container_width=True,
        key="nav_diagnostic",
    ):

        navigate(
            "diagnostic"
        )

    if st.button(
        "🔬 Диагностика парсеров",
        use_container_width=True,
        key="nav_parser_diagnostic",
    ):

        navigate(
            "parser_diagnostic"
        )

    if st.button(
        "🔍 Аудит данных FAJ",
        use_container_width=True,
        key="nav_data_audit",
    ):

        navigate(
            "data_audit"
        )

    st.divider()

    # ========================================================
    # GITHUB STORAGE
    # ========================================================

    st.caption(
        "☁️ ХРАНИЛИЩЕ"
    )

    if st.button(
        "💾 Сохранить базу в GitHub",
        use_container_width=True,
        key="github_save",
    ):

        try:

            from app.github_db_sync import (
                save_database_to_github,
            )

            with st.spinner(
                "Сохранение базы..."
            ):

                result = (
                    save_database_to_github()
                )

            st.success(
                f"✅ База сохранена: "
                f"{result['size']} bytes"
            )

        except Exception as exc:

            st.error(
                f"❌ Ошибка сохранения: {exc}"
            )

    if st.button(
        "🔄 Восстановить базу из GitHub",
        use_container_width=True,
        key="github_load",
    ):

        try:

            from app.github_db_sync import (
                load_database_from_github,
            )

            with st.spinner(
                "Восстановление базы..."
            ):

                result = (
                    load_database_from_github()
                )

            if result.get("loaded"):

                st.success(
                    f"✅ База восстановлена: "
                    f"{result['size']} bytes"
                )

                st.rerun()

            else:

                st.info(
                    "ℹ️ "
                    f"{result.get('reason', '')}"
                )

        except Exception as exc:

            st.error(
                f"❌ Ошибка восстановления: {exc}"
            )

    st.divider()

    # ========================================================
    # STATUS
    # ========================================================

    counts = get_db_counts()

    st.caption(
        "📊 СОСТОЯНИЕ"
    )

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

    if RATINGS_AVAILABLE:

        st.caption(
            "⭐ FAJ Rating: 🟢 загружен"
        )

    else:

        st.caption(
            "⭐ FAJ Rating: 🔴 не загружен"
        )


# ============================================================
# PAGE ROUTER
# ============================================================

CURRENT_PAGE = st.session_state.page


# ============================================================
# ROUND CENTER
# ============================================================

if CURRENT_PAGE == "tour_manager":

    load_page(
        "app.pages.tour_manager",
        "Управление турами",
    )


elif CURRENT_PAGE == "predict_round":

    load_page(
        "app.pages.predict_round",
        "Прогноз тура",
    )


elif CURRENT_PAGE == "import_facts":

    load_page(
        "app.pages.import_facts",
        "Факты тура",
    )


elif CURRENT_PAGE == "round_complete":

    load_page(
        "app.pages.round_complete",
        "Тур сыгран",
    )


# ============================================================
# FAJ CLUB RATINGS
# ============================================================

elif CURRENT_PAGE == "club_ratings":

    st.title(
        "⭐ FAJ Club Rating"
    )

    st.caption(
        "Экспертный стартовый рейтинг клубов "
        "с последующим динамическим обновлением через ETC."
    )

    st.divider()

    if not RATINGS_AVAILABLE:

        st.error(
            "❌ Модуль FAJ Club Rating не найден."
        )

        st.code(
            "app/faj_club_ratings.py"
        )

    else:

        st.info(
            "Стартовый рейтинг — экспертная база "
            "силы команды перед началом динамического "
            "обновления."
        )

        leagues = [
            "РПЛ",
            "Ла Лига",
            "АПЛ",
            "Лига чемпионов",
        ]

        selected_league = st.selectbox(
            "Выберите турнир",
            leagues,
            key="club_rating_league",
        )

        st.divider()

        render_league_rating(
            selected_league
        )

        st.divider()

        st.subheader(
            "⚙️ Логика рейтинга"
        )

        st.write(
            "Сейчас отображается START_RATING."
        )

        st.write(
            "После подключения ClubRatingUpdater "
            "текущий рейтинг будет изменяться "
            "по результатам матчей."
        )

        st.write(
            "START_RATING при этом останется "
            "исторической точкой отсчёта."
        )


# ============================================================
# PASSPORTS
# ============================================================

elif CURRENT_PAGE == "passports":

    st.title(
        "📋 Паспорта команд"
    )

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


# ============================================================
# ANALYTICS
# ============================================================

elif CURRENT_PAGE == "analytics":

    st.title(
        "📊 Аналитика"
    )

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

elif CURRENT_PAGE == "history":

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
# ETC
# ============================================================

elif CURRENT_PAGE == "etc":

    load_page(
        "app.pages.etc",
        "ETC",
    )


# ============================================================
# SYSTEM
# ============================================================

elif CURRENT_PAGE == "system":

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

    # ========================================================
    # CLUB RATINGS
    # ========================================================

    st.subheader(
        "⭐ FAJ Club Rating"
    )

    if RATINGS_AVAILABLE:

        all_ratings = get_all_ratings()

        st.success(
            "🟢 Модуль рейтингов загружен"
        )

        total_teams = sum(
            len(league)
            for league in all_ratings.values()
        )

        st.metric(
            "Клубов в рейтинговой базе",
            total_teams,
        )

    else:

        st.error(
            "🔴 Модуль рейтингов не найден"
        )

    st.divider()

    # ========================================================
    # SQLITE
    # ========================================================

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

    # ========================================================
    # DATABASE INFO
    # ========================================================

    st.subheader(
        "📁 Диагностика БД"
    )

    st.write(
        f"**Путь к БД:** `{DB_PATH}`"
    )

    st.write(
        f"**Файл существует:** "
        f"{os.path.exists(DB_PATH)}"
    )

    if database_exists():

        try:

            size_mb = (
                os.path.getsize(DB_PATH)
                / 1024
                / 1024
            )

            st.write(
                f"**Размер:** "
                f"{size_mb:.2f} MB"
            )

            mtime = os.path.getmtime(
                DB_PATH
            )

            st.write(
                "**Изменён:** "
                f"{datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S')}"
            )

        except Exception:

            pass

    st.divider()

    # ========================================================
    # SUMMARY
    # ========================================================

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

elif CURRENT_PAGE == "reset_data":

    load_page(
        "app.pages.reset_data",
        "Очистка данных",
    )


# ============================================================
# DIAGNOSTIC
# ============================================================

elif CURRENT_PAGE == "diagnostic":

    st.title(
        "🔧 Диагностика FAJ Database"
    )

    # ========================================================
    # PATH
    # ========================================================

    st.subheader(
        "📁 Путь к БД"
    )

    st.code(
        DB_PATH
    )

    # ========================================================
    # FILE
    # ========================================================

    st.subheader(
        "📊 Статус файла"
    )

    if database_exists():

        size = os.path.getsize(
            DB_PATH
        )

        st.success(
            "✅ Файл существует! "
            f"Размер: {size / 1024:.2f} KB"
        )

    else:

        st.error(
            "❌ Файл НЕ СУЩЕСТВУЕТ"
        )

    # ========================================================
    # INITIALIZATION
    # ========================================================

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

        with st.expander(
            "Техническая информация"
        ):

            st.exception(exc)

    # ========================================================
    # DATA DIRECTORY
    # ========================================================

    st.subheader(
        "📁 Содержимое data/"
    )

    try:

        data_dir = os.path.dirname(
            DB_PATH
        )

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
# PARSER DIAGNOSTIC
# ============================================================

elif CURRENT_PAGE == "parser_diagnostic":

    load_page(
        "app.pages.parser_diagnostic",
        "Диагностика парсеров",
    )


# ============================================================
# DATA AUDIT
# ============================================================

elif CURRENT_PAGE == "data_audit":

    st.title(
        "🔍 Аудит данных FAJ"
    )

    st.caption(
        "Проверка данных, необходимых "
        "для Evolution Report"
    )

    st.divider()

    # ========================================================
    # INFORMATION
    # ========================================================

    st.info(
        "Аудит проверяет наличие критических данных "
        "для построения эволюционного отчёта FAJ:\n\n"
        "• Прогнозы (predictions)\n"
        "• Фактические результаты (match_results)\n"
        "• Learning Memory (learning_memory)\n"
        "• Параметры модели (model_parameters)\n"
        "• Связи между данными"
    )

    # ========================================================
    # RUN AUDIT
    # ========================================================

    if st.button(
        "🔍 ЗАПУСТИТЬ АУДИТ",
        type="primary",
        use_container_width=True,
        key="run_data_audit",
    ):

        try:

            import subprocess

            script_path = os.path.join(
                ROOT_DIR,
                "scripts",
                "audit_faj_data.py",
            )

            if not os.path.exists(
                script_path
            ):

                st.error(
                    f"❌ Скрипт аудита не найден:\n"
                    f"{script_path}\n\n"
                    "Создайте файл "
                    "`scripts/audit_faj_data.py`."
                )

            else:

                with st.spinner(
                    "🔍 Выполняется аудит базы FAJ..."
                ):

                    result = subprocess.run(
                        [
                            sys.executable,
                            script_path,
                        ],
                        cwd=ROOT_DIR,
                        capture_output=True,
                        text=True,
                    )

                if result.stdout:

                    st.code(
                        result.stdout,
                        language="text",
                    )

                if result.stderr:

                    with st.expander(
                        "⚠️ Технический вывод"
                    ):

                        st.code(
                            result.stderr,
                            language="text",
                        )

                if result.returncode == 0:

                    st.success(
                        "✅ Аудит завершён."
                    )

                else:

                    st.warning(
                        "⚠️ Аудит завершён. "
                        "Обнаружены проблемы или "
                        "недостающие данные."
                    )

        except Exception as exc:

            st.error(
                f"❌ Ошибка запуска аудита: {exc}"
            )

            with st.expander(
                "Техническая информация"
            ):

                st.exception(exc)

    # ========================================================
    # INTERPRETATION
    # ========================================================

    with st.expander(
        "📖 Как интерпретировать результаты аудита"
    ):

        st.markdown(
            """
### ✅ Критические данные

| Данные | Что проверяет |
|---|---|
| `predictions` | Прогнозы FAJ |
| `prediction_scores` | Точные счета прогнозов |
| `match_results` | Фактические результаты |
| `learning_memory` | Память обучения ETC |
| `model_parameters` | Параметры модели |
| `team_passports` | Паспорта команд |

### ❌ Потенциальные проблемы

- Нет исторических параметров модели
  → нельзя показать «было → стало».

- Нет `match_snapshots`
  → нельзя восстановить состояние модели.

- Нет `prediction_error` в `learning_memory`
  → отсутствует связь обучение → ошибка.

- Нет xG в `match_results`
  → невозможно полноценно сравнить
  прогнозный и фактический xG.

### 📌 Следующий шаг

1. Если данные отсутствуют → добавить их сохранение.
2. Если данные присутствуют → переходить к Evolution Report.
"""
        )


# ============================================================
# FALLBACK
# ============================================================

else:

    st.session_state.page = DEFAULT_PAGE

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

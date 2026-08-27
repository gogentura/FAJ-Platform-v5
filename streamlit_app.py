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

    - SQLite only для игровой/исторической БД
    - database.py — единственный источник схемы БД
    - никакого прямого SQL в Streamlit
    - FAJ Club Rating хранится отдельно от SQLite
    - стартовый рейтинг является экспертной базой
    - текущий рейтинг в будущем изменяется через ETC
    - исторический стартовый рейтинг не перезаписывается
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
FAJ Club Rating не является частью database.py.

Сейчас это экспертный стартовый слой.

Позже:

    START_RATING
          ↓
    CLUB RATING ENGINE
          ↓
    результаты матчей
          ↓
    новый CURRENT_RATING

ETC сможет обновлять текущий рейтинг,
при этом START_RATING останется неизменным.
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

if "page" not in st.session_state:

    st.session_state.page = "tour_manager"


if "bootstrap_result" not in st.session_state:

    st.session_state.bootstrap_result = None


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

        return bool(
            db.table_exists(table_name)
        )

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

        # ----------------------------------------------------
        # Сначала ищем явно активный сезон
        # ----------------------------------------------------

        for season in seasons:

            data = dict(season)

            league = data.get(
                "league",
                ""
            )

            name = data.get(
                "name",
                ""
            )

            status = data.get(
                "status",
                ""
            )

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

        # ----------------------------------------------------
        # Fallback — последний сезон РПЛ
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

            teams = db.get_teams(
                league="РПЛ"
            )

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

                    round_map[
                        row.get("id")
                    ] = row

                count = 0

                for match in matches:

                    match_data = dict(match)

                    round_id = match_data.get(
                        "round_id"
                    )

                    round_data = round_map.get(
                        round_id
                    )

                    if not round_data:

                        continue

                    if (
                        round_data.get(
                            "season_id"
                        )
                        == season["id"]
                    ):

                        count += 1

                result["matches"] = count

            except Exception:

                result["matches"] = 0

        # ----------------------------------------------------
        # PREDICTIONS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

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
                    "team_name": team_data[
                        "name"
                    ],
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
# CLUB RATING HELPERS
# ============================================================

def render_league_rating(
    league_name: str,
    title: str = None,
):

    """
    Показывает рейтинг выбранного турнира.
    """

    if not RATINGS_AVAILABLE:

        st.warning(
            "⚠️ FAJ Club Rating пока не подключён."
        )

        st.info(
            "Создайте файл "
            "`app/faj_club_ratings.py`."
        )

        return

    ratings = get_league_ratings(
        league_name
    )

    if not ratings:

        st.warning(
            f"⚠️ Рейтинг для {league_name} "
            "не найден."
        )

        return

    if title:

        st.subheader(title)

    rows = []

    for position, (
        team,
        rating
    ) in enumerate(
        sorted(
            ratings.items(),
            key=lambda x: x[1],
            reverse=True,
        ),
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

if st.session_state.bootstrap_result is None:

    if bootstrap_faj is not None:

        try:

            with st.spinner(
                "🚀 Проверка FAJ..."
            ):

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

    st.caption(
        "🏟️ ROUND CENTER"
    )

    if st.button(
        "🗓️ Управление турами",
        use_container_width=True,
    ):

        navigate(
            "tour_manager"
        )

    if st.button(
        "🧠 Прогноз тура",
        use_container_width=True,
    ):

        navigate(
            "predict_round"
        )

    if st.button(
        "📥 Факты тура",
        use_container_width=True,
    ):

        navigate(
            "import_facts"
        )

    if st.button(
        "🏁 Тур сыгран",
        use_container_width=True,
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
    ):

        navigate(
            "passports"
        )

    if st.button(
        "📊 Аналитика",
        use_container_width=True,
    ):

        navigate(
            "analytics"
        )

    if st.button(
        "📚 История",
        use_container_width=True,
    ):

        navigate(
            "history"
        )

    if st.button(
        "🧠 ETC",
        use_container_width=True,
    ):

        navigate(
            "etc"
        )

    if st.button(
        "⚙️ Система",
        use_container_width=True,
    ):

        navigate(
            "system"
        )

    if st.button(
        "🧹 Очистка данных",
        use_container_width=True,
    ):

        navigate(
            "reset_data"
        )

    if st.button(
        "🔧 Диагностика",
        use_container_width=True,
    ):

        navigate(
            "diagnostic"
        )

    # ========================================================
    # PARSER DIAGNOSTIC
    # ========================================================

    if st.button(
        "🔬 Диагностика парсеров",
        use_container_width=True,
    ):

        navigate(
            "parser_diagnostic"
        )

    # ========================================================
    # DATA AUDIT
    # ========================================================

    if st.button(
        "🔍 Аудит данных FAJ",
        use_container_width=True,
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
    ):

        try:

            from app.github_db_sync import (
                save_database_to_github
            )

            with st.spinner(
                "Сохранение..."
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

            with st.spinner(
                "Восстановление..."
            ):

                result = (
                    load_database_from_github()
                )

            if result.get(
                "loaded"
            ):

                st.success(
                    f"✅ База восстановлена: "
                    f"{result['size']} bytes"
                )

            else:

                st.info(
                    f"ℹ️ "
                    f"{result.get('reason', '')}"
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

    # --------------------------------------------------------
    # RATING STATUS
    # --------------------------------------------------------

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

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(exc)


elif st.session_state.page == "predict_round":

    try:

        from app.pages.predict_round import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(exc)


elif st.session_state.page == "import_facts":

    try:

        from app.pages.import_facts import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(exc)


elif st.session_state.page == "round_complete":

    try:

        from app.pages.round_complete import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы: {exc}"
        )

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(exc)


# ============================================================
# FAJ CLUB RATINGS
# ============================================================

elif st.session_state.page == "club_ratings":

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

        # ----------------------------------------------------
        # ОБЩАЯ ИНФОРМАЦИЯ
        # ----------------------------------------------------

        st.info(
            "Стартовый рейтинг — это базовая оценка силы "
            "команды перед началом работы динамического "
            "рейтинга FAJ."
        )

        # ----------------------------------------------------
        # ВЫБОР ТУРНИРА
        # ----------------------------------------------------

        leagues = [
            "РПЛ",
            "Ла Лига",
            "АПЛ",
            "Лига чемпионов",
        ]

        selected_league = st.selectbox(
            "Выберите турнир",
            leagues,
        )

        st.divider()

        # ----------------------------------------------------
        # РЕЙТИНГ
        # ----------------------------------------------------

        render_league_rating(
            selected_league
        )

        st.divider()

        # ----------------------------------------------------
        # ЛОГИКА
        # ----------------------------------------------------

        st.subheader(
            "⚙️ Логика рейтинга"
        )

        st.write(
            "Сейчас отображается стартовый FAJ Rating."
        )

        st.write(
            "После подключения ClubRatingUpdater "
            "рейтинг будет изменяться по результатам матчей."
        )

        st.write(
            "При этом стартовое значение останется "
            "исторической точкой отсчёта."
        )


# ============================================================
# PASSPORTS
# ============================================================

elif st.session_state.page == "passports":

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

            df = pd.DataFrame(
                data
            )

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
# ETC — EVOLUTION TRAINING CENTER
# ============================================================

elif st.session_state.page == "etc":

    try:

        from app.pages.etc import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки страницы ETC: {exc}"
        )

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(exc)


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

    # --------------------------------------------------------
    # CLUB RATINGS STATUS
    # --------------------------------------------------------

    st.subheader(
        "⭐ FAJ Club Rating"
    )

    if RATINGS_AVAILABLE:

        all_ratings = (
            get_all_ratings()
        )

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

    # --------------------------------------------------------
    # SQLITE
    # --------------------------------------------------------

    st.subheader(
        "💾 SQLite"
    )

    if database_exists():

        st.success(
            "🟢 SQLite доступна"
        )

        try:

            size_mb = (
                os.path.getsize(
                    DB_PATH
                )
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

    if os.path.exists(
        DB_PATH
    ):

        try:

            size_mb = (
                os.path.getsize(
                    DB_PATH
                )
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

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "🔍 Состояние"
    )

    summary_df = pd.DataFrame(
        [
            {
                "Показатель": "Команды РПЛ",
                "Количество": counts[
                    "teams"
                ],
            },
            {
                "Показатель": "Матчи активного сезона",
                "Количество": counts[
                    "matches"
                ],
            },
            {
                "Показатель": "Результаты",
                "Количество": counts[
                    "results"
                ],
            },
            {
                "Показатель": "Прогнозы",
                "Количество": counts[
                    "predictions"
                ],
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

        with st.expander(
            "Техническая ошибка"
        ):

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

    st.subheader(
        "📁 Путь к БД"
    )

    st.code(
        DB_PATH
    )

    # --------------------------------------------------------
    # FILE
    # --------------------------------------------------------

    st.subheader(
        "📊 Статус файла"
    )

    if os.path.exists(
        DB_PATH
    ):

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

        st.json(
            status
        )

    except Exception as exc:

        st.error(
            f"❌ Ошибка инициализации: {exc}"
        )

        st.exception(
            exc
        )

    # --------------------------------------------------------
    # DATA DIRECTORY
    # --------------------------------------------------------

    st.subheader(
        "📁 Содержимое data/"
    )

    try:

        data_dir = os.path.dirname(
            DB_PATH
        )

        files = (
            os.listdir(data_dir)
            if os.path.exists(
                data_dir
            )
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

elif st.session_state.page == "parser_diagnostic":

    try:

        from app.pages.parser_diagnostic import main

        main()

    except Exception as exc:

        st.error(
            f"❌ Ошибка загрузки диагностики парсеров: {exc}"
        )

        with st.expander(
            "Техническая ошибка"
        ):

            st.exception(
                exc
            )


# ============================================================
# DATA AUDIT
# ============================================================

elif st.session_state.page == "data_audit":

    st.title(
        "🔍 Аудит данных FAJ"
    )

    st.caption(
        "Проверка данных, необходимых "
        "для Evolution Report"
    )

    st.divider()

    # --------------------------------------------------------
    # ИНФОРМАЦИЯ
    # --------------------------------------------------------

    st.info(
        "Аудит проверяет наличие критических данных "
        "для построения эволюционного отчета FAJ:\n\n"
        "• Прогнозы (predictions)\n"
        "• Фактические результаты (match_results)\n"
        "• Learning Memory (learning_memory)\n"
        "• Параметры модели (model_parameters)\n"
        "• Связи между данными"
    )

    # --------------------------------------------------------
    # КНОПКА ЗАПУСКА
    # --------------------------------------------------------

    if st.button(
        "🔍 ЗАПУСТИТЬ АУДИТ",
        type="primary",
        use_container_width=True,
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
                    f"❌ Скрипт аудита не найден: "
                    f"{script_path}\n\n"
                    "Создайте файл "
                    "`scripts/audit_faj_data.py`"
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
                        "✅ Аудит завершён. "
                        "Критические данные присутствуют."
                    )

                else:

                    st.warning(
                        "⚠️ Аудит завершён. "
                        "Обнаружены недостающие данные."
                    )

        except Exception as exc:

            st.error(
                f"❌ Ошибка запуска аудита: {exc}"
            )

            with st.expander(
                "Техническая ошибка"
            ):

                st.exception(
                    exc
                )

    # --------------------------------------------------------
    # ИНСТРУКЦИЯ
    # --------------------------------------------------------

    with st.expander(
        "📖 Как интерпретировать результаты аудита"
    ):

        st.markdown(
            """
**✅ Что должно быть:**

| Данные | Что проверяет |
|--------|---------------|
| `predictions` | Прогнозы FAJ |
| `prediction_scores` | Точные счета прогнозов |
| `match_results` | Фактические результаты |
| `learning_memory` | Память обучения ETC |
| `model_parameters` | Параметры модели |
| `team_passports` | Паспорта команд |

**❌ Чего не хватает для Evolution Report:**

- Нет исторических параметров модели → нельзя показать "было → стало"
- Нет `match_snapshots` → нельзя восстановить состояние модели
- Нет `prediction_error` в learning_memory → нет связи обучение → ошибка
- Нет xG в match_results → нельзя сравнить прогнозный и фактический xG

**📌 Что делать:**

1. Если данных нет → добавить сохранение
2. Если данные есть → перейти к Evolution Report
"""
        )


# ============================================================
# FALLBACK
# ============================================================

else:

    st.session_state.page = (
        "tour_manager"
    )

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.3
MAIN APPLICATION
============================================================

ARCHITECTURE
------------

                    streamlit_app.py
                           │
          ┌────────────────┴────────────────┐
          │                                 │
     ROUND CENTER                         SYSTEM
          │                                 │
          ├── tour_manager                  ├── passports
          ├── predict_round                 ├── analytics
          ├── import_facts                  ├── history
          └── round_complete                ├── etc
                                            ├── system
                                            ├── diagnostic
                                            ├── parser_diagnostic
                                            ├── data_audit
                                            └── reset_data

                  FAJ CLUB RATINGS
                           │
                           └── faj_club_ratings.py

PRINCIPLES
----------

1. SQLite — игровая и историческая БД.
2. database.py — единственный источник схемы БД.
3. Streamlit не содержит прямого SQL.
4. FAJ Club Rating хранится отдельно от SQLite.
5. START RATING является экспертной исторической базой.
6. CURRENT RATING в будущем изменяется через ETC.
7. START RATING никогда не перезаписывается.
8. Predictions не смешиваются с Results.
9. Страницы загружаются лениво — только при выборе.
10. Ошибки страниц отображаются с технической диагностикой.
============================================================
"""

import os
import sys
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

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
    Возвращает новый экземпляр FAJDatabase.

    SQLite остаётся полностью инкапсулированным
    внутри database.py.
    """

    return FAJDatabase()


def database_exists() -> bool:
    return os.path.isfile(DB_PATH)


def table_exists(table_name: str) -> bool:
    """
    Проверяет наличие таблицы через database.py.
    Прямого SQL здесь нет.
    """

    try:
        db = get_db()
        return bool(
            db.table_exists(table_name)
        )

    except Exception:
        return False


def safe_table_count(
    db: FAJDatabase,
    table_name: str,
) -> int:
    """
    Безопасный подсчёт записей таблицы.
    """

    try:
        if not db.table_exists(table_name):
            return 0

        return int(
            db.get_table_count(table_name)
        )

    except Exception:
        return 0


# ============================================================
# ACTIVE SEASON
# ============================================================

def get_active_season() -> Optional[Dict[str, Any]]:
    """
    Возвращает активный сезон РПЛ.

    Приоритет:
        1. status == active
        2. сезон текущего футбольного года
        3. последний сезон РПЛ
    """

    try:
        db = get_db()
        seasons = db.get_seasons()

        if not seasons:
            return None

        normalized = []

        for season in seasons:
            data = dict(season)

            if data.get("league") != "РПЛ":
                continue

            normalized.append(data)

        if not normalized:
            return None

        # ----------------------------------------------------
        # 1. Явно активный
        # ----------------------------------------------------

        for data in normalized:

            if str(
                data.get("status", "")
            ).lower() == "active":

                return {
                    "id": data["id"],
                    "league": data.get(
                        "league",
                        "РПЛ",
                    ),
                    "name": data.get(
                        "name",
                        "",
                    ),
                    "year": data.get(
                        "year"
                    ),
                    "status": data.get(
                        "status"
                    ),
                }

        # ----------------------------------------------------
        # 2. Текущий футбольный сезон
        # ----------------------------------------------------

        current_year = datetime.now().year

        season_patterns = {
            f"{current_year}/{str(current_year + 1)[-2:]}",
            f"{current_year}-{str(current_year + 1)[-2:]}",
            f"{current_year}-{current_year + 1}",
        }

        for data in normalized:

            name = str(
                data.get("name", "")
            )

            if any(
                pattern in name
                for pattern in season_patterns
            ):

                return {
                    "id": data["id"],
                    "league": data.get(
                        "league",
                        "РПЛ",
                    ),
                    "name": name,
                    "year": data.get(
                        "year"
                    ),
                    "status": data.get(
                        "status"
                    ),
                }

        # ----------------------------------------------------
        # 3. Fallback
        # ----------------------------------------------------

        latest = normalized[-1]

        return {
            "id": latest["id"],
            "league": latest.get(
                "league",
                "РПЛ",
            ),
            "name": latest.get(
                "name",
                "",
            ),
            "year": latest.get(
                "year"
            ),
            "status": latest.get(
                "status"
            ),
        }

    except Exception:
        return None


# ============================================================
# DATABASE COUNTS
# ============================================================

def get_db_counts() -> Dict[str, int]:
    """
    Возвращает основные показатели БД.

    Матчи считаются ТОЛЬКО для активного сезона.
    """

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
                # ВАЖНО:
                # используем season_id непосредственно
                # через API database.py.

                rounds = db.get_rounds(
                    season_id=season["id"]
                )

                round_ids = {
                    dict(row)["id"]
                    for row in rounds
                }

                if round_ids:

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

        # ----------------------------------------------------
        # PREDICTIONS
        # ----------------------------------------------------

        result["predictions"] = safe_table_count(
            db,
            "predictions",
        )

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        result["results"] = safe_table_count(
            db,
            "match_results",
        )

    except Exception:
        pass

    return result


# ============================================================
# PASSPORT DATA
# ============================================================

def get_passport_data():
    """
    Загружает паспорта команд активного сезона.
    """

    try:
        db = get_db()

        season = get_active_season()

        if not season:
            return []

        teams = db.get_teams(
            league="РПЛ"
        )

        result = []

        for team in teams:

            team_data = dict(team)

            passport = db.get_team_passport(
                team_data["id"],
                season["id"],
            )

            if not passport:
                continue

            passport_data = dict(passport)

            result.append(
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

        return result

    except Exception:
        return []


# ============================================================
# CLUB RATING UI
# ============================================================

def render_league_rating(
    league_name: str,
    title: Optional[str] = None,
) -> None:

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
            f"⚠️ Рейтинг для {league_name} "
            "не найден."
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

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# PAGE LOADER
# ============================================================

def render_external_page(
    module_name: str,
    page_title: str,
) -> None:
    """
    Единый загрузчик внутренних страниц.

    Пример:
        app.pages.tour_manager
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
            "Техническая ошибка",
            expanded=False,
        ):

            st.exception(exc)


# ============================================================
# BOOTSTRAP
# ============================================================

def run_bootstrap() -> None:
    """
    Выполняет bootstrap один раз за сессию.
    """

    if (
        st.session_state.bootstrap_result
        is not None
    ):
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
    # RATINGS
    # ========================================================

    st.caption("⭐ FAJ RATINGS")

    if st.button(
        "⭐ Рейтинг клубов",
        use_container_width=True,
    ):
        navigate("club_ratings")

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
        "🧠 ETC",
        use_container_width=True,
    ):
        navigate("etc")

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
        "🔬 Диагностика парсеров",
        use_container_width=True,
    ):
        navigate("parser_diagnostic")

    if st.button(
        "🔍 Аудит данных FAJ",
        use_container_width=True,
    ):
        navigate("data_audit")

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
                save_database_to_github,
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
                f"❌ Ошибка сохранения: {exc}"
            )

    if st.button(
        "🔄 Восстановить базу из GitHub",
        use_container_width=True,
    ):

        try:

            from app.github_db_sync import (
                load_database_from_github,
            )

            with st.spinner(
                "Восстановление..."
            ):

                result = (
                    load_database_from_github()
                )

            if result.get("loaded"):

                st.success(
                    f"✅ База восстановлена: "
                    f"{result['size']} bytes"
                )

                # После замены SQLite
                # пересоздаём состояние страницы.

                st.session_state.bootstrap_result = None
                st.rerun()

            else:

                st.info(
                    f"ℹ️ "
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

page = st.session_state.page


# ============================================================
# ROUND CENTER
# ============================================================

if page == "tour_manager":

    render_external_page(
        "app.pages.tour_manager",
        "Управление турами",
    )


elif page == "predict_round":

    render_external_page(
        "app.pages.predict_round",
        "Прогноз тура",
    )


elif page == "import_facts":

    render_external_page(
        "app.pages.import_facts",
        "Факты тура",
    )


elif page == "round_complete":

    render_external_page(
        "app.pages.round_complete",
        "Тур сыгран",
    )


# ============================================================
# CLUB RATINGS
# ============================================================

elif page == "club_ratings":

    st.title("⭐ FAJ Club Rating")

    st.caption(
        "Экспертный стартовый рейтинг клубов "
        "с последующим динамическим обновлением через ETC."
    )

    st.divider()

    if not RATINGS_AVAILABLE:

        st.error(
            "❌ Модуль FAJ Club Rating не найден."
        )

    else:

        st.info(
            "Стартовый рейтинг — базовая экспертная "
            "оценка силы команды перед началом "
            "динамического рейтинга FAJ."
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
            "Сейчас отображается стартовый FAJ Rating."
        )

        st.write(
            "После подключения ClubRatingUpdater "
            "текущий рейтинг будет изменяться "
            "по результатам матчей."
        )

        st.write(
            "START_RATING остаётся исторической "
            "точкой отсчёта и не перезаписывается."
        )


# ============================================================
# PASSPORTS
# ============================================================

elif page == "passports":

    st.title("📋 Паспорта команд")

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


# ============================================================
# ANALYTICS
# ============================================================

elif page == "analytics":

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

elif page == "history":

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
# ETC
# ============================================================

elif page == "etc":

    render_external_page(
        "app.pages.etc",
        "ETC",
    )


# ============================================================
# SYSTEM
# ============================================================

elif page == "system":

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
    # RATINGS
    # --------------------------------------------------------

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

    st.subheader(
        "📁 Диагностика БД"
    )

    st.write(
        f"**Путь к БД:** `{DB_PATH}`"
    )

    st.write(
        f"**Файл существует:** "
        f"{database_exists()}"
    )

    if database_exists():

        try:

            size_mb = (
                os.path.getsize(DB_PATH)
                / 1024
                / 1024
            )

            st.write(
                f"**Размер:** {size_mb:.2f} MB"
            )

            mtime = os.path.getmtime(
                DB_PATH
            )

            st.write(
                "**Изменён:** "
                + datetime.fromtimestamp(
                    mtime
                ).strftime(
                    "%d.%m.%Y %H:%M:%S"
                )
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

elif page == "reset_data":

    render_external_page(
        "app.pages.reset_data",
        "Очистка данных",
    )


# ============================================================
# DIAGNOSTIC
# ============================================================

elif page == "diagnostic":

    st.title(
        "🔧 Диагностика FAJ Database"
    )

    st.subheader("📁 Путь к БД")

    st.code(DB_PATH)

    st.subheader("📊 Статус файла")

    if database_exists():

        size = os.path.getsize(DB_PATH)

        st.success(
            "✅ Файл существует! "
            f"Размер: {size / 1024:.2f} KB"
        )

    else:

        st.error(
            "❌ Файл НЕ СУЩЕСТВУЕТ"
        )

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

    st.subheader(
        "📁 Содержимое data/"
    )

    try:

        data_dir = os.path.dirname(DB_PATH)

        files = (
            os.listdir(data_dir)
            if os.path.isdir(data_dir)
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

elif page == "parser_diagnostic":

    render_external_page(
        "app.pages.parser_diagnostic",
        "Диагностика парсеров",
    )


# ============================================================
# DATA AUDIT
# ============================================================

elif page == "data_audit":

    st.title(
        "🔍 Аудит данных FAJ"
    )

    st.caption(
        "Проверка данных, необходимых "
        "для Evolution Report"
    )

    st.divider()

    st.info(
        "Аудит проверяет наличие критических данных:\n\n"
        "• predictions\n"
        "• prediction_scores\n"
        "• match_results\n"
        "• learning_memory\n"
        "• model_parameters\n"
        "• team_passports\n"
        "• связи между данными"
    )

    if st.button(
        "🔍 ЗАПУСТИТЬ АУДИТ",
        type="primary",
        use_container_width=True,
    ):

        script_path = os.path.join(
            ROOT_DIR,
            "scripts",
            "audit_faj_data.py",
        )

        if not os.path.isfile(script_path):

            st.error(
                "❌ Скрипт аудита не найден:\n\n"
                f"`{script_path}`"
            )

        else:

            try:

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
                        timeout=120,
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
                        "Обнаружены проблемы."
                    )

            except subprocess.TimeoutExpired:

                st.error(
                    "❌ Аудит превысил лимит "
                    "времени 120 секунд."
                )

            except Exception as exc:

                st.error(
                    f"❌ Ошибка запуска аудита: {exc}"
                )

                with st.expander(
                    "Техническая ошибка"
                ):

                    st.exception(exc)

    with st.expander(
        "📖 Как интерпретировать результаты аудита"
    ):

        st.markdown(
            """
### Критические данные

| Данные | Назначение |
|---|---|
| `predictions` | Прогнозы FAJ |
| `prediction_scores` | Точные счета прогнозов |
| `match_results` | Фактические результаты |
| `learning_memory` | Память обучения ETC |
| `model_parameters` | Параметры модели |
| `team_passports` | Паспорта команд |

### Для Evolution Report

Если отсутствуют исторические параметры,
невозможно корректно показать:

`БЫЛО → СТАЛО`

Если отсутствуют `match_snapshots`,
невозможно восстановить состояние модели
на конкретный момент.

Если отсутствует связь ошибки прогноза
с `learning_memory`, невозможно корректно
отследить:

`результат → ошибка → обучение → изменение`
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
LOAD CALENDAR
============================================================

Загрузка календаря РПЛ 2026/27.

Использует:
    app.parsers.rpl_fixtures_parser.RPLFixturesParser

Парсер:
    - Smart Tables
    - Championat
    - Soccerland

Парсер НЕ изменяет БД.
Эта страница отвечает за запись нормализованных матчей
в SQLite.
============================================================
"""

import os
import sqlite3
import streamlit as st

from app.parsers.rpl_fixtures_parser import RPLFixturesParser
from app.sync_engine import SyncEngine


# ============================================================
# DATABASE
# ============================================================

ROOT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

DB_PATH = os.path.join(
    ROOT_DIR,
    "data",
    "faj.db",
)


def get_connection():
    """
    Открывает SQLite.
    """

    os.makedirs(
        os.path.dirname(DB_PATH),
        exist_ok=True,
    )

    return sqlite3.connect(DB_PATH)


# ============================================================
# HELPERS
# ============================================================

def get_or_create_season(
    cursor,
    league="РПЛ",
    season_year="2026-2027",
):
    """
    Находит существующий сезон или создаёт его.

    В нашей БД сезон уже должен существовать после Bootstrap,
    поэтому INSERT OR IGNORE используется только как защита.
    """

    cursor.execute(
        """
        SELECT id
        FROM seasons
        WHERE league = ?
          AND (
              year = ?
              OR name = ?
          )
        LIMIT 1
        """,
        (
            league,
            season_year,
            season_year,
        ),
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    # --------------------------------------------------------
    # Пробуем создать сезон.
    # --------------------------------------------------------

    try:

        cursor.execute(
            """
            INSERT INTO seasons
                (name, league, year)
            VALUES
                (?, ?, ?)
            """,
            (
                season_year,
                league,
                season_year,
            ),
        )

    except sqlite3.OperationalError:

        # Если в конкретной схеме нет year
        cursor.execute(
            """
            INSERT OR IGNORE INTO seasons
                (name, league)
            VALUES
                (?, ?)
            """,
            (
                season_year,
                league,
            ),
        )

    cursor.execute(
        """
        SELECT id
        FROM seasons
        WHERE league = ?
          AND name = ?
        LIMIT 1
        """,
        (
            league,
            season_year,
        ),
    )

    row = cursor.fetchone()

    if not row:
        raise RuntimeError(
            "Не удалось получить season_id"
        )

    return row[0]


def get_team_id(
    cursor,
    team_name,
):
    """
    Возвращает ID существующей команды.
    """

    cursor.execute(
        """
        SELECT id
        FROM teams
        WHERE name = ?
        LIMIT 1
        """,
        (team_name,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return row[0]


def get_or_create_round(
    cursor,
    season_id,
    round_number,
):
    """
    Возвращает ID тура.
    """

    cursor.execute(
        """
        SELECT id
        FROM rounds
        WHERE season_id = ?
          AND round_number = ?
        LIMIT 1
        """,
        (
            season_id,
            round_number,
        ),
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO rounds
            (season_id, round_number)
        VALUES
            (?, ?)
        """,
        (
            season_id,
            round_number,
        ),
    )

    return cursor.lastrowid


# ============================================================
# SAVE MATCH
# ============================================================

def save_match(
    cursor,
    season_id,
    match,
):
    """
    Сохраняет один нормализованный матч.

    Возвращает:
        "created"
        "exists"
        "skipped"
    """

    home_team = match.get(
        "home_team"
    )

    away_team = match.get(
        "away_team"
    )

    round_number = match.get(
        "round"
    )

    match_date = match.get(
        "date"
    )

    status = match.get(
        "status",
        "scheduled",
    )

    home_goals = match.get(
        "home_goals"
    )

    away_goals = match.get(
        "away_goals"
    )

    # --------------------------------------------------------
    # Проверка обязательных данных
    # --------------------------------------------------------

    if not home_team or not away_team:
        return "skipped"

    if not round_number:
        return "skipped"

    home_id = get_team_id(
        cursor,
        home_team,
    )

    away_id = get_team_id(
        cursor,
        away_team,
    )

    if not home_id or not away_id:
        return "skipped"

    # --------------------------------------------------------
    # Тур
    # --------------------------------------------------------

    round_id = get_or_create_round(
        cursor,
        season_id,
        int(round_number),
    )

    # --------------------------------------------------------
    # Проверяем существующий матч
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT id
        FROM matches
        WHERE round_id = ?
          AND home_team_id = ?
          AND away_team_id = ?
        LIMIT 1
        """,
        (
            round_id,
            home_id,
            away_id,
        ),
    )

    existing = cursor.fetchone()

    if existing:

        match_id = existing[0]

        # ----------------------------------------------------
        # Если появился результат — обновляем его
        # ----------------------------------------------------

        if (
            home_goals is not None
            and away_goals is not None
        ):

            cursor.execute(
                """
                UPDATE matches
                SET
                    status = ?,
                    date = ?,
                    actual_home = ?,
                    actual_away = ?
                WHERE id = ?
                """,
                (
                    "finished",
                    match_date,
                    home_goals,
                    away_goals,
                    match_id,
                ),
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO match_results
                    (
                        match_id,
                        home_goals,
                        away_goals
                    )
                VALUES
                    (?, ?, ?)
                """,
                (
                    match_id,
                    home_goals,
                    away_goals,
                ),
            )

        return "exists"

    # --------------------------------------------------------
    # Создаём новый матч
    # --------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO matches
        (
            round_id,
            home_team_id,
            away_team_id,
            competition,
            status,
            date,
            actual_home,
            actual_away
        )
        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            round_id,
            home_id,
            away_id,
            "РПЛ",
            status,
            match_date,
            home_goals,
            away_goals,
        ),
    )

    match_id = cursor.lastrowid

    # --------------------------------------------------------
    # Если матч завершён — сохраняем результат
    # --------------------------------------------------------

    if (
        home_goals is not None
        and away_goals is not None
    ):

        cursor.execute(
            """
            INSERT OR IGNORE INTO match_results
            (
                match_id,
                home_goals,
                away_goals
            )
            VALUES
            (?, ?, ?)
            """,
            (
                match_id,
                home_goals,
                away_goals,
            ),
        )

    return "created"


# ============================================================
# MAIN
# ============================================================

def main():

    st.title(
        "📅 Загрузка календаря РПЛ"
    )

    st.caption(
        "FAJ RPL Fixtures Parser v12.1"
    )

    st.info(
        """
        Система получает календарь из нескольких источников:

        • Smart Tables
        • Championat
        • Soccerland

        Затем объединяет данные, удаляет дубли и
        сохраняет уникальные матчи в FAJ SQLite.
        """
    )

    # --------------------------------------------------------
    # CURRENT DB STATUS
    # --------------------------------------------------------

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM teams WHERE league = 'РПЛ'"
        )

        teams_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM matches"
        )

        matches_count = cursor.fetchone()[0]

    finally:

        conn.close()

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "🏟️ Команд РПЛ",
            teams_count,
        )

    with c2:
        st.metric(
            "📋 Матчей в БД",
            matches_count,
        )

    st.divider()

    # --------------------------------------------------------
    # LOAD BUTTON
    # --------------------------------------------------------

    if st.button(
        "📥 ЗАГРУЗИТЬ КАЛЕНДАРЬ",
        type="primary",
        use_container_width=True,
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            # =================================================
            # 1. Сезон
            # =================================================

            season_id = get_or_create_season(
                cursor,
                league="РПЛ",
                season_year="2026-2027",
            )

            # =================================================
            # 2. Парсинг
            # =================================================

            with st.spinner(
                "🌐 Загружаем календарь из источников..."
            ):

                parser = RPLFixturesParser()

                parser_result = parser.parse()

            matches = parser_result.get(
                "matches",
                [],
            )

            sources = parser_result.get(
                "sources",
                {},
            )

            errors = parser_result.get(
                "errors",
                [],
            )

            duplicates = parser_result.get(
                "duplicates",
                [],
            )

            # =================================================
            # 3. Источники
            # =================================================

            st.subheader(
                "🌐 Источники"
            )

            for source_name, info in sources.items():

                status = info.get(
                    "status",
                    "unknown",
                )

                count = info.get(
                    "matches",
                    0,
                )

                if status == "ok":

                    st.success(
                        f"✅ {source_name}: "
                        f"{count} матчей"
                    )

                else:

                    st.warning(
                        f"⚠️ {source_name}: "
                        f"не удалось получить данные"
                    )

            # =================================================
            # 4. Проверка результата
            # =================================================

            if not matches:

                st.error(
                    "❌ Парсер не вернул ни одного матча."
                )

                if errors:

                    with st.expander(
                        "📋 Ошибки источников"
                    ):

                        for error in errors:
                            st.write(
                                f"• {error}"
                            )

                return

            st.info(
                f"📋 Найдено уникальных матчей: "
                f"{len(matches)}"
            )

            st.info(
                f"♻️ Дубликатов при объединении: "
                f"{len(duplicates)}"
            )

            # =================================================
            # 5. Сохраняем
            # =================================================

            created = 0
            existing = 0
            skipped = 0

            progress = st.progress(
                0
            )

            total = len(matches)

            for index, match in enumerate(matches):

                result = save_match(
                    cursor,
                    season_id,
                    match,
                )

                if result == "created":

                    created += 1

                elif result == "exists":

                    existing += 1

                else:

                    skipped += 1

                progress.progress(
                    (index + 1) / total
                )

            conn.commit()

            # =================================================
            # 6. Результат
            # =================================================

            st.success(
                "✅ Загрузка календаря завершена."
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "🆕 Создано",
                    created,
                )

            with c2:

                st.metric(
                    "♻️ Уже существовали",
                    existing,
                )

            with c3:

                st.metric(
                    "⚠️ Пропущено",
                    skipped,
                )

            # =================================================
            # 7. Финальное состояние БД
            # =================================================

            cursor.execute(
                "SELECT COUNT(*) FROM matches"
            )

            final_matches = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM rounds"
            )

            final_rounds = cursor.fetchone()[0]

            st.divider()

            st.subheader(
                "📊 Состояние БД после загрузки"
            )

            c1, c2 = st.columns(2)

            with c1:

                st.metric(
                    "📋 Матчи",
                    final_matches,
                )

            with c2:

                st.metric(
                    "🔢 Туры",
                    final_rounds,
                )

            # =================================================
            # 8. Ошибки
            # =================================================

            if errors:

                with st.expander(
                    "⚠️ Ошибки источников"
                ):

                    for error in errors:

                        st.write(
                            f"• {error}"
                        )

        except Exception as e:

            conn.rollback()

            st.error(
                f"❌ Ошибка загрузки календаря: {e}"
            )

            import traceback

            st.code(
                traceback.format_exc()
            )

        finally:

            conn.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

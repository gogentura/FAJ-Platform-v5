#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
LOAD CALENDAR PAGE
============================================================

Назначение:
    Диагностика и загрузка календаря РПЛ 2026/27.

ВАЖНО:
    1. Сначала парсим календарь.
    2. Показываем разбивку по 30 турам.
    3. Проверяем количество матчей.
    4. Только после этого пользователь вручную
       запускает запись в SQLite.

Никакой автоматической очистки БД нет.
"""

import os
import sqlite3
from collections import Counter, defaultdict

import pandas as pd
import streamlit as st

from app.parsers.rpl_fixtures_parser import RPLFixturesParser
from app.sync_engine import SyncEngine


# ============================================================
# PATH
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


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """
    Подключение к SQLite.
    """

    os.makedirs(
        os.path.dirname(DB_PATH),
        exist_ok=True,
    )

    return sqlite3.connect(DB_PATH)


# ============================================================
# SESSION STATE
# ============================================================

if "calendar_parse_result" not in st.session_state:
    st.session_state.calendar_parse_result = None


# ============================================================
# PAGE
# ============================================================

def main():

    st.title("📅 ЗАГРУЗКА КАЛЕНДАРЯ РПЛ")

    st.caption(
        "FAJ Platform v12.1 · RPL Fixtures Parser"
    )

    st.info(
        """
        Сначала система получит календарь из доступных источников
        и покажет его полную разбивку по 30 турам.

        **На этапе проверки база данных не изменяется.**

        После проверки появится отдельная кнопка загрузки
        календаря в SQLite.
        """
    )

    st.divider()

    # ========================================================
    # PARSE
    # ========================================================

    if st.button(
        "🔎 ПОЛУЧИТЬ И ПРОВЕРИТЬ КАЛЕНДАРЬ",
        type="primary",
        use_container_width=True,
    ):

        with st.spinner(
            "🌐 Загружаем календарь из источников..."
        ):

            try:

                parser = RPLFixturesParser()

                result = parser.parse()

                st.session_state.calendar_parse_result = result

            except Exception as e:

                st.error(
                    f"❌ Ошибка парсера: {e}"
                )

                st.exception(e)

                return

    # ========================================================
    # RESULT
    # ========================================================

    result = (
        st.session_state.calendar_parse_result
    )

    if not result:
        return

    matches = result.get(
        "matches",
        [],
    )

    sources = result.get(
        "sources",
        {},
    )

    errors = result.get(
        "errors",
        [],
    )

    duplicates = result.get(
        "duplicates",
        [],
    )

    # ========================================================
    # GENERAL STATISTICS
    # ========================================================

    st.subheader(
        "📊 Результат парсинга"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Найдено уникальных",
            len(matches),
        )

    with c2:

        st.metric(
            "Ожидается",
            240,
        )

    with c3:

        st.metric(
            "Дубликатов",
            len(duplicates),
        )

    with c4:

        difference = 240 - len(matches)

        st.metric(
            "До 240",
            difference,
        )

    # ========================================================
    # SOURCE STATISTICS
    # ========================================================

    st.subheader(
        "🌐 Источники"
    )

    source_rows = []

    for source_name, info in sources.items():

        source_rows.append(
            {
                "Источник": source_name,
                "Статус": info.get(
                    "status",
                    "",
                ),
                "Матчей": info.get(
                    "matches",
                    0,
                ),
            }
        )

    if source_rows:

        st.dataframe(
            pd.DataFrame(source_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # ERRORS / WARNINGS
    # ========================================================

    if errors:

        st.warning(
            "⚠️ Есть сообщения об ошибках источников."
        )

        with st.expander(
            "📋 Показать ошибки"
        ):

            for error in errors:

                st.write(
                    f"- {error}"
                )

    # ========================================================
    # DUPLICATES
    # ========================================================

    if duplicates:

        with st.expander(
            f"⚠️ Дубликаты: {len(duplicates)}"
        ):

            for duplicate in duplicates:

                st.write(
                    duplicate
                )

    # ========================================================
    # ROUND ANALYSIS
    # ========================================================

    st.divider()

    st.subheader(
        "🏆 РАЗБИВКА ПО 30 ТУРАМ"
    )

    # --------------------------------------------------------
    # Группируем матчи
    # --------------------------------------------------------

    rounds = defaultdict(list)

    unknown_round = []

    for match in matches:

        round_number = match.get(
            "round"
        )

        if round_number is None:

            unknown_round.append(
                match
            )

        else:

            try:

                round_number = int(
                    round_number
                )

                rounds[
                    round_number
                ].append(match)

            except (
                TypeError,
                ValueError,
            ):

                unknown_round.append(
                    match
                )

    # --------------------------------------------------------
    # Summary table
    # --------------------------------------------------------

    round_rows = []

    for round_number in range(
        1,
        31,
    ):

        round_matches = rounds.get(
            round_number,
            [],
        )

        count = len(
            round_matches
        )

        expected = 8

        if count == expected:

            status = "✅ ПОЛНЫЙ"

        elif count == 0:

            status = "❌ ПУСТО"

        else:

            status = (
                f"⚠️ НЕПОЛНЫЙ "
                f"({count}/8)"
            )

        round_rows.append(
            {
                "Тур": round_number,
                "Матчей": count,
                "Ожидается": expected,
                "Статус": status,
            }
        )

    round_df = pd.DataFrame(
        round_rows
    )

    st.dataframe(
        round_df,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # ROUND TOTAL
    # ========================================================

    total_first_30 = sum(
        len(
            rounds.get(
                number,
                [],
            )
        )
        for number in range(
            1,
            31,
        )
    )

    st.write(
        f"**Матчей в турах 1–30: "
        f"{total_first_30} / 240**"
    )

    if unknown_round:

        st.warning(
            f"⚠️ Матчей без корректного номера тура: "
            f"{len(unknown_round)}"
        )

    # ========================================================
    # DETAILED ROUND VIEW
    # ========================================================

    st.divider()

    st.subheader(
        "📋 МАТЧИ ПО ТУРАМ"
    )

    for round_number in range(
        1,
        31,
    ):

        round_matches = rounds.get(
            round_number,
            [],
        )

        count = len(
            round_matches
        )

        if count == 8:

            title = (
                f"Тур {round_number} "
                f"✅ 8/8"
            )

        elif count == 0:

            title = (
                f"Тур {round_number} "
                f"❌ 0/8"
            )

        else:

            title = (
                f"Тур {round_number} "
                f"⚠️ {count}/8"
            )

        with st.expander(
            title,
            expanded=False,
        ):

            if not round_matches:

                st.warning(
                    "Матчи этого тура не найдены."
                )

                continue

            rows = []

            for index, match in enumerate(
                round_matches,
                start=1,
            ):

                rows.append(
                    {
                        "№": index,
                        "Хозяева": match.get(
                            "home_team",
                            "",
                        ),
                        "Гости": match.get(
                            "away_team",
                            "",
                        ),
                        "Дата": match.get(
                            "date",
                            "",
                        ),
                        "Время": match.get(
                            "time",
                            "",
                        ),
                        "Статус": match.get(
                            "status",
                            "",
                        ),
                        "Счёт": (
                            f"{match.get('home_goals')}:"
                            f"{match.get('away_goals')}"
                            if (
                                match.get(
                                    "home_goals"
                                )
                                is not None
                                and match.get(
                                    "away_goals"
                                )
                                is not None
                            )
                            else "—"
                        ),
                        "Источник": match.get(
                            "source",
                            "",
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    # ========================================================
    # RAW MATCH LIST
    # ========================================================

    with st.expander(
        "🔍 Полный список найденных матчей"
    ):

        raw_rows = []

        for match in matches:

            raw_rows.append(
                {
                    "Тур": match.get(
                        "round"
                    ),
                    "Хозяева": match.get(
                        "home_team"
                    ),
                    "Гости": match.get(
                        "away_team"
                    ),
                    "Дата": match.get(
                        "date"
                    ),
                    "Время": match.get(
                        "time"
                    ),
                    "Статус": match.get(
                        "status"
                    ),
                    "Счёт": (
                        f"{match.get('home_goals')}:"
                        f"{match.get('away_goals')}"
                        if (
                            match.get(
                                "home_goals"
                            )
                            is not None
                            and match.get(
                                "away_goals"
                            )
                            is not None
                        )
                        else "—"
                    ),
                    "Источник": match.get(
                        "source"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(raw_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # DATABASE STATUS BEFORE WRITE
    # ========================================================

    st.divider()

    st.subheader(
        "💾 Текущее состояние SQLite"
    )

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM matches"
        )

        db_matches = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM rounds"
        )

        db_rounds = cursor.fetchone()[0]

        conn.close()

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Матчей в БД сейчас",
                db_matches,
            )

        with c2:

            st.metric(
                "Туров в БД сейчас",
                db_rounds,
            )

    except Exception as e:

        st.error(
            f"❌ Не удалось прочитать БД: {e}"
        )

        return

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    st.divider()

    if len(matches) < 240:

        st.warning(
            f"""
            ⚠️ ВНИМАНИЕ

            Парсер сейчас нашёл только {len(matches)}
            уникальных матчей из ожидаемых 240.

            Поэтому загрузка в БД ниже специально
            не разрешается.

            Сначала необходимо разобраться,
            какие матчи отсутствуют.
            """
        )

        return

    if len(matches) > 240:

        st.warning(
            f"""
            ⚠️ Парсер вернул {len(matches)} матчей.

            Ожидается 240.

            Автоматическая загрузка остановлена
            до проверки данных.
            """
        )

        return

    incomplete_rounds = [
        row
        for row in round_rows
        if row["Матчей"] != 8
    ]

    if incomplete_rounds:

        st.warning(
            "⚠️ Есть неполные туры. "
            "Загрузка заблокирована до проверки."
        )

        return

    # ========================================================
    # LOAD TO DATABASE
    # ========================================================

    st.success(
        "✅ Календарь содержит 240 матчей "
        "и все 30 туров полные."
    )

    st.divider()

    st.subheader(
        "🚀 Загрузка в SQLite"
    )

    st.info(
        """
        Эта кнопка выполнит запись найденного
        календаря в базу.

        Существующие команды, сезоны и паспорта
        не удаляются.
        """
    )

    if st.button(
        "💾 ЗАГРУЗИТЬ ПОДТВЕРЖДЁННЫЙ КАЛЕНДАРЬ В БД",
        type="primary",
        use_container_width=True,
    ):

        conn = get_connection()

        cursor = conn.cursor()

        loaded = 0
        skipped = 0
        results_loaded = 0

        try:

            # =================================================
            # SEASON
            # =================================================

            cursor.execute(
                """
                INSERT OR IGNORE INTO seasons
                (name, league)
                VALUES (?, ?)
                """,
                (
                    "РПЛ 2026-2027",
                    "РПЛ",
                ),
            )

            cursor.execute(
                """
                SELECT id
                FROM seasons
                WHERE name = ?
                AND league = ?
                """,
                (
                    "РПЛ 2026-2027",
                    "РПЛ",
                ),
            )

            season_row = cursor.fetchone()

            if not season_row:

                raise RuntimeError(
                    "Сезон 2026-2027 не найден."
                )

            season_id = season_row[0]

            # =================================================
            # MATCHES
            # =================================================

            for match in matches:

                home_name = match.get(
                    "home_team"
                )

                away_name = match.get(
                    "away_team"
                )

                round_number = match.get(
                    "round"
                )

                if not home_name or not away_name:
                    skipped += 1
                    continue

                # ---------------------------------------------
                # TEAM IDS
                # ---------------------------------------------

                cursor.execute(
                    """
                    SELECT id
                    FROM teams
                    WHERE name = ?
                    AND league = 'РПЛ'
                    """,
                    (home_name,),
                )

                home_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT id
                    FROM teams
                    WHERE name = ?
                    AND league = 'РПЛ'
                    """,
                    (away_name,),
                )

                away_row = cursor.fetchone()

                if not home_row or not away_row:

                    skipped += 1
                    continue

                home_id = home_row[0]
                away_id = away_row[0]

                # ---------------------------------------------
                # ROUND
                # ---------------------------------------------

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO rounds
                    (season_id, round_number)
                    VALUES (?, ?)
                    """,
                    (
                        season_id,
                        round_number,
                    ),
                )

                cursor.execute(
                    """
                    SELECT id
                    FROM rounds
                    WHERE season_id = ?
                    AND round_number = ?
                    """,
                    (
                        season_id,
                        round_number,
                    ),
                )

                round_row = cursor.fetchone()

                if not round_row:

                    skipped += 1
                    continue

                round_id = round_row[0]

                # ---------------------------------------------
                # MATCH
                # ---------------------------------------------

                status = match.get(
                    "status",
                    "scheduled",
                )

                date_value = match.get(
                    "date"
                )

                home_goals = match.get(
                    "home_goals"
                )

                away_goals = match.get(
                    "away_goals"
                )

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO matches
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        home_id,
                        away_id,
                        "РПЛ",
                        status,
                        date_value,
                        home_goals,
                        away_goals,
                    ),
                )

                # Проверяем, существует ли матч
                cursor.execute(
                    """
                    SELECT id
                    FROM matches
                    WHERE round_id = ?
                    AND home_team_id = ?
                    AND away_team_id = ?
                    """,
                    (
                        round_id,
                        home_id,
                        away_id,
                    ),
                )

                match_row = cursor.fetchone()

                if not match_row:

                    skipped += 1
                    continue

                match_id = match_row[0]

                loaded += 1

                # ---------------------------------------------
                # RESULT
                # ---------------------------------------------

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
                        VALUES (?, ?, ?)
                        """,
                        (
                            match_id,
                            home_goals,
                            away_goals,
                        ),
                    )

                    results_loaded += 1

            conn.commit()

            # =================================================
            # PASSPORTS
            # =================================================

            try:

                with st.spinner(
                    "📋 Проверяем паспорта..."
                ):

                    sync = SyncEngine()

                    passport_result = (
                        sync.load_passports()
                    )

            except Exception as passport_error:

                passport_result = {
                    "updated": 0,
                    "error": str(
                        passport_error
                    ),
                }

            # =================================================
            # FINAL STATUS
            # =================================================

            st.success(
                "🎉 КАЛЕНДАРЬ ЗАГРУЖЕН!"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "Загружено",
                    loaded,
                )

            with c2:

                st.metric(
                    "Пропущено",
                    skipped,
                )

            with c3:

                st.metric(
                    "Результатов",
                    results_loaded,
                )

            if passport_result.get(
                "error"
            ):

                st.warning(
                    "⚠️ Паспорта не обновлены: "
                    f"{passport_result['error']}"
                )

            else:

                st.info(
                    "📋 Паспорта проверены: "
                    f"{passport_result.get('updated', 0)}"
                )

        except Exception as e:

            conn.rollback()

            st.error(
                f"❌ Ошибка записи в БД: {e}"
            )

            st.exception(e)

        finally:

            conn.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

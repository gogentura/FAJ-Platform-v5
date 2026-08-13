#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
LOAD CALENDAR PAGE
============================================================

Назначение:
    Диагностика и загрузка календаря РПЛ 2026/27.

АЛГОРИТМ:

    1. Получаем календарь из парсера.
    2. Показываем источники.
    3. Показываем разбивку по 30 турам.
    4. Проверяем каждый найденный матч против SQLite.
    5. Показываем причины пропусков.
    6. Если календарь неполный — загрузка блокируется.
    7. Если календарь полный — разрешается запись.

ВАЖНО:
    - Никакой автоматической очистки БД.
    - DELETE отсутствует.
    - DROP отсутствует.
    - Существующие данные не удаляются.
    - Существующие матчи не перезаписываются.
============================================================
"""

import os
import sqlite3
from collections import defaultdict, Counter

import pandas as pd
import streamlit as st

from app.parsers.rpl_fixtures_parser import RPLFixturesParser


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

    conn = sqlite3.connect(DB_PATH)

    return conn


# ============================================================
# SESSION STATE
# ============================================================

if "calendar_parse_result" not in st.session_state:
    st.session_state["calendar_parse_result"] = None

if "calendar_db_diagnostic" not in st.session_state:
    st.session_state["calendar_db_diagnostic"] = None


# ============================================================
# HELPERS
# ============================================================

def get_team_id(cursor, team_name):
    """
    Возвращает ID команды РПЛ.
    """

    cursor.execute(
        """
        SELECT id
        FROM teams
        WHERE name = ?
        AND league = 'РПЛ'
        LIMIT 1
        """,
        (team_name,),
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    return None


def get_season_id(cursor):
    """
    Возвращает ID сезона 2026-2027.

    Ничего не создаёт.
    """

    cursor.execute(
        """
        SELECT id
        FROM seasons
        WHERE (
            name = 'РПЛ 2026-2027'
            OR name = '2026-2027'
        )
        AND league = 'РПЛ'
        ORDER BY id
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    return None


def get_round_id(cursor, season_id, round_number):
    """
    Возвращает ID тура.

    Ничего не создаёт.
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

    return None


def check_existing_match(
    cursor,
    round_id,
    home_id,
    away_id,
):
    """
    Проверяет наличие матча в БД.
    """

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

    row = cursor.fetchone()

    if row:
        return row[0]

    return None


# ============================================================
# DATABASE DIAGNOSTICS
# ============================================================

def diagnose_matches(matches):
    """
    Проверяет все найденные парсером матчи
    против текущей SQLite БД.

    НИЧЕГО НЕ ИЗМЕНЯЕТ.
    """

    result = {
        "ready": [],
        "existing": [],
        "problems": [],
        "total": len(matches),
    }

    conn = get_connection()
    cursor = conn.cursor()

    try:

        season_id = get_season_id(cursor)

        if not season_id:

            for match in matches:

                result["problems"].append(
                    {
                        "Тур": match.get("round"),
                        "Хозяева": match.get(
                            "home_team",
                            "",
                        ),
                        "Гости": match.get(
                            "away_team",
                            "",
                        ),
                        "Причина": (
                            "Сезон РПЛ 2026-2027 "
                            "не найден в БД"
                        ),
                    }
                )

            return result

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

            # ------------------------------------------------
            # TEAM CHECK
            # ------------------------------------------------

            home_id = get_team_id(
                cursor,
                home_name,
            )

            away_id = get_team_id(
                cursor,
                away_name,
            )

            if not home_id:

                result["problems"].append(
                    {
                        "Тур": round_number,
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "Причина": (
                            f"Команда хозяев "
                            f"'{home_name}' "
                            f"не найдена в teams"
                        ),
                    }
                )

                continue

            if not away_id:

                result["problems"].append(
                    {
                        "Тур": round_number,
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "Причина": (
                            f"Команда гостей "
                            f"'{away_name}' "
                            f"не найдена в teams"
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # ROUND CHECK
            # ------------------------------------------------

            if round_number is None:

                result["problems"].append(
                    {
                        "Тур": "—",
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "Причина": (
                            "У матча отсутствует "
                            "номер тура"
                        ),
                    }
                )

                continue

            try:

                round_number = int(
                    round_number
                )

            except (
                TypeError,
                ValueError,
            ):

                result["problems"].append(
                    {
                        "Тур": round_number,
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "Причина": (
                            "Некорректный номер тура"
                        ),
                    }
                )

                continue

            if not 1 <= round_number <= 30:

                result["problems"].append(
                    {
                        "Тур": round_number,
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "Причина": (
                            "Тур находится "
                            "вне диапазона 1-30"
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # ROUND ID
            # ------------------------------------------------

            round_id = get_round_id(
                cursor,
                season_id,
                round_number,
            )

            if not round_id:

                result["problems"].append(
                    {
                        "Тур": round_number,
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "Причина": (
                            f"Тур {round_number} "
                            "не найден в таблице rounds"
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # EXISTING MATCH
            # ------------------------------------------------

            existing_id = check_existing_match(
                cursor,
                round_id,
                home_id,
                away_id,
            )

            if existing_id:

                result["existing"].append(
                    {
                        "Тур": round_number,
                        "Хозяева": home_name,
                        "Гости": away_name,
                        "ID матча": existing_id,
                        "Статус": "Уже в БД",
                    }
                )

            else:

                result["ready"].append(
                    {
                        "match": match,
                        "season_id": season_id,
                        "round_id": round_id,
                        "home_id": home_id,
                        "away_id": away_id,
                    }
                )

    finally:

        conn.close()

    return result


# ============================================================
# PAGE
# ============================================================

def main():

    st.title(
        "📅 ЗАГРУЗКА КАЛЕНДАРЯ РПЛ"
    )

    st.caption(
        "FAJ Platform v12.1 · "
        "RPL Fixtures Parser"
    )

    st.info(
        """
        Сначала система получает календарь из источников
        и проводит полную диагностику.

        **На этапе проверки база данных НЕ изменяется.**

        Будут проверены:
        - все 30 туров;
        - количество матчей;
        - команды;
        - существующие матчи;
        - причины пропусков.

        Загрузка в SQLite разрешается только после
        успешной проверки полного календаря.
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

                parse_result = parser.parse()

                st.session_state["calendar_parse_result"] = (
                    parse_result
                )

            except Exception as e:

                st.error(
                    f"❌ Ошибка парсера: {e}"
                )

                st.exception(e)

                return

    # ========================================================
    # RESULT
    # ========================================================

    result = st.session_state.get(
        "calendar_parse_result"
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

    difference = 240 - len(matches)

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

        st.metric(
            "Недостаёт",
            max(difference, 0),
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
            pd.DataFrame(
                source_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # ERRORS
    # ========================================================

    if errors:

        st.warning(
            "⚠️ Есть ошибки источников."
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

            continue

        try:

            round_number = int(
                round_number
            )

        except (
            TypeError,
            ValueError,
        ):

            unknown_round.append(
                match
            )

            continue

        rounds[
            round_number
        ].append(match)

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

        missing = max(
            expected - count,
            0,
        )

        if count == 8:

            status = "✅ ПОЛНЫЙ"

        elif count == 0:

            status = "❌ ПУСТО"

        elif count < 8:

            status = (
                f"⚠️ НЕПОЛНЫЙ "
                f"({count}/8)"
            )

        else:

            status = (
                f"⚠️ БОЛЬШЕ 8 "
                f"({count}/8)"
            )

        round_rows.append(
            {
                "Тур": round_number,
                "Матчей": count,
                "Ожидается": expected,
                "Не хватает": missing,
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
    # ROUND SUMMARY
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

    complete_rounds = sum(
        1
        for row in round_rows
        if row["Матчей"] == 8
    )

    incomplete_rounds = [
        row
        for row in round_rows
        if row["Матчей"] != 8
    ]

    st.write(
        f"**Матчей в турах 1–30: "
        f"{total_first_30} / 240**"
    )

    st.write(
        f"**Полных туров: "
        f"{complete_rounds} / 30**"
    )

    if unknown_round:

        st.warning(
            f"⚠️ Матчей без корректного тура: "
            f"{len(unknown_round)}"
        )

    # ========================================================
    # INCOMPLETE ROUNDS
    # ========================================================

    if incomplete_rounds:

        st.warning(
            "⚠️ Неполные туры обнаружены."
        )

        incomplete_df = pd.DataFrame(
            incomplete_rounds
        )

        st.dataframe(
            incomplete_df,
            use_container_width=True,
            hide_index=True,
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
                                ) is not None
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
    # UNKNOWN ROUND MATCHES
    # ========================================================

    if unknown_round:

        st.divider()

        st.subheader(
            "⚠️ МАТЧИ БЕЗ НОМЕРА ТУРА"
        )

        unknown_rows = []

        for match in unknown_round:

            unknown_rows.append(
                {
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
                    "Источник": match.get(
                        "source",
                        "",
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(
                unknown_rows
            ),
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
                            ) is not None
                        )
                        else "—"
                    ),
                    "Источник": match.get(
                        "source"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(
                raw_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # DATABASE STATUS
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

        cursor.execute(
            "SELECT COUNT(*) FROM teams"
        )

        db_teams = cursor.fetchone()[0]

        conn.close()

        c1, c2, c3 = st.columns(3)

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

        with c3:

            st.metric(
                "Команд в БД",
                db_teams,
            )

    except Exception as e:

        st.error(
            f"❌ Не удалось прочитать БД: {e}"
        )

        return

    # ========================================================
    # MATCH DATABASE DIAGNOSTICS
    # ========================================================

    st.divider()

    st.subheader(
        "🔬 ПРОВЕРКА НА ВОЗМОЖНОСТЬ ЗАГРУЗКИ"
    )

    st.info(
        """
        Сейчас проверяем найденные матчи против SQLite.

        Эта проверка **ничего не записывает и ничего
        не изменяет**.
        """
    )

    if st.button(
        "🔬 ПРОВЕРИТЬ ВСЕ МАТЧИ ПРОТИВ БД",
        use_container_width=True,
    ):

        with st.spinner(
            "🔍 Проверяем команды, туры и существующие матчи..."
        ):

            diagnostic = diagnose_matches(
                matches
            )

        st.session_state["calendar_db_diagnostic"] = (
            diagnostic
        )

    diagnostic = st.session_state.get(
        "calendar_db_diagnostic"
    )

    if diagnostic:

        ready_count = len(
            diagnostic.get(
                "ready",
                [],
            )
        )

        existing_count = len(
            diagnostic.get(
                "existing",
                [],
            )
        )

        problem_count = len(
            diagnostic.get(
                "problems",
                [],
            )
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Готовы к загрузке",
                ready_count,
            )

        with c2:

            st.metric(
                "Уже в БД",
                existing_count,
            )

        with c3:

            st.metric(
                "Проблемных",
                problem_count,
            )

        # ----------------------------------------------------
        # PROBLEMS
        # ----------------------------------------------------

        problems = diagnostic.get(
            "problems",
            [],
        )

        if problems:

            st.error(
                f"❌ Найдено проблемных матчей: "
                f"{len(problems)}"
            )

            st.subheader(
                "🚨 ПРИЧИНЫ ПРОПУСКОВ"
            )

            problems_df = pd.DataFrame(
                problems
            )

            st.dataframe(
                problems_df,
                use_container_width=True,
                hide_index=True,
            )

            # ------------------------------------------------
            # REASON SUMMARY
            # ------------------------------------------------

            reason_counter = Counter(
                item.get(
                    "Причина",
                    "",
                )
                for item in problems
            )

            st.subheader(
                "📊 Сводка причин"
            )

            reason_rows = []

            for reason, count in (
                reason_counter.most_common()
            ):

                reason_rows.append(
                    {
                        "Причина": reason,
                        "Количество": count,
                    }
                )

            st.dataframe(
                pd.DataFrame(
                    reason_rows
                ),
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.success(
                "✅ Все найденные матчи "
                "проходят проверку команд и туров."
            )

        # ----------------------------------------------------
        # EXISTING
        # ----------------------------------------------------

        existing = diagnostic.get(
            "existing",
            [],
        )

        if existing:

            with st.expander(
                f"📋 Уже существующие матчи: "
                f"{len(existing)}"
            ):

                st.dataframe(
                    pd.DataFrame(existing),
                    use_container_width=True,
                    hide_index=True,
                )

    # ========================================================
    # FINAL SAFETY GATE
    # ========================================================

    st.divider()

    if len(matches) != 240:

        st.warning(
            f"""
            ⚠️ ЗАГРУЗКА ЗАБЛОКИРОВАНА

            Парсер нашёл {len(matches)} уникальных матчей.

            Ожидается: 240.

            Разница: {abs(240 - len(matches))}.

            Сначала необходимо установить,
            какие матчи отсутствуют.
            """
        )

        return

    if incomplete_rounds:

        st.warning(
            "⚠️ ЗАГРУЗКА ЗАБЛОКИРОВАНА."

            " Есть неполные туры."
        )

        return

    # ========================================================
    # DATABASE DIAGNOSTIC GATE
    # ========================================================

    diagnostic = st.session_state.get(
        "calendar_db_diagnostic"
    )

    if not diagnostic:

        st.info(
            """
            🔬 Перед загрузкой необходимо выполнить
            проверку матчей против БД.

            Нажми кнопку:

            **🔬 ПРОВЕРИТЬ ВСЕ МАТЧИ ПРОТИВ БД**
            """
        )

        return

    if diagnostic.get(
        "problems"
    ):

        st.warning(
            """
            ⚠️ ЗАГРУЗКА ЗАБЛОКИРОВАНА

            Найдены матчи, которые не проходят
            проверку БД.

            Сначала исправляем причину.
            """
        )

        return

    # ========================================================
    # READY
    # ========================================================

    st.success(
        "✅ КАЛЕНДАРЬ ПРОШЁЛ ВСЕ ПРОВЕРКИ."
    )

    st.info(
        f"""
        Готово к загрузке:

        • Матчей: {len(matches)}
        • Туров: 30
        • Проблем: 0

        Существующие данные удаляться не будут.
        """
    )

    # ========================================================
    # WRITE TO DATABASE
    # ========================================================

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
        existing = 0

        try:

            # =================================================
            # SEASON
            # =================================================

            season_id = get_season_id(
                cursor
            )

            if not season_id:

                raise RuntimeError(
                    "Сезон РПЛ 2026-2027 "
                    "не найден в БД."
                )

            # =================================================
            # MATCHES
            # =================================================

            for item in diagnostic.get(
                "ready",
                [],
            ):

                match = item["match"]

                season_id = item[
                    "season_id"
                ]

                round_id = item[
                    "round_id"
                ]

                home_id = item[
                    "home_id"
                ]

                away_id = item[
                    "away_id"
                ]

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

                # ---------------------------------------------
                # MATCH
                # ---------------------------------------------

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

                if cursor.rowcount == 1:

                    loaded += 1

                else:

                    existing += 1

                # ---------------------------------------------
                # RESULT
                # ---------------------------------------------

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

                match_row = cursor.fetchone()

                if not match_row:

                    skipped += 1

                    continue

                match_id = match_row[0]

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

                    if cursor.rowcount == 1:

                        results_loaded += 1

            conn.commit()

            # =================================================
            # FINAL STATUS
            # =================================================

            st.success(
                "🎉 КАЛЕНДАРЬ ЗАГРУЖЕН В SQLITE!"
            )

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                st.metric(
                    "Новых матчей",
                    loaded,
                )

            with c2:

                st.metric(
                    "Уже существовали",
                    existing,
                )

            with c3:

                st.metric(
                    "Пропущено",
                    skipped,
                )

            with c4:

                st.metric(
                    "Новых результатов",
                    results_loaded,
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

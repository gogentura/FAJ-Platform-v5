#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ — Soccer365 Diagnostic
============================================================

Диагностическая страница для проверки фактического
результата работы Soccer365Parser.

НАЗНАЧЕНИЕ:

    URL
     ↓
    Soccer365Parser
     ↓
    raw parsed result
     ↓
    визуальная проверка

СТРАНИЦА НЕ:

    - изменяет SQLite
    - создаёт Prediction
    - запускает FAJ Brain
    - запускает FormModel
    - запускает GoalModel
    - запускает Learning
    - изменяет Team Passport

Главная задача:

    проверить, что parser действительно правильно
    извлекает ВСЕ статистические показатели.

Особенно:

    Удары
    Удары в створ

чтобы вручную исключить проблему label collision.
============================================================
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import streamlit as st


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("FAJ.SOCCER365.DIAGNOSTIC")


# ============================================================
# PAGE CONFIG
#
# ВАЖНО:
# При запуске через st.navigation / streamlit_app.py
# set_page_config обычно уже выполняется в главном файле.
# Поэтому здесь НЕ вызываем st.set_page_config().
# ============================================================


# ============================================================
# IMPORT PARSER
# ============================================================

def load_parser():

    try:

        from app.parsers.soccer365_parser import (
            Soccer365Parser,
        )

        return Soccer365Parser

    except Exception as exc:

        st.error(
            "❌ Не удалось загрузить Soccer365Parser."
        )

        with st.expander(
            "Техническая информация",
            expanded=True,
        ):

            st.exception(exc)

        logger.exception(
            "Soccer365Parser import failed"
        )

        return None


# ============================================================
# HELPERS
# ============================================================

def value_or_dash(
    value: Any,
) -> Any:

    if value is None:
        return "—"

    return value


def format_quality(
    value: Any,
) -> str:

    if value is None:
        return "—"

    try:

        return f"{float(value) * 100:.1f}%"

    except (
        TypeError,
        ValueError,
    ):

        return str(value)


def stat_rows(
    stats: Dict[str, Any],
) -> List[Dict[str, Any]]:

    rows = []

    for key, value in stats.items():

        if key.startswith("home_"):

            away_key = key.replace(
                "home_",
                "away_",
                1,
            )

            rows.append(
                {
                    "key": key,
                    "home": value,
                    "away": stats.get(
                        away_key
                    ),
                }
            )

    return rows


# ============================================================
# SHOTS CHECK
# ============================================================

def render_shots_check(
    stats: Dict[str, Any],
) -> None:

    st.subheader(
        "🎯 Проверка «Удары» / «Удары в створ»"
    )

    home_shots = stats.get(
        "home_shots"
    )

    away_shots = stats.get(
        "away_shots"
    )

    home_sot = stats.get(
        "home_shots_on_target"
    )

    away_sot = stats.get(
        "away_shots_on_target"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            "**🏠 Хозяева**"
        )

        st.metric(
            "Удары",
            value_or_dash(
                home_shots
            ),
        )

        st.metric(
            "Удары в створ",
            value_or_dash(
                home_sot
            ),
        )

    with col2:

        st.markdown(
            "**✈️ Гости**"
        )

        st.metric(
            "Удары",
            value_or_dash(
                away_shots
            ),
        )

        st.metric(
            "Удары в створ",
            value_or_dash(
                away_sot
            ),
        )

    # --------------------------------------------------------
    # ЛОГИЧЕСКАЯ ПРОВЕРКА
    # --------------------------------------------------------

    problems = []

    if (
        home_shots is not None
        and home_sot is not None
        and home_sot > home_shots
    ):

        problems.append(
            "У хозяев SOT больше общего количества ударов."
        )

    if (
        away_shots is not None
        and away_sot is not None
        and away_sot > away_shots
    ):

        problems.append(
            "У гостей SOT больше общего количества ударов."
        )

    if problems:

        for problem in problems:

            st.error(
                f"❌ {problem}"
            )

    elif (
        home_shots is not None
        and away_shots is not None
        and home_sot is not None
        and away_sot is not None
    ):

        st.success(
            "✅ Базовая логическая проверка пройдена: "
            "удары в створ не превышают общее количество ударов."
        )

    else:

        st.warning(
            "⚠️ Одно или несколько значений Shots/SOT "
            "не были найдены parser'ом."
        )


# ============================================================
# RENDER RESULT
# ============================================================

def render_result(
    result: Dict[str, Any],
    match_number: int,
) -> None:

    st.markdown(
        f"## 🧪 Результат теста — матч №{match_number}"
    )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    if result.get("error"):

        st.error(
            f"❌ Parser error: {result['error']}"
        )

    # --------------------------------------------------------
    # BASIC INFO
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "🏠 Хозяева",
            value_or_dash(
                result.get(
                    "home_team"
                )
            ),
        )

    with col2:

        st.metric(
            "✈️ Гости",
            value_or_dash(
                result.get(
                    "away_team"
                )
            ),
        )

    with col3:

        st.metric(
            "⚽ Счёт",
            value_or_dash(
                result.get(
                    "score"
                )
            ),
        )

    with col4:

        st.metric(
            "📊 Качество",
            format_quality(
                result.get(
                    "quality"
                )
            ),
        )

    st.caption(
        f"Дата: "
        f"{value_or_dash(result.get('match_date'))}"
        f"  |  "
        f"Parser: "
        f"{value_or_dash(result.get('parser_version'))}"
    )

    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    with st.expander(
        "🔗 Источник",
        expanded=False,
    ):

        st.code(
            value_or_dash(
                result.get(
                    "source_url"
                )
            )
        )

    # --------------------------------------------------------
    # SHOTS CHECK
    # --------------------------------------------------------

    render_shots_check(
        result.get(
            "stats",
            {},
        )
    )

    # --------------------------------------------------------
    # ALL STATS
    # --------------------------------------------------------

    st.subheader(
        "📊 Все собранные статистические показатели"
    )

    stats = result.get(
        "stats",
        {},
    )

    if not stats:

        st.warning(
            "⚠️ Parser не вернул статистику."
        )

    else:

        rows = stat_rows(
            stats
        )

        if rows:

            table_data = []

            for row in rows:

                table_data.append(
                    {
                        "Parser field": row["key"],
                        "🏠 Home": row["home"],
                        "✈️ Away": row["away"],
                    }
                )

            st.dataframe(
                table_data,
                width="stretch",
                hide_index=True,
            )

        # ----------------------------------------------------
        # RAW DICTIONARY
        # ----------------------------------------------------

        with st.expander(
            f"🔎 Raw stats dictionary ({len(stats)} fields)",
            expanded=False,
        ):

            st.json(
                stats
            )

    # --------------------------------------------------------
    # FULL RAW RESULT
    # --------------------------------------------------------

    with st.expander(
        "🧬 Полный raw result parser",
        expanded=False,
    ):

        st.json(
            result
        )

    # --------------------------------------------------------
    # RAW JSON
    # --------------------------------------------------------

    with st.expander(
        "📦 JSON для передачи разработчику",
        expanded=False,
    ):

        st.code(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            language="json",
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.markdown(
        """
        <div class="faj-header">

        <div class="faj-title">
            🧪 Soccer365 Diagnostic
        </div>

        <div class="faj-subtitle">
            Проверка полного набора фактической статистики
            Soccer365 перед подключением новых показателей
            к математической модели FAJ.
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        """
        **Цель теста:** проверить сам parser.

        Здесь мы пока ничего не прогнозируем.
        Просто смотрим, что Soccer365 действительно
        передаёт FAJ и как parser раскладывает эти данные.
        """
    )

    # ========================================================
    # PARSER
    # ========================================================

    ParserClass = load_parser()

    if ParserClass is None:
        return

    parser = ParserClass()

    # ========================================================
    # URL INPUTS
    # ========================================================

    st.markdown(
        "## 🔗 Испытательные матчи"
    )

    st.caption(
        "Можно вставить ссылку на любой уже сыгранный матч "
        "ЦСКА, Зенита или другой команды."
    )

    url1 = st.text_input(
        "Матч №1",
        placeholder=(
            "https://soccer365.ru/games/2465994/"
        ),
        key="soccer365_diag_url_1",
    )

    url2 = st.text_input(
        "Матч №2",
        placeholder=(
            "https://soccer365.ru/games/2478604/"
        ),
        key="soccer365_diag_url_2",
    )

    # ========================================================
    # RUN
    # ========================================================

    st.divider()

    run_col1, run_col2 = st.columns(2)

    with run_col1:

        test_one = st.button(
            "▶️ Проверить матч №1",
            width="stretch",
            type="primary",
        )

    with run_col2:

        test_both = st.button(
            "▶️ Проверить оба матча",
            width="stretch",
        )

    # ========================================================
    # MATCH 1
    # ========================================================

    if test_one:

        if not url1.strip():

            st.warning(
                "Введите ссылку на матч №1."
            )

        else:

            with st.spinner(
                "Парсим Soccer365..."
            ):

                result = parser.parse(
                    url1.strip()
                )

            render_result(
                result,
                1,
            )

    # ========================================================
    # BOTH
    # ========================================================

    if test_both:

        urls = []

        if url1.strip():
            urls.append(
                (
                    1,
                    url1.strip()
                )
            )

        if url2.strip():
            urls.append(
                (
                    2,
                    url2.strip()
                )
            )

        if not urls:

            st.warning(
                "Введите хотя бы одну ссылку."
            )

        else:

            for match_number, url in urls:

                with st.spinner(
                    f"Парсим матч №{match_number}..."
                ):

                    result = parser.parse(
                        url
                    )

                render_result(
                    result,
                    match_number,
                )

                if match_number != urls[-1][0]:

                    st.divider()

    # ========================================================
    # INSTRUCTIONS
    # ========================================================

    st.divider()

    with st.expander(
        "📋 Что именно проверяем",
        expanded=False,
    ):

        st.markdown(
            """
            ### 1. Удары

            Смотрим:

            - `home_shots`
            - `away_shots`

            ### 2. Удары в створ

            Смотрим:

            - `home_shots_on_target`
            - `away_shots_on_target`

            Они должны быть отдельными полями.

            Например:

            ```text
            Удары            12
            Удары в створ      5
            ```

            должно превратиться в:

            ```text
            home_shots = 12
            home_shots_on_target = 5
            ```

            а не:

            ```text
            home_shots = 5
            ```

            ### 3. Проверяем остальные показатели

            Parser должен показать все поля, которые
            реально присутствуют в `stats`.

            В частности:

            - xG
            - Shots
            - Shots on Target
            - Blocked Shots
            - Woodwork
            - Saves
            - Possession
            - Corners
            - Free Kicks
            - Throw-ins
            - Crosses
            - Fouls
            - Offsides
            - Yellow Cards
            - Red Cards
            - Passes
            - Pass Accuracy
            - Tackles
            - Clearances
            - Big Chances
            - Attacks
            - Dangerous Attacks

            ### 4. Ничего не меняем

            Диагностическая страница только вызывает:

            `Soccer365Parser.parse(url)`

            и показывает результат.

            База данных и основная модель не затрагиваются.
            """
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()

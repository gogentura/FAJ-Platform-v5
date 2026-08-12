#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
PREDICTIONS PAGE
============================================================

Назначение:
    Запуск FAJ Prediction Manager для матчей,
    уже находящихся в SQLite.

ВАЖНО:
    Календарь здесь НЕ загружается.
    Календарь здесь НЕ изменяется.

ВОЗМОЖНОСТИ:
    1. Выбор сезона
    2. Выбор тура
    3. Просмотр матчей тура
    4. Контрольный прогноз одного матча
    5. Прогноз всего тура
    6. Отображение результатов
    7. Диагностика Pipeline

ЦЕПОЧКА:

    SQLite
       ↓
    PredictionManager
       ↓
    PassportManager
       ↓
    PredictionPipeline
       ↓
    XG
       ↓
    Poisson
       ↓
    Monte Carlo
       ↓
    Calibration
       ↓
    Confidence
       ↓
    Risk
       ↓
    SQLite
"""

import streamlit as st
import pandas as pd

from app.core.prediction_manager import (
    get_prediction_manager
)

from app.database import FAJDatabase


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection(db):
    """
    Получает соединение с SQLite.
    """
    return db._get_connection()


def get_season_id(db):
    """
    Получает активный сезон.

    Приоритет:
        1. active season
        2. последний сезон РПЛ
    """

    conn = get_connection(db)
    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # ACTIVE SEASON
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM seasons
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        # ----------------------------------------------------
        # FALLBACK — ПОСЛЕДНИЙ СЕЗОН РПЛ
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM seasons
            WHERE league = 'РПЛ'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return None

    finally:

        conn.close()


def get_rounds(db, season_id):
    """
    Получает все туры выбранного сезона.
    """

    conn = get_connection(db)
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
                id,
                round_number
            FROM rounds
            WHERE season_id = ?
            ORDER BY round_number
            """,
            (season_id,)
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_round_matches(db, round_id):
    """
    Получает все матчи выбранного тура.
    """

    conn = get_connection(db)
    cursor = conn.cursor()

    try:

        cursor.execute(
            """
            SELECT
                m.id,
                m.date,
                m.status,
                m.competition,
                th.name AS home_team,
                ta.name AS away_team

            FROM matches m

            LEFT JOIN teams th
                ON m.home_team_id = th.id

            LEFT JOIN teams ta
                ON m.away_team_id = ta.id

            WHERE m.round_id = ?

            ORDER BY
                m.date,
                m.id
            """,
            (round_id,)
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# FORMAT RESULT
# ============================================================

def build_prediction_row(match, result):
    """
    Формирует строку для таблицы массового прогноза.
    """

    if not result:
        return {
            "Матч": (
                f'{match["home_team"]} — '
                f'{match["away_team"]}'
            ),
            "Статус": "ERROR",
            "Счёт": "—",
            "xG": "—",
            "П1": "—",
            "X": "—",
            "П2": "—",
            "BTTS": "—",
            "ТБ 2.5": "—",
            "Confidence": "—",
            "Risk": "—"
        }

    if result.get("status") != "success":

        return {
            "Матч": (
                f'{match["home_team"]} — '
                f'{match["away_team"]}'
            ),
            "Статус": "ERROR",
            "Счёт": "—",
            "xG": "—",
            "П1": "—",
            "X": "—",
            "П2": "—",
            "BTTS": "—",
            "ТБ 2.5": "—",
            "Confidence": "—",
            "Risk": "—"
        }

    xg = result.get(
        "xg",
        {}
    )

    probability = result.get(
        "probability",
        {}
    )

    confidence = result.get(
        "confidence",
        {}
    )

    risk = result.get(
        "risk",
        {}
    )

    return {
        "Матч": (
            f'{match["home_team"]} — '
            f'{match["away_team"]}'
        ),

        "Статус": "SUCCESS",

        "Счёт":
            result.get(
                "score",
                "—"
            ),

        "xG":
            f'{xg.get("home", 0):.2f} — '
            f'{xg.get("away", 0):.2f}',

        "П1":
            f'{probability.get("home", 0) * 100:.1f}%',

        "X":
            f'{probability.get("draw", 0) * 100:.1f}%',

        "П2":
            f'{probability.get("away", 0) * 100:.1f}%',

        "BTTS":
            f'{result.get("btts", 0) * 100:.1f}%',

        "ТБ 2.5":
            f'{result.get("over_2_5", 0) * 100:.1f}%',

        "Confidence":
            f'{confidence.get("overall", 0) * 100:.1f}%',

        "Risk":
            risk.get(
                "level",
                "—"
            )
    }


# ============================================================
# DISPLAY SINGLE RESULT
# ============================================================

def display_prediction_result(result):

    if not result:
        return

    st.divider()

    st.subheader(
        "🔬 Результат Pipeline"
    )

    # ========================================================
    # ERROR
    # ========================================================

    if result.get("status") != "success":

        st.error(
            "❌ Prediction Pipeline вернул ошибку."
        )

        st.code(
            str(
                result.get(
                    "message",
                    "Unknown error"
                )
            )
        )

        return

    # ========================================================
    # BASIC DATA
    # ========================================================

    xg = result.get(
        "xg",
        {}
    )

    probability = result.get(
        "probability",
        {}
    )

    confidence = result.get(
        "confidence",
        {}
    )

    risk = result.get(
        "risk",
        {}
    )

    agreement = result.get(
        "model_agreement",
        {}
    )

    # ========================================================
    # MAIN RESULT
    # ========================================================

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "🏠 xG хозяев",
            f'{xg.get("home", 0):.2f}'
        )

    with col2:

        st.metric(
            "🎯 Прогноз",
            result.get(
                "score",
                "—"
            )
        )

    with col3:

        st.metric(
            "✈️ xG гостей",
            f'{xg.get("away", 0):.2f}'
        )

    # ========================================================
    # PROBABILITIES
    # ========================================================

    st.subheader(
        "📈 Вероятности исходов"
    )

    p1, px, p2 = st.columns(3)

    with p1:

        st.metric(
            "П1",
            f'{probability.get("home", 0) * 100:.1f}%'
        )

    with px:

        st.metric(
            "X",
            f'{probability.get("draw", 0) * 100:.1f}%'
        )

    with p2:

        st.metric(
            "П2",
            f'{probability.get("away", 0) * 100:.1f}%'
        )

    # ========================================================
    # EXTENDED
    # ========================================================

    extended = result.get(
        "extended",
        {}
    )

    btts = extended.get(
        "btts",
        {}
    )

    totals = extended.get(
        "total",
        {}
    )

    st.subheader(
        "📊 Дополнительные показатели"
    )

    e1, e2, e3, e4 = st.columns(4)

    with e1:

        st.metric(
            "Обе забьют",
            f'{btts.get("yes", 0) * 100:.1f}%'
        )

    with e2:

        st.metric(
            "ТБ 2.5",
            f'{totals.get("over_2_5", 0) * 100:.1f}%'
        )

    with e3:

        st.metric(
            "ТБ 3.5",
            f'{totals.get("over_3_5", 0) * 100:.1f}%'
        )

    with e4:

        st.metric(
            "Вероятность счёта",
            f'{result.get("score_probability", 0) * 100:.1f}%'
        )

    # ========================================================
    # CONFIDENCE / RISK
    # ========================================================

    st.subheader(
        "🧠 Уверенность и риск"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Confidence",
            f'{confidence.get("overall", 0) * 100:.1f}%'
        )

    with c2:

        st.metric(
            "Уровень",
            confidence.get(
                "level",
                "—"
            )
        )

    with c3:

        st.metric(
            "Risk",
            risk.get(
                "level",
                "—"
            )
        )

    st.write(
        f'**Model Agreement:** '
        f'{agreement.get("score", 0) * 100:.1f}% '
        f'({agreement.get("level", "—")})'
    )

    # ========================================================
    # TOP SCORES
    # ========================================================

    top_scores = extended.get(
        "top_scores",
        []
    )

    if top_scores:

        st.subheader(
            "🎯 Топ вероятных счетов"
        )

        score_rows = []

        for score in top_scores:

            score_rows.append(
                {
                    "Место":
                    score.get(
                        "rank",
                        0
                    ),

                    "Счёт":
                    f'{score.get("home", 0)}:'
                    f'{score.get("away", 0)}',

                    "Вероятность":
                    score.get(
                        "prob_percent",
                        ""
                    )
                }
            )

        st.dataframe(
            pd.DataFrame(
                score_rows
            ),
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # DIAGNOSTIC
    # ========================================================

    with st.expander(
        "🔬 Диагностика Pipeline"
    ):

        st.json(
            result.get(
                "diagnostic",
                {}
            )
        )

    # ========================================================
    # FULL RESULT
    # ========================================================

    with st.expander(
        "📦 Полный результат"
    ):

        st.json(
            result
        )

    st.success(
        "✅ Контрольный прогноз успешно прошёл "
        "Prediction Manager → Prediction Pipeline."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    st.title(
        "📊 Прогнозы FAJ"
    )

    st.caption(
        "FAJ Platform v12.1 · "
        "Prediction Manager → Prediction Pipeline"
    )

    # ========================================================
    # INFORMATION
    # ========================================================

    st.info(
        """
        Эта страница работает только с матчами,
        уже находящимися в SQLite.

        **Календарь здесь НЕ загружается и НЕ изменяется.**

        Цепочка прогноза:

        `SQLite → Passport → Rating → XG → Poisson → `
        `Monte Carlo → Calibration → Confidence → Risk`
        """
    )

    # ========================================================
    # INIT
    # ========================================================

    db = FAJDatabase()

    pm = get_prediction_manager()

    # ========================================================
    # SEASON
    # ========================================================

    season_id = get_season_id(
        db
    )

    if season_id is None:

        st.error(
            "❌ В БД не найден сезон РПЛ."
        )

        return

    # ========================================================
    # ROUNDS
    # ========================================================

    rounds = get_rounds(
        db,
        season_id
    )

    if not rounds:

        st.error(
            "❌ В БД не найдены туры."
        )

        return

    round_map = {
        int(row["round_number"]):
        int(row["id"])
        for row in rounds
    }

    round_numbers = sorted(
        round_map.keys()
    )

    # ========================================================
    # SELECT ROUND
    # ========================================================

    st.subheader(
        "🎯 Выбор тура"
    )

    selected_round = st.selectbox(
        "Номер тура",
        round_numbers,
        index=(
            round_numbers.index(4)
            if 4 in round_numbers
            else 0
        )
    )

    round_id = round_map[
        selected_round
    ]

    # ========================================================
    # LOAD MATCHES
    # ========================================================

    matches = get_round_matches(
        db,
        round_id
    )

    st.write(
        f"**Матчей в туре: {len(matches)}**"
    )

    if not matches:

        st.warning(
            "В выбранном туре нет матчей."
        )

        return

    # ========================================================
    # CALENDAR TABLE
    # ========================================================

    st.subheader(
        f"📅 Матчи {selected_round}-го тура"
    )

    match_rows = []

    for match in matches:

        match_rows.append(
            {
                "ID":
                match["id"],

                "Хозяева":
                match["home_team"],

                "Гости":
                match["away_team"],

                "Дата":
                match["date"] or "—",

                "Статус":
                match["status"] or "—"
            }
        )

    st.dataframe(
        pd.DataFrame(
            match_rows
        ),
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # MASS PREDICTION
    # ========================================================

    st.divider()

    st.subheader(
        "🚀 Прогноз на тур"
    )

    st.caption(
        f"Будут рассчитаны все {len(matches)} матчей "
        f"{selected_round}-го тура."
    )

    if st.button(
        f"🚀 РАССЧИТАТЬ ВЕСЬ {selected_round}-Й ТУР",
        type="primary",
        use_container_width=True
    ):

        results = []

        progress = st.progress(
            0
        )

        status_text = st.empty()

        total_matches = len(
            matches
        )

        for index, match in enumerate(
            matches,
            start=1
        ):

            status_text.write(
                f"🧠 Расчёт {index}/{total_matches}: "
                f'{match["home_team"]} — '
                f'{match["away_team"]}'
            )

            try:

                result = pm.predict_by_match_id(
                    int(match["id"])
                )

            except Exception as e:

                result = {
                    "status": "error",
                    "message": str(e)
                }

            results.append(
                {
                    "match": match,
                    "result": result
                }
            )

            progress.progress(
                index / total_matches
            )

        status_text.success(
            f"✅ Расчёт тура завершён: "
            f"{total_matches} матчей."
        )

        st.session_state[
            "round_prediction_results"
        ] = results

        st.session_state[
            "round_prediction_number"
        ] = selected_round

    # ========================================================
    # MASS RESULT
    # ========================================================

    round_results = st.session_state.get(
        "round_prediction_results"
    )

    stored_round = st.session_state.get(
        "round_prediction_number"
    )

    if (
        round_results
        and stored_round == selected_round
    ):

        st.divider()

        st.subheader(
            f"📋 Прогнозы {selected_round}-го тура"
        )

        table_rows = []

        success_count = 0
        error_count = 0

        for item in round_results:

            match = item["match"]
            result = item["result"]

            if result.get("status") == "success":

                success_count += 1

            else:

                error_count += 1

            table_rows.append(
                build_prediction_row(
                    match,
                    result
                )
            )

        st.dataframe(
            pd.DataFrame(
                table_rows
            ),
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        s1, s2, s3 = st.columns(3)

        with s1:

            st.metric(
                "Всего матчей",
                len(round_results)
            )

        with s2:

            st.metric(
                "Успешно",
                success_count
            )

        with s3:

            st.metric(
                "Ошибок",
                error_count
            )

        # ----------------------------------------------------
        # INDIVIDUAL RESULTS
        # ----------------------------------------------------

        for item in round_results:

            match = item["match"]
            result = item["result"]

            with st.expander(
                f'⚽ {match["home_team"]} — '
                f'{match["away_team"]}'
            ):

                if result.get("status") != "success":

                    st.error(
                        result.get(
                            "message",
                            "Unknown error"
                        )
                    )

                    continue

                xg = result.get(
                    "xg",
                    {}
                )

                probability = result.get(
                    "probability",
                    {}
                )

                confidence = result.get(
                    "confidence",
                    {}
                )

                risk = result.get(
                    "risk",
                    {}
                )

                c1, c2, c3, c4 = st.columns(4)

                with c1:

                    st.metric(
                        "Счёт",
                        result.get(
                            "score",
                            "—"
                        )
                    )

                with c2:

                    st.metric(
                        "xG",
                        f'{xg.get("home", 0):.2f} — '
                        f'{xg.get("away", 0):.2f}'
                    )

                with c3:

                    st.metric(
                        "П1 / X / П2",
                        f'{probability.get("home", 0) * 100:.1f}% / '
                        f'{probability.get("draw", 0) * 100:.1f}% / '
                        f'{probability.get("away", 0) * 100:.1f}%'
                    )

                with c4:

                    st.metric(
                        "Confidence",
                        f'{confidence.get("overall", 0) * 100:.1f}%'
                    )

                st.write(
                    f'**Risk:** '
                    f'{risk.get("level", "—")} '
                    f'| **Model Agreement:** '
                    f'{result.get("model_agreement", {}).get("score", 0) * 100:.1f}%'
                )

    # ========================================================
    # SINGLE TEST
    # ========================================================

    st.divider()

    st.subheader(
        "🧪 Контрольный прогноз одного матча"
    )

    st.caption(
        "Используется для диагностики Prediction Pipeline "
        "перед массовым расчётом."
    )

    match_options = {
        (
            f'{m["home_team"]} — '
            f'{m["away_team"]} '
            f'(ID {m["id"]})'
        ):
        m["id"]
        for m in matches
    }

    selected_match_label = st.selectbox(
        "Матч для проверки",
        list(
            match_options.keys()
        ),
        key="prediction_test_match"
    )

    selected_match_id = match_options[
        selected_match_label
    ]

    if st.button(
        "🧪 РАССЧИТАТЬ КОНТРОЛЬНЫЙ ПРОГНОЗ",
        use_container_width=True
    ):

        with st.spinner(
            "🧠 Prediction Manager → Pipeline..."
        ):

            try:

                result = pm.predict_by_match_id(
                    int(selected_match_id)
                )

            except Exception as e:

                result = {
                    "status": "error",
                    "message": str(e)
                }

        st.session_state[
            "last_prediction_result"
        ] = result

    # ========================================================
    # DISPLAY SINGLE RESULT
    # ========================================================

    result = st.session_state.get(
        "last_prediction_result"
    )

    if result:

        display_prediction_result(
            result
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

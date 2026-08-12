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
# HELPERS
# ============================================================

def get_connection(db):
    return db._get_connection()


def get_season_id(db):
    """
    Получает активный сезон.

    Если active отсутствует,
    берём последний сезон РПЛ.
    """

    conn = get_connection(db)
    cursor = conn.cursor()

    try:

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
    Получает туры выбранного сезона.
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

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:

        conn.close()


def get_round_matches(db, round_id):
    """
    Получает матчи тура.
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

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:

        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("📊 Прогнозы FAJ")

    st.caption(
        "FAJ Platform v12.1 · Prediction Manager → Prediction Pipeline"
    )

    st.info(
        """
        Эта страница работает только с матчами,
        уже находящимися в SQLite.

        **Календарь здесь не загружается и не изменяется.**

        Прогноз строится через:

        `Passport → Rating → XG → Poisson → Monte Carlo → Calibration → Confidence → Risk`
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

    season_id = get_season_id(db)

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
    # MATCHES
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
    # MATCH TABLE
    # ========================================================

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
        pd.DataFrame(match_rows),
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # SINGLE TEST
    # ========================================================

    st.divider()

    st.subheader(
        "🧪 Контрольный прогноз"
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
        list(match_options.keys())
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

            result = pm.predict_by_match_id(
                selected_match_id
            )

        st.session_state[
            "last_prediction_result"
        ] = result

    # ========================================================
    # LAST RESULT
    # ========================================================

    result = st.session_state.get(
        "last_prediction_result"
    )

    if result:

        st.divider()

        st.subheader(
            "🔬 Результат Pipeline"
        )

        if result.get(
            "status"
        ) != "success":

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

        # ----------------------------------------------------
        # MAIN METRICS
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # PROBABILITIES
        # ----------------------------------------------------

        st.subheader(
            "📈 Вероятности"
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

        # ----------------------------------------------------
        # EXTENDED
        # ----------------------------------------------------

        extended = result.get(
            "extended",
            {}
        )

        st.subheader(
            "📊 Дополнительные показатели"
        )

        btts = extended.get(
            "btts",
            {}
        )

        totals = extended.get(
            "total",
            {}
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

        # ----------------------------------------------------
        # CONFIDENCE / RISK
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # TOP SCORES
        # ----------------------------------------------------

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
                                "rank"
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

        # ----------------------------------------------------
        # DIAGNOSTIC
        # ----------------------------------------------------

        with st.expander(
            "🔬 Диагностика Pipeline"
        ):

            st.json(
                result.get(
                    "diagnostic",
                    {}
                )
            )

        # ----------------------------------------------------
        # FULL RESULT
        # ----------------------------------------------------

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
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

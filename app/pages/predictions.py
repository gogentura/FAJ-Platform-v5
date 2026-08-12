#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
PREDICTIONS PAGE
============================================================

Назначение:

    Работа prediction pipeline FAJ
    непосредственно с матчами SQLite.

Архитектура:

    SQLite matches
          ↓
    PredictionManager
          ↓
    Team Passport
          ↓
    PredictionPipeline
          ↓
    xG / Poisson / Monte Carlo
          ↓
    predictions
    prediction_scores
    prediction_distributions

ВАЖНО:

    Эта страница НЕ загружает календарь.

    Календарь уже находится в faj.db.

    Эта страница только запускает прогнозирование.
============================================================
"""

import streamlit as st
import pandas as pd

from app.core.prediction_manager import (
    get_prediction_manager,
)

from app.database import FAJDatabase


# ============================================================
# HELPERS
# ============================================================

def get_rounds(db):
    """
    Получает доступные туры из SQLite.
    """

    conn = db._get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                r.id,
                r.round_number,
                r.season_id,
                COUNT(m.id) AS matches_count

            FROM rounds r

            LEFT JOIN matches m
                ON m.round_id = r.id

            GROUP BY
                r.id,
                r.round_number,
                r.season_id

            ORDER BY
                r.round_number
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


def get_round_matches(
    db,
    round_id,
):
    """
    Получает матчи выбранного тура.
    """

    conn = db._get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                m.id,
                m.date,
                m.status,
                m.actual_home,
                m.actual_away,

                th.name AS home_team,
                ta.name AS away_team

            FROM matches m

            LEFT JOIN teams th
                ON th.id = m.home_team_id

            LEFT JOIN teams ta
                ON ta.id = m.away_team_id

            WHERE m.round_id = ?

            ORDER BY
                m.date,
                m.id
            """,
            (round_id,),
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# PAGE
# ============================================================

def main():

    st.title(
        "📊 ПРОГНОЗЫ FAJ"
    )

    st.caption(
        "FAJ Platform v12.1 · Prediction Pipeline"
    )

    # ========================================================
    # SESSION STATE
    # ========================================================

    if "predictions" not in st.session_state:

        st.session_state[
            "predictions"
        ] = []

    if "prediction_round_id" not in st.session_state:

        st.session_state[
            "prediction_round_id"
        ] = None

    # ========================================================
    # INITIALIZATION
    # ========================================================

    db = FAJDatabase()

    pm = get_prediction_manager()

    # ========================================================
    # DATABASE STATUS
    # ========================================================

    st.subheader(
        "💾 Состояние базы"
    )

    try:

        conn = db._get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM matches"
        )

        match_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM teams"
        )

        team_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM team_passports"
        )

        passport_count = cursor.fetchone()[0]

        conn.close()

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Матчей",
                match_count,
            )

        with c2:

            st.metric(
                "Команд",
                team_count,
            )

        with c3:

            st.metric(
                "Паспортов",
                passport_count,
            )

    except Exception as e:

        st.error(
            f"❌ Ошибка чтения БД: {e}"
        )

        return

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if match_count == 0:

        st.warning(
            "⚠️ В БД нет матчей. "
            "Сначала загрузите календарь РПЛ."
        )

        return

    if passport_count < 16:

        st.warning(
            f"""
            ⚠️ В БД только {passport_count}
            паспортов.

            Для полноценного прогнозирования РПЛ
            ожидается 16 паспортов.
            """
        )

    # ========================================================
    # LOAD ROUNDS
    # ========================================================

    rounds = get_rounds(db)

    if not rounds:

        st.error(
            "❌ В БД нет туров."
        )

        return

    # ========================================================
    # ROUND SELECTOR
    # ========================================================

    st.divider()

    st.subheader(
        "🎯 Выбор тура"
    )

    round_numbers = [
        item["round_number"]
        for item in rounds
    ]

    # Сначала пытаемся выбрать 4-й тур,
    # если он существует.
    default_index = (
        round_numbers.index(4)
        if 4 in round_numbers
        else 0
    )

    selected_round_number = st.selectbox(
        "Номер тура",
        round_numbers,
        index=default_index,
    )

    selected_round = next(
        (
            item
            for item in rounds
            if item["round_number"]
            == selected_round_number
        ),
        None,
    )

    if not selected_round:

        st.error(
            "❌ Тур не найден."
        )

        return

    round_id = selected_round["id"]

    # ========================================================
    # MATCH LIST
    # ========================================================

    matches = get_round_matches(
        db,
        round_id,
    )

    st.subheader(
        f"📋 Матчи {selected_round_number} тура"
    )

    if not matches:

        st.warning(
            "В выбранном туре нет матчей."
        )

        return

    match_rows = []

    for match in matches:

        status = (
            match.get("status")
            or "unknown"
        )

        if status in {
            "finished",
            "completed",
            "played",
        }:

            result_text = (
                f"{match.get('actual_home')}:"
                f"{match.get('actual_away')}"
            )

        else:

            result_text = "—"

        match_rows.append(
            {
                "ID": match["id"],
                "Дата": match.get(
                    "date"
                ),
                "Хозяева": match.get(
                    "home_team"
                ),
                "Гости": match.get(
                    "away_team"
                ),
                "Статус": status,
                "Результат": result_text,
            }
        )

    st.dataframe(
        pd.DataFrame(match_rows),
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # ROUND STATISTICS
    # ========================================================

    scheduled = [
        match
        for match in matches
        if str(
            match.get(
                "status",
                ""
            )
        ).lower()
        not in {
            "finished",
            "completed",
            "played",
        }
    ]

    finished = [
        match
        for match in matches
        if str(
            match.get(
                "status",
                ""
            )
        ).lower()
        in {
            "finished",
            "completed",
            "played",
        }
    ]

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Матчей в туре",
            len(matches),
        )

    with c2:

        st.metric(
            "Предстоящих",
            len(scheduled),
        )

    with c3:

        st.metric(
            "Завершено",
            len(finished),
        )

    # ========================================================
    # PREDICT BUTTON
    # ========================================================

    st.divider()

    st.subheader(
        "🧠 Prediction Pipeline"
    )

    st.info(
        """
        FAJ возьмёт матчи непосредственно из SQLite,
        загрузит паспорта команд и передаст их
        в PredictionPipeline.

        Календарь при этом не изменяется.
        """
    )

    if st.button(
        f"🧠 РАССЧИТАТЬ ПРОГНОЗЫ НА {selected_round_number} ТУР",
        type="primary",
        use_container_width=True,
    ):

        st.session_state[
            "predictions"
        ] = []

        st.session_state[
            "prediction_round_id"
        ] = round_id

        if not scheduled:

            st.warning(
                "⚠️ В этом туре нет "
                "предстоящих матчей."
            )

        else:

            progress = st.progress(
                0
            )

            status_box = st.empty()

            results = []

            total = len(
                scheduled
            )

            for index, match in enumerate(
                scheduled,
                start=1,
            ):

                status_box.info(
                    f"""
                    🧠 Расчёт {index}/{total}

                    {match['home_team']}
                    —
                    {match['away_team']}
                    """
                )

                try:

                    result = (
                        pm.predict_by_match_id(
                            match["id"]
                        )
                    )

                    results.append(
                        result
                    )

                except Exception as e:

                    results.append(
                        {
                            "status": "error",
                            "match_id": match[
                                "id"
                            ],
                            "home_team": match[
                                "home_team"
                            ],
                            "away_team": match[
                                "away_team"
                            ],
                            "message": str(e),
                        }
                    )

                progress.progress(
                    index / total
                )

            status_box.empty()

            st.session_state[
                "predictions"
            ] = results

            successful = [
                r
                for r in results
                if r.get("status")
                != "error"
            ]

            errors = [
                r
                for r in results
                if r.get("status")
                == "error"
            ]

            st.success(
                f"""
                ✅ Расчёт завершён.

                Матчей: {total}
                Успешно: {len(successful)}
                Ошибок: {len(errors)}
                """
            )

    # ========================================================
    # RESULTS
    # ========================================================

    predictions = (
        st.session_state.get(
            "predictions",
            [],
        )
    )

    if not predictions:

        st.info(
            "ℹ️ Прогнозы ещё не рассчитаны."
        )

        return

    # ========================================================
    # DISPLAY
    # ========================================================

    st.divider()

    st.subheader(
        "📊 РЕЗУЛЬТАТЫ FAJ"
    )

    for pred in predictions:

        st.markdown(
            "---"
        )

        home_team = pred.get(
            "home_team",
            "—",
        )

        away_team = pred.get(
            "away_team",
            "—",
        )

        match_id = pred.get(
            "match_id",
            "—",
        )

        # ----------------------------------------------------
        # ERROR
        # ----------------------------------------------------

        if pred.get(
            "status"
        ) == "error":

            st.error(
                f"""
                ❌ Ошибка

                Матч #{match_id}

                {home_team}
                —
                {away_team}

                {pred.get('message', '')}
                """
            )

            continue

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        prediction = pred.get(
            "prediction",
            pred,
        )

        probability = pred.get(
            "probability",
            prediction.get(
                "probability",
                {},
            ),
        )

        xg = pred.get(
            "xg",
            prediction.get(
                "xg",
                {},
            ),
        )

        score = (
            prediction.get(
                "score"
            )
            or pred.get(
                "score",
                "—",
            )
        )

        score_probability = (
            prediction.get(
                "score_probability",
                0,
            )
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        col1, col2, col3 = st.columns(
            [2, 1, 2]
        )

        with col1:

            st.metric(
                "🏠 Хозяева",
                home_team,
            )

            st.caption(
                f"xG: "
                f"{float(xg.get('home', 0)):.2f}"
            )

        with col2:

            st.markdown(
                f"## {score}"
            )

            try:

                st.caption(
                    "Вероятность счёта: "
                    f"{float(score_probability):.1%}"
                )

            except (
                TypeError,
                ValueError,
            ):

                st.caption(
                    "Вероятность счёта: —"
                )

        with col3:

            st.metric(
                "✈️ Гости",
                away_team,
            )

            st.caption(
                f"xG: "
                f"{float(xg.get('away', 0)):.2f}"
            )

        # ----------------------------------------------------
        # 1X2
        # ----------------------------------------------------

        p1 = probability.get(
            "home",
            0,
        )

        px = probability.get(
            "draw",
            0,
        )

        p2 = probability.get(
            "away",
            0,
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "П1",
                f"{float(p1):.1%}",
            )

        with c2:

            st.metric(
                "X",
                f"{float(px):.1%}",
            )

        with c3:

            st.metric(
                "П2",
                f"{float(p2):.1%}",
            )

        # ----------------------------------------------------
        # DETAILS
        # ----------------------------------------------------

        with st.expander(
            "📊 Детали прогноза"
        ):

            st.json(
                pred
            )

    # ========================================================
    # FINAL DATABASE STATUS
    # ========================================================

    st.divider()

    st.subheader(
        "💾 Состояние prediction layer"
    )

    try:

        conn = db._get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM predictions"
        )

        predictions_count = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            "SELECT COUNT(*) FROM prediction_scores"
        )

        scores_count = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            "SELECT COUNT(*) FROM prediction_distributions"
        )

        distributions_count = (
            cursor.fetchone()[0]
        )

        conn.close()

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "predictions",
                predictions_count,
            )

        with c2:

            st.metric(
                "prediction_scores",
                scores_count,
            )

        with c3:

            st.metric(
                "prediction_distributions",
                distributions_count,
            )

    except Exception as e:

        st.warning(
            f"⚠️ Не удалось прочитать "
            f"prediction layer: {e}"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

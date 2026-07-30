# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0

Football Analytics Journal

Главный интерфейс Streamlit
"""

import streamlit as st

from app.database import FAJDatabase
from app.faj_engine import FAJEngine
from app.prediction_engine import PredictionEngine


st.set_page_config(
    page_title="FAJ Platform 9.0",
    page_icon="⚽",
    layout="wide"
)


@st.cache_resource
def load_engine():

    db = FAJDatabase()
    db.load_all()

    engine = FAJEngine(db)
    predictor = PredictionEngine(engine)

    return db, engine, predictor


db, engine, predictor = load_engine()


st.title("⚽ FAJ Platform 9.0")
st.caption("Football Analytics Journal")


st.divider()


teams = sorted(
    [
        team["team"]
        for team in db.passports
    ]
)


col1, col2 = st.columns(2)


with col1:

    home_team = st.selectbox(
        "Домашняя команда",
        teams
    )


with col2:

    away_team = st.selectbox(
        "Гостевая команда",
        teams,
        index=1
    )


if st.button(
    "Анализировать матч",
    use_container_width=True
):

    prediction = predictor.predict_result(
        home_team,
        away_team
    )

    if prediction is None:

        st.error(
            "Команды не найдены."
        )

    else:

        st.divider()

        st.subheader("Результат анализа")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "xG хозяев",
                prediction["xg_home"]
            )

        with c2:
            st.metric(
                "xG гостей",
                prediction["xg_away"]
            )

        with c3:
            st.metric(
                "Исход",
                prediction["result"]
            )

        st.success(
            f"Прогнозируемый счёт: {prediction['score_prediction']}"
        )

        st.info(
            f"Модель: {prediction['model']}"
        )

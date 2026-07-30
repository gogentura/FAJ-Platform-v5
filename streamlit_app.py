# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0

Football Analytics Journal

Streamlit Interface
"""

import streamlit as st

from app.database import FAJDatabase
from app.faj_engine import FAJEngine
from app.prediction_engine import PredictionEngine
from app.faj_core import FAJCore


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

    predictor = PredictionEngine(
        engine
    )

    faj_core = FAJCore()

    return db, engine, predictor, faj_core


db, engine, predictor, faj_core = load_engine()


st.title("⚽ FAJ Platform 9.0")
st.caption(
    "Football Analytics Journal — Adaptive Football Intelligence"
)


st.divider()


# ================================
# Состояние модели
# ================================

with st.expander(
    "🧠 Состояние FAJ"
):

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Версия",
            faj_core.version
        )

    with c2:

        st.metric(
            "Команд в базе",
            len(db.passports)
        )

    with c3:

        st.metric(
            "Записей памяти",
            len(
                faj_core.memory.memory
            )
        )


st.divider()


# ================================
# Вкладка анализа матча
# ================================

tab1, tab2 = st.tabs(
    [
        "⚽ Анализ матча",
        "🧬 Обновление FAJ"
    ]
)


# --------------------------------
# Анализ матча
# --------------------------------

with tab1:


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
                "Команды не найдены"
            )


        else:

            st.divider()

            st.subheader(
                "Результат анализа"
            )


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
                f"Прогнозируемый счёт: "
                f"{prediction['score_prediction']}"
            )


            st.info(
                f"Модель: {prediction['model']}"
            )



# --------------------------------
# Обновление модели
# --------------------------------

with tab2:


    st.subheader(
        "⚙️ Цикл обучения FAJ"
    )


    st.write(
        """
        После загрузки результатов тура FAJ выполняет:

        1. Анализ ошибок прогнозов
        2. Запись опыта в память
        3. Корректировку паспортов
        4. Создание новой версии модели
        """
    )


    if st.button(
        "🚀 Запустить обработку тура",
        use_container_width=True
    ):


        test_results = []


        if len(test_results) == 0:


            st.warning(
                "Данные тура пока не загружены."
            )


        else:

            faj_core.process_round(
                1,
                test_results
            )


            st.success(
                "FAJ обновлён"
            )

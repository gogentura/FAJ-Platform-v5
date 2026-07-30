# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0

Football Analytics Journal

Главный интерфейс Streamlit

Модули:
- FAJ Database
- Prediction Engine
- FAJ Core
- Round Loader
"""

import streamlit as st


from app.database import FAJDatabase
from app.faj_engine import FAJEngine
from app.prediction_engine import PredictionEngine
from app.faj_core import FAJCore
from app.round_loader import RoundLoader



# ==================================================
# CONFIG
# ==================================================

st.set_page_config(
    page_title="FAJ Platform 9.0",
    page_icon="⚽",
    layout="wide"
)



# ==================================================
# LOAD SYSTEM
# ==================================================

@st.cache_resource
def load_system():

    db = FAJDatabase()

    db.load_all()


    engine = FAJEngine(
        db
    )


    predictor = PredictionEngine(
        engine
    )


    faj_core = FAJCore()


    loader = RoundLoader()


    return (
        db,
        engine,
        predictor,
        faj_core,
        loader
    )



db, engine, predictor, faj_core, loader = load_system()



# ==================================================
# HEADER
# ==================================================

st.title(
    "⚽ FAJ Platform 9.0"
)


st.caption(
    "Football Analytics Journal — Adaptive Football Intelligence"
)


st.divider()



# ==================================================
# SYSTEM STATUS
# ==================================================

with st.expander(
    "🧠 Состояние организма FAJ",
    expanded=True
):


    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "Версия",
            faj_core.version
        )


    with c2:

        st.metric(
            "Команд",
            len(db.passports)
        )


    with c3:

        st.metric(
            "Память",
            len(
                faj_core.memory.memory
            )
        )


    with c4:

        st.metric(
            "История",
            len(
                faj_core.passport.history
            )
        )



st.divider()



# ==================================================
# TABS
# ==================================================

tab1, tab2, tab3 = st.tabs(
    [
        "⚽ Анализ матча",
        "🧬 Обновление FAJ",
        "📚 Память модели"
    ]
)



# ==================================================
# TAB 1
# MATCH ANALYSIS
# ==================================================

with tab1:


    st.subheader(
        "Анализ матча"
    )


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
        "🔮 Анализировать матч",
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



# ==================================================
# TAB 2
# MODEL UPDATE
# ==================================================

with tab2:


    st.subheader(
        "⚙️ Цикл обучения FAJ"
    )


    st.write(
        """
FAJ выполняет цикл:

1. Загружает результаты тура
2. Сравнивает прогноз и факт
3. Записывает ошибки в память
4. Обновляет знания
5. Создаёт новую историю паспортов
        """
    )



    round_number = st.number_input(
        "Номер тура",
        min_value=1,
        value=1
    )



    if st.button(
        "🚀 Обработать тур",
        use_container_width=True
    ):


        try:


            with st.spinner(
                "FAJ анализирует тур..."
            ):


                round_data = loader.load_round(
                    int(round_number)
                )


                faj_core.process_round(
                    int(round_number),
                    round_data
                )



            st.success(
                f"Тур {round_number} успешно обработан"
            )



            st.info(
                f"Матчей обработано: {len(round_data)}"
            )



        except Exception as e:


            st.error(
                f"Ошибка FAJ: {e}"
            )



# ==================================================
# TAB 3
# MEMORY
# ==================================================

with tab3:


    st.subheader(
        "🧠 Память FAJ"
    )



    memory = faj_core.memory.memory



    if len(memory) == 0:


        st.warning(
            "Память пока пустая"
        )


    else:


        st.dataframe(
            memory,
            use_container_width=True
        )

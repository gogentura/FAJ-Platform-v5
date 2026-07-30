# -*- coding: utf-8 -*-

"""
FAJ Platform 9.1

Football Analytics Journal Platform

Adaptive Football Intelligence

Modules:
- FAJ Database
- FAJ Engine
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
    page_title="FAJ Platform 9.1",
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
    "⚽ FAJ Platform 9.1"
)


st.caption(
    "Football Analytics Journal — Adaptive Football Intelligence | Learning Cycle v9.1"
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
            len(faj_core.memory.memory)
        )


    with c4:

        st.metric(
            "История",
            len(faj_core.passport.history)
        )



st.divider()



# ==================================================
# TABS
# ==================================================

tab1, tab2, tab3 = st.tabs(
    [
        "⚽ Анализ матча",
        "🧬 Learning Cycle",
        "📚 Память FAJ"
    ]
)



# ==================================================
# MATCH ANALYSIS
# ==================================================

with tab1:


    st.subheader(
        "Анализ матча"
    )


    teams = sorted(
        [
            item["team"]
            for item in db.passports
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
        width="stretch"
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


            st.subheader(
                "Результат FAJ"
            )


            c1, c2, c3 = st.columns(3)


            with c1:

                st.metric(
                    "xG хозяев",
                    prediction.get(
                        "xg_home",
                        "-"
                    )
                )


            with c2:

                st.metric(
                    "xG гостей",
                    prediction.get(
                        "xg_away",
                        "-"
                    )
                )


            with c3:

                st.metric(
                    "Исход",
                    prediction.get(
                        "result",
                        "-"
                    )
                )



            st.success(
                f"Прогноз счёта: "
                f"{prediction.get('score_prediction','-')}"
            )


            st.info(
                f"Модель: "
                f"{prediction.get('model','FAJ Engine')}"
            )



# ==================================================
# LEARNING CYCLE
# ==================================================

with tab2:


    st.subheader(
        "🧬 Learning Cycle FAJ"
    )


    st.write(
        """
Цикл обучения:

1. Получение результатов тура
2. Сравнение FAJ Prediction и факта
3. Анализ ошибок
4. Запись памяти
5. История паспортов
6. Подготовка к калибровке
        """
    )


    round_number = st.number_input(
        "Номер тура",
        min_value=1,
        value=1
    )



    if st.button(
        "🚀 Обработать тур",
        width="stretch"
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
# MEMORY
# ==================================================

with tab3:


    st.subheader(
        "📚 Память FAJ"
    )


    memory = faj_core.memory.memory



    if len(memory) == 0:


        st.warning(
            "Память пока пустая"
        )


    else:


        memory_view = memory.copy()


        # исправление Arrow ошибки Streamlit

        for column in memory_view.columns:

            memory_view[column] = (
                memory_view[column]
                .astype(str)
            )


        st.dataframe(
            memory_view,
            width="stretch"
        )

# -*- coding: utf-8 -*-

"""
FAJ Platform 9.1.1

Football Analytics Journal

Adaptive Football Intelligence

Modules:

- Database
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
    page_title="FAJ Platform 9.1.1",
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


    core = FAJCore()


    loader = RoundLoader()


    return (
        db,
        engine,
        predictor,
        core,
        loader
    )



db, engine, predictor, core, loader = load_system()



# ==================================================
# HEADER
# ==================================================

st.title(
    "⚽ FAJ Platform 9.1.1"
)


st.caption(
    "Football Analytics Journal — Adaptive Football Intelligence"
)


st.divider()



# ==================================================
# STATUS
# ==================================================

with st.expander(
    "🧠 Состояние FAJ",
    expanded=True
):


    c1,c2,c3,c4 = st.columns(4)


    with c1:

        st.metric(
            "Версия",
            core.version
        )


    with c2:

        st.metric(
            "Команды",
            len(db.passports)
        )


    with c3:

        st.metric(
            "Память",
            len(core.memory.memory)
        )


    with c4:

        st.metric(
            "Паспорта",
            len(core.passport.passports)
        )



st.divider()



# ==================================================
# TABS
# ==================================================

tab1, tab2, tab3 = st.tabs(
    [
        "⚽ Матч",
        "🧬 Learning Cycle",
        "📚 Память FAJ"
    ]
)



# ==================================================
# MATCH
# ==================================================

with tab1:


    st.subheader(
        "Анализ матча"
    )


    teams = sorted(
        [
            x["team"]
            for x in db.passports
        ]
    )


    col1,col2 = st.columns(2)


    with col1:

        home = st.selectbox(
            "Хозяева",
            teams
        )


    with col2:

        away = st.selectbox(
            "Гости",
            teams,
            index=1
        )


    if st.button(
        "🔮 Анализировать",
        width="stretch"
    ):


        result = predictor.predict_result(
            home,
            away
        )


        if result:


            st.success(
                "FAJ расчёт завершён"
            )


            st.json(
                result
            )


        else:

            st.error(
                "Нет данных"
            )



# ==================================================
# LEARNING CYCLE
# ==================================================

with tab2:


    st.subheader(
        "🧬 Learning Cycle"
    )


    st.write(
        """
FAJ цикл:

Матч
↓
Прогноз
↓
Факт
↓
Ошибка
↓
Память
↓
Калибровка
↓
Обновление паспорта
        """
    )


    round_number = st.number_input(
        "Тур",
        min_value=1,
        value=1
    )


    if st.button(
        "🚀 Обработать тур",
        width="stretch"
    ):


        try:

            data = loader.load_round(
                int(round_number)
            )


            core.process_round(
                int(round_number),
                data
            )


            st.success(
                f"Тур {round_number} обработан"
            )


            st.info(
                f"Матчей: {len(data)}"
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


    memory = core.memory.memory


    if len(memory)==0:


        st.warning(
            "Память пустая"
        )


    else:


        view = memory.copy()


        for col in view.columns:

            view[col] = (
                view[col]
                .fillna("")
                .astype(str)
            )


        st.dataframe(
            view,
            width="stretch"
        )

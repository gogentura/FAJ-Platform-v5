#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0

Football Analytics Journal
Adaptive Football Intelligence

Streamlit Professional Interface

Русский интерфейс
"""

import streamlit as st
import pandas as pd


from app.faj_core import FAJCore


# ==================================================
# CONFIG
# ==================================================

st.set_page_config(
    page_title="FAJ Platform 10.0",
    page_icon="⚽",
    layout="wide"
)


# ==================================================
# CORE
# ==================================================

@st.cache_resource
def load_core():

    return FAJCore()


core = load_core()


status = core.status()

if status is None:
    status = {
        "version": "10.0",
        "teams": 0,
        "memory": 0,
        "passports": 0,
        "model_events": 0,
        "team_events": 0,
        "system_events": 0
    }



passport = getattr(
    core,
    "passport",
    None
)


teams = []


if passport and hasattr(passport, "passports"):

    for item in passport.passports:

        if isinstance(item, dict):

            name = item.get("team")

            if name:
                teams.append(name)



teams = sorted(
    list(set(teams))
)



# ==================================================
# HEADER
# ==================================================

st.title(
    "⚽ FAJ Platform 10.0"
)


st.subheader(
    "Football Analytics Journal"
)


st.caption(
    "Adaptive Football Intelligence"
)



# ==================================================
# TOP NAVIGATION
# ==================================================

page = st.radio(

    "",

    [
        "🏟 Центр матчей",
        "👥 Команды",
        "🔮 Прогнозы",
        "🧠 Обучение",
        "📜 Журнал",
        "⚙️ Система"
    ],

    horizontal=True

)



st.divider()



# ==================================================
# DASHBOARD
# ==================================================

c1, c2, c3, c4 = st.columns(4)



with c1:

    st.metric(
        "Команды",
        status.get(
            "teams",
            0
        )
    )


with c2:

    st.metric(
        "Паспорта",
        status.get(
            "passports",
            0
        )
    )


with c3:

    st.metric(
        "Память",
        status.get(
            "memory",
            0
        )
    )


with c4:

    st.metric(
        "Версия",
        status.get(
            "version",
            "10.0"
        )
    )



st.divider()



# ==================================================
# MATCH CENTER
# ==================================================

if page == "🏟 Центр матчей":


    st.header(
        "🏟 Центр матчей"
    )


    if not teams:


        teams = [
            "Зенит",
            "Спартак",
            "ЦСКА",
            "Динамо М",
            "Краснодар",
            "Локомотив"
        ]



    col1, col2 = st.columns(2)



    with col1:

        home = st.selectbox(

            "Домашняя команда",

            teams

        )


    with col2:

        away = st.selectbox(

            "Гостевая команда",

            [

                x for x in teams

                if x != home

            ]

        )



    st.write("")



    if st.button(

        "🔮 Рассчитать прогноз",

        use_container_width=True

    ):


        st.info(

            f"""

Матч:

**{home} — {away}**


Цикл анализа:

FAJ Core

↓

xG Engine

↓

Poisson

↓

Expert Layer

↓

Prediction


"""

        )


        st.warning(

            "Модуль прогнозирования подключается"

        )



        st.subheader(
            "Вероятности"
        )


        st.progress(
            0
        )


        st.write(
            "Победа хозяев — ожидание расчёта"
        )


        st.write(
            "Ничья — ожидание расчёта"
        )


        st.write(
            "Победа гостей — ожидание расчёта"
        )



        st.subheader(
            "Ожидаемый xG"
        )


        colx1, colx2 = st.columns(2)


        with colx1:

            st.metric(
                home,
                "-"
            )


        with colx2:

            st.metric(
                away,
                "-"
            )


        st.subheader(
            "Вероятные счета"
        )


        st.write(
            "Poisson модуль не подключен"
        )



# ==================================================
# TEAMS
# ==================================================

elif page == "👥 Команды":


    st.header(
        "👥 Команды FAJ"
    )


    if not teams:

        st.warning(
            "Паспорта команд не найдены"
        )


    else:


        selected = st.selectbox(

            "Выберите команду",

            teams

        )


        data = None



        for item in passport.passports:


            if (

                isinstance(item, dict)

                and

                item.get("team") == selected

            ):

                data = item



        if data:


            col1,col2,col3 = st.columns(3)


            with col1:

                st.metric(
                    "Атака",
                    data.get(
                        "attack",
                        "-"
                    )
                )


            with col2:

                st.metric(
                    "Защита",
                    data.get(
                        "defense",
                        "-"
                    )
                )


            with col3:

                st.metric(
                    "Форма",
                    data.get(
                        "form",
                        "-"
                    )
                )


            with st.expander(
                "Полный паспорт"
            ):


                st.dataframe(

                    pd.DataFrame(
                        [data]
                    ),

                    use_container_width=True

                )



# ==================================================
# PREDICTIONS
# ==================================================

elif page == "🔮 Прогнозы":


    st.header(
        "🔮 История прогнозов"
    )


    st.info(
        "История прогнозов появится после подключения Prediction Engine"
    )



# ==================================================
# LEARNING
# ==================================================

elif page == "🧠 Обучение":


    st.header(
        "🧠 Learning Center"
    )


    st.metric(
        "Ошибки модели",
        status.get(
            "model_events",
            0
        )
    )


    st.info(
        "Learning Engine подключается"
    )



# ==================================================
# JOURNAL
# ==================================================

elif page == "📜 Журнал":


    st.header(
        "📜 Журнал модели"
    )


    st.info(
        "История версий FAJ появится здесь"
    )



# ==================================================
# SYSTEM
# ==================================================

elif page == "⚙️ Система":


    st.header(
        "⚙️ Состояние системы"
    )


    st.json(

        {

            "Версия": status.get(
                "version"
            ),

            "Команды": status.get(
                "teams"
            ),

            "Паспорта": status.get(
                "passports"
            ),

            "Память": status.get(
                "memory"
            ),

            "Ошибки модели": status.get(
                "model_events"
            )

        }

    )



st.divider()


st.caption(
    "FAJ Platform 10.0 | Adaptive Football Intelligence"
)

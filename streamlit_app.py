#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.7.1

Football Analytics Journal
Adaptive Football Intelligence

Streamlit Interface

"""


import streamlit as st
import pandas as pd


from app.faj_core import FAJCore
from app.passport_updater import PassportUpdater



# ======================================
# CONFIG
# ======================================


st.set_page_config(

    page_title="FAJ Platform",

    page_icon="⚽",

    layout="wide"

)



# ======================================
# INIT
# ======================================


@st.cache_resource
def load_core():

    return FAJCore()



core = load_core()



passport = core.passport



status = core.status()



# ======================================
# HEADER
# ======================================


st.title(
    "⚽ FAJ Platform 9.3.1"
)


st.caption(
    "Football Analytics Journal — Adaptive Football Intelligence"
)



# ======================================
# STATUS BLOCK
# ======================================


col1, col2, col3, col4 = st.columns(4)



with col1:

    st.metric(

        "Версия",

        status.get(
            "version",
            "9.3.1"

        )

    )



with col2:

    st.metric(

        "Команды",

        status.get(
            "teams",
            0

        )

    )



with col3:

    st.metric(

        "Память",

        status.get(
            "memory",
            0

        )

    )



with col4:

    st.metric(

        "Паспорта",

        status.get(
            "passports",
            0

        )

    )



st.divider()



# ======================================
# TEAM SELECT
# ======================================


st.subheader(
    "⚽ Выбор команды"
)



teams = []



if hasattr(
    passport,
    "passports"
):


    for item in passport.passports:


        if isinstance(
            item,
            dict
        ):


            name = item.get(
                "team"
            )


            if name:

                teams.append(
                    name
                )



teams = sorted(
    list(
        set(
            teams
        )
    )
)



if not teams:


    teams = [

        "Зенит",

        "Спартак",

        "ЦСКА",

        "Динамо М"

    ]



selected_team = st.selectbox(

    "Команда",

    teams

)



# ======================================
# PASSPORT
# ======================================


st.divider()


st.subheader(

    f"📘 FAJ Passport — {selected_team}"

)



team_data = None



for item in passport.passports:


    if isinstance(
        item,
        dict
    ):


        if item.get(
            "team"
        ) == selected_team:


            team_data = item



if team_data:


    c1,c2,c3 = st.columns(3)


    with c1:

        st.metric(

            "Атака",

            team_data.get(
                "attack",
                "-"
            )

        )


    with c2:

        st.metric(

            "Защита",

            team_data.get(
                "defense",
                "-"
            )

        )


    with c3:

        st.metric(

            "Форма",

            team_data.get(
                "form",
                "-"
            )

        )



    with st.expander(
        "Полный паспорт"
    ):


        df = pd.DataFrame(

            [

                team_data

            ]

        )


        st.dataframe(

            df,

            width="stretch"

        )



else:


    st.warning(

        "Паспорт команды не найден"

    )



# ======================================
# PREDICTION
# ======================================


st.divider()


st.subheader(
    "🔮 FAJ Prediction Engine"
)



home = selected_team



away = st.selectbox(

    "Соперник",

    [

        x for x in teams

        if x != home

    ]

)



if st.button(

    "Рассчитать прогноз",

    type="primary"

):


    st.success(

        "FAJ Engine запущен"

    )


    st.info(

        f"""
Матч:

{home} — {away}


Цикл:

FAJ Core

↓

xG Engine

↓

Poisson Model

↓

Expert Layer

"""

    )



    # временный результат

    st.metric(

        "Ожидаемый исход",

        "Расчётный модуль подключается"

    )



# ======================================
# MEMORY
# ======================================


st.divider()


st.subheader(

    "🧠 Learning Memory"

)



memory_count = status.get(

    "memory",

    0

)



st.write(

    f"""

Записей памяти FAJ:

**{memory_count}**

"""

)



# ======================================
# EVENTS
# ======================================


st.subheader(

    "📊 Системные события"

)



e1,e2,e3 = st.columns(3)



with e1:

    st.metric(

        "Ошибки модели",

        status.get(

            "model_events",

            0

        )

    )


with e2:

    st.metric(

        "Командные события",

        status.get(

            "team_events",

            0

        )

    )


with e3:

    st.metric(

        "Система",

        status.get(

            "system_events",

            0

        )

    )



st.divider()



st.caption(

    "FAJ Platform 9.3.1 | Adaptive Football Intelligence"

)

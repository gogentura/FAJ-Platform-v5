#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.5

Football Analytics Journal
Adaptive Football Intelligence

Главный интерфейс платформы.

Цикл:

Команда
↓
Паспорт
↓
Матч
↓
FAJ Core
↓
Прогноз
↓
Memory Engine

"""


import streamlit as st
import pandas as pd


from app.faj_core import FAJCore
from app.passport_updater import PassportUpdater
from app.memory_engine import MemoryEngine



# ==================================================
# CONFIG
# ==================================================


st.set_page_config(

    page_title="FAJ Platform 9.5",

    page_icon="⚽",

    layout="wide"

)



# ==================================================
# STYLE
# ==================================================


st.markdown(
"""
<style>

body {
    background-color:#ffffff;
}

.main-title {

    text-align:center;
    font-size:38px;
    font-weight:700;

}

.subtitle {

    text-align:center;
    color:#666;
    font-size:18px;

}


.card {

    padding:20px;

    border-radius:15px;

    border:1px solid #ddd;

    background:#fafafa;

}


</style>

""",
unsafe_allow_html=True
)



# ==================================================
# INIT
# ==================================================


@st.cache_resource
def load_system():

    return {

        "core": FAJCore(),

        "passport": PassportUpdater(),

        "memory": MemoryEngine()

    }



system = load_system()


core = system["core"]

passport = system["passport"]

memory = system["memory"]



# ==================================================
# HEADER
# ==================================================


st.markdown(

"""
<div class="main-title">
⚽ FAJ Platform 9.5
</div>

<div class="subtitle">
Football Analytics Journal — Adaptive Football Intelligence
</div>

""",

unsafe_allow_html=True

)


st.write("")



# ==================================================
# MENU
# ==================================================


page = st.radio(

    "",

    [

        "🏠 Главная",

        "⚽ Матч",

        "🏆 Тур",

        "📖 Паспорта",

        "🧠 Память"

    ],

    horizontal=True

)



# ==================================================
# HELPERS
# ==================================================


def get_passport(team):

    """
    Безопасное получение паспорта.
    Поддерживает список и словарь.
    """

    data = passport.passports


    if isinstance(data, dict):

        return data.get(team)


    if isinstance(data, list):

        for item in data:

            if isinstance(item, dict):

                if item.get("team") == team:

                    return item


    return None




def value(data,key):

    if not data:

        return 0

    return data.get(key,0)



# ==================================================
# HOME
# ==================================================


if page=="🏠 Главная":


    col1,col2,col3,col4 = st.columns(4)


    with col1:

        st.metric(

            "Версия",

            "9.5"

        )


    with col2:

        st.metric(

            "Команды",

            len(passport.passports)

        )


    with col3:

        st.metric(

            "Память",

            len(memory.memory)

        )


    with col4:

        st.metric(

            "Паспорта",

            len(passport.passports)

        )



    st.divider()


    st.markdown(

    """
    ## FAJ Intelligence Cycle


    ⚽ Анализ матча

    ↓

    📊 Расчёт вероятностей

    ↓

    🔮 Прогноз

    ↓

    🧠 Обучение на результате

    ↓

    📖 Обновление паспортов

    """

    )



# ==================================================
# MATCH
# ==================================================


elif page=="⚽ Матч":


    st.header(
        "⚽ FAJ Match Analyzer"
    )


    teams=[]


    for p in passport.passports:


        if isinstance(p,dict):

            teams.append(
                p.get("team")
            )


    teams=[x for x in teams if x]


    col1,col2=st.columns(2)


    with col1:

        home=st.selectbox(

            "Домашняя команда",

            teams

        )


    with col2:

        away=st.selectbox(

            "Гостевая команда",

            teams,

            index=1

        )



    st.divider()



    c1,c2=st.columns(2)



    with c1:

        st.subheader(home)

        hp=get_passport(home)

        st.write(

            "Атака:",
            value(hp,"attack")

        )

        st.write(

            "Защита:",
            value(hp,"defense")

        )

        st.write(

            "Форма:",
            value(hp,"form")

        )



    with c2:

        st.subheader(away)

        ap=get_passport(away)

        st.write(

            "Атака:",
            value(ap,"attack")

        )

        st.write(

            "Защита:",
            value(ap,"defense")

        )

        st.write(

            "Форма:",
            value(ap,"form")

        )



    st.divider()



    if st.button(
        "🔮 Рассчитать прогноз",
        use_container_width=True
    ):


        st.success(
            "FAJ Engine запущен"
        )


        st.info(

        """
        Модуль прогнозирования подключается через FAJ Core.

        Следующий этап:
        xG Engine + Poisson + Expert Layer

        """

        )



# ==================================================
# ROUND
# ==================================================


elif page=="🏆 Тур":


    st.header(
        "🏆 Анализ тура"
    )


    st.write(

        "Последний обработанный тур"

    )


    st.metric(

        "Матчей",

        8

    )


    st.metric(

        "Точность",

        "2 / 8"

    )



# ==================================================
# PASSPORTS
# ==================================================


elif page=="📖 Паспорта":


    st.header(

        "📖 FAJ Team Passports"

    )


    teams=[]


    for p in passport.passports:

        if isinstance(p,dict):

            teams.append(
                p.get("team")
            )


    team=st.selectbox(

        "Выберите команду",

        teams

    )


    data=get_passport(team)



    if data:


        st.subheader(team)


        st.write(

            "Атака:",

            value(data,"attack")

        )


        st.write(

            "Защита:",

            value(data,"defense")

        )


        st.write(

            "Форма:",

            value(data,"form")

        )


    else:

        st.warning(

            "Паспорт не найден"

        )



# ==================================================
# MEMORY
# ==================================================


elif page=="🧠 Память":


    st.header(

        "🧠 FAJ Learning Memory"

    )


    if memory.memory:


        df=pd.DataFrame(

            memory.memory

        )


        st.dataframe(

            df,

            use_container_width=True

        )


    else:

        st.info(

            "Память пуста"

        )

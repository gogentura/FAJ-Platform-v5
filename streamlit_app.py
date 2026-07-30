#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.4

Football Analytics Journal
Adaptive Football Intelligence

Dashboard Edition
"""


import streamlit as st
import pandas as pd
from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater



# ==================================
# CONFIG
# ==================================

VERSION = "9.4"


st.set_page_config(
    page_title="FAJ Platform 9.4",
    page_icon="⚽",
    layout="wide"
)



# ==================================
# LIGHT STYLE
# ==================================

st.markdown(
"""
<style>

.stApp {
    background:white;
}

h1,h2,h3 {
    color:#0f172a;
}


[data-testid="stSidebar"] {
    background:#f8fafc;
}


</style>

""",
unsafe_allow_html=True
)



# ==================================
# LOAD DATA
# ==================================


memory = MemoryEngine()

passport = PassportUpdater()



# ==================================
# TEAM LIST
# ==================================


teams = [

    "Зенит",
    "Спартак",
    "ЦСКА",
    "Динамо М",
    "Локомотив",
    "Краснодар",
    "Ростов",
    "Ахмат",
    "Рубин",
    "Крылья Советов",
    "Факел",
    "Оренбург",
    "Балтика",
    "Акрон",
    "Динамо Мх",
    "Родина"

]



# ==================================
# SIDEBAR
# ==================================


st.sidebar.title(
    "⚽ FAJ MENU"
)



section = st.sidebar.radio(
    "Раздел",
    [

        "🏠 Главная",

        "⚽ Команды",

        "📊 Тур РПЛ",

        "🧠 Память FAJ",

        "📖 Паспорта",

        "🔄 Калибровка",

        "📈 Статистика модели"

    ]
)



# ==================================
# HEADER
# ==================================


st.title(
    "⚽ FAJ Platform 9.4"
)


st.caption(
    "Football Analytics Journal — Adaptive Football Intelligence"
)



st.divider()



# ==================================
# HOME
# ==================================


if section == "🏠 Главная":


    st.header(
        "📌 Состояние системы"
    )


    c1,c2,c3,c4 = st.columns(4)



    with c1:

        st.metric(
            "Версия",
            VERSION
        )


    with c2:

        st.metric(
            "Команды",
            len(passport.passports)
        )


    with c3:

        try:

            count = len(
                memory.memory
            )

        except:

            count = 0


        st.metric(
            "Память",
            count
        )


    with c4:

        st.metric(
            "Паспорта",
            len(passport.passports)
        )



    st.divider()


    st.header(
        "🧠 Learning Cycle"
    )


    st.info(
"""
Матч

⬇

FAJ Prediction

⬇

Факт

⬇

Ошибка

⬇

Memory Engine

⬇

Calibration

⬇

Passport Update
"""
    )



# ==================================
# TEAMS
# ==================================


elif section == "⚽ Команды":


    st.header(
        "⚽ Командный анализ FAJ"
    )


    team = st.selectbox(
        "Выберите команду",
        teams
    )


    st.subheader(
        team
    )



    st.write(
        "FAJ Passport"
    )


    try:


        data = passport.passports.get(
            team
        )


        if data:

            st.json(
                data
            )

        else:

            st.warning(
                "Паспорт команды пока не найден"
            )


    except Exception as e:

        st.error(e)



# ==================================
# MEMORY
# ==================================


elif section == "🧠 Память FAJ":


    st.header(
        "🧠 Memory Engine"
    )


    try:

        df = pd.DataFrame(
            memory.memory
        )


        if not df.empty:


            if "version" in df.columns:

                df["version"] = (
                    df["version"]
                    .astype(str)
                )


            st.dataframe(
                df,
                use_container_width=True
            )


        else:

            st.warning(
                "Память пустая"
            )


    except Exception as e:

        st.error(e)



# ==================================
# PASSPORTS
# ==================================


elif section == "📖 Паспорта":


    st.header(
        "📖 База паспортов"
    )


    try:

        df = pd.DataFrame(
            passport.passports
        )


        st.dataframe(
            df,
            use_container_width=True
        )


    except Exception as e:

        st.error(e)



# ==================================
# ROUND
# ==================================


elif section == "📊 Тур РПЛ":


    st.header(
        "📊 Анализ тура"
    )


    st.info(
        """
        Последний обработанный тур:

        РПЛ Тур 1

        Матчей: 8

        Основной вывод:

        FAJ переоценил ничьи.
        """
    )



# ==================================
# CALIBRATION
# ==================================


elif section == "🔄 Калибровка":


    st.header(
        "🔄 Calibration Engine"
    )


    st.write(
"""
Активные направления:

- снижение веса ничьих
- усиление формы
- корректировка Home Advantage
- учет красных карточек
"""
)



# ==================================
# STATS
# ==================================


elif section == "📈 Статистика модели":


    st.header(
        "📈 FAJ Model Statistics"
    )


    st.metric(
        "Последний тур",
        "2 / 8"
    )


    st.metric(
        "Ошибок",
        "6"
    )



# ==================================
# FOOTER
# ==================================


st.divider()


st.caption(
f"""
FAJ Platform {VERSION}

Последнее обновление:
{datetime.now().strftime("%d.%m.%Y %H:%M")}
"""
)

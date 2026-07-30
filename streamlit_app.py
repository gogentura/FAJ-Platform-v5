#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.7

Streamlit Interface

Football Analytics Journal
Adaptive Football Intelligence

"""


import streamlit as st


from app.faj_core import FAJCore



# ==================================================
# CONFIG
# ==================================================


st.set_page_config(

    page_title="FAJ Platform",

    page_icon="⚽",

    layout="wide"

)



# ==================================================
# STYLE
# ==================================================


st.markdown(

"""
<style>

.main {

    background-color: #ffffff;

}


.block-container {

    padding-top:2rem;

}


.faj-card {

    background:#f5f7fa;

    padding:20px;

    border-radius:12px;

    margin-top:15px;

}


.center {

    text-align:center;

}

</style>

""",

unsafe_allow_html=True

)



# ==================================================
# INIT
# ==================================================


@st.cache_resource

def load_core():

    return FAJCore()



core = load_core()



# ==================================================
# TRANSLATION
# ==================================================


TRANSLATE = {


"attack":"Атака",

"defense":"Защита",

"control":"Контроль",

"efficiency":"Эффективность",

"mentality":"Ментальность",

"tempo":"Темп",

"press":"Прессинг",

"predictability":"Предсказуемость",

"flexibility":"Гибкость",

"home_power":"Домашняя сила",

"coach":"Тренер",

"form":"Форма",

"transfer_index":"Трансферы",

"depth":"Глубина состава",

"uncertainty":"Неопределенность"



}



# ==================================================
# HEADER
# ==================================================


st.title(

"⚽ FAJ Platform 9.7"

)


st.caption(

"Football Analytics Journal — Adaptive Football Intelligence"

)



# ==================================================
# STATUS
# ==================================================


status = core.status()



col1,col2,col3,col4 = st.columns(4)



with col1:

    st.metric(

        "Версия",

        status["version"]

    )


with col2:

    st.metric(

        "Команды",

        status["teams"]

    )


with col3:

    st.metric(

        "Память",

        status["memory"]

    )


with col4:

    st.metric(

        "Дата",

        status["date"]

    )



st.divider()



# ==================================================
# TEAM SELECT
# ==================================================


st.subheader(

"🎯 Выбор матча"

)



teams=[]



for team in core.passport.passports:


    if isinstance(team,dict):

        name = team.get("team")

        if name:

            teams.append(name)



teams = sorted(teams)



col1,col2 = st.columns(2)



with col1:


    home = st.selectbox(

        "🏠 Хозяева",

        teams

    )


with col2:


    away = st.selectbox(

        "✈️ Гости",

        teams,

        index=1

    )



# ==================================================
# PASSPORT DISPLAY
# ==================================================


def show_passport(team_name):


    passport = core.get_team(
        team_name
    )


    if passport is None:

        st.warning(

            "Паспорт не найден"

        )

        return



    st.markdown(

    f"""

    <div class="faj-card">

    <h3>📘 FAJ Passport — {team_name}</h3>

    </div>

    """,

    unsafe_allow_html=True

    )


    cols = st.columns(3)



    count=0


    for key,value in passport.items():


        if key=="team":

            continue



        title = TRANSLATE.get(

            key,

            key

        )


        cols[count%3].metric(

            title,

            value

        )


        count+=1





# ==================================================
# PASSPORT BUTTONS
# ==================================================


with st.expander(

"📘 Паспорт хозяев"

):

    show_passport(home)



with st.expander(

"📘 Паспорт гостей"

):

    show_passport(away)



st.divider()



# ==================================================
# PREDICT
# ==================================================


st.markdown(

"""

<div class="center">

<h2>🤖 FAJ Engine</h2>

</div>

""",

unsafe_allow_html=True

)



if st.button(

"⚡ Рассчитать прогноз",

use_container_width=True

):


    with st.spinner(

        "FAJ Core → xG → Poisson → Expert Layer"

    ):


        prediction = core.predict_match(

            home,

            away

        )



    st.success(

        "Прогноз рассчитан"

    )



    st.markdown(

    """

    <div class="faj-card">

    <h3>⚽ FAJ Prediction</h3>

    </div>

    """,

    unsafe_allow_html=True

    )



    st.write(

        "Матч:",

        prediction["match"]

    )



    # xG


    c1,c2 = st.columns(2)



    with c1:

        st.metric(

            "xG хозяева",

            prediction["xG"]["home"]

        )


    with c2:

        st.metric(

            "xG гости",

            prediction["xG"]["away"]

        )



    st.subheader(

        "Вероятности"

    )


    st.json(

        prediction["probability"]

    )



    st.subheader(

        "Основной счет"

    )


    st.info(

        prediction["score"]["main"]

    )



    st.subheader(

        "Экспертный слой"

    )


    st.write(

        prediction["expert"]["comment"]

    )



# ==================================================
# FOOTER
# ==================================================


st.divider()


st.markdown(

"""

<div class="center">

FAJ Platform 9.7<br>

Adaptive Football Intelligence

</div>

""",

unsafe_allow_html=True

)

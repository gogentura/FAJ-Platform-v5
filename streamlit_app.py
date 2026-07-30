# -*- coding: utf-8 -*-

"""
FAJ Platform v9.6

Football Analytics Journal
Adaptive Football Intelligence

UI Recovery Version

"""


import streamlit as st
import pandas as pd
import os


from app.passport_updater import PassportUpdater


# ==========================================
# CONFIG
# ==========================================

st.set_page_config(
    page_title="FAJ Platform",
    page_icon="⚽",
    layout="wide"
)


# ==========================================
# STYLE
# ==========================================

st.markdown(
"""
<style>

.main-title {
    text-align:center;
    font-size:34px;
    font-weight:700;
}

.subtitle {
    text-align:center;
    color:#777;
    font-size:18px;
}

.menu {
    display:flex;
    justify-content:center;
    gap:20px;
}

</style>
""",
unsafe_allow_html=True
)



# ==========================================
# LOAD PASSPORTS
# ==========================================


@st.cache_data
def load_passports():

    updater = PassportUpdater()

    return updater.passports



passports = load_passports()



teams = sorted(
    [
        x.get("team")
        for x in passports
        if x.get("team")
    ]
)



# ==========================================
# HEADER
# ==========================================


st.markdown(
"""
<div class="main-title">
⚽ FAJ Platform 9.6
</div>

<div class="subtitle">
Football Analytics Journal — Adaptive Football Intelligence
</div>
""",
unsafe_allow_html=True
)



st.divider()



# ==========================================
# CENTER MENU
# ==========================================


menu = st.radio(

    "",

    [
        "🏠 Главная",
        "⚽ Матч",
        "🏟 Команды",
        "🧠 Память"
    ],

    horizontal=True

)



st.divider()



# ==========================================
# HOME
# ==========================================


if menu == "🏠 Главная":


    st.subheader(
        "📊 Состояние FAJ"
    )


    col1,col2,col3,col4 = st.columns(4)


    col1.metric(
        "Версия",
        "9.6"
    )


    col2.metric(
        "Команды",
        len(teams)
    )


    col3.metric(
        "Паспорта",
        len(passports)
    )


    memory_count = 0


    if os.path.exists(
        "data/faj_memory.csv"
    ):

        try:

            df = pd.read_csv(
                "data/faj_memory.csv"
            )

            memory_count=len(df)

        except:

            pass



    col4.metric(
        "Память",
        memory_count
    )



    st.info(
        """
FAJ Engine готов.

Следующий этап:
xG Engine
Poisson Model
Expert Layer

"""
    )




# ==========================================
# TEAM PASSPORT
# ==========================================


elif menu == "🏟 Команды":


    st.subheader(
        "🏟 FAJ Passport команды"
    )


    team_name = st.selectbox(

        "Выберите команду",

        teams

    )



    team = None


    for t in passports:

        if t.get("team") == team_name:

            team=t
            break



    if team:


        st.success(
            team_name
        )


        c1,c2,c3 = st.columns(3)



        c1.metric(
            "Атака",
            team.get(
                "attack",
                "-"
            )
        )


        c2.metric(
            "Защита",
            team.get(
                "defense",
                "-"
            )
        )


        c3.metric(
            "Форма",
            team.get(
                "form",
                "-"
            )
        )



        st.json(
            team
        )



# ==========================================
# MATCH
# ==========================================


elif menu == "⚽ Матч":


    st.subheader(
        "⚽ FAJ Match Analyzer"
    )



    home = st.selectbox(

        "Домашняя команда",

        teams,

        index=0

    )



    away = st.selectbox(

        "Гостевая команда",

        teams,

        index=min(
            1,
            len(teams)-1
        )

    )



    if st.button(
        "🔮 Рассчитать FAJ прогноз"
    ):


        st.warning(
            """
Модуль прогноза подключается.

FAJ Core → xG → Poisson → Expert Layer

"""
        )


        st.write(
            "Матч:",
            home,
            "-",
            away
        )




# ==========================================
# MEMORY
# ==========================================


elif menu == "🧠 Память":


    st.subheader(
        "🧠 FAJ Learning Memory"
    )


    files = [

        "data/faj_memory.csv",

        "data/passport_history_v9.csv"

    ]


    loaded=False



    for file in files:


        if os.path.exists(file):


            try:

                df=pd.read_csv(file)


                st.dataframe(
                    df,
                    use_container_width=True
                )


                loaded=True


                break


            except Exception as e:


                st.error(
                    str(e)
                )



    if not loaded:


        st.info(
            "Память пока пуста"
        )



st.divider()


st.caption(
    "FAJ Platform 9.6 — UI Recovery"
)

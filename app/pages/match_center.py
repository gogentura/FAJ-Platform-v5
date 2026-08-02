#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Match Center

Центр прогнозирования матчей
Связь:
Passport → FAJ Engine → Memory Brain
"""

import streamlit as st
import pandas as pd
import json
import os


DATA_DIR = "data"


# =====================================================
# ЗАГРУЗКА JSON
# =====================================================

def load_json(filename):

    path = os.path.join(
        DATA_DIR,
        filename
    )

    if not os.path.exists(path):
        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return {}



# =====================================================
# ПАСПОРТА
# =====================================================

def get_team_passport(team_name):

    passports = load_json(
        "passports_2026.json"
    )

    return passports.get(
        team_name.strip(),
        {}
    )



# =====================================================
# ИСХОД
# =====================================================

def get_outcome(score):

    if not score or ":" not in score:
        return None

    try:

        h,a = map(
            int,
            score.split(":")
        )

        if h>a:
            return "П1"

        elif h==a:
            return "X"

        else:
            return "П2"

    except:

        return None



# =====================================================
# ОСНОВНАЯ СТРАНИЦА
# =====================================================

def render():

    st.markdown(
        "## 🏟 Матч-центр FAJ v10.0"
    )


    tour = load_json(
        "tour2_predictions.json"
    )


    if not tour:

        st.warning(
            "Нет файла tour2_predictions.json"
        )

        return



    # =============================================
    # СПИСОК МАТЧЕЙ
    # =============================================

    st.markdown(
        "### 📊 Прогнозы тура"
    )


    rows=[]


    for match,data in tour.items():

        rows.append({

            "Матч":
                match,

            "FAJ":
                data.get(
                    "faj",
                    "-"
                ),

            "Эксперт":
                data.get(
                    "expert",
                    "-"
                )

        })


    df=pd.DataFrame(rows)


    st.dataframe(
        df,
        width="stretch",
        hide_index=True
    )



    st.divider()



    # =============================================
    # ВЫБОР МАТЧА
    # =============================================

    selected = st.selectbox(

        "Выберите матч",

        list(tour.keys())

    )



    if not selected:
        return



    if "-" in selected:

        home,away = selected.split("-",1)

    else:

        home,away = selected.split("–",1)



    home=home.strip()
    away=away.strip()



    st.markdown(
        f"## ⚔️ {home} — {away}"
    )



    home_passport=get_team_passport(home)

    away_passport=get_team_passport(away)



    if not home_passport or not away_passport:

        st.error(
            "Нет паспорта одной из команд"
        )

        return



    # =============================================
    # ENGINE
    # =============================================

    from app.faj_match_engine import FAJMatchEngine


    engine=FAJMatchEngine()


    result=engine.predict_match(

        home_passport,

        away_passport

    )



    # DEBUG

    with st.expander(
        "🔧 DEBUG FAJ Engine"
    ):

        st.json(result)



    st.divider()



    # =============================================
    # ОСНОВНЫЕ ПОКАЗАТЕЛИ
    # =============================================


    c1,c2,c3=st.columns(3)


    with c1:

        st.metric(

            f"Победа {home}",

            f"{result.get('home_win',0)}%"

        )


    with c2:

        st.metric(

            "Ничья",

            f"{result.get('draw',0)}%"

        )


    with c3:

        st.metric(

            f"Победа {away}",

            f"{result.get('away_win',0)}%"

        )



    st.divider()



    # =============================================
    # СИЛА И xG
    # =============================================


    c1,c2=st.columns(2)



    with c1:

        st.metric(

            f"⚽ xG {home}",

            result.get(
                "xg_home",
                "-"
            )

        )


        st.metric(

            f"🏠 Сила {home}",

            result.get(
                "home_power",
                "-"
            )

        )



    with c2:


        st.metric(

            f"⚽ xG {away}",

            result.get(
                "xg_away",
                "-"
            )

        )


        st.metric(

            f"✈️ Сила {away}",

            result.get(
                "away_power",
                "-"
            )

        )



    st.divider()



    # =============================================
    # ДОПОЛНИТЕЛЬНЫЕ
    # =============================================


    c1,c2,c3,c4=st.columns(4)


    with c1:

        st.metric(

            "Уверенность",

            f"{result.get('confidence',0)}%"

        )


    with c2:

        st.metric(

            "Тотал >2.5",

            f"{result.get('over25',0)}%"

        )


    with c3:

        st.metric(

            "Обе забьют",

            f"{result.get('btts',0)}%"

        )


    with c4:

        st.metric(

            "Риск",

            result.get(
                "risk",
                "-"
            )

        )



    st.divider()



    # =============================================
    # ВЕРОЯТНЫЕ СЧЕТА
    # =============================================


    st.markdown(
        "### 🎯 Вероятные счета"
    )


    scores=result.get(
        "top_scores",
        []
    )


    if scores:

        st.dataframe(

            pd.DataFrame(scores),

            width="stretch",

            hide_index=True

        )



    # =============================================
    # СОХРАНЕНИЕ В ПАМЯТЬ
    # =============================================


    st.divider()


    if st.button(
        "🧠 Сохранить прогноз в память FAJ",
        width="stretch"
    ):

        from app.brain.memory_brain import FAJMemoryBrain


        memory=FAJMemoryBrain()


        memory.save_prediction(

            selected,

            result

        )


        st.success(
            "✅ Прогноз сохранён в faj_memory.json"
        )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Match Center

Центр прогнозирования:
- показывает матчи
- запускает FAJ Engine
- сохраняет прогнозы в память
"""

import streamlit as st
import pandas as pd
import json
import os


DATA_DIR = "data"



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



def get_team_passport(team):

    passports = load_json(
        "passports_2026.json"
    )

    return passports.get(
        team.strip(),
        {}
    )



def get_outcome(score):

    if not score:
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



def render():


    st.markdown(
        "## 🏟 Матч-центр FAJ"
    )


    from app.database import FAJDatabase
    from app.faj_match_engine import FAJMatchEngine
    from app.brain.memory_brain import FAJMemoryBrain


    db = FAJDatabase()


    memory = FAJMemoryBrain()


    engine = FAJMatchEngine()



    # ============================
    # ЗАГРУЗКА ТУРА
    # ============================


    tour = load_json(
        "tour2_predictions.json"
    )


    if not tour:

        st.warning(
            "Нет файла tour2_predictions.json"
        )

        return



    st.markdown(
        "### 📊 Прогнозы FAJ"
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


    st.dataframe(
        pd.DataFrame(rows),
        width="stretch"
    )



    st.divider()



    # ============================
    # ВЫБОР МАТЧА
    # ============================


    selected = st.selectbox(

        "Выберите матч",

        list(tour.keys())

    )


    if not selected:

        return



    if "-" in selected:

        home,away = selected.split(
            "-",
            1
        )

    else:

        home,away = selected.split(
            "–",
            1
        )


    home=home.strip()
    away=away.strip()



    st.markdown(
        f"## ⚔️ {home} — {away}"
    )



    home_passport = get_team_passport(
        home
    )

    away_passport = get_team_passport(
        away
    )



    if not home_passport or not away_passport:

        st.error(
            "Нет паспорта одной из команд"
        )

        st.write(
            home_passport
        )

        st.write(
            away_passport
        )

        return



    # ============================
    # ЗАПУСК ENGINE
    # ============================


    result = engine.predict_match(

        home_passport,

        away_passport

    )


    # DEBUG

    with st.expander(
        "🔧 DEBUG FAJ Engine"
    ):

        st.json(result)



    # ============================
    # БЕЗОПАСНЫЕ ЗНАЧЕНИЯ
    # ============================


    home_power = result.get(
        "home_power",
        0
    )


    away_power = result.get(
        "away_power",
        0
    )


    xg_home = result.get(
        "xg_home",
        0
    )


    xg_away = result.get(
        "xg_away",
        0
    )



    # ============================
    # ПОКАЗАТЕЛИ
    # ============================


    c1,c2,c3 = st.columns(3)


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



    c1,c2 = st.columns(2)


    with c1:

        st.metric(
            f"🏠 Сила {home}",
            home_power
        )

        st.metric(
            "xG хозяев",
            xg_home
        )


    with c2:

        st.metric(
            f"✈️ Сила {away}",
            away_power
        )

        st.metric(
            "xG гостей",
            xg_away
        )



    st.divider()



    c1,c2,c3 = st.columns(3)


    with c1:

        st.metric(
            "Уверенность",
            f"{result.get('confidence',0)}%"
        )


    with c2:

        st.metric(
            "Риск",
            result.get(
                "risk",
                "-"
            )
        )


    with c3:

        st.metric(
            "Обе забьют",
            f"{result.get('btts',0)}%"
        )



    st.markdown(
        "### 🎯 Вероятные счета"
    )


    scores = result.get(
        "top_scores",
        []
    )


    if scores:

        st.dataframe(
            pd.DataFrame(scores),
            width="stretch"
        )



    # ============================
    # СОХРАНЕНИЕ В ПАМЯТЬ
    # ============================


    if st.button(
        "🧠 Сохранить прогноз в память FAJ",
        width="stretch"
    ):


        memory.save_prediction(

            selected,

            result

        )


        st.success(
            "Прогноз сохранён. Создана запись в faj_memory.json"
        )

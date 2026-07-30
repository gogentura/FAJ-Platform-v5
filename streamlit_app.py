#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

Football Analytics Journal
Adaptive Football Intelligence

Streamlit Interface

"""


import streamlit as st
import pandas as pd
import os



from app.faj_core import FAJCore
from app.round_analyzer import RoundAnalyzer



st.set_page_config(

    page_title="FAJ Platform",

    page_icon="⚽",

    layout="wide"

)



# ==========================================
# HEADER
# ==========================================


st.title(
    "⚽ FAJ Platform 9.2"
)


st.subheader(
    "Football Analytics Journal — Adaptive Football Intelligence"
)



st.divider()



# ==========================================
# INIT
# ==========================================


@st.cache_resource

def load_engine():


    return FAJCore()



faj = load_engine()



# ==========================================
# STATUS
# ==========================================


col1, col2, col3, col4 = st.columns(4)



with col1:

    st.metric(

        "Версия",

        faj.version

    )


with col2:

    st.metric(

        "Команды",

        len(
            faj.passport.passports
        )

    )


with col3:

    st.metric(

        "Память",

        len(
            faj.memory.memory
        )

    )


with col4:

    st.metric(

        "Паспорта",

        len(
            faj.passport.passports
        )

    )



st.divider()



# ==========================================
# MENU
# ==========================================


tab1, tab2, tab3, tab4 = st.tabs(

    [

        "⚽ Анализ тура",

        "🧠 Learning Memory",

        "🛡 Паспорта",

        "📈 Calibration"

    ]

)



# ==========================================
# ROUND ANALYSIS
# ==========================================


with tab1:


    st.header(
        "Анализ тура"
    )



    if st.button(
        "▶ Обработать тур 1"
    ):


        predictions_path = (

            "data/rpl_round1_predictions.csv"

        )


        if os.path.exists(
            predictions_path
        ):


            df = pd.read_csv(
                predictions_path
            )


            matches = df.to_dict(
                "records"
            )



            analyzer = RoundAnalyzer()



            result = analyzer.analyze_round(

                1,

                matches

            )



            st.success(

                "Тур 1 успешно обработан"

            )



            st.write(

                f"Матчей: {result['total_matches']}"

            )


            st.write(

                f"Точность FAJ: {result['accuracy']}%"

            )



            st.session_state["round"] = result



        else:


            st.error(

                "Файл прогнозов не найден"

            )




    if "round" in st.session_state:


        data = st.session_state["round"]



        st.subheader(
            "Ошибки модели"
        )


        errors = pd.DataFrame(

            data["errors_list"]

        )


        if not errors.empty:


            st.dataframe(

                errors,

                use_container_width=True

            )



# ==========================================
# MEMORY
# ==========================================


with tab2:


    st.header(
        "🧠 Learning Memory"
    )



    memory = faj.memory.memory



    if memory:


        df_memory = pd.DataFrame(
            memory
        )



        # FIX ARROW ERROR

        if "version" in df_memory.columns:

            df_memory["version"] = (

                df_memory["version"]
                .astype(str)

            )



        st.dataframe(

            df_memory,

            use_container_width=True

        )


    else:


        st.info(

            "Память пуста"

        )



# ==========================================
# PASSPORTS
# ==========================================


with tab3:


    st.header(
        "🛡 Team Passports"
    )


    passports = pd.DataFrame(

        faj.passport.passports

    )


    if not passports.empty:


        st.dataframe(

            passports,

            use_container_width=True

        )



# ==========================================
# CALIBRATION
# ==========================================


with tab4:


    st.header(

        "📈 Calibration Queue"

    )


    st.info(

        "Ошибки FAJ передаются сюда для будущей калибровки"

    )



    memory_df = pd.DataFrame(

        faj.memory.memory

    )



    if not memory_df.empty:


        calibration = memory_df[

            memory_df["category"]
            .astype(str)
            .str.contains(
                "Error"
            )

        ]



        st.dataframe(

            calibration,

            use_container_width=True

        )

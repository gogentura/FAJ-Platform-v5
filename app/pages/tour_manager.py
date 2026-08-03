#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11
Tour Manager

Работа только через FAJDatabase

SQLite:
data/faj.db

Функции:
- сезоны
- туры
- матчи
"""

import streamlit as st
from app.database import FAJDatabase
from datetime import datetime


def render():

    st.title("🏟️ FAJ Season Center")

    db = FAJDatabase()


    # ================================
    # СОЗДАНИЕ ТУРА
    # ================================

    st.subheader("➕ Создать тур")


    season_name = st.text_input(
        "Название сезона",
        value="РПЛ 2026/27"
    )


    round_number = st.number_input(
        "Номер тура",
        min_value=1,
        step=1
    )


    if st.button(
        "Создать тур"
    ):

        try:

            db.create_round(
                season_name,
                int(round_number)
            )

            st.success(
                "Тур создан в базе"
            )

            st.rerun()


        except Exception as e:

            st.error(
                str(e)
            )



    st.divider()



    # ================================
    # СПИСОК ТУРОВ
    # ================================

    st.subheader(
        "📅 Туры FAJ"
    )


    rounds = db.get_rounds()


    if not rounds:

        st.info(
            "Туры пока не созданы"
        )

        return



    for r in rounds:

        st.write(
            f"⚽ {r}"
        )


    st.divider()



    # ================================
    # ДОБАВЛЕНИЕ МАТЧА
    # ================================


    st.subheader(
        "➕ Добавить матч"
    )


    home = st.text_input(
        "Хозяева"
    )

    away = st.text_input(
        "Гости"
    )


    if st.button(
        "Добавить матч"
    ):

        try:

            db.add_match(
                home,
                away
            )

            st.success(
                "Матч добавлен"
            )

            st.rerun()


        except Exception as e:

            st.error(
                str(e)
            )



    st.divider()



    # ================================
    # МАТЧИ
    # ================================


    st.subheader(
        "📋 Матчи"
    )


    matches = db.get_matches()


    if not matches:

        st.info(
            "Матчей пока нет"
        )

    else:

        for m in matches:

            st.write(
                f"""
                ⚽ {m.get('home')}
                -
                {m.get('away')}
                """
            )

            st.caption(
                f"Создан: {m.get('created','')}"
            )



    st.divider()


    st.caption(
        f"FAJ Tour Manager v11 | {datetime.now().strftime('%d.%m.%Y')}"
    )

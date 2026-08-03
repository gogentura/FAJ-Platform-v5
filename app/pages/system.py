#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ System Monitor v11
"""

import streamlit as st
from app.database import FAJDatabase


def render():

    st.title(
        "⚙️ Система FAJ"
    )


    db = FAJDatabase()


    st.subheader(
        "🗄️ Информация о базе данных"
    )


    try:

        status = db.get_status()

        st.json(
            status
        )


    except Exception as e:

        st.error(
            f"Ошибка базы: {e}"
        )



    st.divider()


    st.subheader(
        "📊 Таблицы"
    )


    try:

        tables = db.get_tables()

        st.json(
            tables
        )


    except Exception as e:

        st.error(
            str(e)
        )

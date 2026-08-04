#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0 - Главный навигатор
"""

import streamlit as st

# =====================================================
# STARTUP — АВТОМАТИЧЕСКАЯ МИГРАЦИЯ
# =====================================================
from app.startup import run_startup_checks
run_startup_checks()


st.set_page_config(
    page_title="FAJ Platform 10.0",
    page_icon="⚽",
    layout="wide"
)


# =====================================================
# STYLE
# =====================================================

st.markdown("""
<style>

.main-header {
    font-size: 32px;
    font-weight: 700;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.sub-header {
    color: #9ca3af;
    font-size: 16px;
    margin-bottom: 20px;
}

</style>
""",
unsafe_allow_html=True)



# =====================================================
# HEADER
# =====================================================

st.markdown(
    '<div class="main-header">⚽ FAJ PLATFORM 10.0</div>',
    unsafe_allow_html=True
)


st.markdown(
    '<div class="sub-header">'
    'Adaptive Football Intelligence — Самообучающаяся система прогнозирования'
    '</div>',
    unsafe_allow_html=True
)



# =====================================================
# NAVIGATION
# =====================================================

page = st.radio(
    "",
    [
        "🏠 Матч-центр",
        "📊 Сравнение",
        "🧠 Обучение",
        "🧠 Brain Center",
        "📘 Команды",
        "⚙️ Система",
        "📥 Загрузка данных",
        "📜 Архив прогнозов",
        "📡 API Тест",
        "📊 РПЛ",
        "🗓️ Туры"
    ],
    horizontal=True
)



st.divider()



# =====================================================
# PAGES
# =====================================================


if page == "🏠 Матч-центр":

    from app.pages.match_center import render
    render()



elif page == "📊 Сравнение":

    from app.pages.comparison import render
    render()



elif page == "🧠 Обучение":

    from app.pages.learning import render
    render()



elif page == "🧠 Brain Center":

    from app.pages.brain_center import render
    render()



elif page == "📘 Команды":

    from app.pages.teams import render
    render()



elif page == "⚙️ Система":

    from app.pages.system import render
    render()



elif page == "📥 Загрузка данных":

    from app.pages.load_data import render
    render()



elif page == "📜 Архив прогнозов":

    from app.pages.archive import render
    render()



elif page == "📡 API Тест":

    from app.pages.api_test import render
    render()



elif page == "📊 РПЛ":

    from app.pages.rpl import render
    render()



elif page == "🗓️ Туры":

    from app.pages.tour_manager import render
    render()



# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "⚽ FAJ Platform 10.0 | Adaptive Football Intelligence | Brain Layer Active"
)

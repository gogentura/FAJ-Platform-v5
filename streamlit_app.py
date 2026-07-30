#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.3 RU Edition

Главная панель FAJ
Football Analytics Journal
Adaptive Football Intelligence
"""

import streamlit as st
import pandas as pd
from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater


# ==========================
# CONFIG
# ==========================

VERSION = "9.3"


st.set_page_config(
    page_title="FAJ Platform 9.3",
    page_icon="⚽",
    layout="wide"
)


# ==========================
# LIGHT THEME
# ==========================

st.markdown(
"""
<style>

.stApp {
    background-color:#ffffff;
    color:#111111;
}

h1,h2,h3 {
    color:#0f172a;
}

.metric-card {

    background:#f8fafc;
    padding:20px;
    border-radius:15px;
    border:1px solid #e2e8f0;

}

</style>
""",
unsafe_allow_html=True
)



# ==========================
# LOAD ENGINES
# ==========================


memory = MemoryEngine()

passport = PassportUpdater()



# ==========================
# HEADER
# ==========================


st.title(
    "⚽ FAJ Platform 9.3"
)


st.subheader(
    "Football Analytics Journal — Adaptive Football Intelligence"
)


st.divider()



# ==========================
# STATUS
# ==========================


st.header(
    "📌 Статус системы"
)


c1,c2,c3,c4 = st.columns(4)


with c1:
    st.metric(
        "Версия модели",
        VERSION
    )


with c2:
    st.metric(
        "Команды",
        len(passport.passports)
    )


with c3:

    try:
        memory_count = len(
            memory.memory
        )

    except:

        memory_count = 0


    st.metric(
        "Память",
        memory_count
    )


with c4:

    st.metric(
        "Паспорта",
        len(passport.passports)
    )



st.divider()



# ==========================
# LEARNING CYCLE
# ==========================


st.header(
    "🧠 Цикл обучения FAJ"
)


st.info(
"""
Матч

⬇

Прогноз FAJ

⬇

Фактический результат

⬇

Анализ ошибки

⬇

Память модели

⬇

Калибровка

⬇

Обновление паспорта команды
"""
)



# ==========================
# MEMORY
# ==========================


st.header(
    "🧠 Последние выводы FAJ"
)


try:

    df_memory = pd.DataFrame(
        memory.memory
    )


    if not df_memory.empty:


        if "version" in df_memory.columns:

            df_memory["version"] = (
                df_memory["version"]
                .astype(str)
            )


        st.dataframe(
            df_memory.tail(10),
            use_container_width=True
        )


    else:

        st.warning(
            "Память FAJ пока пустая"
        )


except Exception as e:

    st.error(e)



# ==========================
# PASSPORTS
# ==========================


st.header(
    "⚽ Паспорта команд"
)


try:

    st.success(
        f"""
Активно паспортов:

{len(passport.passports)}

Последнее обновление:

{datetime.now().strftime("%d.%m.%Y")}
"""
    )


except:

    st.warning(
        "Нет данных паспортов"
    )



# ==========================
# MODULES
# ==========================


st.sidebar.title(
    "Модули FAJ"
)


menu = st.sidebar.radio(
    "",
    [
        "🏠 Главная",
        "📊 Анализ тура",
        "🧠 Память модели",
        "⚽ Паспорта команд",
        "🔄 Калибровка",
        "📈 Статистика модели"
    ]
)



# ==========================
# FOOTER
# ==========================


st.divider()


st.caption(
"""
FAJ Platform 9.3  
Adaptive Learning Engine  
Football Analytics Journal
"""
)

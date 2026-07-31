#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0
Football Analytics Journal
Adaptive Football Intelligence
Professional Match Center Interface
"""
import streamlit as st
import pandas as pd
from app.faj_core import FAJCore

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="FAJ Platform 10.0",
    page_icon="⚽",
    layout="wide"
)

# =====================================================
# CORE
# =====================================================
@st.cache_resource
def get_core():
    return FAJCore()

core = get_core()
status = core.status() if hasattr(core, 'status') else {
    "version": "10.0",
    "teams": 0,
    "memory": 0,
    "passports": 0,
    "model_events": 0,
    "team_events": 0,
    "system_events": 0
}

passport = getattr(core, "passport", None)

# =====================================================
# STYLE
# =====================================================
st.markdown(
"""
<style>
.block-container {
    padding-top: 2rem;
}
.card {
    background:#111827;
    padding:25px;
    border-radius:18px;
    margin-bottom:20px;
}
.big-title {
    font-size:40px;
    font-weight:800;
}
.subtitle {
    color:#9ca3af;
    font-size:18px;
}
.metric-box {
    background:#1f2937;
    padding:20px;
    border-radius:15px;
    text-align:center;
}
</style>
""",
unsafe_allow_html=True
)

# =====================================================
# HEADER
# =====================================================
st.markdown(
"""
<div class="big-title">
⚽ FAJ PLATFORM 10.0
</div>
<div class="subtitle">
Football Analytics Journal — Adaptive Football Intelligence
</div>
""",
unsafe_allow_html=True
)
st.write("")

# =====================================================
# NAVIGATION
# =====================================================
section = st.radio(
    "",
    [
        "🏟 Матч-центр",
        "👥 Команды",
        "🧠 Обучение",
        "📜 Журнал",
        "⚙️ Система"
    ],
    horizontal=True
)
st.divider()

# =====================================================
# TEAM LIST
# =====================================================
teams = []
if passport and hasattr(passport, "passports"):
    for item in passport.passports:
        if isinstance(item, dict):
            name = item.get("team")
            if name:
                teams.append(name)
teams = sorted(list(set(teams)))

if not teams:
    teams = [
        "Зенит",
        "Спартак",
        "ЦСКА",
        "Динамо М",
        "Краснодар",
        "Локомотив",
        "Ростов"
    ]

# =====================================================
# MATCH CENTER
# =====================================================
if section == "🏟 Матч-центр":
    st.header("🏟 Центр прогнозирования")
    col1,col2 = st.columns(2)
    with col1:
        home = st.selectbox("Домашняя команда", teams)
    with col2:
        away = st.selectbox(
            "Гостевая команда",
            [x for x in teams if x != home]
        )
    st.write("")
    
    if st.button("🔮 Рассчитать прогноз", use_container_width=True):
        st.markdown(
        f"""
        <div class="card">
        <h2>{home} ⚔️ {away}</h2>
        <h3>FAJ Prediction</h3>
        </div>
        """,
        unsafe_allow_html=True
        )
        st.info(
"""
Цикл анализа:
FAJ Core
↓
xG Engine
↓
Poisson Model
↓
Expert Layer
↓
Final Prediction
"""
        )
        c1,c2,c3 = st.columns(3)
        with c1:
            st.metric("Победа хозяев", "—")
        with c2:
            st.metric("Ничья", "—")
        with c3:
            st.metric("Победа гостей", "—")
        
        st.subheader("⚽ Ожидаемый xG")
        x1,x2 = st.columns(2)
        with x1:
            st.metric(home, "—")
        with x2:
            st.metric(away, "—")
        
        st.subheader("🎯 Вероятные счета")
        st.write("""
        1:0
        1:1
        2:1
        2:0
        0:0
        """)
        
        st.subheader("Почему FAJ выбрал такой прогноз")
        st.write("""
        ✔ Форма команд
        ✔ Паспорт силы
        ✔ Атакующий рейтинг
        ✔ Защитный баланс
        ✔ Домашний фактор
        """)
        st.progress(0)
        st.caption("Confidence Index: модуль расчета подключается")

# =====================================================
# TEAMS / PASSPORT CENTER
# =====================================================
elif section == "👥 Команды":
    st.header("👥 Команды FAJ")
    col1, col2 = st.columns(2)
    with col1:
        team_one = st.selectbox("Выберите команду", teams, key="passport_team")
    with col2:
        compare = st.checkbox("Сравнить команды")
    
    def get_team_data(name):
        if not passport:
            return None
        if not hasattr(passport, "passports"):
            return None
        for item in passport.passports:
            if isinstance(item, dict):
                if item.get("team") == name:
                    return item
        return None
    
    team_data = get_team_data(team_one)
    
    if team_data:
        st.subheader(f"📘 {team_one}")
        c1,c2,c3 = st.columns(3)
        with c1:
            st.metric("⚔️ Атака", team_data.get("attack", "-"))
        with c2:
            st.metric("🛡 Защита", team_data.get("defense", "-"))
        with c3:
            st.metric("🔥 Форма", team_data.get("form", "-"))
        
        st.divider()
        st.subheader("FAJ Passport")
        translate = {
            "attack": "Атака",
            "defense": "Защита",
            "control": "Контроль",
            "efficiency": "Эффективность",
            "mentality": "Ментальность",
            "tempo": "Темп",
            "press": "Прессинг",
            "predictability": "Предсказуемость",
            "flexibility": "Гибкость",
            "home_power": "Сила дома",
            "coach": "Тренер",
            "form": "Форма",
            "transfer_index": "Трансферы",
            "depth": "Глубина состава"
        }
        for key,value in translate.items():
            if key in team_data:
                score = float(team_data[key])
                st.write(f"**{value}** — {score}")
                st.progress(min(int(score), 100))
    else:
        st.warning("Паспорт команды не найден")
    
    # =====================================================
    # COMPARE TEAMS
    # =====================================================
    if compare:
        st.divider()
        st.subheader("⚔️ Сравнение команд")
        team_two = st.selectbox(
            "Вторая команда",
            [x for x in teams if x != team_one],
            key="compare_team"
        )
        data_two = get_team_data(team_two)
        
        if team_data and data_two:
            compare_fields = {
                "attack": "⚔️ Атака",
                "defense": "🛡 Защита",
                "form": "🔥 Форма",
                "control": "🎯 Контроль",
                "mentality": "🧠 Ментальность",
                "coach": "👔 Тренер",
                "depth": "👥 Глубина состава"
            }
            rows = []
            for key,label in compare_fields.items():
                rows.append({
                    "Показатель": label,
                    team_one: team_data.get(key, "-"),
                    team_two: data_two.get(key, "-")
                })
            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
            st.info(
f"""
FAJ анализ:
{team_one}
vs
{team_two}
Следующий этап:
FAJ Compare Engine
↓
Преимущество команд
↓
Вероятность матча
"""
            )

# =====================================================
# LEARNING CENTER
# =====================================================
elif section == "🧠 Обучение":
    st.header("🧠 Learning Center")
    st.subheader("Последние выводы FAJ")
    
    memory = []
    if hasattr(core, "memory"):
        if hasattr(core.memory, "memory"):
            memory = core.memory.memory
    
    if not memory:
        st.info(
            "Память пока пуста. "
            "После обработки тура FAJ начнет обучение."
        )
    else:
        for item in reversed(memory[-10:]):
            if isinstance(item, dict):
                st.markdown(
f"""
<div class="card">
<b>{item.get('category','EVENT')}</b>
<br>
{item.get('observation','')}
<br><br>
<b>Вывод:</b>
{item.get('conclusion','')}
<br>
<b>Действие:</b>
{item.get('action','')}
</div>
""",
                    unsafe_allow_html=True
                )

# =====================================================
# JOURNAL
# =====================================================
elif section == "📜 Журнал":
    st.header("📜 Журнал модели")
    st.write("История изменений FAJ")
    
    journal = []
    if hasattr(core, "memory"):
        if hasattr(core.memory, "memory"):
            journal = core.memory.memory
    
    if journal:
        df = pd.DataFrame(journal)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Записей журнала нет")

# =====================================================
# SYSTEM
# =====================================================
elif section == "⚙️ Система":
    st.header("⚙️ FAJ System")
    
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.metric("Версия", status.get("version", "10.0"))
    with c2:
        st.metric("Команды", status.get("teams", 0))
    with c3:
        st.metric("Паспорта", status.get("passports", 0))
    with c4:
        st.metric("Память", status.get("memory", 0))
    
    st.divider()
    st.subheader("Состояние модулей")
    modules = {
        "FAJ Core": "🟢 Активен",
        "Passport Engine": "🟢 Активен",
        "Memory Engine": "🟡 Ожидает данные",
        "xG Engine": "🟡 Подключается",
        "Poisson Model": "🟡 Подключается",
        "Expert Layer": "🟡 Подключается"
    }
    for name,state in modules.items():
        st.write(f"{name}: {state}")
    
    st.divider()
    st.subheader("FAJ Statistics")
    st.json({
        "Версия": status.get("version"),
        "Команд": status.get("teams"),
        "Паспортов": status.get("passports"),
        "Записей памяти": status.get("memory"),
        "Ошибок модели": status.get("model_events")
    })

# =====================================================
# FOOTER
# =====================================================
st.divider()
st.caption("⚽ FAJ Platform 10.0 | Adaptive Football Intelligence")

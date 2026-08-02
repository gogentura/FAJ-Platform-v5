#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Команды и паспорта
"""

import streamlit as st
import pandas as pd
import json
import os

DATA_DIR = "data"

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

TRANSLATE = {
    "attack": "⚔️ Атака",
    "defense": "🛡 Защита",
    "control": "🎯 Контроль мяча",
    "efficiency": "📊 Эффективность",
    "mentality": "🧠 Ментальность",
    "tempo": "⚡ Темп",
    "press": "🔥 Прессинг",
    "transition": "🔄 Переходы",
    "flexibility": "🔄 Гибкость",
    "coach": "👔 Тренер",
    "form": "📈 Форма",
    "depth": "👥 Глубина состава",
    "home_rating": "🏠 Сила дома",
    "away_rating": "✈️ Сила выезда"
}

def get_all_teams():
    passports = load_json("passports_2026.json")
    return list(passports.keys())

def get_team_passport(team_name):
    passports = load_json("passports_2026.json")
    return passports.get(team_name, {})

def render():
    st.markdown("### 📘 Паспорта команд")
    
    teams = get_all_teams()
    if not teams:
        st.warning("Нет команд в базе")
        return
    
    selected = st.selectbox("Выберите команду", teams)
    if selected:
        passport = get_team_passport(selected)
        if passport:
            st.markdown(f"## {selected}")
            col1, col2 = st.columns(2)
            items = list(passport.items())
            mid = len(items) // 2
            with col1:
                for key, value in items[:mid]:
                    label = TRANSLATE.get(key, key)
                    st.metric(label, value)
            with col2:
                for key, value in items[mid:]:
                    label = TRANSLATE.get(key, key)
                    st.metric(label, value)
            
            st.divider()
            st.markdown("### 📊 Профиль команды")
            df = pd.DataFrame({
                "Показатель": [TRANSLATE.get(k, k) for k in passport.keys()],
                "Значение": list(passport.values())
            })
            st.bar_chart(df.set_index("Показатель"))
        else:
            st.warning(f"Нет данных для команды {selected}")

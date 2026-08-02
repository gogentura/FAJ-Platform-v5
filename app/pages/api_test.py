#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - API Тест
"""

import streamlit as st
import pandas as pd

from app.api.football_api import FootballAPI
from app.api.football_data import FootballDataAPI
from app.api.ids import IDs

def render():
    st.markdown("### 📡 Тест подключения API")
    
    football_api = FootballAPI()
    football_data = FootballDataAPI()
    
    st.markdown("#### 🔑 Статус токенов")
    col1, col2 = st.columns(2)
    with col1:
        if football_api.is_ready():
            st.success("✅ API Football токен настроен")
        else:
            st.error("❌ API Football токен НЕ настроен")
    with col2:
        if football_data.is_ready():
            st.success("✅ Football-data токен настроен")
        else:
            st.error("❌ Football-data токен НЕ настроен")
    
    st.divider()
    
    if "api_requests" not in st.session_state:
        st.session_state.api_requests = 0
    
    st.markdown("#### 📊 Счётчик запросов")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("API Football запросов сегодня", st.session_state.api_requests)
    with col2:
        st.metric("Лимит", "100")
    with col3:
        remaining = max(0, 100 - st.session_state.api_requests)
        st.metric("Осталось", remaining)
    
    st.divider()
    
    st.markdown("#### 🔍 Поиск ID команды")
    search_team = st.text_input("Введите название команды на русском", placeholder="Например: Зенит")
    if st.button("🔍 Найти ID команды", use_container_width=True):
        if search_team:
            with st.spinner("Поиск..."):
                result = football_api.get_teams(league=235, season=2026)
                if result.get("response"):
                    found = False
                    for team in result["response"]:
                        if search_team.lower() in team["team"]["name"].lower():
                            st.success(f"✅ {team['team']['name']} → ID: {team['team']['id']}")
                            found = True
                    if not found:
                        st.warning(f"Команда '{search_team}' не найдена в РПЛ")
                else:
                    st.error("Не удалось получить список команд")
    
    st.divider()
    
    st.markdown("#### ⚽ Тест API Football (по команде)")
    
    team_options = IDs.get_all_teams()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_team = st.selectbox("Выберите команду для теста", team_options)
    with col2:
        league_for_team = st.selectbox("Лига", ["EPL", "LALIGA", "UCL", "BUNDESLIGA", "SERIEA"])
    
    if st.button("🔍 Получить статистику команды", use_container_width=True):
        with st.spinner(f"Запрос статистики для {selected_team}..."):
            result = football_api.get_team_stats_by_name(selected_team, league_for_team)
            st.session_state.api_requests += 1
        
        if result.get("error"):
            st.error(f"❌ Ошибка: {result.get('message')}")
        else:
            stats = result.get("response", {})
            if stats and stats.get("fixtures"):
                st.success(f"✅ Статистика для {selected_team} получена")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🏟 Матчей", stats.get("fixtures", {}).get("played", {}).get("total", "—"))
                with col2:
                    st.metric("✅ Побед", stats.get("fixtures", {}).get("wins", {}).get("total", "—"))
                with col3:
                    st.metric("🤝 Ничьих", stats.get("fixtures", {}).get("draws", {}).get("total", "—"))
                
                with st.expander("📋 Полная статистика"):
                    st.json(stats)
            else:
                st.warning("Нет данных по команде. Проверьте ID команды.")

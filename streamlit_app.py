#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.0 — ГЛАВНОЕ ПРИЛОЖЕНИЕ
"""

import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import config
from app.database import get_connection, FAJDatabase
from app.core.prediction_manager import get_prediction_manager

# ============================================================
# AUTO BOOTSTRAP
# ============================================================
from app.bootstrap import bootstrap_faj

bootstrap_result = bootstrap_faj()

if not bootstrap_result.get("ready"):
    st.warning("⚠️ FAJ требует настройки")
    with st.expander("📋 Детали загрузки"):
        for msg in bootstrap_result.get("messages", []):
            st.text(msg)

st.set_page_config(
    page_title=f"FAJ Platform v{config.PLATFORM_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'prediction_result' not in st.session_state:
    st.session_state.prediction_result = None

# ============================================================
# БОКОВОЕ МЕНЮ
# ============================================================
with st.sidebar:
    st.title("⚽ FAJ")
    st.caption(f"v{config.PLATFORM_VERSION}")
    st.divider()
    
    if st.button("🏠 Главная", use_container_width=True):
        st.session_state.page = 'home'
        st.session_state.prediction_result = None
    
    if st.button("📊 Прогнозы", use_container_width=True):
        st.session_state.page = 'predictions'
        st.session_state.prediction_result = None
    
    if st.button("🔬 Match Lab", use_container_width=True):
        st.session_state.page = 'match_analysis'
        st.session_state.prediction_result = None
    
    if st.button("📋 Паспорта", use_container_width=True):
        st.session_state.page = 'passports'
    
    if st.button("🚀 Загрузить данные", use_container_width=True):
        st.session_state.page = 'force_load_data'
    
    if st.button("🔧 Исправить команды", use_container_width=True):
        st.session_state.page = 'fix_teams'
    
    if st.button("⚙️ Система", use_container_width=True):
        st.session_state.page = 'system'
    
    st.divider()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        teams = cursor.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        matches = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        conn.close()
        
        st.caption("📊 Статус:")
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"🏟️ {teams}")
        with col2:
            st.caption(f"📋 {matches}")
        st.caption("Команды | Матчи")
    except:
        pass

# ============================================================
# СТРАНИЦЫ
# ============================================================

# ----- ГЛАВНАЯ -----
if st.session_state.page == 'home':
    st.title("🏠 FAJ Platform v12")
    st.caption(f"Ядро v{config.CORE_VERSION} · Pipeline v{config.PIPELINE_VERSION}")
    
    if bootstrap_result.get("ready"):
        st.success("✅ Система готова к работе")
    else:
        st.warning("⚠️ Система не полностью готова")
    
    st.divider()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        teams = cursor.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        matches = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        results = cursor.execute("SELECT COUNT(*) FROM match_results").fetchone()[0]
        stats = cursor.execute("SELECT COUNT(*) FROM match_statistics").fetchone()[0]
        conn.close()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏟️ Команды", teams)
        with col2:
            st.metric("📋 Матчи", matches)
        with col3:
            st.metric("📊 Результаты", results)
        with col4:
            st.metric("📈 Статистика", stats)
    except:
        st.warning("⚠️ Статус БД недоступен")
    
    st.divider()
    
    st.subheader("🚀 Быстрый старт")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Сделать прогноз", use_container_width=True, type="primary"):
            st.session_state.page = 'predictions'
            st.rerun()
    with col2:
        if st.button("🔬 Match Lab", use_container_width=True):
            st.session_state.page = 'match_analysis'
            st.rerun()

# ----- ПРОГНОЗЫ -----
elif st.session_state.page == 'predictions':
    st.title("📊 Прогнозы матчей")
    st.caption(f"FAJ Prediction Engine v{config.PIPELINE_VERSION}")
    
    try:
        conn = get_connection()
        teams_df = pd.read_sql("SELECT id, name FROM teams ORDER BY name", conn)
        conn.close()
    except:
        teams_df = pd.DataFrame()
    
    if teams_df.empty:
        st.warning("⚠️ В базе нет команд. Сначала загрузите данные через 'Загрузить данные'.")
        if st.button("🚀 Перейти к загрузке"):
            st.session_state.page = 'force_load_data'
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            team1 = st.selectbox("🏠 Хозяева", teams_df['name'].tolist())
        with col2:
            team2 = st.selectbox("✈️ Гости", teams_df['name'].tolist())
        
        if st.button("🔮 Сделать прогноз", type="primary", use_container_width=True):
            if team1 == team2:
                st.error("❌ Команды не могут совпадать!")
                st.session_state.prediction_result = None
            else:
                with st.spinner("🧠 Вычисление прогноза..."):
                    try:
                        pm = get_prediction_manager()
                        result = pm.predict(
                            home_team=team1,
                            away_team=team2,
                            league="RPL"
                        )
                        st.session_state.prediction_result = result
                        if result.get('status') == 'error':
                            st.error(f"❌ Ошибка: {result.get('message')}")
                        else:
                            st.success("✅ Прогноз выполнен!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
                        st.session_state.prediction_result = None
        
        # --- ОТОБРАЖЕНИЕ РЕЗУЛЬТАТА ---
        if st.session_state.prediction_result:
            result = st.session_state.prediction_result
            if result.get('status') != 'error':
                st.divider()
                st.subheader(f"📊 {result.get('home_team', '')} vs {result.get('away_team', '')}")
                
                col

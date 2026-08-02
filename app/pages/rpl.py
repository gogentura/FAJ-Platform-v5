#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - РПЛ данные
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

DATA_DIR = "data"

def render():
    st.markdown("### 📊 РПЛ — данные с сайтов")
    
    from app.parsers.soccerland_parser import SoccerlandParser
    parser = SoccerlandParser()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div style="background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px;">
            <h4 style="color: #f3f4f6; margin-top: 0;">📋 Что собираем</h4>
            <p style="color: #9ca3af; font-size: 14px;">
                ✅ Турнирная таблица<br>
                ✅ Результаты матчей с голами<br>
                ✅ Предстоящие матчи (календарь)<br>
                ✅ Бомбардиры и ассистенты
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px;">
            <h4 style="color: #f3f4f6; margin-top: 0;">🌐 Источники</h4>
            <p style="color: #9ca3af; font-size: 14px;">
                soccerland.ru — таблица, результаты, бомбардиры<br>
                championat.com — календарь (предстоящие матчи)
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    if st.button("🔄 Обновить данные РПЛ", use_container_width=True, type="primary"):
        with st.spinner("Сбор данных с сайтов..."):
            result = parser.update_all()
        
        st.success(f"✅ Данные обновлены: {datetime.now().strftime('%H:%M:%S')}")
        st.session_state.rpl_data = result
    
    st.divider()
    
    rpl_data = st.session_state.get("rpl_data")
    if not rpl_data:
        try:
            with open("data/rpl_live_data.json", "r", encoding="utf-8") as f:
                rpl_data = json.load(f)
        except:
            rpl_data = None
    
    if rpl_data:
        if rpl_data.get("standings"):
            st.markdown("### 📊 Турнирная таблица")
            df_standings = pd.DataFrame(rpl_data["standings"])
            st.dataframe(df_standings, use_container_width=True, hide_index=True)
        
        st.divider()
        
        if rpl_data.get("upcoming"):
            st.markdown("### ⏳ Предстоящие матчи")
            df_upcoming = pd.DataFrame(rpl_data["upcoming"])
            st.dataframe(df_upcoming, use_container_width=True, hide_index=True)
        
        if rpl_data.get("matches"):
            st.markdown("### ✅ Сыгранные матчи")
            matches = rpl_data["matches"]
            played = [m for m in matches if m.get("status") == "FT"]
            if played:
                df_played = pd.DataFrame(played)
                st.dataframe(df_played, use_container_width=True, hide_index=True)
        
        st.divider()
        
        if rpl_data.get("scorers"):
            st.markdown("### ⚽ Бомбардиры")
            df_scorers = pd.DataFrame(rpl_data["scorers"])
            st.dataframe(df_scorers, use_container_width=True, hide_index=True)
        
        st.caption(f"Последнее обновление: {rpl_data.get('timestamp', '—')}")
    else:
        st.info("Нажмите 'Обновить данные РПЛ' для загрузки информации.")

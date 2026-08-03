#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11.1
Архив прогнозов
"""

import streamlit as st
import pandas as pd


def render():
    st.markdown("### 📜 Архив прогнозов FAJ")
    
    from app.database import FAJDatabase
    db = FAJDatabase()
    
    # Получаем все матчи (без limit)
    matches = db.get_matches()
    
    if not matches:
        st.info("Нет сохранённых прогнозов. Загрузите данные.")
        return
    
    archive_data = []
    for match in matches:
        # Получаем названия команд
        home_team = db.get_team(match['home_team_id'])
        away_team = db.get_team(match['away_team_id'])
        home_name = home_team['name'] if home_team else '?'
        away_name = away_team['name'] if away_team else '?'
        
        # Счёт
        if match.get('actual_home') is not None and match.get('actual_away') is not None:
            score = f"{match['actual_home']}:{match['actual_away']}"
        else:
            score = "—"
        
        # Статус
        status = "✅ Завершён" if match.get('status') == 'finished' else "⏳ Ожидается"
        
        # Получаем прогноз
        pred, scores, dist = db.get_prediction(match['id'])
        if pred:
            prediction = f"{pred.get('algorithm', 'FAJ')} v{pred.get('model_version', '11')}"
            confidence = f"{pred.get('confidence', 0)}%"
        else:
            prediction = "—"
            confidence = "—"
        
        archive_data.append({
            "Матч": f"{home_name} – {away_name}",
            "Прогноз": prediction,
            "Счёт": score,
            "Уверенность": confidence,
            "Статус": status
        })
    
    if archive_data:
        st.dataframe(pd.DataFrame(archive_data), use_container_width=True, hide_index=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего матчей", len(archive_data))
        with col2:
            completed = sum(1 for m in archive_data if "Завершён" in m["Статус"])
            st.metric("Завершённых", completed)
        with col3:
            pending = len(archive_data) - completed
            st.metric("Ожидается", pending)

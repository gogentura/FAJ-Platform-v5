#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Архив прогнозов
"""

import streamlit as st
import pandas as pd

def render():
    st.markdown("### 📜 Архив прогнозов FAJ")
    
    from app.database import FAJDatabase
    db = FAJDatabase()
    matches = db.get_matches(limit=100)
    
    if not matches:
        st.info("Нет сохранённых прогнозов. Загрузите данные через '📥 Загрузка данных'.")
    else:
        archive_data = []
        for match in matches:
            home = match.get('home_team_name', '?')
            away = match.get('away_team_name', '?')
            home_goals = match.get('home_goals')
            away_goals = match.get('away_goals')
            if home_goals is not None and away_goals is not None:
                score = f"{home_goals}:{away_goals}"
            else:
                score = "—"
            status = match.get('status', 'NS')
            
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT predicted_score, confidence
                    FROM predictions WHERE match_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (match.get('id'),))
                pred_row = cursor.fetchone()
            
            if pred_row:
                archive_data.append({
                    "Матч": f"{home} – {away}",
                    "Прогноз": pred_row[0] if pred_row[0] else "—",
                    "Счёт": score,
                    "Уверенность": f"{pred_row[1]}%" if pred_row[1] else "—",
                    "Статус": "✅ Завершён" if status == "FT" else "⏳ Ожидается"
                })
            else:
                archive_data.append({
                    "Матч": f"{home} – {away}",
                    "Прогноз": "—",
                    "Счёт": score,
                    "Уверенность": "—",
                    "Статус": "✅ Завершён" if status == "FT" else "⏳ Ожидается"
                })
        
        if archive_data:
            st.dataframe(pd.DataFrame(archive_data), use_container_width=True, hide_index=True)
            st.divider()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Всего прогнозов", len(archive_data))
            with col2:
                completed = sum(1 for m in matches if m.get('status') == 'FT')
                st.metric("Завершённых матчей", completed)
            with col3:
                pending = len(archive_data) - completed
                st.metric("Ожидается", pending)

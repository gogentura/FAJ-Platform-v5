#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Управление турами
Автоматическая загрузка и обновление результатов
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

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

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def render():
    st.markdown("### 🗓️ Управление турами")
    
    from app.database import FAJDatabase
    db = FAJDatabase()
    
    # =========================================================
    # 1. ЗАГРУЗКА НОВОГО ТУРА
    # =========================================================
    st.markdown("#### 📥 Загрузить новый тур")
    
    # Список доступных файлов с турами
    available_tours = []
    for f in os.listdir(DATA_DIR):
        if f.startswith("tour") and f.endswith(".json") and "results" not in f:
            available_tours.append(f)
    
    if available_tours:
        selected_file = st.selectbox("Выберите файл с туром", available_tours)
        
        if st.button("📥 Загрузить тур в базу", use_container_width=True):
            tour_data = load_json(selected_file)
            if tour_data:
                loaded = 0
                for match_name, data in tour_data.items():
                    if '-' in match_name:
                        home, away = match_name.split('-')
                    else:
                        home, away = match_name.split('–')
                    
                    # Проверяем, есть ли уже матч
                    existing = db.get_matches(limit=1000)
                    exists = False
                    for m in existing:
                        if m.get('home_team_name') == home and m.get('away_team_name') == away:
                            exists = True
                            break
                    
                    if not exists:
                        match_id = db.save_match({
                            "home_team": home,
                            "away_team": away,
                            "league": "RPL",
                            "season": 2026,
                            "status": "NS",
                            "xg_home": data.get('xg_home'),
                            "xg_away": data.get('xg_away')
                        })
                        # Сохраняем прогнозы
                        faj_pred = data.get('faj', '')
                        if faj_pred:
                            db.save_prediction(match_id, faj_pred)
                        loaded += 1
                
                st.success(f"✅ Загружено матчей: {loaded}")
    else:
        st.info("Нет файлов с турами. Добавьте файл в папку data/")
    
    st.divider()
    
    # =========================================================
    # 2. ОБНОВЛЕНИЕ РЕЗУЛЬТАТОВ
    # =========================================================
    st.markdown("#### 📊 Обновить результаты тура")
    
    # Ищем файлы с результатами
    result_files = []
    for f in os.listdir(DATA_DIR):
        if "results" in f and f.endswith(".json"):
            result_files.append(f)
    
    if result_files:
        selected_results = st.selectbox("Выберите файл с результатами", result_files)
        
        if st.button("📊 Обновить результаты из файла", use_container_width=True):
            results_data = load_json(selected_results)
            if results_data:
                updated = 0
                for match_name, data in results_data.items():
                    actual = data.get('actual', '')
                    if ':' in actual:
                        try:
                            hg, ag = map(int, actual.split(':'))
                            matches = db.get_matches(limit=1000)
                            for m in matches:
                                home = m.get('home_team_name')
                                away = m.get('away_team_name')
                                if f"{home}-{away}" == match_name:
                                    with db._get_connection() as conn:
                                        cursor = conn.cursor()
                                        cursor.execute("""
                                            UPDATE matches 
                                            SET home_goals = ?, away_goals = ?, status = 'FT'
                                            WHERE id = ?
                                        """, (hg, ag, m.get('id')))
                                        conn.commit()
                                        updated += 1
                                    break
                        except:
                            pass
                
                st.success(f"✅ Обновлено результатов: {updated}")
    else:
        st.info("Нет файлов с результатами")
    
    st.divider()
    
    # =========================================================
    # 3. ТЕКУЩЕЕ СОСТОЯНИЕ ТУРОВ
    # =========================================================
    st.markdown("#### 📋 Текущее состояние")
    
    matches = db.get_matches(limit=1000)
    if matches:
        df = pd.DataFrame(matches)
        df_display = df[['home_team_name', 'away_team_name', 'status', 'home_goals', 'away_goals']]
        df_display.columns = ['Хозяева', 'Гости', 'Статус', 'Голы хозяев', 'Голы гостей']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        total = len(matches)
        completed = sum(1 for m in matches if m.get('status') == 'FT')
        st.metric("Всего матчей", total)
        st.metric("Завершённых", completed)
        st.metric("Ожидается", total - completed)
    else:
        st.info("Нет загруженных матчей")
    
    st.divider()
    
    # =========================================================
    # 4. СОЗДАНИЕ НОВОГО ТУРА
    # =========================================================
    with st.expander("➕ Создать новый тур (вручную)"):
        st.markdown("Создайте файл тура вручную и сохраните в data/")
        st.code("""
{
  "Команда1-Команда2": {
    "faj": "1:0",
    "expert": "2:1",
    "xg_home": 1.35,
    "xg_away": 0.85
  }
}
        """, language="json")
        st.caption("Файл должен называться tourX_predictions.json (где X — номер тура)")

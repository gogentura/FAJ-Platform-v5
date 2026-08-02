#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Управление турами
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

def render():
    st.markdown("### 🗓️ Управление турами")
    
    from app.database import FAJDatabase
    db = FAJDatabase()
    
    # =========================================================
    # 1. ТЕКУЩЕЕ СОСТОЯНИЕ БАЗЫ
    # =========================================================
    st.markdown("#### 📋 Матчи в базе данных")
    matches = db.get_matches(limit=1000)
    
    if matches:
        df = pd.DataFrame(matches)
        df_display = df[['home_team_name', 'away_team_name', 'status', 'home_goals', 'away_goals']]
        df_display.columns = ['Хозяева', 'Гости', 'Статус', 'Голы хозяев', 'Голы гостей']
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.caption(f"Всего матчей: {len(matches)}")
    else:
        st.info("В базе пока нет матчей")
    
    st.divider()
    
    # =========================================================
    # 2. ЗАГРУЗКА ТУРА
    # =========================================================
    st.markdown("#### 📥 Загрузить тур")
    
    tour_files = [f for f in os.listdir(DATA_DIR) if f.startswith("tour") and f.endswith(".json") and "results" not in f]
    
    if not tour_files:
        st.warning("Нет файлов с турами в папке data/")
        return
    
    selected_file = st.selectbox("Выберите файл с туром", tour_files)
    
    # Показываем содержимое файла
    tour_data = load_json(selected_file)
    if tour_data:
        st.markdown(f"**Файл `{selected_file}` содержит {len(tour_data)} матчей:**")
        for match_name in tour_data.keys():
            st.write(f"- {match_name}")
    
    if st.button("📥 Загрузить тур в базу", use_container_width=True):
        if not tour_data:
            st.error("❌ Файл пуст или не найден")
        else:
            loaded = 0
            skipped = 0
            errors = []
            
            for match_name, data in tour_data.items():
                try:
                    if '-' in match_name:
                        home, away = match_name.split('-', 1)
                    else:
                        home, away = match_name.split('–', 1)
                    
                    # Проверяем, есть ли уже
                    existing = db.get_matches(limit=1000)
                    exists = False
                    for m in existing:
                        if m.get('home_team_name') == home and m.get('away_team_name') == away:
                            exists = True
                            break
                    
                    if not exists:
                        match_id = db.save_match({
                            "home_team": home.strip(),
                            "away_team": away.strip(),
                            "league": "RPL",
                            "season": 2026,
                            "status": "NS",
                            "xg_home": data.get('xg_home'),
                            "xg_away": data.get('xg_away')
                        })
                        faj_pred = data.get('faj', '')
                        if faj_pred:
                            db.save_prediction(match_id, faj_pred)
                        loaded += 1
                    else:
                        skipped += 1
                except Exception as e:
                    errors.append(f"{match_name}: {str(e)}")
            
            st.success(f"✅ Загружено: {loaded}, пропущено (уже есть): {skipped}")
            if errors:
                st.warning(f"⚠️ Ошибок: {len(errors)}")
                for err in errors[:5]:
                    st.write(f"- {err}")
    
    st.divider()
    
    # =========================================================
    # 3. ОБНОВЛЕНИЕ РЕЗУЛЬТАТОВ
    # =========================================================
    st.markdown("#### 📊 Обновить результаты тура")
    
    result_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_results.json")]
    
    if not result_files:
        st.info("Нет файлов с результатами")
    else:
        selected_results = st.selectbox("Выберите файл с результатами", result_files)
        
        results_data = load_json(selected_results)
        if results_data:
            st.markdown(f"**Файл `{selected_results}` содержит {len(results_data)} результатов:**")
            for match_name in results_data.keys():
                actual = results_data[match_name].get('actual', '—')
                st.write(f"- {match_name} → {actual}")
        
        if st.button("📊 Обновить результаты из файла", use_container_width=True):
            if not results_data:
                st.error("❌ Файл пуст или не найден")
            else:
                updated = 0
                not_found = 0
                errors = []
                
                for match_name, data in results_data.items():
                    actual = data.get('actual', '')
                    if ':' not in actual:
                        continue
                    
                    try:
                        hg, ag = map(int, actual.split(':'))
                        matches_list = db.get_matches(limit=1000)
                        found = False
                        
                        for m in matches_list:
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
                                    found = True
                                break
                        
                        if not found:
                            not_found += 1
                            errors.append(f"{match_name} — матч не найден в БД")
                    except Exception as e:
                        errors.append(f"{match_name}: {str(e)}")
                
                st.success(f"✅ Обновлено: {updated} матчей")
                if not_found > 0:
                    st.warning(f"⚠️ Не найдено в БД: {not_found}")
                if errors:
                    for err in errors[:5]:
                        st.write(f"- {err}")
    
    st.divider()
    
    # =========================================================
    # 4. ОЧИСТКА
    # =========================================================
    with st.expander("🗑️ Очистка базы"):
        st.warning("⚠️ Это удалит ВСЕ матчи и прогнозы!")
        if st.button("🗑️ Удалить все матчи и прогнозы", use_container_width=True):
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM predictions")
                cursor.execute("DELETE FROM matches")
                conn.commit()
            st.success("✅ База очищена")
            st.rerun()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Матч-центр
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

def get_team_passport(team_name):
    passports = load_json("passports_2026.json")
    return passports.get(team_name, {})

def get_all_teams():
    passports = load_json("passports_2026.json")
    return list(passports.keys())

def get_outcome(score):
    if not score or score == "-":
        return None
    try:
        h, a = map(int, score.split(':'))
        if h > a:
            return "П1"
        elif h == a:
            return "X"
        else:
            return "П2"
    except:
        return None

def render():
    st.markdown("### 🏟 Центр прогнозирования — 2-й тур РПЛ")
    
    teams = get_all_teams()
    if not teams:
        st.warning("Нет команд в базе данных")
        return
    
    from app.faj_match_engine import FAJMatchEngine
    from app.database import FAJDatabase
    from app.passport_manager import PassportManager
    
    engine = FAJMatchEngine()
    db = FAJDatabase()
    passport_mgr = PassportManager()
    
    tour2 = load_json("tour2_predictions.json")
    
    if not tour2:
        st.warning("Нет данных для 2-го тура. Проверьте файл tour2_predictions.json")
        return
    
    # =========================================================
    # ПОЛУЧАЕМ РЕЗУЛЬТАТЫ ИЗ SQLite
    # =========================================================
    existing_matches = db.get_matches(limit=100)
    results_map = {}
    for m in existing_matches:
        home = m.get('home_team_name')
        away = m.get('away_team_name')
        if home and away:
            key = f"{home}-{away}"
            if m.get('status') == 'FT':
                results_map[key] = {
                    "score": f"{m.get('home_goals', '')}:{m.get('away_goals', '')}",
                    "status": "✅ Завершён"
                }
            else:
                results_map[key] = {
                    "score": "—",
                    "status": "⏳ Ожидается"
                }
    
    # =========================================================
    # ТАБЛИЦА ПРОГНОЗОВ + РЕЗУЛЬТАТОВ
    # =========================================================
    st.markdown("### 📊 Прогнозы и результаты 2-го тура")
    
    matches_data = []
    for match, data in tour2.items():
        if '-' in match:
            home, away = match.split('-')
        else:
            home, away = match.split('–')
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        
        # Берём результат из SQLite
        result_info = results_map.get(match, {"score": "—", "status": "⏳ Ожидается"})
        actual_score = result_info["score"]
        status = result_info["status"]
        
        faj_outcome = get_outcome(faj_pred) if faj_pred != '—' else '—'
        
        if faj_outcome == "П1":
            best_bet = f"Победа {home}"
        elif faj_outcome == "П2":
            best_bet = f"Победа {away}"
        elif faj_outcome == "X":
            best_bet = "Ничья"
        else:
            best_bet = "—"
        
        # Проверяем совпадение прогноза с результатом
        match_result = "—"
        if actual_score != "—":
            if faj_pred == actual_score:
                match_result = "✅ Точный счёт!"
            elif faj_outcome == get_outcome(actual_score):
                match_result = "✅ Исход угадан"
            else:
                match_result = "❌ Не угадан"
        
        matches_data.append({
            "Матч": f"{home} – {away}",
            "Прогноз FAJ": faj_pred,
            "Ваш прогноз": expert_pred,
            "Результат": actual_score,
            "Статус": status,
            "Совпадение": match_result,
            "Лучшая ставка": best_bet
        })
    
    df_matches = pd.DataFrame(matches_data)
    st.dataframe(df_matches, use_container_width=True, hide_index=True)
    
    # =========================================================
    # КНОПКА ОБНОВЛЕНИЯ РЕЗУЛЬТАТОВ
    # =========================================================
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Обновить результаты", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # =========================================================
    # ДЕТАЛЬНЫЙ ПРОГНОЗ ПО МАТЧУ
    # =========================================================
    st.markdown("### 🔍 Детальный прогноз по матчу")
    
    match_options = list(tour2.keys())
    selected_match = st.selectbox("Выберите матч для детального прогноза", match_options)
    
    if selected_match:
        data = tour2[selected_match]
        
        if '-' in selected_match:
            home, away = selected_match.split('-')
        else:
            home, away = selected_match.split('–')
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        
        home_passport = get_team_passport(home)
        away_passport = get_team_passport(away)
        
        if home_passport and away_passport:
            result = engine.predict_match(home_passport, away_passport)
            
            # =========================================================
            # СОХРАНЯЕМ ПРОГНОЗ В SQLite
            # =========================================================
            try:
                match_id = None
                existing_matches = db.get_matches(limit=1000)
                for m in existing_matches:
                    if m.get('home_team_name') == home and m.get('away_team_name') == away:
                        match_id = m.get('id')
                        break
                
                if not match_id:
                    match_id = db.save_match({
                        "home_team": home,
                        "away_team": away,
                        "league": "RPL",
                        "season": 2026,
                        "status": "NS",
                        "xg_home": result['xg_home'],
                        "xg_away": result['xg_away']
                    })
                
                predicted_score = result['top_scores'][0]['score'] if result['top_scores'] else "1:1"
                db.save_prediction(match_id, predicted_score, result['confidence'])
                
                # Обновляем паспорта через PassportManager (если есть результат)
                result_info = results_map.get(selected_match, {})
                if result_info.get("status") == "✅ Завершён":
                    score = result_info.get("score", "")
                    if ":" in score:
                        try:
                            hg, ag = map(int, score.split(':'))
                            passport_mgr.update_after_match(home, away, hg, ag, result['xg_home'], result['xg_away'])
                        except:
                            pass
                
                st.success("✅ Прогноз сохранён в базу данных!")
            except Exception as e:
                st.warning(f"⚠️ Не удалось сохранить прогноз: {e}")
            
            # =========================================================
            # ОТОБРАЖАЕМ РЕЗУЛЬТАТ
            # =========================================================
            
            # Проверяем, есть ли результат
            result_info = results_map.get(selected_match, {})
            actual_score = result_info.get("score", "—")
            status = result_info.get("status", "⏳ Ожидается")
            
            st.markdown(f"""
            <div style="background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px;">
                <h2 style="text-align:center; color:#f3f4f6; margin:0;">{home} ⚔️ {away}</h2>
                <p style="text-align:center; color:#9ca3af;">
                    FAJ Prediction v10.0
                    {f' | Результат: {actual_score} {status}' if actual_score != '—' else ''}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"Победа {home}", f"{result['home_win']}%")
            with col2:
                st.metric("Ничья", f"{result['draw']}%")
            with col3:
                st.metric(f"Победа {away}", f"{result['away_win']}%")
            
            st.divider()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"⚽ xG {home}", result['xg_home'])
                st.metric(f"🏠 Сила {home}", result['home_power'])
            with col2:
                st.metric(f"⚽ xG {away}", result['xg_away'])
                st.metric(f"✈️ Сила {away}", result['away_power'])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Уверенность", f"{result['confidence']}%")
            with col2:
                st.metric("⚽ Тотал > 2.5", f"{result['over25']}%")
            with col3:
                st.metric("🤝 Обе забьют", f"{result['btts']}%")
            with col4:
                st.metric("📉 Риск", result['risk'])
            
            st.markdown("### 🎯 Самые вероятные счета")
            if result['top_scores']:
                st.dataframe(pd.DataFrame(result['top_scores']), hide_index=True, use_container_width=True)
            
            with st.expander("🧠 Почему FAJ выбрал такой прогноз"):
                st.write(f"""
                Анализ матча {home} vs {away} на основе:
                
                1. **Сила команд**: {home} {result['home_power']} vs {away} {result['away_power']}
                2. **xG**: {home} {result['xg_home']} vs {away} {result['xg_away']}
                3. **Вероятности**: П1 {result['home_win']}% | X {result['draw']}% | П2 {result['away_win']}%
                4. **Уверенность модели**: {result['confidence']}%
                5. **Ключевые факторы**:
                   - {'Домашнее преимущество' if result['xg_home'] > result['xg_away'] else 'Гостевой фактор'}
                   - {'Атакующий стиль' if result['xg_home'] > 1.5 else 'Сбалансированная игра'}
                """)
            
            if expert_pred != '—':
                st.divider()
                st.markdown("### 📊 Сравнение прогнозов")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("FAJ", faj_pred)
                with col2:
                    st.metric("Ваш прогноз", expert_pred)
        else:
            st.warning(f"Нет паспортов для команд {home} или {away}")

# Стиль для карточек
st.markdown("""
<style>
    .prediction-card { background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)

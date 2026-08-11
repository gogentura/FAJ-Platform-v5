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
        st.session_state.page = 'load_data'
    
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
            st.session_state.page = 'load_data'
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
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    xg = result.get('xg', {})
                    st.metric("🏠 xG Хозяев", f"{xg.get('home', 0):.2f}")
                with col2:
                    st.metric("🎯 Прогноз", result.get('score', '0:0'))
                    st.caption(f"Вероятность: {result.get('score_probability', 0):.1%}")
                with col3:
                    xg = result.get('xg', {})
                    st.metric("✈️ xG Гостей", f"{xg.get('away', 0):.2f}")
                
                st.subheader("📈 Распределение вероятностей")
                prob = result.get('probability', {})
                prob_df = pd.DataFrame({
                    'Исход': ['Победа хозяев', 'Ничья', 'Победа гостей'],
                    'Вероятность': [
                        prob.get('home', 0),
                        prob.get('draw', 0),
                        prob.get('away', 0)
                    ]
                })
                st.bar_chart(prob_df.set_index('Исход'))
                
                extended = result.get('extended', {})
                if extended:
                    st.subheader("📋 Расширенные метрики")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**⚽ Обе забьют (BTTS)**")
                        btts = extended.get('btts', {})
                        st.metric("Да", f"{btts.get('yes', 0):.1%}")
                        st.metric("Нет", f"{btts.get('no', 0):.1%}")
                    with col2:
                        st.write("**📊 Тоталы**")
                        total = extended.get('total', {})
                        st.metric("Тотал > 2.5", f"{total.get('over_2_5', 0):.1%}")
                        st.metric("Тотал > 3.5", f"{total.get('over_3_5', 0):.1%}")
                    
                    top_scores = extended.get('top_scores', [])
                    if top_scores:
                        st.subheader("🎯 Топ-5 точных счетов")
                        scores_data = []
                        for score in top_scores:
                            scores_data.append({
                                "№": score.get('rank', 0),
                                "Счёт": f"{score.get('home', 0)}:{score.get('away', 0)}",
                                "Вероятность": score.get('prob_percent', '0%')
                            })
                        st.table(pd.DataFrame(scores_data).set_index("№"))
                
                with st.expander("📋 Детали прогноза (JSON)"):
                    st.json(result)

# ----- MATCH LABORATORY -----
elif st.session_state.page == 'match_analysis':
    try:
        from app.pages.match_analysis import main as match_analysis_main
        match_analysis_main()
    except ImportError as e:
        st.error(f"❌ Страница Match Laboratory не найдена: {e}")
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")

# ----- ПАСПОРТА -----
elif st.session_state.page == 'passports':
    st.title("📋 Паспорта команд")
    st.caption("FAJ Passport Manager v1.4")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.name as team_name,
                tp.attack,
                tp.defense,
                tp.control,
                tp.goalkeeper,
                tp.faj_rating
            FROM teams t
            LEFT JOIN team_passports tp ON t.id = tp.team_id
            WHERE t.league = 'РПЛ'
            ORDER BY t.name
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            st.warning("⚠️ Паспорта не загружены. Загрузите данные через 'Загрузить данные'.")
            if st.button("🚀 Перейти к загрузке"):
                st.session_state.page = 'load_data'
                st.rerun()
        else:
            data = []
            for row in rows:
                if row['team_name']:
                    data.append({
                        "Команда": row['team_name'],
                        "Атака": round(row['attack'] or 50, 1),
                        "Защита": round(row['defense'] or 50, 1),
                        "Контроль": round(row['control'] or 50, 1),
                        "Вратарь": round(row['goalkeeper'] or 50, 1),
                        "FAJ Rating": round(row['faj_rating'] or 0, 1),
                    })
            
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"📊 Всего команд: {len(data)}")
    except Exception as e:
        st.error(f"❌ Ошибка загрузки паспортов: {e}")

# ----- ЗАГРУЗКА ДАННЫХ -----
elif st.session_state.page == 'load_data':
    try:
        from app.pages.load_data import main as load_data_main
        load_data_main()
    except ImportError as e:
        st.error(f"❌ Страница загрузки не найдена: {e}")
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")

# ----- СИСТЕМА -----
elif st.session_state.page == 'system':
    st.title("⚙️ Система")
    
    try:
        db = FAJDatabase()
        status_db = db.get_status()
        tables = status_db.get("tables", {})
        
        st.subheader("📊 База данных")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Основные**")
            st.write(f"- teams: {tables.get('teams', 0)}")
            st.write(f"- matches: {tables.get('matches', 0)}")
            st.write(f"- match_results: {tables.get('match_results', 0)}")
        with col2:
            st.write("**Системные**")
            st.write(f"- team_passports: {tables.get('team_passports', 0)}")
            st.write(f"- predictions: {tables.get('predictions', 0)}")
        
        st.divider()
        
        db_path = "data/faj.db"
        if os.path.exists(db_path):
            size = os.path.getsize(db_path) / (1024 * 1024)
            st.write(f"**Файл БД:** {db_path}")
            st.write(f"**Размер:** {size:.2f} MB")
        
        st.divider()
        
        st.subheader("📌 Версии")
        st.write(f"**Платформа:** v{config.PLATFORM_VERSION}")
        st.write(f"**Ядро:** v{config.CORE_VERSION}")
        st.write(f"**Pipeline:** v{config.PIPELINE_VERSION}")
        
        st.divider()
        st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")

# ============================================================
# ФУТЕР
# ============================================================
st.divider()
st.caption(
    f"⚽ FAJ Platform v{config.PLATFORM_VERSION} · "
    f"Core v{config.CORE_VERSION} · "
    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
)

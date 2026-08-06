#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.0 — ПОЛНАЯ БОЕВАЯ ВЕРСИЯ
"""

import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import config, PLATFORM_VERSION, CORE_VERSION, PIPELINE_VERSION
from app.database import get_connection, FAJDatabase
from app.migrations.learning import ensure_learning_layer
from app.sync_engine import SyncEngine
from app.prediction.prediction_manager import get_prediction_manager
from app.passports.passport_manager import get_passport_manager

# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================
st.set_page_config(
    page_title=f"FAJ Platform v{PLATFORM_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# АВТОМАТИЧЕСКАЯ МИГРАЦИЯ
# ============================================================
try:
    ensure_learning_layer()
except Exception as e:
    st.error(f"⚠️ Ошибка миграции: {e}")

# ============================================================
# ИНИЦИАЛИЗАЦИЯ СЕССИИ
# ============================================================
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'prediction_result' not in st.session_state:
    st.session_state.prediction_result = None

# ============================================================
# БОКОВОЕ МЕНЮ
# ============================================================
with st.sidebar:
    st.title("⚽ FAJ")
    st.caption(f"v{PLATFORM_VERSION}")
    st.divider()
    
    # === НАВИГАЦИЯ ===
    if st.button("🏠 Главная", use_container_width=True):
        st.session_state.page = 'home'
        st.session_state.prediction_result = None
    
    if st.button("📊 Прогнозы", use_container_width=True):
        st.session_state.page = 'predictions'
        st.session_state.prediction_result = None
    
    if st.button("🔄 Синхронизация", use_container_width=True):
        st.session_state.page = 'sync'
    
    if st.button("⚙️ Система", use_container_width=True):
        st.session_state.page = 'system'
    
    st.divider()
    
    # === СТАТУС ===
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        teams = cursor.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        matches = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        gold = cursor.execute("SELECT COUNT(*) FROM gold_dataset").fetchone()[0]
        conn.close()
        
        st.caption("📊 Статус системы:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"{'✅' if teams > 0 else '❌'} {teams}")
        with col2:
            st.caption(f"{'✅' if matches > 0 else '❌'} {matches}")
        with col3:
            st.caption(f"{'✅' if gold > 0 else '❌'} {gold}")
        st.caption("Команды | Матчи | Gold")
        
    except Exception as e:
        st.caption(f"⚠️ Статус: {str(e)[:30]}")

# ============================================================
# РОУТИНГ (БЕЗ return ВНЕ ФУНКЦИЙ!)
# ============================================================
try:
    # ============================================================
    # ГЛАВНАЯ
    # ============================================================
    if st.session_state.page == 'home':
        st.title("🏠 FAJ Platform v12")
        st.caption(f"Ядро v{CORE_VERSION} · Pipeline v{PIPELINE_VERSION}")
        
        st.divider()
        
        # СТАТУС
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            teams = cursor.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
            matches = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
            gold = cursor.execute("SELECT COUNT(*) FROM gold_dataset").fetchone()[0]
            learning = cursor.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0]
            conn.close()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🏟️ Команды", teams)
            with col2:
                st.metric("📋 Матчи", matches)
            with col3:
                st.metric("💎 Gold", gold)
            with col4:
                st.metric("🧠 Learning", learning)
        except:
            st.warning("⚠️ Не удалось загрузить статус БД")
        
        st.divider()
        
        # БЫСТРЫЙ СТАРТ
        st.subheader("🚀 Быстрый старт")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Сделать прогноз", use_container_width=True, type="primary"):
                st.session_state.page = 'predictions'
                st.rerun()
        with col2:
            if st.button("🔄 Синхронизация", use_container_width=True):
                st.session_state.page = 'sync'
                st.rerun()
    
    # ============================================================
    # ПРОГНОЗЫ
    # ============================================================
    elif st.session_state.page == 'predictions':
        st.title("📊 Прогнозы матчей")
        st.caption("FAJ Prediction Engine v12.0")
        
        # --- ЗАГРУЗКА КОМАНД ---
        try:
            conn = get_connection()
            teams_df = pd.read_sql("SELECT id, name FROM teams ORDER BY name", conn)
            conn.close()
        except:
            teams_df = pd.DataFrame()
        
        if teams_df.empty:
            st.warning("⚠️ В базе нет команд. Сначала загрузите данные через 'Синхронизацию'.")
            
            if st.button("🔄 Перейти к синхронизации"):
                st.session_state.page = 'sync'
                st.rerun()
        else:
            # --- ИНТЕРФЕЙС ---
            col1, col2 = st.columns(2)
            
            with col1:
                team1 = st.selectbox("🏠 Хозяева", teams_df['name'].tolist(), key="home_team")
            
            with col2:
                team2 = st.selectbox("✈️ Гости", teams_df['name'].tolist(), key="away_team")
            
            # --- ДОПОЛНИТЕЛЬНЫЕ ПАРАМЕТРЫ ---
            with st.expander("⚙️ Дополнительные параметры"):
                league = st.selectbox(
                    "Турнир",
                    ["RPL", "EPL", "La Liga", "Bundesliga", "Serie A", "UCL"],
                    index=0
                )
            
            # --- КНОПКА ПРОГНОЗА ---
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
                                league=league
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
                    
                    # ОСНОВНЫЕ ПОКАЗАТЕЛИ
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        xg = result.get('xg', {})
                        st.metric("🏠 xG Хозяев", f"{xg.get('home', 0):.2f}")
                    
                    with col2:
                        st.metric("🎯 Прогноз", result.get('score', '0:0'))
                    
                    with col3:
                        xg = result.get('xg', {})
                        st.metric("✈️ xG Гостей", f"{xg.get('away', 0):.2f}")
                    
                    # ВЕРОЯТНОСТИ
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
                    
                    # РАСШИРЕННЫЕ МЕТРИКИ
                    extended = result.get('extended', {})
                    if extended:
                        st.subheader("📋 Расширенные метрики")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Обе забьют (BTTS)**")
                            btts = extended.get('btts', {})
                            st.metric("Да", f"{btts.get('yes', 0):.1%}")
                            st.metric("Нет", f"{btts.get('no', 0):.1%}")
                        
                        with col2:
                            st.write("**Тоталы**")
                            total = extended.get('total', {})
                            st.metric("Тотал > 2.5", f"{total.get('over_2_5', 0):.1%}")
                            st.metric("Тотал > 3.5", f"{total.get('over_3_5', 0):.1%}")
                        
                        # ТОП-5 СЧЕТОВ
                        st.subheader("🎯 Топ-5 точных счетов")
                        
                        top_scores = extended.get('top_scores', [])
                        if top_scores:
                            scores_data = []
                            for score in top_scores:
                                scores_data.append({
                                    "№": score.get('rank', 0),
                                    "Счёт": f"{score.get('home', 0)}:{score.get('away', 0)}",
                                    "Вероятность": score.get('prob_percent', '0%')
                                })
                            scores_df = pd.DataFrame(scores_data)
                            st.table(scores_df.set_index("№"))
                    
                    # ДЕТАЛИ
                    with st.expander("📋 Детали прогноза"):
                        st.json(result)
    
    # ============================================================
    # СИНХРОНИЗАЦИЯ
    # ============================================================
    elif st.session_state.page == 'sync':
        st.title("🔄 Синхронизация данных")
        st.caption("Загрузка и обновление данных")
        
        sync = SyncEngine()
        
        try:
            status = sync.get_status()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🏟️ Команды", status.get('teams', 0))
            with col2:
                st.metric("📋 Матчи", status.get('matches', 0))
            with col3:
                st.metric("💎 Gold", status.get('gold_dataset', 0))
        except:
            st.warning("⚠️ Не удалось получить статус")
        
        st.divider()
        
        # ОСНОВНЫЕ ДЕЙСТВИЯ
        st.subheader("🚀 Основные действия")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Полная синхронизация", use_container_width=True, type="primary"):
                with st.spinner("Выполняется полная синхронизация..."):
                    try:
                        result = sync.sync_teams()
                        if result.get('status') == 'success':
                            st.success(f"✅ Загружено {result.get('loaded', 0)} команд")
                            st.rerun()
                        else:
                            st.warning("⚠️ Синхронизация завершена с ошибками")
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
        
        with col2:
            if st.button("🔍 Запустить Audit", use_container_width=True):
                with st.spinner("Выполняется аудит..."):
                    try:
                        result = sync.run_audit()
                        st.success(f"✅ Обработано {result.get('processed', 0)} матчей")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
    
    # ============================================================
    # СИСТЕМА
    # ============================================================
    elif st.session_state.page == 'system':
        st.title("⚙️ Системная информация")
        st.caption("Статус и настройки")
        
        try:
            db = FAJDatabase()
            status_db = db.get_status()
            tables = status_db.get("tables", {})
            
            st.subheader("📊 База данных")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Основные таблицы**")
                st.write(f"- teams: {tables.get('teams', 0)}")
                st.write(f"- matches: {tables.get('matches', 0)}")
                st.write(f"- seasons: {tables.get('seasons', 0)}")
            
            with col2:
                st.write("**Системные таблицы**")
                st.write(f"- gold_dataset: {tables.get('gold_dataset', 0)}")
                st.write(f"- learning_records: {tables.get('learning_records', 0)}")
                st.write(f"- team_passport_meta: {tables.get('team_passport_meta', 0)}")
            
            st.divider()
            
            # ИНФОРМАЦИЯ О ФАЙЛАХ
            db_path = "data/faj.db"
            if os.path.exists(db_path):
                size = os.path.getsize(db_path) / (1024 * 1024)
                st.write(f"**Файл БД:** {db_path}")
                st.write(f"**Размер:** {size:.2f} MB")
            
            st.divider()
            
            # ВЕРСИИ
            st.subheader("📌 Версии компонентов")
            st.write(f"**Платформа:** v{PLATFORM_VERSION}")
            st.write(f"**Ядро:** v{CORE_VERSION}")
            st.write(f"**Pipeline:** v{PIPELINE_VERSION}")
            st.write(f"**Prediction Manager:** v{get_prediction_manager().VERSION}")
            
            st.divider()
            st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            
            if st.button("🔄 Обновить", use_container_width=True):
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Ошибка загрузки системной информации: {e}")

except Exception as e:
    st.error(f"❌ Критическая ошибка: {e}")

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(
    f"⚽ FAJ Platform v{PLATFORM_VERSION} · "
    f"Core v{CORE_VERSION} · "
    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
)

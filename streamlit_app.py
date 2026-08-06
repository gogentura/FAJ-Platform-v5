#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.0 — ПОЛНАЯ БОЕВАЯ ВЕРСИЯ
Интеграция: PredictionManager + DiagnosticService + SyncEngine
"""

import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import config, PLATFORM_VERSION, CORE_VERSION, PIPELINE_VERSION
from app.database import get_connection, FAJDatabase
from app.migrations.learning import ensure_learning_layer
from app.sync_engine import SyncEngine
from app.prediction.prediction_manager import get_prediction_manager
from app.passports.passport_manager import get_passport_manager
from app.core.prediction_pipeline import get_prediction_pipeline

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
    
    if st.button("🔬 Диагностика", use_container_width=True):
        st.session_state.page = 'diagnostic'
    
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
# РОУТИНГ
# ============================================================
try:
    # ============================================================
    # ГЛАВНАЯ
    # ============================================================
    if st.session_state.page == 'home':
        st.title("🏠 FAJ Platform v12")
        st.caption(f"Ядро v{CORE_VERSION} · Pipeline v{PIPELINE_VERSION} · Менеджер v{get_prediction_manager().VERSION}")
        
        st.divider()
        
        # СТАТУС
        conn = get_connection()
        cursor = conn.cursor()
        
        teams = cursor.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        matches = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        gold = cursor.execute("SELECT COUNT(*) FROM gold_dataset").fetchone()[0]
        learning = cursor.execute("SELECT COUNT(*) FROM learning_records").fetchone()[0]
        diagnostic = cursor.execute("SELECT COUNT(*) FROM diagnostic_history").fetchone()[0]
        conn.close()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🏟️ Команды", teams)
        with col2:
            st.metric("📋 Матчи", matches)
        with col3:
            st.metric("💎 Gold", gold)
        with col4:
            st.metric("🧠 Learning", learning)
        with col5:
            st.metric("🔬 Диагностика", diagnostic)
        
        st.divider()
        
        # БЫСТРЫЙ СТАРТ
        st.subheader("🚀 Быстрый старт")
        
        if teams == 0:
            st.warning("⚠️ Нет данных. Перейдите в 'Синхронизация' → 'Обновить систему'")
            
            if st.button("🔄 Перейти к синхронизации", use_container_width=True):
                st.session_state.page = 'sync'
                st.rerun()
        elif matches == 0:
            st.warning("⚠️ Нет матчей. Загрузите данные через синхронизацию")
            
            if st.button("🔄 Перейти к синхронизации", use_container_width=True):
                st.session_state.page = 'sync'
                st.rerun()
        else:
            st.success("✅ Система полностью готова к работе!")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Сделать прогноз", use_container_width=True, type="primary"):
                    st.session_state.page = 'predictions'
                    st.rerun()
            with col2:
                if st.button("🔬 Запустить диагностику", use_container_width=True):
                    st.session_state.page = 'diagnostic'
                    st.rerun()
        
        # ИНФОРМАЦИЯ О СИСТЕМЕ
        st.divider()
        st.subheader("📌 О системе")
        
        st.markdown(f"""
        - **Платформа:** FAJ Platform v{PLATFORM_VERSION}
        - **Ядро:** FAJ Core v{CORE_VERSION}
        - **Pipeline:** v{PIPELINE_VERSION}
        - **Prediction Manager:** v{get_prediction_manager().VERSION}
        - **Passport Manager:** v{get_passport_manager().VERSION}
        - **Модель xG:** v{config.MODEL_VERSION}
        - **Итераций Monte Carlo:** {config.MONTE_CARLO_ITERATIONS}
        """)
    
    # ============================================================
    # ПРОГНОЗЫ — ПОЛНАЯ ИНТЕГРАЦИЯ
    # ============================================================
    elif st.session_state.page == 'predictions':
        st.title("📊 Прогнозы матчей")
        st.caption("FAJ Prediction Engine v12.0")
        
        # --- ЗАГРУЗКА КОМАНД ---
        conn = get_connection()
        teams_df = pd.read_sql("SELECT id, name FROM teams ORDER BY name", conn)
        conn.close()
        
        if teams_df.empty:
            st.warning("⚠️ В базе нет команд. Сначала загрузите данные.")
            
            if st.button("🔄 Перейти к синхронизации"):
                st.session_state.page = 'sync'
                st.rerun()
            return
        
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
                ["RPL", "EPL", "La Liga", "Bundesliga", "Serie A", "UCL", "UEL"],
                index=0
            )
            
            match_type = st.selectbox(
                "Тип матча",
                ["league", "cup", "friendly", "playoff"],
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
                        # ПОЛУЧАЕМ МЕНЕДЖЕР
                        pm = get_prediction_manager()
                        
                        # ВЫПОЛНЯЕМ ПРОГНОЗ
                        result = pm.predict(
                            home_team=team1,
                            away_team=team2,
                            league=league,
                            match_type=match_type
                        )
                        
                        # СОХРАНЯЕМ В СЕССИЮ
                        st.session_state.prediction_result = result
                        
                        if result.get('status') == 'error':
                            st.error(f"❌ Ошибка: {result.get('message')}")
                        else:
                            st.success("✅ Прогноз успешно выполнен!")
                            
                    except Exception as e:
                        st.error(f"❌ Критическая ошибка: {e}")
                        st.session_state.prediction_result = None
        
        # --- ОТОБРАЖЕНИЕ РЕЗУЛЬТАТА ---
        if st.session_state.prediction_result:
            result = st.session_state.prediction_result
            
            if result.get('status') != 'error':
                st.divider()
                st.subheader("📊 Результат прогноза")
                
                # ОСНОВНЫЕ ПОКАЗАТЕЛИ
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "🏠 Хозяева",
                        f"{result.get('xg', {}).get('home', 0):.2f}",
                        delta=f"xG {result.get('xg', {}).get('home', 0):.2f}"
                    )
                
                with col2:
                    st.metric(
                        "✈️ Гости",
                        f"{result.get('xg', {}).get('away', 0):.2f}",
                        delta=f"xG {result.get('xg', {}).get('away', 0):.2f}"
                    )
                
                with col3:
                    st.metric(
                        "🎯 Прогноз",
                        result.get('score', '0:0'),
                        delta=f"FAJ Score"
                    )
                
                with col4:
                    conf = result.get('confidence', {})
                    st.metric(
                        "📊 Уверенность",
                        f"{conf.get('overall', 0.5):.1%}",
                        delta=f"Уровень {conf.get('level', 'MEDIUM')}"
                    )
                
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
                
                # ДЕТАЛИ
                with st.expander("📋 Детали прогноза"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**xG Модель**")
                        st.json(result.get('xg', {}))
                        
                        st.write("**Poisson**")
                        st.json(result.get('poisson', {}))
                    
                    with col2:
                        st.write("**Monte Carlo**")
                        mc = result.get('monte_carlo', {})
                        st.write(f"Итераций: {mc.get('iterations', 0)}")
                        st.write(f"Сходимость: {mc.get('convergence', 0):.3f}")
                        
                        st.write("**Риск**")
                        risk = result.get('risk', {})
                        st.write(f"Уровень: {risk.get('level', 'UNKNOWN')}")
                        st.write(f"Скор: {risk.get('score', 0):.2f}")
                        
                        st.write("**Модели**")
                        st.write(f"Pipeline: v{result.get('pipeline_version', 'unknown')}")
                        st.write(f"Модель xG: v{result.get('model_version', 'unknown')}")
            else:
                st.error(f"❌ Ошибка прогноза: {result.get('message')}")
    
    # ============================================================
    # ДИАГНОСТИКА
    # ============================================================
    elif st.session_state.page == 'diagnostic':
        try:
            from app.pages.diagnostic import main as diagnostic_main
            diagnostic_main()
        except ImportError as e:
            st.error(f"❌ Страница диагностики не найдена: {e}")
            st.info("Создайте файл app/pages/diagnostic.py")
        except Exception as e:
            st.error(f"❌ Ошибка диагностики: {e}")
    
    # ============================================================
    # СИНХРОНИЗАЦИЯ
    # ============================================================
    elif st.session_state.page == 'sync':
        st.title("🔄 Синхронизация данных")
        st.caption("Загрузка и обновление данных")
        
        sync = SyncEngine()
        status = sync.get_status()
        
        # СТАТУС
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏟️ Команды", status.get('teams', 0))
        with col2:
            st.metric("📋 Матчи", status.get('matches', 0))
        with col3:
            st.metric("💎 Gold", status.get('gold_dataset', 0))
        with col4:
            st.metric("🧠 Learning", status.get('learning_records', 0))
        
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
        
        # ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ
        with st.expander("🔧 Дополнительные действия"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🏆 Только команды", use_container_width=True):
                    with st.spinner("Загрузка..."):
                        try:
                            result = sync.sync_teams()
                            st.success(f"✅ {result.get('loaded', 0)} команд")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
            
            with col2:
                if st.button("📊 Построить Gold Dataset", use_container_width=True):
                    with st.spinner("Построение..."):
                        try:
                            result = sync.build_gold_dataset()
                            st.success(f"✅ {result.get('loaded', 0)} записей")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
            
            with col3:
                if st.button("🧹 Очистить кэш", use_container_width=True):
                    st.cache_data.clear()
                    st.success("✅ Кэш очищен")
                    st.rerun()
    
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
                st.write(f"- rounds: {tables.get('rounds', 0)}")
            
            with col2:
                st.write("**Системные таблицы**")
                st.write(f"- gold_dataset: {tables.get('gold_dataset', 0)}")
                st.write(f"- learning_records: {tables.get('learning_records', 0)}")
                st.write(f"- team_passport_meta: {tables.get('team_passport_meta', 0)}")
                st.write(f"- diagnostic_history: {tables.get('diagnostic_history', 0)}")
            
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
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Платформа:** v{PLATFORM_VERSION}")
                st.write(f"**Ядро:** v{CORE_VERSION}")
                st.write(f"**Pipeline:** v{PIPELINE_VERSION}")
                st.write(f"**Модель xG:** v{config.MODEL_VERSION}")
            
            with col2:
                st.write(f"**Prediction Manager:** v{get_prediction_manager().VERSION}")
                st.write(f"**Passport Manager:** v{get_passport_manager().VERSION}")
                st.write(f"**Passport Data:** v{config.PASSPORT_VERSION}")
            
            st.divider()
            
            # КОНФИГУРАЦИЯ
            st.subheader("⚙️ Конфигурация")
            
            with st.expander("Показать настройки"):
                st.json({
                    "MAX_GOALS": config.MAX_GOALS,
                    "MONTE_CARLO_ITERATIONS": config.MONTE_CARLO_ITERATIONS,
                    "SAVE_TO_GOLD_DATASET": config.SAVE_TO_GOLD_DATASET,
                    "DIAGNOSTIC_HISTORY_LIMIT": config.DIAGNOSTIC_HISTORY_LIMIT,
                    "XG_MIN": config.XG_MIN,
                    "XG_MAX": config.XG_MAX,
                    "XG_LEAGUE_MEAN": config.XG_LEAGUE_MEAN
                })
            
            st.divider()
            st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
            
            if st.button("🔄 Обновить", use_container_width=True):
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Ошибка загрузки системной информации: {e}")

except Exception as e:
    st.error(f"❌ Критическая ошибка: {e}")
    st.code(f"Трассировка: {str(e)}", language="python")

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(
    f"⚽ FAJ Platform v{PLATFORM_VERSION} · "
    f"Core v{CORE_VERSION} · "
    f"Pipeline v{PIPELINE_VERSION} · "
    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
)

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
from app.migrations.learning import ensure_learning_layer
from app.sync_engine import SyncEngine
from app.core.prediction_manager import get_prediction_manager
from app.passports.passport_manager import get_passport_manager

# ============================================================
# AUTO BOOTSTRAP — АВТОМАТИЧЕСКАЯ ЗАГРУЗКА
# ============================================================
from app.bootstrap import bootstrap_faj

# FAJ AUTO START — проверка и подготовка системы
bootstrap_result = bootstrap_faj()

# Если что-то пошло не так — показываем
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

try:
    ensure_learning_layer()
except Exception as e:
    st.error(f"⚠️ Ошибка миграции: {e}")

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
    
    if st.button("📋 Паспорта", use_container_width=True):
        st.session_state.page = 'passports'
    
    if st.button("🔄 Синхронизация", use_container_width=True):
        st.session_state.page = 'sync'
    
    if st.button("⚙️ Система", use_container_width=True):
        st.session_state.page = 'system'
    
    st.divider()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        teams = cursor.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        matches = cursor.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        gold = cursor.execute("SELECT COUNT(*) FROM gold_dataset").fetchone()[0]
        conn.close()
        
        st.caption("📊 Статус:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"{'✅' if teams > 0 else '❌'} {teams}")
        with col2:
            st.caption(f"{'✅' if matches > 0 else '❌'} {matches}")
        with col3:
            st.caption(f"{'✅' if gold > 0 else '❌'} {gold}")
        st.caption("Команды | Матчи | Gold")
    except:
        pass

# ============================================================
# СТРАНИЦЫ
# ============================================================

# ----- ГЛАВНАЯ -----
if st.session_state.page == 'home':
    st.title("🏠 FAJ Platform v12")
    st.caption(f"Ядро v{config.CORE_VERSION} · Pipeline v{config.PIPELINE_VERSION}")
    
    # Показываем статус Bootstrap
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
        st.warning("⚠️ Статус БД недоступен")
    
    st.divider()
    
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
        st.warning("⚠️ В базе нет команд. Сначала загрузите данные через 'Синхронизацию'.")
        if st.button("🔄 Перейти к синхронизации"):
            st.session_state.page = 'sync'
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            team1 = st.selectbox("🏠 Хозяева", teams_df['name'].tolist())
        with col2:
            team2 = st.selectbox("✈️ Гости", teams_df['name'].tolist())
        
        with st.expander("⚙️ Дополнительные параметры"):
            league = st.selectbox(
                "Турнир",
                ["RPL", "EPL", "La Liga", "Bundesliga", "Serie A", "UCL"],
                index=0
            )
        
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
                with col3:
                    xg = result.get('xg', {})
                    st.metric("✈️ xG Гостей", f"{xg.get('away', 0):.2f}")
                
                st.subheader("📈 Распределение вероятностей")
                prob = result.get('probability', {})
                prob_df = pd.DataFrame({
                    'Исход': ['Победа хозяев', 'Ничья', 'Победа гостей'],
                    'Вероятность': [prob.get('home', 0), prob.get('draw', 0), prob.get('away', 0)]
                })
                st.bar_chart(prob_df.set_index('Исход'))
                
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
                
                with st.expander("📋 Детали прогноза"):
                    st.json(result)

# ----- ПАСПОРТА -----
elif st.session_state.page == 'passports':
    st.title("📋 Паспорта команд")
    st.caption("FAJ Passport Manager v1.4")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.id,
                t.name as team_name,
                tp.attack,
                tp.defense,
                tp.control,
                tp.tempo,
                tp.press,
                tp.transition,
                tp.finishing,
                tp.goalkeeper,
                tp.squad_quality,
                tp.coach_factor,
                tp.mental,
                tp.faj_rating,
                tp.version,
                tp.source,
                tp.created_at
            FROM teams t
            LEFT JOIN team_passports tp ON t.id = tp.team_id
            ORDER BY t.name
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows or not any(r['team_name'] for r in rows):
            st.warning("⚠️ Паспорта не загружены. Нажмите 'Синхронизация' → 'Полная синхронизация'")
            if st.button("🔄 Перейти к синхронизации"):
                st.session_state.page = 'sync'
                st.rerun()
        else:
            data = []
            for row in rows:
                if row['team_name'] and row['faj_rating'] is not None:
                    data.append({
                        "Команда": row['team_name'],
                        "Атака": round(row['attack'] or 50, 1),
                        "Защита": round(row['defense'] or 50, 1),
                        "Контроль": round(row['control'] or 50, 1),
                        "Темп": round(row['tempo'] or 50, 1),
                        "Прессинг": round(row['press'] or 50, 1),
                        "Реализация": round(row['finishing'] or 50, 1),
                        "FAJ Rating": round(row['faj_rating'] or 0, 1),
                        "Версия": row['version'] or 'N/A'
                    })
            
            if data:
                df = pd.DataFrame(data)
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "FAJ Rating": st.column_config.NumberColumn(
                            "FAJ Rating",
                            help="Рейтинг команды от 0 до 100",
                            format="%.1f"
                        )
                    }
                )
                
                st.caption(f"📊 Всего команд: {len(data)}")
                
                st.divider()
                st.subheader("🔍 Детальный просмотр паспорта")
                
                selected_team = st.selectbox(
                    "Выберите команду",
                    [row['team_name'] for row in rows if row['team_name']]
                )
                
                if selected_team:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT *
                        FROM team_passports tp
                        JOIN teams t ON tp.team_id = t.id
                        WHERE t.name = ?
                        ORDER BY CAST(REPLACE(tp.version, 'v', '') AS FLOAT) DESC
                        LIMIT 1
                    """, (selected_team,))
                    
                    detail_row = cursor.fetchone()
                    conn.close()
                    
                    if detail_row:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write("**📊 Базовые параметры**")
                            st.write(f"Атака: {detail_row['attack'] or 50}")
                            st.write(f"Защита: {detail_row['defense'] or 50}")
                            st.write(f"Контроль: {detail_row['control'] or 50}")
                            st.write(f"Темп: {detail_row['tempo'] or 50}")
                        with col2:
                            st.write("**🎯 Дополнительные параметры**")
                            st.write(f"Реализация: {detail_row['finishing'] or 50}")
                            st.write(f"FAJ Rating: {detail_row['faj_rating'] or 0}")
                            st.write(f"Версия: {detail_row['version'] or 'N/A'}")
            else:
                st.info("ℹ️ Паспорта загружены, но данные отсутствуют")
                
    except Exception as e:
        st.error(f"❌ Ошибка загрузки паспортов: {e}")

# ----- СИНХРОНИЗАЦИЯ -----
elif st.session_state.page == 'sync':
    st.title("🔄 Синхронизация данных")
    
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
        st.warning("⚠️ Статус недоступен")
    
    st.divider()
    
    if st.button("🔄 Полная синхронизация", type="primary", use_container_width=True):
        with st.spinner("Синхронизация..."):
            try:
                result = sync.sync_teams()
                st.success(f"✅ {result.get('created', 0)} создано, {result.get('updated', 0)} обновлено")
                st.rerun()
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
        with col2:
            st.write("**Системные**")
            st.write(f"- gold_dataset: {tables.get('gold_dataset', 0)}")
            st.write(f"- team_passports: {tables.get('team_passports', 0)}")
        
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

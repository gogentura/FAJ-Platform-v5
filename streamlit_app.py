#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform — Минимальная рабочая версия
Главная как панель управления с подсказкой следующего шага
"""

import streamlit as st
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import FAJDatabase
from app.migrations.learning import ensure_learning_layer
from app.sync_engine import SyncEngine

# ============================================================
# НАСТРОЙКА
# ============================================================
st.set_page_config(
    page_title="FAJ Platform",
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
    print(f"⚠️ Learning migration: {e}")

# ============================================================
# БОКОВОЕ МЕНЮ
# ============================================================
with st.sidebar:
    st.title("⚽ FAJ")
    st.caption("Аналитическая система")
    
    st.divider()
    
    page = st.radio(
        "📌 Меню",
        ["🏠 Главная", "🔄 Синхронизация", "⚙️ Система"],
        index=0
    )
    
    st.divider()
    
    # Статус в боковой панели (краткий)
    try:
        sync = SyncEngine()
        status = sync.get_status()
        
        # Три индикатора
        col1, col2, col3 = st.columns(3)
        with col1:
            if status['teams'] > 0:
                st.write("🟢")
            else:
                st.write("🔴")
        with col2:
            if status['matches'] > 0:
                st.write("🟢")
            else:
                st.write("🔴")
        with col3:
            if status['gold_dataset'] > 0:
                st.write("🟢")
            else:
                st.write("🟡")
        
        st.caption("Команды | Матчи | Gold")
    except:
        st.caption("⚠️ Статус недоступен")

# ============================================================
# СТРАНИЦА: ГЛАВНАЯ
# ============================================================
if page == "🏠 Главная":
    st.title("🏠 FAJ Platform")
    st.caption("Панель управления")
    
    st.divider()
    
    # Получаем статус
    sync = SyncEngine()
    status = sync.get_status()
    
    # ============================================================
    # СТАТУС СИСТЕМЫ (цветные индикаторы)
    # ============================================================
    st.subheader("📊 Состояние системы")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if status['teams'] > 0:
            st.markdown("🟢 **Команды**")
            st.caption(f"{status['teams']} шт.")
        else:
            st.markdown("🔴 **Команды**")
            st.caption("не загружены")
    
    with col2:
        if status['matches'] > 0:
            st.markdown("🟢 **Матчи**")
            st.caption(f"{status['matches']} шт.")
        else:
            st.markdown("🔴 **Матчи**")
            st.caption("не загружены")
    
    with col3:
        if status['gold_dataset'] > 0:
            st.markdown("🟢 **Gold Dataset**")
            st.caption(f"{status['gold_dataset']} зап.")
        else:
            st.markdown("🟡 **Gold Dataset**")
            st.caption("не построен")
    
    with col4:
        if status['learning_records'] > 0:
            st.markdown("🟢 **Learning**")
            st.caption(f"{status['learning_records']} зап.")
        else:
            st.markdown("🟡 **Learning**")
            st.caption("не запущен")
    
    st.divider()
    
    # ============================================================
    # СЛЕДУЮЩЕЕ ДЕЙСТВИЕ
    # ============================================================
    st.subheader("🎯 Следующее действие")
    
    # Определяем следующий шаг
    if status['teams'] == 0:
        st.warning("⚠️ Команды не загружены")
        st.info("Перейдите в 'Синхронизация' → 'Загрузить команды РПЛ'")
        
    elif status['matches'] == 0:
        st.warning("⚠️ Матчи не загружены")
        st.info("Перейдите в 'Синхронизация' → 'Загрузить матчи'")
        
    elif status['gold_dataset'] == 0:
        st.warning("⚠️ Нет данных для обучения")
        st.info("Перейдите в 'Синхронизация' → 'Построить Gold Dataset'")
        
    elif status['learning_records'] == 0:
        st.warning("⚠️ Audit не запускался")
        st.info("Перейдите в 'Синхронизация' → 'Запустить Audit'")
        
    else:
        st.success("✅ Все системы готовы!")
        st.info("🔄 Обновите данные или дождитесь новых матчей")
    
    st.divider()
    
    # ============================================================
    # БЫСТРАЯ ИНФОРМАЦИЯ
    # ============================================================
    st.subheader("📋 Последние события")
    
    try:
        db = FAJDatabase()
        matches = db.get_matches()
        
        if matches:
            # Показываем последние 3 матча
            for m in matches[:3]:
                home = db.get_team(m['home_team_id'])
                away = db.get_team(m['away_team_id'])
                home_name = home['name'] if home else '?'
                away_name = away['name'] if away else '?'
                
                if m['status'] == 'finished':
                    st.write(f"✅ {home_name} {m['actual_home']}:{m['actual_away']} {away_name}")
                else:
                    st.write(f"📅 {home_name} — {away_name} ({m['status']})")
        else:
            st.caption("Нет матчей")
    except:
        st.caption("Ошибка загрузки")

# ============================================================
# СТРАНИЦА: СИНХРОНИЗАЦИЯ
# ============================================================
elif page == "🔄 Синхронизация":
    st.title("🔄 Синхронизация")
    st.caption("Загрузка и обновление данных")
    
    # Показываем статус
    sync = SyncEngine()
    status = sync.get_status()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Команды", status['teams'])
    with col2:
        st.metric("Матчи", status['matches'])
    with col3:
        st.metric("Gold Dataset", status['gold_dataset'])
    
    st.divider()
    
    # ============================================================
    # ШАГ 1: КОМАНДЫ
    # ============================================================
    st.subheader("🏆 Шаг 1. Команды")
    
    if status['teams'] > 0:
        st.success(f"✅ {status['teams']} команд загружено")
    else:
        if st.button("📥 Загрузить команды РПЛ", use_container_width=True):
            with st.spinner("Загрузка..."):
                result = sync.sync_teams_rpl()
                if result['status'] == 'success':
                    st.success(f"✅ Загружено {result['loaded']} команд!")
                    st.rerun()
                else:
                    st.error("❌ Ошибка загрузки")
    
    st.divider()
    
    # ============================================================
    # ШАГ 2: МАТЧИ
    # ============================================================
    st.subheader("⚽ Шаг 2. Матчи")
    
    if status['matches'] > 0:
        st.success(f"✅ {status['matches']} матчей загружено")
    else:
        st.warning("⚠️ Матчи не загружены")
        st.info("Данные будут загружены после обновления парсера")
        # Пока кнопка заглушка
        if st.button("📥 Загрузить матчи (в разработке)", use_container_width=True):
            st.info("Функция будет добавлена после настройки парсера")
    
    st.divider()
    
    # ============================================================
    # ШАГ 3: GOLD DATASET
    # ============================================================
    st.subheader("🧠 Шаг 3. Gold Dataset")
    
    if status['gold_dataset'] > 0:
        st.success(f"✅ {status['gold_dataset']} записей в Gold Dataset")
    else:
        st.warning("⚠️ Gold Dataset не построен")
        if st.button("📊 Построить Gold Dataset", use_container_width=True):
            with st.spinner("Построение..."):
                st.info("Функция будет добавлена после загрузки прогнозов")
                # result = sync.build_gold_dataset()
    
    st.divider()
    
    # ============================================================
    # ШАГ 4: AUDIT
    # ============================================================
    st.subheader("🔍 Шаг 4. Audit")
    
    if status['learning_records'] > 0:
        st.success(f"✅ {status['learning_records']} записей в Learning Records")
    else:
        st.warning("⚠️ Audit не запускался")
        if st.button("🔍 Запустить Audit", use_container_width=True):
            with st.spinner("Аудит..."):
                from app.audit_engine import audit_all_pending
                results = audit_all_pending()
                st.success(f"✅ Аудировано {len(results)} матчей")
                st.rerun()

# ============================================================
# СТРАНИЦА: СИСТЕМА
# ============================================================
elif page == "⚙️ Система":
    st.title("⚙️ Система")
    st.caption("Статус базы данных")
    
    try:
        db = FAJDatabase()
        status_db = db.get_status()
        tables = status_db.get("tables", {})
        
        st.subheader("📊 Таблицы")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Основные**")
            st.write(f"- teams: {tables.get('teams', 0)}")
            st.write(f"- matches: {tables.get('matches', 0)}")
            st.write(f"- seasons: {tables.get('seasons', 0)}")
            st.write(f"- rounds: {tables.get('rounds', 0)}")
        
        with col2:
            st.write("**Обучение**")
            st.write(f"- gold_dataset: {tables.get('gold_dataset', 0)}")
            st.write(f"- learning_records: {tables.get('learning_records', 0)}")
        
        st.divider()
        
        # Информация о БД
        import os
        db_path = "data/faj.db"
        if os.path.exists(db_path):
            size = os.path.getsize(db_path) / 1024
            st.write(f"**Файл БД:** {db_path}")
            st.write(f"**Размер:** {size:.2f} KB")
        else:
            st.error("Файл БД не найден")
        
        st.write(f"**Версия:** FAJ v11.2.1 + Learning Layer")
        st.write(f"**Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        if st.button("🔄 Обновить", use_container_width=True):
            st.rerun()
            
    except Exception as e:
        st.error(f"Ошибка: {e}")

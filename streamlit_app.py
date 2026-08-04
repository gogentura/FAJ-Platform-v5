#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform — Минимальная рабочая версия
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
    st.error(f"⚠️ Ошибка миграции: {e}")

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
    
    try:
        sync = SyncEngine()
        status = sync.get_status()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("🟢" if status['teams'] > 0 else "🔴")
        with col2:
            st.write("🟢" if status['matches'] > 0 else "🔴")
        with col3:
            st.write("🟢" if status['gold_dataset'] > 0 else "🟡")
        st.caption("Команды | Матчи | Gold")
    except Exception as e:
        st.caption(f"⚠️ Статус недоступен: {e}")

# ============================================================
# ГЛАВНАЯ
# ============================================================
if page == "🏠 Главная":
    st.title("🏠 FAJ Platform")
    st.caption("Панель управления")
    
    st.divider()
    
    sync = SyncEngine()
    status = sync.get_status()
    
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
    
    st.subheader("🎯 Следующее действие")
    
    if status['teams'] == 0:
        st.warning("⚠️ Команды не загружены")
        st.info("Перейдите в 'Синхронизация' → 'Обновить систему'")
    elif status['matches'] == 0:
        st.warning("⚠️ Матчи не загружены")
        st.info("Перейдите в 'Синхронизация' → 'Обновить систему'")
    elif status['gold_dataset'] == 0:
        st.warning("⚠️ Gold Dataset не построен")
        st.info("Перейдите в 'Синхронизация' → 'Построить Gold Dataset'")
    elif status['learning_records'] == 0:
        st.warning("⚠️ Audit не запускался")
        st.info("Перейдите в 'Синхронизация' → 'Запустить Audit'")
    else:
        st.success("✅ Все системы готовы!")

# ============================================================
# СИНХРОНИЗАЦИЯ
# ============================================================
elif page == "🔄 Синхронизация":
    st.title("🔄 Синхронизация")
    st.caption("Управление данными")
    
    sync = SyncEngine()
    status = sync.get_status()
    
    # ============================================================
    # ОСНОВНАЯ КНОПКА
    # ============================================================
    st.subheader("🚀 Главное действие")
    
    if st.button("🔄 Обновить систему", use_container_width=True):
        with st.spinner("Выполняется синхронизация..."):
            try:
                result = sync.sync_teams()
                if result['status'] == 'success':
                    st.success(f"✅ Загружено {result['loaded']} команд, {result['passports']} паспортов, {result['meta']} мета-записей")
                else:
                    st.warning("⚠️ Синхронизация завершена с ошибками")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # ============================================================
    # ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ
    # ============================================================
    st.subheader("🔧 Дополнительно")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏆 Только команды", use_container_width=True):
            with st.spinner("Загрузка..."):
                try:
                    result = sync.sync_teams()
                    st.success(f"✅ {result['loaded']} команд, {result['passports']} паспортов")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
        
        if st.button("📘 Загрузить паспорта", use_container_width=True):
            with st.spinner("Загрузка..."):
                try:
                    result = sync.sync_passports()
                    st.success(f"✅ {result['updated']} паспортов")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    with col2:
        if st.button("📊 Построить Gold Dataset", use_container_width=True):
            with st.spinner("Построение..."):
                try:
                    result = sync.build_gold_dataset()
                    st.success(f"✅ {result['loaded']} записей")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
        
        if st.button("🔍 Запустить Audit", use_container_width=True):
            with st.spinner("Аудит..."):
                try:
                    result = sync.run_audit()
                    st.success(f"✅ {result['processed']} матчей")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # ============================================================
    # СТАТУС
    # ============================================================
    st.subheader("📊 Текущий статус")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Команды", status['teams'])
    with col2:
        st.metric("Матчи", status['matches'])
    with col3:
        st.metric("Gold Dataset", status['gold_dataset'])

# ============================================================
# СИСТЕМА
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
            st.write(f"- team_passport_meta: {tables.get('team_passport_meta', 0)}")
        
        st.divider()
        
        import os
        db_path = "data/faj.db"
        if os.path.exists(db_path):
            size = os.path.getsize(db_path) / 1024
            st.write(f"**Файл БД:** {db_path}")
            st.write(f"**Размер:** {size:.2f} KB")
        
        st.write(f"**Версия:** FAJ v11.2.1 + Learning Layer")
        st.write(f"**Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        if st.button("🔄 Обновить"):
            st.rerun()
            
    except Exception as e:
        st.error(f"Ошибка: {e}")

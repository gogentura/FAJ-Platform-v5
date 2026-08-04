#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform — Главное приложение
"""

import streamlit as st
import sys
import os

# Добавляем корневую папку в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# ИМПОРТЫ
# ============================================================
from app.database import FAJDatabase
from app.migrations.learning import ensure_learning_layer

# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================
st.set_page_config(
    page_title="FAJ Platform",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# АВТОМАТИЧЕСКАЯ МИГРАЦИЯ (без дублей)
# ============================================================
try:
    ensure_learning_layer()
except Exception as e:
    print(f"⚠️ Learning migration: {e}")

# ============================================================
# БОКОВАЯ ПАНЕЛЬ
# ============================================================
with st.sidebar:
    st.title("⚽ FAJ Platform")
    st.caption("Adaptive Football Intelligence")
    
    st.divider()
    
    # Простая навигация через radio
    page = st.radio(
        "📌 Навигация",
        ["🏠 Главная", "⚙️ Система", "📥 Загрузка данных"],
        index=0
    )
    
    st.divider()
    
    # Статус
    try:
        db = FAJDatabase()
        status = db.get_status()
        tables = status.get("tables", {})
        
        st.caption(f"📊 gold_dataset: {tables.get('gold_dataset', 0)}")
        st.caption(f"📝 learning_records: {tables.get('learning_records', 0)}")
    except:
        st.caption("⚠️ Ошибка загрузки статуса")

# ============================================================
# РОУТИНГ СТРАНИЦ
# ============================================================

if page == "🏠 Главная":
    # ============================================================
    # ОСНОВНАЯ СТРАНИЦА
    # ============================================================
    st.title("⚽ FAJ Platform")
    st.subheader("🧠 Адаптивная система прогнозирования")

    # Статистика
    try:
        db = FAJDatabase()
        status = db.get_status()
        tables = status.get("tables", {})

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📊 Всего таблиц", len(tables))

        with col2:
            st.metric("🧠 gold_dataset", tables.get("gold_dataset", 0))

        with col3:
            st.metric("📝 learning_records", tables.get("learning_records", 0))

        with col4:
            st.metric("📋 migrations", tables.get("migrations", 0))
    except Exception as e:
        st.error(f"Ошибка загрузки статистики: {e}")

    st.divider()

    # ============================================================
    # ИНФОРМАЦИЯ О СИСТЕМЕ
    # ============================================================
    st.subheader("ℹ️ О системе")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Версия:** FAJ v11.2.1 + Learning Layer")
        st.write("**База данных:** SQLite")

    with col2:
        import datetime
        st.write(f"**Дата:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
        st.write(f"**Статус:** ✅ Работает")

    st.divider()

    # ============================================================
    # БЫСТРЫЙ СТАРТ
    # ============================================================
    st.subheader("🚀 Быстрый старт")
    st.info("Используйте боковое меню для навигации по разделам")

    st.divider()
    st.caption("© 2026 FAJ Platform | Football Adaptive Intelligence")

elif page == "⚙️ Система":
    # ============================================================
    # СТРАНИЦА СИСТЕМЫ
    # ============================================================
    from app.pages.system import render as render_system
    render_system()

elif page == "📥 Загрузка данных":
    # ============================================================
    # СТРАНИЦА ЗАГРУЗКИ
    # ============================================================
    from app.pages.loading import render as render_loading
    render_loading()

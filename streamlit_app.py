#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform — Диагностика миграции
"""

import streamlit as st
import sys
import os
import traceback

# Добавляем корневую папку в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="FAJ Диагностика",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Диагностика FAJ")
st.caption("Проверка структуры проекта и миграции")

# ============================================================
# 1. ПРОВЕРКА ФАЙЛОВОЙ СТРУКТУРЫ
# ============================================================
st.subheader("📁 1. Проверка файлов")

files_to_check = [
    ("app/__init__.py", "Папка app как пакет"),
    ("app/migrations/__init__.py", "Папка migrations как пакет"),
    ("app/migrations/learning.py", "Файл миграции"),
    ("app/database.py", "Файл базы данных"),
]

all_ok = True
for file_path, description in files_to_check:
    if os.path.exists(file_path):
        st.success(f"✅ {description} — найден")
    else:
        st.error(f"❌ {description} — НЕ НАЙДЕН! (путь: {file_path})")
        all_ok = False

st.divider()

# ============================================================
# 2. ПРОВЕРКА ИМПОРТОВ
# ============================================================
st.subheader("📦 2. Проверка импортов")

try:
    from app.database import DB_FILE
    st.success(f"✅ app.database импортирован. Путь к БД: {DB_FILE}")
except Exception as e:
    st.error(f"❌ Ошибка импорта app.database: {e}")

try:
    from app.migrations.learning import ensure_learning_layer
    st.success("✅ app.migrations.learning импортирован")
except Exception as e:
    st.error(f"❌ Ошибка импорта app.migrations.learning: {e}")
    st.code(traceback.format_exc())

st.divider()

# ============================================================
# 3. ЗАПУСК МИГРАЦИИ С ВЫВОДОМ ОШИБОК
# ============================================================
st.subheader("🚀 3. Запуск миграции")

if st.button("🔧 Запустить миграцию сейчас", use_container_width=True):
    with st.spinner("Выполняется миграция..."):
        try:
            from app.migrations.learning import apply_learning_layer
            result = apply_learning_layer()
            if result:
                st.success("✅ Миграция выполнена успешно!")
            else:
                st.error("❌ Миграция вернула False")
        except Exception as e:
            st.error("❌ КРИТИЧЕСКАЯ ОШИБКА при миграции:")
            st.code(traceback.format_exc())

st.divider()

# ============================================================
# 4. ПРОВЕРКА ТАБЛИЦ В БАЗЕ ДАННЫХ
# ============================================================
st.subheader("📊 4. Проверка таблиц в базе данных")

try:
    from app.database import FAJDatabase
    import sqlite3

    db = FAJDatabase()
    status = db.get_status()
    tables = status.get("tables", {})

    required_tables = ["gold_dataset", "learning_records", "migrations"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("gold_dataset", tables.get("gold_dataset", 0))
    with col2:
        st.metric("learning_records", tables.get("learning_records", 0))
    with col3:
        st.metric("migrations", tables.get("migrations", 0))

    all_exists = all(t in tables for t in required_tables)
    if all_exists:
        st.success("✅ Все необходимые таблицы найдены!")
    else:
        missing = [t for t in required_tables if t not in tables]
        st.warning(f"⚠️ Отсутствуют таблицы: {missing}")

    # Проверяем наличие файла БД
    if os.path.exists("data/faj.db"):
        size = os.path.getsize("data/faj.db") / 1024
        st.info(f"📁 Файл БД: data/faj.db ({size:.2f} KB)")
    else:
        st.error("❌ Файл БД data/faj.db не найден!")

except Exception as e:
    st.error(f"❌ Ошибка при проверке таблиц: {e}")
    st.code(traceback.format_exc())

st.divider()
st.caption("FAJ — Диагностический режим")

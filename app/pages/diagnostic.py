#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Диагностика FAJ Database
"""

import streamlit as st
import os

from app.database import FAJDatabase, DB_FILE


def main():
    st.title("🔧 Диагностика FAJ Database")

    st.subheader("📁 Путь к БД")
    st.code(DB_FILE)

    st.subheader("📊 Статус файла")
    if os.path.exists(DB_FILE):
        size = os.path.getsize(DB_FILE)
        st.success(f"✅ Файл существует! Размер: {size / 1024:.2f} KB")
    else:
        st.error("❌ Файл НЕ СУЩЕСТВУЕТ")

    st.subheader("📊 Попытка инициализации")
    try:
        db = FAJDatabase()
        status = db.get_status()
        st.success(f"✅ Database initialized: {status['status']}")
        st.json(status)
    except Exception as e:
        st.error(f"❌ Ошибка инициализации: {e}")

    st.subheader("📁 Содержимое data/")
    try:
        files = os.listdir(os.path.dirname(DB_FILE))
        st.write(files)
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()

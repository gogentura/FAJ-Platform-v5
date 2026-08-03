#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11
System Page

Проверка статуса базы данных и системы
"""

import streamlit as st
import os
from datetime import datetime

from app.storage import get_storage


def render():
    st.title("⚙️ FAJ System v11")
    st.caption("Статус базы данных и системы")

    storage = get_storage()
    status = storage.get_status()

    # =========================================================
    # 1. СТАТУС БАЗЫ ДАННЫХ
    # =========================================================
    st.subheader("🗄️ База данных")

    col1, col2 = st.columns(2)
    with col1:
        if status.get("status") == "ACTIVE":
            st.success("✅ Статус: ACTIVE")
        else:
            st.error("❌ Статус: ERROR")

        st.write(f"**Файл:** {status.get('file', '—')}")

    with col2:
        db_size = 0
        if os.path.exists(status.get('file', '')):
            db_size = os.path.getsize(status.get('file', '')) / 1024
        st.metric("Размер БД", f"{db_size:.2f} KB")

    st.divider()

    # =========================================================
    # 2. ТАБЛИЦЫ
    # =========================================================
    st.subheader("📊 Таблицы")

    tables = status.get("tables", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Сезоны", tables.get("seasons", 0))
    with col2:
        st.metric("Туры", tables.get("rounds", 0))
    with col3:
        st.metric("Матчи", tables.get("matches", 0))
    with col4:
        st.metric("Память", tables.get("faj_memory", 0))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Команды", tables.get("teams", 0))
    with col2:
        st.metric("Паспорта", tables.get("team_passports", 0))
    with col3:
        st.metric("Прогнозы", tables.get("predictions", 0))
    with col4:
        st.metric("Журнал", tables.get("journal", 0))

    st.divider()

    # =========================================================
    # 3. ИНФОРМАЦИЯ О СИСТЕМЕ
    # =========================================================
    st.subheader("ℹ️ О системе")

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Версия:** FAJ v11")
        st.write(f"**Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    with col2:
        st.write(f"**База:** SQLite")
        st.write(f"**Статус:** {'✅ Работает' if status.get('status') == 'ACTIVE' else '❌ Ошибка'}")

    st.divider()

    # =========================================================
    # 4. ПОСЛЕДНИЕ ЗАПИСИ (для проверки)
    # =========================================================
    st.subheader("📋 Последние записи")

    with st.expander("Последние матчи"):
        matches = storage.get_matches()
        if matches:
            for m in matches[:5]:
                st.write(f"- {m['home']} — {m['away']} | Статус: {m['status']}")
        else:
            st.write("Нет матчей")

    with st.expander("Последние записи памяти"):
        # Здесь можно добавить вывод памяти
        st.write("Память пока пуста")


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":
    render()

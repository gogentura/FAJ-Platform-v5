#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ System Page — Статус базы данных
"""

import streamlit as st
import os
import sqlite3
from datetime import datetime

from app.database import DB_FILE, FAJDatabase


def render():
    st.title("⚙️ FAJ Система")
    st.caption("Статус базы данных и системы")

    db = FAJDatabase()
    status = db.get_status()
    tables = status.get("tables", {})

    # =========================================================
    # СТАТУС БАЗЫ
    # =========================================================
    st.subheader("🗄️ База данных")

    col1, col2 = st.columns(2)
    with col1:
        st.success("✅ Статус: ACTIVE")
        st.write(f"**Файл:** {DB_FILE}")

    with col2:
        if os.path.exists(DB_FILE):
            size = os.path.getsize(DB_FILE) / 1024
            st.metric("Размер БД", f"{size:.2f} KB")
        else:
            st.error("Файл БД не найден")

    st.divider()

    # =========================================================
    # ТАБЛИЦЫ
    # =========================================================
    st.subheader("📊 Таблицы")

    main = ["seasons", "rounds", "matches", "teams"]
    passport = ["team_base", "team_dynamic", "team_identity", "tactical_matchup", "player_impact"]
    pred = ["predictions", "prediction_scores", "prediction_distributions", "expert_predictions", "match_predictions"]
    learning = ["gold_dataset", "learning_records", "learning_events", "audit_log", "migrations"]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("**📋 Основные**")
        for t in main:
            if t in tables:
                st.metric(t, tables[t])

    with col2:
        st.markdown("**📘 Паспорта**")
        for t in passport:
            if t in tables:
                st.metric(t, tables[t])

    with col3:
        st.markdown("**📊 Прогнозы**")
        for t in pred:
            if t in tables:
                st.metric(t, tables[t])

    with col4:
        st.markdown("**🧠 Обучение**")
        for t in learning:
            if t in tables:
                st.metric(t, tables[t])

    st.divider()

    # =========================================================
    # ПОСЛЕДНИЕ ЗАПИСИ GOLD_DATASET
    # =========================================================
    st.subheader("📋 Последние записи gold_dataset")

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, home_team, away_team, faj_score, actual_score, status
            FROM gold_dataset
            ORDER BY id DESC LIMIT 10
        """)
        records = cursor.fetchall()
        conn.close()

        if records:
            for r in records:
                icon = "✅" if r['status'] == 'audited' else "⏳" if r['status'] == 'pending' else "📊"
                actual = r['actual_score'] if r['actual_score'] else "—"
                st.write(f"{icon} {r['home_team']} — {r['away_team']} | FAJ: {r['faj_score']} | Факт: {actual} | {r['status']}")
        else:
            st.info("Нет записей в gold_dataset. Загрузите данные через 'Загрузка данных'")
    except Exception as e:
        st.warning(f"Ошибка: {e}")

    st.divider()

    # =========================================================
    # О СИСТЕМЕ
    # =========================================================
    st.subheader("ℹ️ О системе")

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Версия:** FAJ v11.2.1 + Learning Layer")
    with col2:
        st.write(f"**Дата:** {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    if st.button("🔄 Обновить", use_container_width=True):
        st.rerun()


if __name__ == "__main__":
    render()

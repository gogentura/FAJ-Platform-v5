#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11.1
System Page

Проверка статуса базы данных и системы
"""

import streamlit as st
import os
from datetime import datetime

from app.database import FAJDatabase


def render():
    st.title("⚙️ FAJ System v11")
    st.caption("Статус базы данных и системы")

    db = FAJDatabase()
    status = db.get_status()

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
    # 2. ТАБЛИЦЫ (все, включая новые)
    # =========================================================
    st.subheader("📊 Таблицы")

    tables = status.get("tables", {})

    # Группируем таблицы для красивого отображения
    main_tables = ["seasons", "rounds", "matches", "teams"]
    passport_tables = ["team_base", "team_dynamic", "team_identity", "tactical_matchup"]
    prediction_tables = ["predictions", "prediction_scores", "prediction_distributions", "expert_predictions"]
    learning_tables = ["gold_dataset", "learning_records", "learning_memory", "journal"]
    other_tables = ["match_predictions", "match_events", "players", "player_events",
                    "team_competition_profile", "team_events", "team_history",
                    "model_parameters", "xg_memory", "match_snapshots"]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("**📋 Основные**")
        for table in main_tables:
            if table in tables:
                st.metric(table, tables[table])

    with col2:
        st.markdown("**📘 Паспорта**")
        for table in passport_tables:
            if table in tables:
                st.metric(table, tables[table])

    with col3:
        st.markdown("**📊 Прогнозы**")
        for table in prediction_tables:
            if table in tables:
                st.metric(table, tables[table])

    with col4:
        st.markdown("**🧠 Обучение**")
        for table in learning_tables:
            if table in tables:
                st.metric(table, tables[table])

    # Остальные таблицы
    with st.expander("📂 Другие таблицы"):
        for table in other_tables:
            if table in tables:
                st.write(f"{table}: {tables[table]}")

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
    # 4. ПОСЛЕДНИЕ ЗАПИСИ
    # =========================================================
    st.subheader("📋 Последние записи")

    with st.expander("Последние матчи"):
        matches = db.get_matches()
        if matches:
            for m in matches[:5]:
                home = db.get_team(m['home_team_id'])
                away = db.get_team(m['away_team_id'])
                home_name = home['name'] if home else '?'
                away_name = away['name'] if away else '?'
                st.write(f"- {home_name} — {away_name} | Статус: {m['status']}")
        else:
            st.write("Нет матчей")

    with st.expander("Последние записи памяти"):
        # Получаем данные из gold_dataset
        conn = db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM gold_dataset ORDER BY id DESC LIMIT 5")
            gold_data = cursor.fetchall()
            if gold_data:
                for row in gold_data:
                    st.write(f"- {row['home_team']} — {row['away_team']} | {row['faj_score']} → {row['actual_score']}")
            else:
                st.write("Нет данных в gold_dataset")
        except:
            st.write("Таблица gold_dataset пока не создана")
        conn.close()


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":
    render()

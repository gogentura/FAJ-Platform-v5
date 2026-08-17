#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Очистка турнирных данных через UI.
"""

import streamlit as st
import sqlite3
import os
import shutil
from datetime import datetime

from app.database import DB_FILE, get_connection


# ============================================================
# СПИСОК ТАБЛИЦ FAJ BASE (НЕ УДАЛЯЕМ)
# ============================================================
FAJ_BASE_TABLES = {
    "teams",
    "seasons",
    "team_passports",
    "team_passport_meta",
    "team_base",
    "team_dynamic",
    "team_identity",
    "tactical_matchup",
    "model_parameters",
    "xg_memory",
    "schema_migrations",
    "diagnostic_history",
    "players",
    "player_events",
    "team_events",
    "team_history",
    "player_impact",
    "team_competition_profile",
}

# ============================================================
# ТАБЛИЦЫ LEARNING (МОЖНО ОЧИСТИТЬ ИЛИ ОСТАВИТЬ)
# ============================================================
LEARNING_TABLES = {
    "learning_memory",
    "learning_records",
    "learning_events",
}

# ============================================================
# СПИСОК ТУРНИРНЫХ ТАБЛИЦ (УДАЛЯЕМ)
# ============================================================
TURNAMENT_TABLES = {
    "rounds",
    "matches",
    "match_results",
    "match_statistics",
    "predictions",
    "prediction_scores",
    "prediction_distributions",
    "expert_predictions",
    "standings",
    "match_predictions",
    "match_snapshots",
    "team_form_history",
    "team_dynamics",
    "gold_dataset",
    "audit_log",
    "journal",
    "prediction_validation",
    "match_events",
    "migrations",  # старая таблица миграций (технический мусор)
}


def get_all_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_table_counts(tables):
    counts = {}
    conn = get_connection()
    cursor = conn.cursor()
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row = cursor.fetchone()
            counts[table] = row[0] if row else 0
        except sqlite3.OperationalError:
            counts[table] = 0
    conn.close()
    return counts


def reset_tournament_data(clear_learning=False):
    backup_path = DB_FILE + ".backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(DB_FILE, backup_path)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF")

    tables = get_all_tables()
    cleared = []

    for table in tables:
        if table in TURNAMENT_TABLES:
            try:
                cursor.execute(f"DELETE FROM {table}")
                cleared.append(table)
            except sqlite3.OperationalError:
                pass
        elif table in LEARNING_TABLES and clear_learning:
            try:
                cursor.execute(f"DELETE FROM {table}")
                cleared.append(table)
            except sqlite3.OperationalError:
                pass

    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()

    return {
        "backup_path": backup_path,
        "cleared": cleared,
        "count": len(cleared),
    }


def main():
    st.title("🧹 Очистка турнирных данных")
    st.caption("Эта операция удалит все туры, матчи, результаты, прогнозы и статистику, но оставит команды, паспорта и параметры модели.")

    all_tables = get_all_tables()
    if not all_tables:
        st.warning("База данных пуста или не найдена.")
        return

    # Категоризация
    base_tables = [t for t in all_tables if t in FAJ_BASE_TABLES]
    learning_tables = [t for t in all_tables if t in LEARNING_TABLES]
    turnament_tables = [t for t in all_tables if t in TURNAMENT_TABLES]
    unknown_tables = [t for t in all_tables if t not in FAJ_BASE_TABLES and t not in LEARNING_TABLES and t not in TURNAMENT_TABLES]

    # Если есть неизвестные таблицы — очистка блокируется
    if unknown_tables:
        st.error(f"🚫 Очистка невозможна. Найдены неизвестные таблицы: {', '.join(unknown_tables)}. Проверьте database.py и обновите списки.")
        st.stop()

    # Предпросмотр
    counts_base = get_table_counts(base_tables)
    counts_learning = get_table_counts(learning_tables)
    counts_turn = get_table_counts(turnament_tables)

    st.subheader("📊 Текущее состояние базы")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🟢 FAJ BASE (сохраняется)**")
        if base_tables:
            for table in sorted(base_tables):
                st.write(f"  {table}: {counts_base.get(table, 0)}")
        else:
            st.write("  (нет таблиц)")

    with col2:
        st.markdown("**🟡 LEARNING (по желанию)**")
        if learning_tables:
            for table in sorted(learning_tables):
                st.write(f"  {table}: {counts_learning.get(table, 0)}")
        else:
            st.write("  (нет таблиц)")

    with col3:
        st.markdown("**🔴 ТУРНИРНЫЕ ДАННЫЕ (будут удалены)**")
        if turnament_tables:
            for table in sorted(turnament_tables):
                st.write(f"  {table}: {counts_turn.get(table, 0)}")
        else:
            st.write("  (нет таблиц)")

    st.divider()
    st.subheader("⚠️ Подтверждение очистки")

    clear_learning = st.checkbox("☑ Также очистить LEARNING (learning_memory, learning_records, learning_events)", key="clear_learning")
    confirm = st.checkbox("☑ Я подтверждаю, что хочу очистить турнирные данные и начать новый цикл", key="confirm_reset")

    if st.button("🔴 ОЧИСТИТЬ И НАЧАТЬ НОВЫЙ ЦИКЛ", type="primary", disabled=not confirm):
        if not confirm:
            st.error("Подтвердите очистку, чтобы продолжить.")
        else:
            with st.spinner("Выполняется очистка..."):
                result = reset_tournament_data(clear_learning=clear_learning)

            # --- Итоговый статус ---
            st.balloons()
            st.success("✅ ОЧИСТКА УСПЕШНО ЗАВЕРШЕНА")

            # Считаем новое состояние
            new_counts_base = get_table_counts(base_tables)
            new_counts_turn = get_table_counts(turnament_tables)

            st.subheader("📋 СОСТОЯНИЕ ПОСЛЕ ОЧИСТКИ")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🟢 FAJ BASE**")
                st.write(f"  Команды: {new_counts_base.get('teams', 0)}")
                st.write(f"  Паспорта: {new_counts_base.get('team_passports', 0)}")
                st.write(f"  FAJ Rating: {new_counts_base.get('team_passports', 0)}")
                st.write(f"  Model Parameters: {new_counts_base.get('model_parameters', 0)}")

            with col2:
                st.markdown("**🔴 ТУРНИР**")
                st.write(f"  Туры: {new_counts_turn.get('rounds', 0)}")
                st.write(f"  Матчи: {new_counts_turn.get('matches', 0)}")
                st.write(f"  Результаты: {new_counts_turn.get('match_results', 0)}")
                st.write(f"  Прогнозы: {new_counts_turn.get('predictions', 0)}")

            with col3:
                st.markdown("**🧠 LEARNING**")
                if clear_learning:
                    st.write(f"  История обучения: 0")
                else:
                    st.write(f"  История обучения: сохранена")

            st.info(f"📁 Резервная копия: {result['backup_path']}")

            if st.button("🗓️ СОЗДАТЬ ТУР 1", type="primary"):
                st.session_state.page = "tour_manager"
                st.rerun()


if __name__ == "__main__":
    main()

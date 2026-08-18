#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Управление турами — создание календаря вручную.
Только: создать тур → добавить матч → сохранить.
Без требований к 8 матчам.
"""

import streamlit as st
from datetime import datetime

from app.database import FAJDatabase
from app.match_manager import MatchManager


def main():
    st.title("🗓️ Управление турами")
    st.caption("Создайте тур и добавляйте матчи по одному.")

    db = FAJDatabase()
    match_mgr = MatchManager(db)

    # ============================================================
    # 1. Сезон
    # ============================================================
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name FROM seasons
        WHERE league = 'РПЛ' AND (name LIKE '%2026%' OR name LIKE '%2026-27%')
        ORDER BY id DESC LIMIT 1
    """)
    season_row = cursor.fetchone()
    conn.close()

    if not season_row:
        st.error("❌ Сезон РПЛ 2026/27 не найден.")
        return

    season_id, season_name = season_row
    st.success(f"Сезон: {season_name}")

    # ============================================================
    # 2. Команды
    # ============================================================
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM teams WHERE league = 'РПЛ' ORDER BY name")
    teams = cursor.fetchall()
    conn.close()

    if not teams:
        st.warning("⚠️ Нет команд РПЛ.")
        return

    team_options = {row['name']: row['id'] for row in teams}
    team_names = list(team_options.keys())

    # ============================================================
    # 3. Выбор тура
    # ============================================================
    round_number = st.number_input("Тур", min_value=1, max_value=30, value=1, step=1)

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rounds WHERE season_id = ? AND round_number = ?", (season_id, round_number))
    existing_round = cursor.fetchone()
    conn.close()

    if existing_round:
        round_id = existing_round[0]
        st.info(f"ℹ️ Тур {round_number} уже существует.")
        matches = match_mgr.get_round_matches(round_id)
        if matches:
            st.subheader(f"📋 Матчи тура {round_number}")
            for m in matches:
                home = [name for name, tid in team_options.items() if tid == m['home_team_id']][0]
                away = [name for name, tid in team_options.items() if tid == m['away_team_id']][0]
                st.write(f"  {home} — {away}")
        else:
            st.write("  (матчей нет)")
    else:
        round_id = None
        st.info(f"ℹ️ Тур {round_number} ещё не создан.")

    st.divider()

    # ============================================================
    # 4. Добавление матча
    # ============================================================
    st.subheader("➕ Добавить матч")

    # Список уже использованных команд в этом туре
    used_teams = []
    if round_id:
        matches = match_mgr.get_round_matches(round_id)
        for m in matches:
            home = [name for name, tid in team_options.items() if tid == m['home_team_id']][0]
            away = [name for name, tid in team_options.items() if tid == m['away_team_id']][0]
            used_teams.extend([home, away])

    available_teams = [t for t in team_names if t not in used_teams]

    if not available_teams:
        st.info("✅ Все 16 команд уже использованы в этом туре.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            home = st.selectbox("Хозяева", [""] + available_teams)
        with col2:
            away = st.selectbox("Гости", [""] + available_teams)

        if home and away and home != away:
            if st.button("➕ Добавить матч"):
                # Если тур ещё не создан — создаём
                if round_id is None:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO rounds (season_id, round_number, created_at) VALUES (?, ?, ?)",
                        (season_id, round_number, datetime.now().isoformat())
                    )
                    round_id = cursor.lastrowid
                    conn.commit()
                    conn.close()

                # Проверяем, не существует ли уже такой матч в этом туре
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM matches
                    WHERE round_id = ? AND home_team_id = ? AND away_team_id = ?
                """, (round_id, team_options[home], team_options[away]))
                exists = cursor.fetchone()[0] > 0
                conn.close()

                if exists:
                    st.error(f"❌ Матч {home} — {away} уже существует в этом туре.")
                else:
                    match_data = {
                        "home_team_id": team_options[home],
                        "away_team_id": team_options[away],
                        "date": datetime.now().date().isoformat(),
                        "competition": "РПЛ",
                        "round_id": round_id,
                    }
                    match_mgr.save_match(match_data)
                    st.success(f"✅ Матч {home} — {away} добавлен в тур {round_number}")
                    st.rerun()
        elif home and away and home == away:
            st.error("❌ Команда не может играть сама с собой")

    # ============================================================
    # 5. Переход к прогнозу (если есть матчи)
    # ============================================================
    if round_id:
        matches = match_mgr.get_round_matches(round_id)
        if matches:
            st.divider()
            st.caption(f"Всего матчей в туре: {len(matches)}")
            if st.button("🔮 Перейти к прогнозам тура", type="primary"):
                st.session_state.page = "predict_round"
                st.rerun()


if __name__ == "__main__":
    main()

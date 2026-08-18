#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED
Управление турами v2.0 — создание календаря вручную.

ИСПРАВЛЕНИЯ v2.0:
    1. Убраны все прямые SQL-запросы — только через FAJDatabase
    2. Получение сезона — через db.get_seasons()
    3. Получение команд — через db.get_teams()
    4. Проверка тура — через db.get_rounds()
    5. Создание тура — через db.create_round()
    6. Проверка существования матча — через match_mgr.get_round_matches()

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
    # 1. Сезон (через FAJDatabase)
    # ============================================================

    seasons = db.get_seasons()
    season_row = None

    for season in seasons:
        if season.get("league") == "РПЛ":
            name = season.get("name", "")
            if "2026" in name or "2026-27" in name:
                season_row = season
                break

    if not season_row:
        st.error("❌ Сезон РПЛ 2026/27 не найден.")
        return

    season_id = season_row["id"]
    season_name = season_row["name"]
    st.success(f"Сезон: {season_name}")

    # ============================================================
    # 2. Команды (через FAJDatabase)
    # ============================================================

    teams = db.get_teams(league="РПЛ")

    if not teams:
        st.warning("⚠️ Нет команд РПЛ.")
        return

    team_options = {row["name"]: row["id"] for row in teams}
    team_names = list(team_options.keys())

    # ============================================================
    # 3. Выбор тура (через FAJDatabase)
    # ============================================================

    round_number = st.number_input("Тур", min_value=1, max_value=30, value=1, step=1)

    # Проверяем существование тура через db.get_rounds()
    rounds = db.get_rounds(season_id)
    existing_round = None

    for r in rounds:
        if r["round_number"] == round_number:
            existing_round = r
            break

    if existing_round:
        round_id = existing_round["id"]
        st.info(f"ℹ️ Тур {round_number} уже существует.")
        matches = match_mgr.get_round_matches(round_id)
        if matches:
            st.subheader(f"📋 Матчи тура {round_number}")
            for m in matches:
                home = [name for name, tid in team_options.items() if tid == m["home_team_id"]][0]
                away = [name for name, tid in team_options.items() if tid == m["away_team_id"]][0]
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
            home = [name for name, tid in team_options.items() if tid == m["home_team_id"]][0]
            away = [name for name, tid in team_options.items() if tid == m["away_team_id"]][0]
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
                # Если тур ещё не создан — создаём через FAJDatabase
                if round_id is None:
                    round_id = db.create_round(season_id, round_number)

                # Проверяем, не существует ли уже такой матч в этом туре
                existing_matches = match_mgr.get_round_matches(round_id)
                exists = False

                for m in existing_matches:
                    if m["home_team_id"] == team_options[home] and m["away_team_id"] == team_options[away]:
                        exists = True
                        break

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

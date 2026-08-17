#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Calendar Fix — БЕЗОПАСНОЕ ИСПРАВЛЕНИЕ
ТОЛЬКО меняет home_team_id / away_team_id в 21 матче.
match_results НЕ ТРОГАЕТ.
"""

import streamlit as st
import sqlite3
from pathlib import Path

from app.database import DB_FILE


def main():
    st.title("🔧 Исправление календаря РПЛ (1-4 туры)")
    st.caption("Меняет местами команды в matches. Результаты НЕ ТРОГАЕТ.")

    if not Path(DB_FILE).exists():
        st.error("❌ База данных не найдена")
        return

    # ============================================================
    # ЭТАЛОННЫЙ КАЛЕНДАРЬ (правильный порядок)
    # ============================================================
    CALENDAR = {
        (1, "ЦСКА", "Балтика"): ("ЦСКА", "Балтика"),
        (1, "Рубин", "Краснодар"): ("Рубин", "Краснодар"),
        (1, "Спартак", "Родина"): ("Спартак", "Родина"),
        (1, "Акрон", "Зенит"): ("Акрон", "Зенит"),
        (1, "Динамо Москва", "Крылья Советов"): ("Динамо Москва", "Крылья Советов"),
        (1, "Факел", "Динамо Махачкала"): ("Факел", "Динамо Махачкала"),
        (1, "Оренбург", "Ростов"): ("Оренбург", "Ростов"),
        (1, "Локомотив", "Ахмат"): ("Локомотив", "Ахмат"),
        (2, "Ахмат", "Спартак"): ("Ахмат", "Спартак"),
        (2, "Краснодар", "Факел"): ("Краснодар", "Факел"),
        (2, "Оренбург", "Зенит"): ("Оренбург", "Зенит"),
        (2, "Балтика", "Динамо Москва"): ("Балтика", "Динамо Москва"),
        (2, "Динамо Махачкала", "Локомотив"): ("Динамо Махачкала", "Локомотив"),
        (2, "ЦСКА", "Крылья Советов"): ("ЦСКА", "Крылья Советов"),
        (2, "Акрон", "Рубин"): ("Акрон", "Рубин"),
        (2, "Родина", "Ростов"): ("Родина", "Ростов"),
        (3, "Факел", "Ахмат"): ("Факел", "Ахмат"),
        (3, "Спартак", "Краснодар"): ("Спартак", "Краснодар"),
        (3, "Рубин", "Оренбург"): ("Рубин", "Оренбург"),
        (3, "Зенит", "Родина"): ("Зенит", "Родина"),
        (3, "Динамо Москва", "Динамо Махачкала"): ("Динамо Москва", "Динамо Махачкала"),
        (3, "ЦСКА", "Ростов"): ("ЦСКА", "Ростов"),
        (3, "Локомотив", "Акрон"): ("Локомотив", "Акрон"),
        (3, "Крылья Советов", "Балтика"): ("Крылья Советов", "Балтика"),
        (4, "Родина", "Акрон"): ("Родина", "Акрон"),
        (4, "Оренбург", "Локомотив"): ("Оренбург", "Локомотив"),
        (4, "Балтика", "Спартак"): ("Балтика", "Спартак"),
        (4, "Крылья Советов", "Динамо Махачкала"): ("Крылья Советов", "Динамо Махачкала"),
        (4, "Зенит", "Динамо Москва"): ("Зенит", "Динамо Москва"),
        (4, "Краснодар", "Ахмат"): ("Краснодар", "Ахмат"),
        (4, "Ростов", "Рубин"): ("Ростов", "Рубин"),
        (4, "ЦСКА", "Факел"): ("ЦСКА", "Факел"),
    }

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # ============================================================
    # 1. НАХОДИМ СЕЗОН
    # ============================================================
    cursor.execute("""
        SELECT id, name
        FROM seasons
        WHERE name LIKE '%2026%' OR name LIKE '%РПЛ%'
        ORDER BY id DESC LIMIT 1
    """)
    season = cursor.fetchone()
    if not season:
        st.error("❌ Сезон не найден")
        conn.close()
        return
    season_id, season_name = season
    st.success(f"Сезон: {season_name} (ID={season_id})")

    # ============================================================
    # 2. ТУРЫ 1-4
    # ============================================================
    cursor.execute("SELECT id, round_number FROM rounds WHERE season_id = ? AND round_number BETWEEN 1 AND 4", (season_id,))
    rounds = {row[1]: row[0] for row in cursor.fetchall()}
    st.write(f"Туры 1-4: {len(rounds)}")

    # ============================================================
    # 3. ЗАГРУЖАЕМ МАТЧИ
    # ============================================================
    db_matches = []  # (match_id, round, home, away)
    for rn, rid in rounds.items():
        cursor.execute("""
            SELECT m.id, th.name AS home, ta.name AS away
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.round_id = ?
        """, (rid,))
        for row in cursor.fetchall():
            db_matches.append((row[0], rn, row[1], row[2]))

    # ============================================================
    # 4. НАХОДИМ ПЕРЕПУТАННЫЕ
    # ============================================================
    to_fix = []
    for match_id, rn, db_home, db_away in db_matches:
        # Проверяем по эталону
        correct_home, correct_away = CALENDAR.get((rn, db_home, db_away), (None, None))
        if correct_home is None:
            # Пробуем перевёрнутый вариант
            correct_home, correct_away = CALENDAR.get((rn, db_away, db_home), (None, None))
            if correct_home is not None:
                to_fix.append((match_id, rn, db_home, db_away, correct_home, correct_away))

    if not to_fix:
        st.success("✅ Все матчи в правильном порядке!")
        conn.close()
        return

    st.warning(f"⚠️ Найдено {len(to_fix)} матчей с перепутанными командами:")

    # ============================================================
    # 5. ПОКАЗЫВАЕМ СПИСОК
    # ============================================================
    data = []
    for match_id, rn, db_home, db_away, correct_home, correct_away in to_fix:
        data.append({
            "Тур": rn,
            "Сейчас": f"{db_home} — {db_away}",
            "Должно быть": f"{correct_home} — {correct_away}",
            "match_id": match_id,
        })
    st.dataframe(data, use_container_width=True)

    # ============================================================
    # 6. КНОПКА — ТОЛЬКО ОБНОВЛЕНИЕ matches
    # ============================================================
    if st.button("🔧 Исправить календарь (ТОЛЬКО команды)", type="primary"):
        try:
            fixed = 0
            for match_id, rn, db_home, db_away, correct_home, correct_away in to_fix:
                # Получаем ID правильных команд
                cursor.execute("SELECT id FROM teams WHERE name = ?", (correct_home,))
                home_id = cursor.fetchone()
                cursor.execute("SELECT id FROM teams WHERE name = ?", (correct_away,))
                away_id = cursor.fetchone()
                if not home_id or not away_id:
                    st.warning(f"⚠️ Не найдены команды: {correct_home} или {correct_away}")
                    continue

                # Обновляем только matches
                cursor.execute(
                    "UPDATE matches SET home_team_id = ?, away_team_id = ? WHERE id = ?",
                    (home_id[0], away_id[0], match_id)
                )
                fixed += 1

            conn.commit()
            st.success(f"✅ Исправлено {fixed} матчей в календаре.")
            st.info("📌 match_results НЕ ТРОГАЛИ. Проверь результаты отдельно.")

        except Exception as e:
            conn.rollback()
            st.error(f"❌ Ошибка: {e}")

    conn.close()


if __name__ == "__main__":
    main()

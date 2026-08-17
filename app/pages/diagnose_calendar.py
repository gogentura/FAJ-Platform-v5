#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Calendar Diagnostic v1.3 (READ-ONLY)
Страница для Streamlit — показывает состояние календаря 1-4 туров.
Теперь ищет сезон по имени, а не по league.
"""

import streamlit as st
import sqlite3
from pathlib import Path

from app.database import DB_FILE


def main():
    st.title("📋 Диагностика календаря РПЛ 1-4 туры")
    st.caption("Сравнение эталона с БД. Ничего не изменяет.")

    if not Path(DB_FILE).exists():
        st.error("❌ База данных не найдена")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # ============================================================
    # 1. ПОКАЗЫВАЕМ ВСЕ СЕЗОНЫ (для диагностики)
    # ============================================================
    cursor.execute("SELECT id, name, league FROM seasons ORDER BY id")
    all_seasons = cursor.fetchall()
    st.write("**Найденные сезоны:**")
    for s in all_seasons:
        st.write(f"ID={s[0]}, name='{s[1]}', league='{s[2]}'")

    # ============================================================
    # 2. ИЩЕМ СЕЗОН РПЛ 2026/27 (по имени, без league)
    # ============================================================
    cursor.execute("""
        SELECT id, name
        FROM seasons
        WHERE name LIKE '%РПЛ%' OR name LIKE '%2026%'
        ORDER BY id DESC LIMIT 1
    """)
    season = cursor.fetchone()
    if not season:
        st.error("❌ Сезон РПЛ 2026/27 не найден ни по имени, ни по league.")
        conn.close()
        return
    season_id, season_name = season
    st.success(f"✅ Используем сезон: {season_name} (ID={season_id})")

    # ============================================================
    # 3. ТУРЫ 1-4
    # ============================================================
    cursor.execute("SELECT id, round_number FROM rounds WHERE season_id = ? AND round_number BETWEEN 1 AND 4", (season_id,))
    rounds_rows = cursor.fetchall()
    if not rounds_rows:
        st.warning("⚠️ В БД нет туров 1-4 для этого сезона")
        conn.close()
        return
    rounds = {row[1]: row[0] for row in rounds_rows}
    st.write(f"Найдено туров 1-4: {len(rounds)}")

    # ============================================================
    # 4. ЭТАЛОННЫЙ КАЛЕНДАРЬ (32 матча)
    # ============================================================
    CALENDAR = [
        (1, "ЦСКА", "Балтика"), (1, "Рубин", "Краснодар"),
        (1, "Спартак", "Родина"), (1, "Акрон", "Зенит"),
        (1, "Динамо Москва", "Крылья Советов"), (1, "Факел", "Динамо Махачкала"),
        (1, "Оренбург", "Ростов"), (1, "Локомотив", "Ахмат"),
        (2, "Ахмат", "Спартак"), (2, "Краснодар", "Факел"),
        (2, "Оренбург", "Зенит"), (2, "Балтика", "Динамо Москва"),
        (2, "Динамо Махачкала", "Локомотив"), (2, "ЦСКА", "Крылья Советов"),
        (2, "Акрон", "Рубин"), (2, "Родина", "Ростов"),
        (3, "Факел", "Ахмат"), (3, "Спартак", "Краснодар"),
        (3, "Рубин", "Оренбург"), (3, "Зенит", "Родина"),
        (3, "Динамо Москва", "Динамо Махачкала"), (3, "ЦСКА", "Ростов"),
        (3, "Локомотив", "Акрон"), (3, "Крылья Советов", "Балтика"),
        (4, "Родина", "Акрон"), (4, "Оренбург", "Локомотив"),
        (4, "Балтика", "Спартак"), (4, "Крылья Советов", "Динамо Махачкала"),
        (4, "Зенит", "Динамо Москва"), (4, "Краснодар", "Ахмат"),
        (4, "Ростов", "Рубин"), (4, "ЦСКА", "Факел"),
    ]

    # ============================================================
    # 5. ЗАГРУЗКА МАТЧЕЙ ИЗ БД
    # ============================================================
    db_matches = {}
    for rn, rid in rounds.items():
        cursor.execute("""
            SELECT m.id, th.name AS home, ta.name AS away
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.round_id = ?
        """, (rid,))
        for row in cursor.fetchall():
            db_matches[(rn, row[1], row[2])] = row[0]

    # ============================================================
    # 6. РЕЗУЛЬТАТЫ ИЗ match_results
    # ============================================================
    cursor.execute("SELECT match_id FROM match_results")
    results = {row[0] for row in cursor.fetchall()}
    conn.close()

    # ============================================================
    # 7. АНАЛИЗ
    # ============================================================
    missing = []
    extra = []
    mismatch = []
    duplicates = []

    for r, h, a in CALENDAR:
        if (r, h, a) not in db_matches:
            # ищем в другом туре
            found = False
            for (rr, hh, aa), mid in db_matches.items():
                if hh == h and aa == a and rr != r:
                    mismatch.append((r, h, a, rr))
                    found = True
                    break
            if not found:
                missing.append((r, h, a))

    for (r, h, a), mid in db_matches.items():
        if (r, h, a) not in CALENDAR:
            extra.append((r, h, a, mid))

    # дубли
    seen = set()
    for key, mid in db_matches.items():
        if key in seen:
            duplicates.append((*key, mid))
        else:
            seen.add(key)

    # ============================================================
    # 8. ВЫВОД
    # ============================================================
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Эталон", len(CALENDAR))
    with col2:
        st.metric("В БД (1-4 туры)", len(db_matches))

    if missing:
        st.error(f"🔴 Отсутствуют ({len(missing)})")
        for r, h, a in missing:
            st.write(f"Тур {r}: {h} — {a}")
    else:
        st.success("✅ Все эталонные матчи присутствуют")

    if extra:
        st.warning(f"⚠️ Лишние ({len(extra)})")
        for r, h, a, mid in extra:
            st.write(f"Тур {r}: {h} — {a} (match_id={mid})")
    else:
        st.success("✅ Нет лишних матчей")

    if mismatch:
        st.warning(f"🔄 Неправильный тур ({len(mismatch)})")
        for r, h, a, rr in mismatch:
            st.write(f"Должен быть тур {r}, а в БД тур {rr}: {h} — {a}")
    else:
        st.success("✅ Все матчи в правильном туре")

    if duplicates:
        st.error(f"🔁 Дубли ({len(duplicates)})")
        for r, h, a, mid in duplicates:
            st.write(f"Тур {r}: {h} — {a} (match_id={mid})")
    else:
        st.success("✅ Нет дублей")

    # Результаты
    with_results = sum(1 for key in db_matches if db_matches[key] in results)
    st.metric("Матчи с результатами", with_results, f"из {len(db_matches)}")

    st.caption("📌 READ-ONLY: данные не изменяются")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Calendar Diagnostic v1.2 (схема v12.1)
Ничего не изменяет — только диагностика.
Работает с таблицами: teams, seasons, rounds, matches, match_results.
"""

import sqlite3
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).parent
DB_PATH = ROOT_DIR / "data" / "faj.db"

# ============================================================
# ЭТАЛОННЫЙ КАЛЕНДАРЬ (32 матча, 1–4 туры)
# ============================================================

CALENDAR = [
    # Тур 1
    (1, "ЦСКА", "Балтика"),
    (1, "Рубин", "Краснодар"),
    (1, "Спартак", "Родина"),
    (1, "Акрон", "Зенит"),
    (1, "Динамо Москва", "Крылья Советов"),
    (1, "Факел", "Динамо Махачкала"),
    (1, "Оренбург", "Ростов"),
    (1, "Локомотив", "Ахмат"),
    # Тур 2
    (2, "Ахмат", "Спартак"),
    (2, "Краснодар", "Факел"),
    (2, "Оренбург", "Зенит"),
    (2, "Балтика", "Динамо Москва"),
    (2, "Динамо Махачкала", "Локомотив"),
    (2, "ЦСКА", "Крылья Советов"),
    (2, "Акрон", "Рубин"),
    (2, "Родина", "Ростов"),
    # Тур 3
    (3, "Факел", "Ахмат"),
    (3, "Спартак", "Краснодар"),
    (3, "Рубин", "Оренбург"),
    (3, "Зенит", "Родина"),
    (3, "Динамо Москва", "Динамо Махачкала"),
    (3, "ЦСКА", "Ростов"),
    (3, "Локомотив", "Акрон"),
    (3, "Крылья Советов", "Балтика"),
    # Тур 4
    (4, "Родина", "Акрон"),
    (4, "Оренбург", "Локомотив"),
    (4, "Балтика", "Спартак"),
    (4, "Крылья Советов", "Динамо Махачкала"),
    (4, "Зенит", "Динамо Москва"),
    (4, "Краснодар", "Ахмат"),
    (4, "Ростов", "Рубин"),
    (4, "ЦСКА", "Факел"),
]

# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def find_team_id(cursor, name):
    """Возвращает team_id по имени или None."""
    cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
    row = cursor.fetchone()
    return row[0] if row else None

# ============================================================
# ОСНОВНАЯ ДИАГНОСТИКА
# ============================================================

def diagnose():
    print("\n" + "=" * 70)
    print("FAJ CALENDAR DIAGNOSTIC v1.2 (схема v12.1)")
    print("=" * 70)

    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Проверяем наличие таблиц
    required_tables = {"teams", "seasons", "rounds", "matches", "match_results"}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    missing_tables = required_tables - existing_tables
    if missing_tables:
        print(f"❌ Отсутствуют таблицы: {', '.join(missing_tables)}")
        conn.close()
        return

    # ============================================================
    # 1. ПОИСК СЕЗОНА РПЛ 2026/27 (БОЛЕЕ СТРОГИЙ ВАРИАНТ)
    # ============================================================
    cursor.execute("""
        SELECT id, name
        FROM seasons
        WHERE league = 'РПЛ'
          AND (
              name LIKE '%2026%'
              OR name LIKE '%2026/27%'
              OR name LIKE '%2026-2027%'
          )
        ORDER BY id DESC
        LIMIT 1
    """)
    season_row = cursor.fetchone()
    if not season_row:
        # fallback – если league не заполнена, используем старый поиск
        cursor.execute("""
            SELECT id, name
            FROM seasons
            WHERE name LIKE '%РПЛ%' OR name LIKE '%2026%'
            ORDER BY id DESC LIMIT 1
        """)
        season_row = cursor.fetchone()
        if not season_row:
            print("❌ Сезон РПЛ 2026/27 не найден.")
            conn.close()
            return

    season_id, season_name = season_row
    print(f"✅ Сезон: {season_name} (ID={season_id})")

    # ============================================================
    # 2. ТУРЫ 1–4 ДЛЯ ЭТОГО СЕЗОНА
    # ============================================================
    cursor.execute("""
        SELECT id, round_number
        FROM rounds
        WHERE season_id = ? AND round_number BETWEEN 1 AND 4
    """, (season_id,))
    rounds = {row[1]: row[0] for row in cursor.fetchall()}
    for r in range(1, 5):
        if r not in rounds:
            print(f"⚠️ Тур {r} отсутствует в БД.")
    print(f"✅ Найдено туров 1-4: {len(rounds)}")

    # ============================================================
    # 3. ЗАГРУЗКА МАТЧЕЙ ИЗ БД
    # ============================================================
    db_matches = {}  # ключ: (round_number, home, away) -> данные
    for round_num, round_id in rounds.items():
        cursor.execute("""
            SELECT m.id, m.home_team_id, m.away_team_id,
                   th.name AS home, ta.name AS away
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE m.round_id = ?
        """, (round_id,))
        for row in cursor.fetchall():
            match_id, home_id, away_id, home, away = row
            key = (round_num, home, away)
            db_matches[key] = {
                'match_id': match_id,
                'home_team_id': home_id,
                'away_team_id': away_id,
            }

    # ============================================================
    # 4. РЕЗУЛЬТАТЫ ИЗ match_results
    # ============================================================
    cursor.execute("SELECT match_id, home_goals, away_goals FROM match_results")
    results = {row[0]: {'home_goals': row[1], 'away_goals': row[2]} for row in cursor.fetchall()}

    # ============================================================
    # 5. СРАВНЕНИЕ С ЭТАЛОНОМ
    # ============================================================
    missing = []
    extra = []
    mismatch_round = []
    duplicates = []

    # Проверка эталонных матчей
    for round_num, home, away in CALENDAR:
        key = (round_num, home, away)
        if key in db_matches:
            # проверим, нет ли дубля (одинаковые пары в одном туре)
            # уже проверим позже
            pass
        else:
            # пробуем найти матч с этими командами в любом другом туре
            found = False
            for (r, h, a), data in db_matches.items():
                if h == home and a == away and r != round_num:
                    mismatch_round.append((round_num, home, away, r, data['match_id']))
                    found = True
                    break
            if not found:
                missing.append((round_num, home, away))

    # Проверка лишних матчей в БД (которых нет в эталоне)
    for (r, h, a), data in db_matches.items():
        if (r, h, a) not in CALENDAR:
            extra.append((r, h, a, data['match_id']))

    # Проверка дублей (одинаковые пары в одном туре)
    seen = set()
    for (r, h, a), data in db_matches.items():
        key = (r, h, a)
        if key in seen:
            duplicates.append((r, h, a, data['match_id']))
        else:
            seen.add(key)

    # ============================================================
    # 6. ВЫВОД
    # ============================================================
    print("\n" + "-" * 70)
    print(f"ЭТАЛОН: {len(CALENDAR)} матчей (1-4 туры)")
    print(f"В БД (1-4 туры): {len(db_matches)} матчей")
    print("-" * 70)

    if missing:
        print(f"\n🔴 ОТСУТСТВУЮТ В БД ({len(missing)}):")
        for r, h, a in missing:
            print(f"  Тур {r}: {h} — {a}")
    else:
        print("\n✅ Все эталонные матчи присутствуют в БД (по турам).")

    if extra:
        print(f"\n⚠️ ЛИШНИЕ В БД (нет в эталоне) ({len(extra)}):")
        for r, h, a, mid in extra:
            print(f"  Тур {r}: {h} — {a} (match_id={mid})")
    else:
        print("\n✅ Нет лишних матчей в БД для 1-4 туров.")

    if mismatch_round:
        print(f"\n🔄 НЕПРАВИЛЬНЫЙ ТУР (в БД привязан к другому туру) ({len(mismatch_round)}):")
        for r, h, a, actual_r, mid in mismatch_round:
            print(f"  Должен быть тур {r}, а в БД тур {actual_r}: {h} — {a} (match_id={mid})")
    else:
        print("\n✅ Все матчи привязаны к правильному туру.")

    if duplicates:
        print(f"\n🔁 ДУБЛИ (одинаковые пары в одном туре) ({len(duplicates)}):")
        for r, h, a, mid in duplicates:
            print(f"  Тур {r}: {h} — {a} (match_id={mid})")
    else:
        print("\n✅ Нет дублей.")

    # Статистика по результатам
    results_count = 0
    for key, data in db_matches.items():
        if data['match_id'] in results:
            results_count += 1
    print(f"\n📊 Из {len(db_matches)} матчей в БД: {results_count} имеют результаты в match_results.")

    # Дополнительно: список матчей без результатов
    if results_count < len(db_matches):
        print("\n⚠️ Матчи без результатов:")
        for (r, h, a), data in db_matches.items():
            if data['match_id'] not in results:
                print(f"  Тур {r}: {h} — {a} (match_id={data['match_id']})")

    conn.close()
    print("\n" + "=" * 70)

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == "__main__":
    diagnose()

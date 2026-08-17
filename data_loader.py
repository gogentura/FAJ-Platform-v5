import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'faj.db')

TEAM_NAME_MAP = {
    'ЦСКА': 'ЦСКА',
    'Балтика': 'Балтика',
    'Рубин': 'Рубин',
    'Краснодар': 'Краснодар',
    'Спартак': 'Спартак',
    'Родина': 'Родина',
    'Акрон': 'Акрон',
    'Зенит': 'Зенит',
    'Динамо М': 'Динамо Москва',
    'Крылья Советов': 'Крылья Советов',
    'Факел': 'Факел',
    'Динамо Мх': 'Динамо Махачкала',
    'Оренбург': 'Оренбург',
    'Ростов': 'Ростов',
    'Локомотив': 'Локомотив',
    'Ахмат': 'Ахмат',
}

MATCHES = {
    1: [
        ('ЦСКА', 'Балтика'),
        ('Динамо М', 'Крылья Советов'),
        ('Акрон', 'Зенит'),
        ('Факел', 'Динамо Мх'),
        ('Спартак', 'Родина'),
        ('Локомотив', 'Ахмат'),
        ('Оренбург', 'Ростов'),
        ('Рубин', 'Краснодар'),
    ],
    2: [
        ('Родина', 'Ростов'),
        ('Акрон', 'Рубин'),
        ('ЦСКА', 'Крылья Советов'),
        ('Динамо Мх', 'Локомотив'),
        ('Балтика', 'Динамо М'),
        ('Оренбург', 'Зенит'),
        ('Краснодар', 'Факел'),
        ('Ахмат', 'Спартак'),
    ],
    3: [
        ('Факел', 'Ахмат'),
        ('Спартак', 'Краснодар'),
        ('Рубин', 'Оренбург'),
        ('Зенит', 'Родина'),
        ('Динамо М', 'Динамо Мх'),
        ('ЦСКА', 'Ростов'),
        ('Локомотив', 'Акрон'),
        ('Крылья Советов', 'Балтика'),
    ],
    4: [
        ('Родина', 'Акрон'),
        ('Оренбург', 'Локомотив'),
        ('Балтика', 'Спартак'),
        ('Крылья Советов', 'Динамо Мх'),
        ('Зенит', 'Динамо М'),
        ('Краснодар', 'Ахмат'),
        ('Ростов', 'Рубин'),
        ('ЦСКА', 'Факел'),
    ],
}

RESULTS = {
    1: [
        ('ЦСКА', 'Балтика', 2, 1),
        ('Динамо М', 'Крылья Советов', 0, 0),
        ('Акрон', 'Зенит', 0, 5),
        ('Факел', 'Динамо Мх', 1, 2),
        ('Спартак', 'Родина', 3, 0),
        ('Локомотив', 'Ахмат', 1, 1),
        ('Оренбург', 'Ростов', 2, 1),
        ('Рубин', 'Краснодар', 1, 3),
    ],
    2: [
        ('Родина', 'Ростов', 2, 4),
        ('Акрон', 'Рубин', 1, 2),
        ('ЦСКА', 'Крылья Советов', 1, 1),
        ('Динамо Мх', 'Локомотив', 2, 1),
        ('Балтика', 'Динамо М', 2, 1),
        ('Оренбург', 'Зенит', 0, 3),
        ('Краснодар', 'Факел', 3, 2),
        ('Ахмат', 'Спартак', 1, 2),
    ],
    3: [
        ('Факел', 'Ахмат', 0, 0),
        ('Спартак', 'Краснодар', 0, 1),
        ('Рубин', 'Оренбург', 0, 0),
        ('Зенит', 'Родина', 1, 2),
        ('Динамо М', 'Динамо Мх', 3, 1),
        ('ЦСКА', 'Ростов', 0, 0),
        ('Локомотив', 'Акрон', 1, 1),
        ('Крылья Советов', 'Балтика', 0, 2),
    ],
    4: [
        ('Родина', 'Акрон', 3, 3),
        ('Оренбург', 'Локомотив', 1, 1),
        ('Балтика', 'Спартак', 1, 2),
        ('Крылья Советов', 'Динамо Мх', 1, 4),
        ('Зенит', 'Динамо М', 3, 0),
        ('Краснодар', 'Ахмат', 1, 0),
        ('Ростов', 'Рубин', 1, 1),
        ('ЦСКА', 'Факел', 1, 0),
    ],
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_team_id(conn, name):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("SELECT id, name FROM teams")
    for team in cursor.fetchall():
        if team['name'].lower().strip() == name.lower().strip():
            return team['id']
    cursor.execute("INSERT INTO teams (name, league, created_at) VALUES (?, ?, ?)",
                   (name, 'РПЛ', datetime.now().isoformat()))
    conn.commit()
    return cursor.lastrowid

def get_season_id(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM seasons WHERE name = 'РПЛ 2026-2027' OR name = '2026-2027' LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO seasons (name, league, year, created_at) VALUES (?, ?, ?, ?)",
                   ('РПЛ 2026-2027', 'РПЛ', '2026-2027', datetime.now().isoformat()))
    conn.commit()
    return cursor.lastrowid

def get_round_id(conn, season_id, round_number):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM rounds WHERE season_id = ? AND round_number = ?", (season_id, round_number))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO rounds (season_id, round_number, created_at) VALUES (?, ?, ?)",
                   (season_id, round_number, datetime.now().isoformat()))
    conn.commit()
    return cursor.lastrowid

def add_match_if_not_exists(conn, round_number, home_name, away_name, season_id):
    home_id = get_team_id(conn, home_name)
    away_id = get_team_id(conn, away_name)
    round_id = get_round_id(conn, season_id, round_number)

    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM matches
        WHERE round_id = ? AND home_team_id = ? AND away_team_id = ?
    ''', (round_id, home_id, away_id))
    row = cursor.fetchone()
    if row:
        return row['id']

    cursor.execute('''
        INSERT INTO matches (round_id, home_team_id, away_team_id, date, competition, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (round_id, home_id, away_id, None, 'РПЛ', 'scheduled', datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    return cursor.lastrowid

def add_result(conn, match_id, home_score, away_score):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='match_results'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_results (
                match_id INTEGER PRIMARY KEY,
                home_goals INTEGER,
                away_goals INTEGER
            )
        ''')
        conn.commit()
    cursor.execute('''
        INSERT OR REPLACE INTO match_results (match_id, home_goals, away_goals)
        VALUES (?, ?, ?)
    ''', (match_id, home_score, away_score))
    conn.commit()

    # Также обновим поля actual_home и actual_away в matches
    cursor.execute('''
        UPDATE matches SET actual_home = ?, actual_away = ?, status = 'finished', updated_at = ?
        WHERE id = ?
    ''', (home_score, away_score, datetime.now().isoformat(), match_id))
    conn.commit()

def load_initial_data():
    conn = get_db_connection()
    try:
        season_id = get_season_id(conn)
        for round_num, matches in MATCHES.items():
            for home, away in matches:
                home_mapped = TEAM_NAME_MAP.get(home, home)
                away_mapped = TEAM_NAME_MAP.get(away, away)
                match_id = add_match_if_not_exists(conn, round_num, home_mapped, away_mapped, season_id)
                if match_id:
                    # Проверим, есть ли результат
                    cursor = conn.cursor()
                    cursor.execute("SELECT match_id FROM match_results WHERE match_id = ?", (match_id,))
                    if not cursor.fetchone():
                        for rnd, results in RESULTS.items():
                            if rnd == round_num:
                                for r_home, r_away, hs, as_ in results:
                                    if r_home == home and r_away == away:
                                        add_result(conn, match_id, hs, as_)
                                        break
        print("✅ Данные 1-4 туров загружены (или уже были в базе).")
    except Exception as e:
        print(f"⚠️ Ошибка при загрузке данных: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    load_initial_data()

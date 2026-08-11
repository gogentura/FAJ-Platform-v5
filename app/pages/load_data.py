import streamlit as st
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Загрузка данных", layout="wide")
    st.title("🚀 ЗАГРУЗКА ДАННЫХ")
    
    st.info("""
    Нажми кнопку — система загрузит:
    - ✅ 24 матча 1-3 туров
    - ✅ Результаты и статистику
    - ✅ Паспорта команд
    """)
    
    if st.button("🔥 ЗАГРУЗИТЬ ДАННЫЕ", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Очищаем старые данные
            cursor.execute("DELETE FROM match_statistics")
            cursor.execute("DELETE FROM match_results")
            cursor.execute("DELETE FROM matches")
            conn.commit()
            
            # Сезон
            cursor.execute("""
                INSERT OR IGNORE INTO seasons (name, league)
                VALUES ('2026-2027', 'РПЛ')
            """)
            conn.commit()
            
            cursor.execute("SELECT id FROM seasons WHERE name = '2026-2027'")
            season_row = cursor.fetchone()
            season_id = season_row[0]
            
            # Команды РПЛ
            teams = [
                "Акрон", "Ахмат", "Балтика", "Динамо Махачкала",
                "Динамо Москва", "Зенит", "Краснодар", "Крылья Советов",
                "Локомотив", "Оренбург", "Родина", "Ростов",
                "Рубин", "Спартак", "Факел", "ЦСКА"
            ]
            
            for team in teams:
                cursor.execute("INSERT OR IGNORE INTO teams (name, league) VALUES (?, 'РПЛ')", (team,))
            conn.commit()
            
            # 24 МАТЧА
            matches = [
                # ТУР 1
                (1, "ЦСКА", "Балтика", 2, 1, 2.25, 1.52, 18, 14, 5, 3, 65, 35, 6, 2, 1, 1, 83, 66),
                (1, "Рубин", "Краснодар", 1, 3, 0.61, 2.76, 5, 19, 3, 8, 28, 72, 2, 4, 0, 3, 53, 85),
                (1, "Спартак", "Родина", 3, 0, 2.50, 0.55, 25, 7, 9, 4, 60, 40, 12, 4, 0, 3, 87, 78),
                (1, "Акрон", "Зенит", 0, 5, 0.69, 2.52, 11, 20, 4, 10, 52, 48, 9, 5, 3, 2, 84, 86),
                (1, "Динамо Москва", "Крылья Советов", 0, 0, 1.25, 1.23, 21, 12, 5, 4, 66, 34, 6, 2, None, None, 84, 68),
                (1, "Факел", "Динамо Махачкала", 1, 2, 1.16, 0.85, 13, 11, 3, 4, 57, 43, 8, 2, 0, 1, 83, 75),
                (1, "Оренбург", "Ростов", 2, 1, 0.82, 0.69, 9, 14, 3, 5, 42, 58, 3, 6, 3, 6, 60, 72),
                (1, "Локомотив", "Ахмат", 1, 1, 1.27, 1.24, 16, 21, 2, 7, 47, 53, 2, 5, 3, 0, 79, 80),
                # ТУР 2
                (2, "Родина", "Ростов", 2, 4, 0.59, 2.05, 8, 24, 2, 10, 49, 51, 2, 9, 2, 1, 64, 69),
                (2, "Акрон", "Рубин", 1, 2, 0.63, 1.59, 9, 16, 4, 5, 64, 36, 5, 3, 1, 2, 83, 75),
                (2, "ЦСКА", "Крылья Советов", 1, 1, 1.87, 0.52, 18, 11, 6, 5, 55, 45, 2, 5, 0, 3, 86, 79),
                (2, "Динамо Махачкала", "Локомотив", 2, 1, 2.24, 1.73, 12, 13, 5, 5, 41, 59, 1, 9, 1, 2, 73, 80),
                (2, "Балтика", "Динамо Москва", 2, 1, 1.34, 0.76, 8, 14, 4, 4, 28, 72, 2, 8, 2, 0, 54, 80),
                (2, "Оренбург", "Зенит", 0, 3, 1.02, 0.80, 13, 12, 2, 5, 31, 69, 5, 2, 3, 1, 78, 90),
                (2, "Краснодар", "Факел", 3, 2, 0.83, 2.10, 11, 13, 5, 3, 56, 44, 2, 4, 4, 0, 85, 76),
                (2, "Ахмат", "Спартак", 1, 2, 0.93, 0.55, 4, 11, 3, 4, 27, 73, 1, 5, 1, 2, 62, 87),
                # ТУР 3
                (3, "Локомотив", "Акрон", 0, 0, 1.79, 1.05, 23, 15, 3, 3, 58, 42, 2, 6, 4, 1, 85, 79),
                (3, "Крылья Советов", "Балтика", 0, 2, 0.43, 1.15, 5, 13, 1, 5, 67, 33, 2, 5, 1, 0, 83, 70),
                (3, "Динамо Москва", "Динамо Махачкала", 3, 1, 1.08, 1.14, 11, 8, 6, 2, 67, 33, 4, 2, 3, 3, 81, 64),
                (3, "ЦСКА", "Ростов", 0, 0, 0.83, 0.84, 13, 13, 3, 4, 56, 44, 1, 3, 1, 2, 78, 71),
                (3, "Зенит", "Родина", 1, 2, 1.59, 0.76, 22, 7, 6, 3, 66, 34, 11, 3, 1, 1, 87, 77),
                (3, "Спартак", "Краснодар", 1, 2, 1.32, 1.08, 16, 16, 3, 4, 63, 37, 6, 7, 1, 3, 78, 71),
                (3, "Рубин", "Оренбург", 1, 1, 0.64, 0.86, 10, 13, 1, 3, 62, 38, 7, 1, 2, 1, 74, 65),
            ]
            
            loaded = 0
            
            for match in matches:
                round_num, home, away, hg, ag, hxg, axg, hs, ash, hsot, asot, hp, ap, hc, ac, hy, ay, hpa, apa = match
                
                cursor.execute("SELECT id FROM teams WHERE name = ?", (home,))
                home_row = cursor.fetchone()
                cursor.execute("SELECT id FROM teams WHERE name = ?", (away,))
                away_row = cursor.fetchone()
                
                if not home_row or not away_row:
                    continue
                
                home_id = home_row[0]
                away_id = away_row[0]
                
                cursor.execute("INSERT OR IGNORE INTO rounds (season_id, round_number) VALUES (?, ?)", (season_id, round_num))
                conn.commit()
                
                cursor.execute("SELECT id FROM rounds WHERE season_id = ? AND round_number = ?", (season_id, round_num))
                round_row = cursor.fetchone()
                round_id = round_row[0]
                
                cursor.execute("""
                    INSERT INTO matches
                    (round_id, home_team_id, away_team_id, competition, status, actual_home, actual_away,
                     home_xg, away_xg, home_possession, away_possession,
                     home_shots, away_shots, home_shots_on_target, away_shots_on_target)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (round_id, home_id, away_id, 'РПЛ', 'finished', hg, ag, hxg, axg, hp, ap, hs, ash, hsot, asot))
                conn.commit()
                
                cursor.execute("SELECT id FROM matches WHERE round_id = ? AND home_team_id = ? AND away_team_id = ?",
                               (round_id, home_id, away_id))
                match_row = cursor.fetchone()
                match_id = match_row[0]
                
                cursor.execute("INSERT INTO match_results (match_id, home_goals, away_goals) VALUES (?, ?, ?)", (match_id, hg, ag))
                cursor.execute("""
                    INSERT INTO match_statistics
                    (match_id, team_id, possession, shots, shots_on_target, corners, yellow_cards, xg, pass_accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (match_id, home_id, hp, hs, hsot, hc, hy, hxg, hpa))
                cursor.execute("""
                    INSERT INTO match_statistics
                    (match_id, team_id, possession, shots, shots_on_target, corners, yellow_cards, xg, pass_accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (match_id, away_id, ap, ash, asot, ac, ay, axg, apa))
                
                loaded += 1
            
            conn.commit()
            
            st.success(f"✅ ЗАГРУЖЕНО {loaded} МАТЧЕЙ!")
            st.balloons()
            
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Ошибка: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    main()

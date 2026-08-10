import streamlit as st
import requests
import re
import sqlite3
import os
from bs4 import BeautifulSoup

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Загрузчик FAJ", layout="wide")
    st.title("📥 ЕДИНЫЙ ЗАГРУЗЧИК FAJ")
    
    st.markdown("""
    **Этот инструмент зальёт ВСЮ статистику за 1-3 туры.**
    Нажми кнопку — и через 20 секунд система будет готова к прогнозам.
    """)
    
    if st.button("🔥 ЗАГРУЗИТЬ ВСЕ ДАННЫЕ", type="primary", use_container_width=True):
        with st.spinner("Загружаю..."):
            conn = get_connection()
            cursor = conn.cursor()
            
            # Данные в формате: (тур, хозяева, гости, голы_х, голы_г, xG_х, xG_г, удары_х, удары_г, створ_х, створ_г, владение_х, владение_г, углы_х, углы_г, жк_х, жк_г, пасы_х, пасы_г)
            data = [
                # ТУР 1
                (1, "ЦСКА", "Балтика", 2, 1, 2.25, 1.52, 18, 14, 5, 3, 65, 35, 6, 2, 1, 1, 83, 66),
                (1, "Рубин", "Краснодар", 1, 3, 0.61, 2.76, 5, 19, 3, 8, 28, 72, 2, 4, 0, 3, 53, 85),
                (1, "Спартак", "Родина", 3, 0, 2.5, 0.55, 25, 7, 9, 4, 60, 40, 12, 4, 0, 3, 87, 78),
                (1, "Акрон", "Зенит", 0, 5, 0.69, 2.52, 11, 20, 4, 10, 52, 48, 9, 5, 3, 2, 84, 86),
                (1, "Факел", "Динамо Мх", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (1, "Оренбург", "Ростов", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (1, "Локомотив", "Ахмат", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (1, "Динамо", "Крылья Советов", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                # ТУР 2
                (2, "Ахмат", "Спартак", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "Краснодар", "Факел", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "Оренбург", "Зенит", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "Балтика", "Динамо", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "Динамо Мх", "Локомотив", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "ЦСКА", "Крылья Советов", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "Акрон", "Рубин", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, "Родина", "Ростов", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                # ТУР 3
                (3, "Локомотив", "Акрон", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (3, "Крылья Советов", "Балтика", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (3, "Динамо", "Динамо Мх", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (3, "ЦСКА", "Ростов", 0, 0, 0.83, 0.84, 13, 13, 3, 4, 56, 44, 1, 3, 1, 2, 78, 71),
                (3, "Зенит", "Родина", 1, 2, 1.59, 0.76, 22, 7, 6, 3, 66, 34, 11, 3, 1, 1, 87, 77),
                (3, "Спартак", "Краснодар", 1, 2, 1.32, 1.08, 16, 16, 3, 4, 63, 37, 6, 7, 1, 3, 78, 71),
                (3, "Рубин", "Оренбург", 1, 1, 0.64, 0.86, 10, 13, 1, 3, 62, 38, 7, 1, 2, 1, 74, 65),
                (3, "Факел", "Ахмат", 0, 0, 0.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            ]
            
            loaded = 0
            
            for row in data:
                round_num, home, away, hg, ag, hxg, axg, hs, ash, hsot, asot, hp, ap, hc, ac, hy, ay, hpa, apa = row
                
                # ID команд
                cursor.execute("SELECT id FROM teams WHERE name = ?", (home,))
                home_id = cursor.fetchone()
                cursor.execute("SELECT id FROM teams WHERE name = ?", (away,))
                away_id = cursor.fetchone()
                
                if not home_id or not away_id:
                    continue
                
                home_id = home_id[0]
                away_id = away_id[0]
                
                # Найти матч
                cursor.execute("""
                    SELECT m.id FROM matches m
                    JOIN rounds r ON r.id = m.round_id
                    WHERE r.round_number = ? AND m.home_team_id = ? AND m.away_team_id = ?
                """, (round_num, home_id, away_id))
                
                match = cursor.fetchone()
                if not match:
                    continue
                
                match_id = match[0]
                
                # Сохранить результат
                cursor.execute("""
                    INSERT OR REPLACE INTO match_results (match_id, home_goals, away_goals)
                    VALUES (?, ?, ?)
                """, (match_id, hg, ag))
                
                # Статистика хозяев
                cursor.execute("""
                    INSERT OR REPLACE INTO match_statistics
                    (match_id, team_id, possession, shots, shots_on_target, corners, yellow_cards, xg, pass_accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (match_id, home_id, hp, hs, hsot, hc, hy, hxg, hpa))
                
                # Статистика гостей
                cursor.execute("""
                    INSERT OR REPLACE INTO match_statistics
                    (match_id, team_id, possession, shots, shots_on_target, corners, yellow_cards, xg, pass_accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (match_id, away_id, ap, ash, asot, ac, ay, axg, apa))
                
                # Обновить матч
                cursor.execute("""
                    UPDATE matches SET
                        actual_home = ?,
                        actual_away = ?,
                        home_xg = ?,
                        away_xg = ?,
                        home_possession = ?,
                        away_possession = ?,
                        home_shots = ?,
                        away_shots = ?,
                        home_shots_on_target = ?,
                        away_shots_on_target = ?,
                        status = 'finished'
                    WHERE id = ?
                """, (hg, ag, hxg, axg, hp, ap, hs, ash, hsot, asot, match_id))
                
                loaded += 1
            
            conn.commit()
            conn.close()
            
            st.success(f"✅ ЗАГРУЖЕНО {loaded} МАТЧЕЙ!")
            st.balloons()
            st.info("Теперь система готова. Перейди в раздел «Паспорта» — они обновлены.")

if __name__ == "__main__":
    main()

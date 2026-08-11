import streamlit as st
import sqlite3
import os
from app.parsers.championat_calendar_parser import ChampionatCalendarParser
from app.sync_engine import SyncEngine

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Загрузка календаря", layout="wide")
    st.title("📅 ЗАГРУЗКА КАЛЕНДАРЯ РПЛ")
    
    st.info("""
    Нажми кнопку — система загрузит календарь и результаты матчей РПЛ 2026/27 с championat.com.
    Всего 30 туров, 240 матчей.
    """)
    
    if st.button("📥 ЗАГРУЗИТЬ КАЛЕНДАРЬ", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # ============================================================
            # 1. Очистка данных (опционально)
            # ============================================================
            if st.checkbox("Очистить старые данные перед загрузкой", value=False):
                cursor.execute("DELETE FROM match_statistics")
                cursor.execute("DELETE FROM match_results")
                cursor.execute("DELETE FROM matches")
                conn.commit()
                st.info("🗑️ Старые данные очищены")
            
            # ============================================================
            # 2. Сезон и команды
            # ============================================================
            cursor.execute("""
                INSERT OR IGNORE INTO seasons (name, league)
                VALUES ('2026-2027', 'РПЛ')
            """)
            conn.commit()
            
            cursor.execute("SELECT id FROM seasons WHERE name = '2026-2027'")
            season_row = cursor.fetchone()
            season_id = season_row[0]
            
            teams = [
                "Акрон", "Ахмат", "Балтика", "Динамо Махачкала",
                "Динамо Москва", "Зенит", "Краснодар", "Крылья Советов",
                "Локомотив", "Оренбург", "Родина", "Ростов",
                "Рубин", "Спартак", "Факел", "ЦСКА"
            ]
            for team in teams:
                cursor.execute("INSERT OR IGNORE INTO teams (name, league) VALUES (?, 'РПЛ')", (team,))
            conn.commit()
            
            # ============================================================
            # 3. Парсинг календаря
            # ============================================================
            with st.spinner("Парсим календарь с championat.com..."):
                parser = ChampionatCalendarParser()
                matches = parser.parse()
            
            if not matches:
                st.error("❌ Не удалось загрузить календарь.")
                return
            
            # ============================================================
            # 4. Сохранение матчей
            # ============================================================
            loaded = 0
            
            for match in matches:
                home = match["home_team"]
                away = match["away_team"]
                round_num = match["round"]
                date = match["match_date"]
                time = match["match_time"]
                hg = match.get("home_goals")
                ag = match.get("away_goals")
                
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
                
                status = 'finished' if hg is not None and ag is not None else 'scheduled'
                
                cursor.execute("""
                    INSERT OR IGNORE INTO matches
                    (round_id, home_team_id, away_team_id, competition, status, date, actual_home, actual_away)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (round_id, home_id, away_id, 'РПЛ', status, date, hg, ag))
                conn.commit()
                
                if status == 'finished':
                    cursor.execute("SELECT id FROM matches WHERE round_id = ? AND home_team_id = ? AND away_team_id = ?",
                                 (round_id, home_id, away_id))
                    match_row = cursor.fetchone()
                    if match_row:
                        match_id = match_row[0]
                        cursor.execute("INSERT OR IGNORE INTO match_results (match_id, home_goals, away_goals) VALUES (?, ?, ?)",
                                     (match_id, hg, ag))
                        conn.commit()
                
                loaded += 1
            
            # ============================================================
            # 5. Обновление паспортов
            # ============================================================
            with st.spinner("Обновляем паспорта команд..."):
                sync = SyncEngine()
                result = sync.load_passports()
                st.info(f"📋 Обновлено паспортов: {result['updated']}")
            
            st.success(f"✅ ЗАГРУЖЕНО {loaded} МАТЧЕЙ!")
            st.balloons()
            
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Ошибка: {e}")
            import traceback
            st.code(traceback.format_exc())
        finally:
            conn.close()

if __name__ == "__main__":
    main()

import streamlit as st
import pandas as pd
import sys
import os
import sqlite3

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.parsers.soccerland_parser import SoccerlandParser

# Путь к БД
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def get_table_columns(cursor, table_name):
    """Возвращает список колонок таблицы"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [col[1] for col in cursor.fetchall()]

def load_fixtures():
    """Загружает календарь в БД (без дублей)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем структуру
    if not table_exists(cursor, 'seasons'):
        st.error("❌ Таблица seasons не существует")
        return 0
    
    columns = get_table_columns(cursor, 'seasons')
    
    # Проверяем сезон
    if 'name' in columns:
        cursor.execute("SELECT id FROM seasons WHERE name = '2026-2027'")
        season = cursor.fetchone()
        
        if not season:
            if 'is_active' in columns:
                cursor.execute(
                    "INSERT INTO seasons (name, is_active) VALUES (?, ?)",
                    ('2026-2027', 1)
                )
            else:
                cursor.execute(
                    "INSERT INTO seasons (name) VALUES (?)",
                    ('2026-2027',)
                )
            conn.commit()
            season_id = cursor.lastrowid
        else:
            season_id = season[0]
    else:
        st.error("❌ Нет колонки name в seasons")
        return 0
    
    # Парсим календарь
    parser = SoccerlandParser()
    matches = parser.parse_fixtures()
    
    if not matches:
        st.error("❌ Матчи не найдены")
        return 0
    
    total_loaded = 0
    
    # Загружаем матчи
    for match in matches:
        # Создаём тур
        if table_exists(cursor, 'rounds'):
            cursor.execute(
                "INSERT OR IGNORE INTO rounds (season_id, round_number) VALUES (?, ?)",
                (season_id, match["round"])
            )
            conn.commit()
            
            cursor.execute(
                "SELECT id FROM rounds WHERE season_id = ? AND round_number = ?",
                (season_id, match["round"])
            )
            round_row = cursor.fetchone()
            
            if not round_row:
                continue
            
            round_id = round_row[0]
            
            # Получаем команды
            if table_exists(cursor, 'teams'):
                cursor.execute(
                    "SELECT id FROM teams WHERE name = ?",
                    (match["home_team"],)
                )
                home = cursor.fetchone()
                
                cursor.execute(
                    "SELECT id FROM teams WHERE name = ?",
                    (match["away_team"],)
                )
                away = cursor.fetchone()
                
                if home and away:
                    home_id = home[0]
                    away_id = away[0]
                    
                    if table_exists(cursor, 'matches'):
                        # Проверяем существование матча (защита от дублей)
                        cursor.execute(
                            """SELECT id FROM matches 
                               WHERE round_id = ? AND home_team_id = ? AND away_team_id = ?""",
                            (round_id, home_id, away_id)
                        )
                        
                        if not cursor.fetchone():
                            cursor.execute(
                                """INSERT INTO matches 
                                   (round_id, home_team_id, away_team_id, match_date, match_time)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (
                                    round_id,
                                    home_id,
                                    away_id,
                                    match["match_date"],
                                    match.get("match_time", "19:00")
                                )
                            )
                            conn.commit()
                            total_loaded += 1
    
    conn.close()
    return total_loaded

def main():
    st.set_page_config(page_title="Загрузка данных", layout="wide")
    st.title("📥 Загрузка календаря РПЛ")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем текущее состояние
    matches_count = 0
    if table_exists(cursor, 'matches'):
        cursor.execute("SELECT COUNT(*) FROM matches")
        matches_count = cursor.fetchone()[0]
        st.info(f"📊 В БД: {matches_count} матчей")
    else:
        st.warning("⚠️ Таблица matches не существует")
    
    conn.close()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚀 Загрузка календаря")
        
        # Кнопка загрузки
        if st.button("📥 Загрузить календарь с Soccerland", use_container_width=True):
            with st.spinner("Парсим и загружаем календарь..."):
                loaded = load_fixtures()
                
                if loaded > 0:
                    st.success(f"✅ Загружено {loaded} новых матчей!")
                    st.balloons()
                    
                    # Обновляем счётчик
                    conn = get_connection()
                    cursor = conn.cursor()
                    if table_exists(cursor, 'matches'):
                        cursor.execute("SELECT COUNT(*) FROM matches")
                        new_count = cursor.fetchone()[0]
                        st.info(f"📊 Теперь в БД: {new_count} матчей")
                    conn.close()
                    
                    # Показываем статистику
                    st.subheader("📊 Статистика")
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT r.round_number, COUNT(m.id) 
                        FROM rounds r
                        LEFT JOIN matches m ON m.round_id = r.id
                        GROUP BY r.round_number
                        ORDER BY r.round_number
                    """)
                    stats = cursor.fetchall()
                    conn.close()
                    
                    if stats:
                        df = pd.DataFrame(stats, columns=['Тур', 'Матчей'])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ Новых матчей не найдено (возможно, уже загружены)")
        
        # Автоматическая загрузка при старте (если матчей нет)
        if matches_count == 0:
            with st.spinner("🔄 Автоматическая загрузка календаря..."):
                loaded = load_fixtures()
                if loaded > 0:
                    st.success(f"✅ Автоматически загружено {loaded} матчей!")
                    st.rerun()
    
    with col2:
        st.subheader("📤 Ручная загрузка через CSV")
        
        uploaded_file = st.file_uploader(
            "Выберите CSV файл",
            type=["csv"],
            key="manual_upload"
        )
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                required_cols = ['round', 'home_team', 'away_team', 'match_date']
                
                if all(col in df.columns for col in required_cols):
                    st.success(f"✅ Файл загружен ({len(df)} матчей)")
                    st.dataframe(df.head(5), use_container_width=True)
                    
                    if st.button("📥 Загрузить CSV в БД", use_container_width=True):
                        conn = get_connection()
                        cursor = conn.cursor()
                        
                        # Проверяем сезон
                        columns = get_table_columns(cursor, 'seasons')
                        if 'name' in columns:
                            cursor.execute("SELECT id FROM seasons WHERE name = '2026-2027'")
                            season = cursor.fetchone()
                            
                            if not season:
                                if 'is_active' in columns:
                                    cursor.execute(
                                        "INSERT INTO seasons (name, is_active) VALUES (?, ?)",
                                        ('2026-2027', 1)
                                    )
                                else:
                                    cursor.execute(
                                        "INSERT INTO seasons (name) VALUES (?)",
                                        ('2026-2027',)
                                    )
                                conn.commit()
                                season_id = cursor.lastrowid
                            else:
                                season_id = season[0]
                            
                            loaded = 0
                            for _, row in df.iterrows():
                                # Тур
                                cursor.execute(
                                    "INSERT OR IGNORE INTO rounds (season_id, round_number) VALUES (?, ?)",
                                    (season_id, int(row['round']))
                                )
                                conn.commit()
                                
                                cursor.execute(
                                    "SELECT id FROM rounds WHERE season_id = ? AND round_number = ?",
                                    (season_id, int(row['round']))
                                )
                                round_row = cursor.fetchone()
                                
                                if not round_row:
                                    continue
                                
                                round_id = round_row[0]
                                
                                # Команды
                                cursor.execute(
                                    "SELECT id FROM teams WHERE name = ?",
                                    (row['home_team'],)
                                )
                                home = cursor.fetchone()
                                
                                cursor.execute(
                                    "SELECT id FROM teams WHERE name = ?",
                                    (row['away_team'],)
                                )
                                away = cursor.fetchone()
                                
                                if home and away:
                                    cursor.execute(
                                        """INSERT OR IGNORE INTO matches 
                                           (round_id, home_team_id, away_team_id, match_date, match_time)
                                           VALUES (?, ?, ?, ?, ?)""",
                                        (
                                            round_id,
                                            home[0],
                                            away[0],
                                            row['match_date'],
                                            row.get('match_time', '19:00')
                                        )
                                    )
                                    conn.commit()
                                    loaded += 1
                            
                            conn.close()
                            st.success(f"✅ Загружено {loaded} матчей из CSV")
                            st.balloons()
                            st.rerun()
                else:
                    st.error(f"❌ Требуются колонки: {', '.join(required_cols)}")
                    
            except Exception as e:
                st.error(f"❌ Ошибка: {str(e)}")
        
        # Шаблон CSV
        if st.button("📥 Скачать шаблон CSV", use_container_width=True):
            template = pd.DataFrame({
                'round': [1, 1, 2],
                'home_team': ['Зенит', 'Спартак', 'ЦСКА'],
                'away_team': ['Спартак', 'ЦСКА', 'Динамо'],
                'match_date': ['2026-07-20', '2026-07-21', '2026-07-27'],
                'match_time': ['19:00', '17:30', '20:00']
            })
            csv = template.to_csv(index=False)
            st.download_button(
                label="⬇️ Скачать",
                data=csv,
                file_name="rpl_calendar_template.csv",
                mime="text/csv",
                use_container_width=True
            )

if __name__ == "__main__":
    main()

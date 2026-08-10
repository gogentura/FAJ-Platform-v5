import streamlit as st
import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Проверка календаря", layout="wide")
    st.title("📋 Проверка загруженного календаря")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Проверяем команды
    st.subheader("🏆 Команды")
    cursor.execute("SELECT id, name FROM teams ORDER BY name")
    teams = cursor.fetchall()
    
    if teams:
        st.success(f"✅ Найдено {len(teams)} команд")
        df_teams = pd.DataFrame(teams, columns=['ID', 'Команда'])
        st.dataframe(df_teams, use_container_width=True, hide_index=True)
    else:
        st.error("❌ Команды не найдены")
    
    # 2. Проверяем туры
    st.subheader("📅 Туры")
    cursor.execute("""
        SELECT r.id, r.round_number, COUNT(m.id) as matches_count
        FROM rounds r
        LEFT JOIN matches m ON m.round_id = r.id
        GROUP BY r.id, r.round_number
        ORDER BY r.round_number
    """)
    rounds = cursor.fetchall()
    
    if rounds:
        total_matches = sum(r[2] for r in rounds)
        st.success(f"✅ Найдено {len(rounds)} туров, {total_matches} матчей")
        
        df_rounds = pd.DataFrame(rounds, columns=['ID', 'Тур', 'Матчей'])
        st.dataframe(df_rounds, use_container_width=True, hide_index=True)
        
        # Проверяем полноту
        if len(rounds) == 30 and total_matches == 240:
            st.success("✅ Идеально! 30 туров по 8 матчей")
        elif len(rounds) < 30:
            st.warning(f"⚠️ Найдено {len(rounds)} туров (ожидается 30)")
        elif total_matches < 240:
            st.warning(f"⚠️ Найдено {total_matches} матчей (ожидается 240)")
    else:
        st.error("❌ Туры не найдены")
    
    # 3. Проверяем дубли
    st.subheader("🔄 Проверка дублей")
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(DISTINCT round_id || '-' || home_team_id || '-' || away_team_id) as unique_count
        FROM matches
    """)
    total, unique = cursor.fetchone()
    
    if total == unique:
        st.success(f"✅ Дублей нет ({total} уникальных матчей)")
    else:
        st.error(f"⚠️ Найдено {total - unique} дублей")
    
    # 4. Показываем примеры матчей
    st.subheader("📋 Примеры матчей (первые 10)")
    cursor.execute("""
        SELECT 
            r.round_number as тур,
            t1.name as хозяева,
            t2.name as гости,
            m.match_date as дата,
            m.match_time as время
        FROM matches m
        JOIN rounds r ON r.id = m.round_id
        JOIN teams t1 ON t1.id = m.home_team_id
        JOIN teams t2 ON t2.id = m.away_team_id
        ORDER BY r.round_number, m.match_date
        LIMIT 10
    """)
    examples = cursor.fetchall()
    
    if examples:
        df_examples = pd.DataFrame(examples, columns=['Тур', 'Хозяева', 'Гости', 'Дата', 'Время'])
        st.dataframe(df_examples, use_container_width=True, hide_index=True)
    
    conn.close()

if __name__ == "__main__":
    main()

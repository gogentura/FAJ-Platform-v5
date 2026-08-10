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
    st.title("📋 Проверка календаря РПЛ")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Общая статистика
    st.subheader("📊 Общая статистика")
    
    cursor.execute("SELECT COUNT(*) FROM teams WHERE league = 'RPL'")
    teams_count = cursor.fetchone()[0]
    st.metric("Команды", teams_count)
    
    cursor.execute("SELECT COUNT(*) FROM rounds")
    rounds_count = cursor.fetchone()[0]
    st.metric("Туры", rounds_count)
    
    cursor.execute("SELECT COUNT(*) FROM matches")
    matches_count = cursor.fetchone()[0]
    st.metric("Матчи", matches_count)
    
    # 2. Проверка по турам
    st.subheader("📅 Матчи по турам")
    
    cursor.execute("""
        SELECT 
            r.round_number as тур,
            COUNT(m.id) as матчей
        FROM rounds r
        LEFT JOIN matches m ON m.round_id = r.id
        GROUP BY r.round_number
        ORDER BY r.round_number
    """)
    
    rounds_data = cursor.fetchall()
    
    if rounds_data:
        df = pd.DataFrame(rounds_data, columns=['Тур', 'Матчей'])
        
        # Подсвечиваем проблемы
        def highlight_matches(val):
            if val < 8:
                return 'background-color: #ffcccc'
            elif val == 8:
                return 'background-color: #ccffcc'
            return ''
        
        styled = df.style.applymap(highlight_matches, subset=['Матчей'])
        st.dataframe(styled, use_container_width=True, hide_index=True)
        
        # Проверка полноты
        total_expected = 30 * 8  # 30 туров × 8 матчей
        if matches_count >= 200:
            st.success(f"✅ Календарь загружен: {matches_count} матчей (ожидается ~240)")
        else:
            st.warning(f"⚠️ Загружено только {matches_count} матчей (ожидается ~240)")
    else:
        st.warning("⚠️ Нет данных о турах")
    
    # 3. Проверка дублей
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
        st.warning(f"⚠️ Найдено {total - unique} дублей")
    
    # 4. Примеры матчей
    st.subheader("📋 Примеры матчей")
    
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
    
    # 5. Команды с пропущенными матчами
    st.subheader("🏆 Команды")
    
    cursor.execute("""
        SELECT 
            t.name as команда,
            COUNT(DISTINCT m.id) as матчей,
            MIN(r.round_number) as первый_тур,
            MAX(r.round_number) as последний_тур
        FROM teams t
        LEFT JOIN matches m ON m.home_team_id = t.id OR m.away_team_id = t.id
        LEFT JOIN rounds r ON r.id = m.round_id
        WHERE t.league = 'RPL'
        GROUP BY t.id, t.name
        ORDER BY матчей DESC
    """)
    
    teams_data = cursor.fetchall()
    if teams_data:
        df_teams = pd.DataFrame(teams_data, columns=['Команда', 'Матчей', 'Первый тур', 'Последний тур'])
        st.dataframe(df_teams, use_container_width=True, hide_index=True)
        
        # Проверяем, что у всех команд есть матчи
        teams_without_matches = [row[0] for row in teams_data if row[1] == 0]
        if teams_without_matches:
            st.warning(f"⚠️ Команды без матчей: {', '.join(teams_without_matches)}")
    
    conn.close()

if __name__ == "__main__":
    main()

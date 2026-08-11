import streamlit as st
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Диагностика матчей", layout="wide")
    st.title("🔍 ДИАГНОСТИКА МАТЧЕЙ — КАКОЙ МАТЧ ОТСУТСТВУЕТ?")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Все матчи, которые должны быть в базе
    expected_matches = [
        # ТУР 1
        (1, "ЦСКА", "Балтика"),
        (1, "Рубин", "Краснодар"),
        (1, "Спартак", "Родина"),
        (1, "Акрон", "Зенит"),
        (1, "Динамо Москва", "Крылья Советов"),
        (1, "Факел", "Динамо Махачкала"),
        (1, "Оренбург", "Ростов"),
        (1, "Локомотив", "Ахмат"),
        # ТУР 2
        (2, "Родина", "Ростов"),
        (2, "Акрон", "Рубин"),
        (2, "ЦСКА", "Крылья Советов"),
        (2, "Динамо Махачкала", "Локомотив"),
        (2, "Балтика", "Динамо Москва"),
        (2, "Оренбург", "Зенит"),
        (2, "Краснодар", "Факел"),
        (2, "Ахмат", "Спартак"),
        # ТУР 3
        (3, "Локомотив", "Акрон"),
        (3, "Крылья Советов", "Балтика"),
        (3, "Динамо Москва", "Динамо Махачкала"),
        (3, "ЦСКА", "Ростов"),
        (3, "Зенит", "Родина"),
        (3, "Спартак", "Краснодар"),
        (3, "Рубин", "Оренбург"),
    ]
    
    st.subheader("📊 Проверка матчей в БД")
    
    missing = []
    found = []
    
    for round_num, home, away in expected_matches:
        cursor.execute("""
            SELECT m.id
            FROM matches m
            JOIN rounds r ON r.id = m.round_id
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
            WHERE r.round_number = ? AND th.name = ? AND ta.name = ?
        """, (round_num, home, away))
        
        row = cursor.fetchone()
        if row:
            found.append(f"✅ Тур {round_num}: {home} vs {away} (ID: {row[0]})")
        else:
            missing.append(f"❌ Тур {round_num}: {home} vs {away} — НЕ НАЙДЕН!")
    
    st.write("### ✅ Найдено:", len(found))
    for f in found:
        st.write(f)
    
    if missing:
        st.error(f"### ❌ Не найдено: {len(missing)}")
        for m in missing:
            st.error(m)
    else:
        st.success("🎉 ВСЕ 24 МАТЧА НАЙДЕНЫ!")
    
    conn.close()

if __name__ == "__main__":
    main()

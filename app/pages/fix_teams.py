import streamlit as st
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Исправление команд", layout="wide")
    st.title("🔧 ИСПРАВЛЕНИЕ КОМАНД")
    
    st.warning("""
    ⚠️ ЭТО УДАЛИТ ДУБЛИ И НЕСУЩЕСТВУЮЩИЕ КОМАНДЫ:
    - Динамо (дубль Динамо Москва)
    - Динамо Мх (дубль Динамо Махачкала)
    - Химки (нет в РПЛ 2026/27)
    """)
    
    if st.button("🔥 ИСПРАВИТЬ КОМАНДЫ", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # 1. Удаляем дубли и мусор
            cursor.execute("DELETE FROM teams WHERE name IN ('Динамо', 'Динамо Мх', 'Химки')")
            conn.commit()
            
            # 2. Переименовываем правильные названия (если нужно)
            cursor.execute("UPDATE teams SET name = 'Динамо Москва' WHERE name = 'Динамо Москва'")
            cursor.execute("UPDATE teams SET name = 'Динамо Махачкала' WHERE name = 'Динамо Махачкала'")
            conn.commit()
            
            # 3. Проверяем, что осталось
            cursor.execute("SELECT id, name FROM teams WHERE league = 'РПЛ' ORDER BY name")
            teams = cursor.fetchall()
            
            conn.close()
            
            st.success(f"✅ ОСТАЛОСЬ {len(teams)} КОМАНД РПЛ:")
            
            for team_id, name in teams:
                st.write(f"  ✅ {name}")
            
            st.balloons()
            
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Ошибка: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    main()

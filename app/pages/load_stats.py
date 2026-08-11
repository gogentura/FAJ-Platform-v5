import streamlit as st
import sqlite3
import os
from app.parsers.nb_bet_loader import NBBetLoader

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'faj.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def main():
    st.set_page_config(page_title="Загрузка статистики", layout="wide")
    st.title("📊 ЗАГРУЗКА СТАТИСТИКИ")
    
    st.info("""
    Нажми кнопку — система загрузит статистику 24 матчей 1-3 туров с nb-bet.com.
    """)
    
    match_urls = [
        # ТУР 1
        "https://nb-bet.com/Events/1612885-cska-baltika-prognoz-na-match",
        "https://nb-bet.com/Events/1612882-rubin-krasnodar-prognoz-na-match",
        "https://nb-bet.com/Events/1612883-spartak-moskva-rodina-prognoz-na-match",
        "https://nb-bet.com/Events/1663973-akron-tolyatti-zenit-prognoz-na-match",
        "https://nb-bet.com/Events/1612879-dinamo-moskva-krylya-sovetov-prognoz-na-match",
        "https://nb-bet.com/Events/1612884-fakel-dinamo-mahachkala-prognoz-na-match",
        "https://nb-bet.com/Events/1612881-orenburg-rostov-prognoz-na-match",
        "https://nb-bet.com/Events/1612880-lokomotiv-moskva-ahmat-prognoz-na-match",
        # ТУР 2
        "https://nb-bet.com/Events/1612871-ahmat-spartak-moskva-prognoz-na-match",
        "https://nb-bet.com/Events/1612874-krasnodar-fakel-prognoz-na-match",
        "https://nb-bet.com/Events/1612875-orenburg-zenit-prognoz-na-match",
        "https://nb-bet.com/Events/1663972-baltika-dinamo-moskva-prognoz-na-match",
        "https://nb-bet.com/Events/1612873-dinamo-mahachkala-lokomotiv-moskva-prognoz-na-match",
        "https://nb-bet.com/Events/1612877-cska-krylya-sovetov-prognoz-na-match",
        "https://nb-bet.com/Events/1612870-akron-tolyatti-rubin-prognoz-na-match",
        "https://nb-bet.com/Events/1612876-rodina-rostov-prognoz-na-match",
        # ТУР 3
        "https://nb-bet.com/Events/1612865-lokomotiv-moskva-akron-tolyatti-prognoz-na-match",
        "https://nb-bet.com/Events/1612864-krylya-sovetov-baltika-prognoz-na-match",
        "https://nb-bet.com/Events/1612862-dinamo-moskva-dinamo-mahachkala-prognoz-na-match",
        "https://nb-bet.com/Events/1681931-cska-rostov-prognoz-na-match",
        "https://nb-bet.com/Events/1612863-zenit-rodina-prognoz-na-match",
        "https://nb-bet.com/Events/1612868-spartak-moskva-krasnodar-prognoz-na-match",
        "https://nb-bet.com/Events/1612867-rubin-orenburg-prognoz-na-match",
        "https://nb-bet.com/Events/1612869-fakel-ahmat-prognoz-na-match",
    ]
    
    # ============================================================
    # ОПЦИИ
    # ============================================================
    with st.expander("⚙️ Настройки"):
        clear_existing = st.checkbox("Очистить существующую статистику перед загрузкой", value=False)
    
    if st.button("📊 ЗАГРУЗИТЬ СТАТИСТИКУ", type="primary", use_container_width=True):
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # ============================================================
            # 1. Очистка (опционально)
            # ============================================================
            if clear_existing:
                cursor.execute("DELETE FROM match_statistics")
                conn.commit()
                st.info("🗑️ Старая статистика очищена")
            
            # ============================================================
            # 2. Парсинг и загрузка
            # ============================================================
            parser = NBBetLoader()
            loaded = 0
            skipped = 0
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, url in enumerate(match_urls):
                status_text.text(f"Загрузка {i+1}/{len(match_urls)}...")
                
                match_data = parser.parse_match(url)
                if not match_data:
                    skipped += 1
                    progress_bar.progress((i + 1) / len(match_urls))
                    continue
                
                # Находим матч в БД
                cursor.execute("""
                    SELECT m.id FROM matches m
                    JOIN teams th ON th.id = m.home_team_id
                    JOIN teams ta ON ta.id = m.away_team_id
                    WHERE th.name = ? AND ta.name = ?
                """, (match_data["home_team"], match_data["away_team"]))
                
                match_row = cursor.fetchone()
                if not match_row:
                    st.warning(f"⚠️ Матч не найден: {match_data['home_team']} vs {match_data['away_team']}")
                    skipped += 1
                    progress_bar.progress((i + 1) / len(match_urls))
                    continue
                
                match_id = match_row[0]
                
                # Получаем ID команд
                cursor.execute("SELECT id FROM teams WHERE name = ?", (match_data["home_team"],))
                home_row = cursor.fetchone()
                cursor.execute("SELECT id FROM teams WHERE name = ?", (match_data["away_team"],))
                away_row = cursor.fetchone()
                
                if not home_row or not away_row:
                    skipped += 1
                    progress_bar.progress((i + 1) / len(match_urls))
                    continue
                
                home_id = home_row[0]
                away_id = away_row[0]
                
                # ============================================================
                # 3. Обновляем матч (xG и т.д.)
                # ============================================================
                cursor.execute("""
                    UPDATE matches SET
                        home_xg = ?,
                        away_xg = ?,
                        home_possession = ?,
                        away_possession = ?,
                        home_shots = ?,
                        away_shots = ?,
                        home_shots_on_target = ?,
                        away_shots_on_target = ?
                    WHERE id = ?
                """, (
                    match_data.get("home_xg"),
                    match_data.get("away_xg"),
                    match_data.get("home_possession"),
                    match_data.get("away_possession"),
                    match_data.get("home_shots"),
                    match_data.get("away_shots"),
                    match_data.get("home_shots_on_target"),
                    match_data.get("away_shots_on_target"),
                    match_id
                ))
                
                # ============================================================
                # 4. Статистика хозяев (с защитой от дублей)
                # ============================================================
                cursor.execute("""
                    INSERT OR REPLACE INTO match_statistics
                    (match_id, team_id, possession, shots, shots_on_target,
                     corners, yellow_cards, xg, pass_accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, home_id,
                    match_data.get("home_possession"),
                    match_data.get("home_shots"),
                    match_data.get("home_shots_on_target"),
                    match_data.get("home_corners"),
                    match_data.get("home_yellow_cards"),
                    match_data.get("home_xg"),
                    match_data.get("home_pass_accuracy")
                ))
                
                # ============================================================
                # 5. Статистика гостей (с защитой от дублей)
                # ============================================================
                cursor.execute("""
                    INSERT OR REPLACE INTO match_statistics
                    (match_id, team_id, possession, shots, shots_on_target,
                     corners, yellow_cards, xg, pass_accuracy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, away_id,
                    match_data.get("away_possession"),
                    match_data.get("away_shots"),
                    match_data.get("away_shots_on_target"),
                    match_data.get("away_corners"),
                    match_data.get("away_yellow_cards"),
                    match_data.get("away_xg"),
                    match_data.get("away_pass_accuracy")
                ))
                
                loaded += 1
                progress_bar.progress((i + 1) / len(match_urls))
            
            conn.commit()
            status_text.text("✅ Загрузка завершена!")
            
            # ============================================================
            # 6. Результат
            # ============================================================
            st.success(f"✅ ЗАГРУЖЕНО {loaded} МАТЧЕЙ!")
            if skipped > 0:
                st.warning(f"⚠️ Пропущено: {skipped} матчей")
            
            # Показываем статистику
            cursor.execute("SELECT COUNT(*) FROM match_statistics")
            total_stats = cursor.fetchone()[0]
            st.info(f"📊 Всего записей статистики: {total_stats}")
            
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

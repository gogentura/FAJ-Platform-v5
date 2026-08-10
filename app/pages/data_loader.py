import streamlit as st
import pandas as pd
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.parsers.soccerland_parser import SoccerlandParser
from app.database import get_db

def main():
    st.set_page_config(page_title="Загрузка данных", layout="wide")
    st.title("📥 Загрузка календаря РПЛ")
    
    # Получаем соединение с БД
    db = get_db()
    
    # Проверяем текущее состояние
    try:
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches")
        matches_count = cursor.fetchone()[0]
        st.info(f"📊 В БД: {matches_count} матчей")
    except:
        st.warning("⚠️ Таблица matches пуста или не создана")
        matches_count = 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚀 Автоматическая загрузка")
        
        if st.button("📥 Загрузить календарь с Soccerland", use_container_width=True):
            with st.spinner("Парсим календарь..."):
                try:
                    parser = SoccerlandParser()
                    matches = parser.parse_fixtures()
                    
                    if matches:
                        st.success(f"✅ Найдено {len(matches)} матчей!")
                        
                        # Сохраняем в БД
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Получаем или создаём сезон
                        cursor = db.cursor()
                        
                        # Проверяем сезон
                        cursor.execute(
                            "SELECT id FROM seasons WHERE name = '2026-2027'"
                        )
                        season = cursor.fetchone()
                        
                        if not season:
                            cursor.execute(
                                "INSERT INTO seasons (name, is_active) VALUES (?, ?)",
                                ('2026-2027', 1)
                            )
                            db.commit()
                            season_id = cursor.lastrowid
                        else:
                            season_id = season[0]
                        
                        total_loaded = 0
                        
                        for i, match in enumerate(matches):
                            status_text.text(f"Загружаем матч {i+1}/{len(matches)}")
                            
                            # Создаём тур
                            cursor.execute(
                                "INSERT OR IGNORE INTO rounds (season_id, round_number) VALUES (?, ?)",
                                (season_id, match["round"])
                            )
                            db.commit()
                            
                            # Получаем ID тура
                            cursor.execute(
                                "SELECT id FROM rounds WHERE season_id = ? AND round_number = ?",
                                (season_id, match["round"])
                            )
                            round_row = cursor.fetchone()
                            
                            if not round_row:
                                continue
                            
                            round_id = round_row[0]
                            
                            # Получаем ID команд
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
                                
                                # Проверяем, есть ли уже такой матч
                                cursor.execute(
                                    """SELECT id FROM matches 
                                       WHERE round_id = ? AND home_team_id = ? AND away_team_id = ?""",
                                    (round_id, home_id, away_id)
                                )
                                
                                if not cursor.fetchone():
                                    # Создаём матч
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
                                    db.commit()
                                    total_loaded += 1
                            
                            progress_bar.progress((i + 1) / len(matches))
                        
                        status_text.text("✅ Загрузка завершена!")
                        st.success(f"✅ Загружено {total_loaded} новых матчей")
                        st.balloons()
                        
                        # Показываем статистику
                        st.subheader("📊 Статистика загрузки")
                        
                        # Группируем по турам
                        df = pd.DataFrame(matches)
                        rounds_stats = df.groupby('round').size().reset_index(name='matches')
                        
                        st.dataframe(
                            rounds_stats,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Показываем примеры
                        st.subheader("📋 Примеры загруженных матчей")
                        st.dataframe(
                            df.head(10),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.error("❌ Матчи не найдены на сайте")
                        
                except Exception as e:
                    st.error(f"❌ Ошибка: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
    
    with col2:
        st.subheader("📤 Ручная загрузка через CSV")
        
        uploaded_file = st.file_uploader(
            "Выберите CSV файл с календарём",
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
                    
                    if st.button("📥 Загрузить в БД", use_container_width=True):
                        # Загружаем CSV в БД
                        cursor = db.cursor()
                        
                        # Создаём сезон
                        cursor.execute(
                            "INSERT OR IGNORE INTO seasons (name, is_active) VALUES (?, ?)",
                            ('2026-2027', 1)
                        )
                        db.commit()
                        
                        cursor.execute(
                            "SELECT id FROM seasons WHERE name = '2026-2027'"
                        )
                        season_row = cursor.fetchone()
                        season_id = season_row[0]
                        
                        loaded = 0
                        for _, row in df.iterrows():
                            # Создаём тур
                            cursor.execute(
                                "INSERT OR IGNORE INTO rounds (season_id, round_number) VALUES (?, ?)",
                                (season_id, int(row['round']))
                            )
                            db.commit()
                            
                            cursor.execute(
                                "SELECT id FROM rounds WHERE season_id = ? AND round_number = ?",
                                (season_id, int(row['round']))
                            )
                            round_row = cursor.fetchone()
                            
                            if not round_row:
                                continue
                            
                            round_id = round_row[0]
                            
                            # Получаем команды
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
                                db.commit()
                                loaded += 1
                        
                        st.success(f"✅ Загружено {loaded} матчей из CSV")
                        st.balloons()
                        
                else:
                    st.error(f"❌ Требуются колонки: {', '.join(required_cols)}")
                    st.info("Ваши колонки: " + ", ".join(df.columns))
                    
            except Exception as e:
                st.error(f"❌ Ошибка чтения файла: {str(e)}")
        
        # Шаблон для скачивания
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
                label="⬇️ Скачать шаблон CSV",
                data=csv,
                file_name="rpl_calendar_template.csv",
                mime="text/csv",
                use_container_width=True
            )

if __name__ == "__main__":
    main()

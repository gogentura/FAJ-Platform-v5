# app/pages/data_loader.py

import streamlit as st
import pandas as pd
from app.parsers.soccerland_parser import SoccerlandParser
from app.database import Database

def main():
    st.set_page_config(page_title="Загрузка данных", layout="wide")
    st.title("📥 Загрузка календаря РПЛ")
    
    db = Database()
    
    # Проверяем текущее состояние
    matches_count = db.get_matches_count()
    st.info(f"📊 В БД: {matches_count} матчей")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Загрузить календарь с Soccerland", use_container_width=True):
            with st.spinner("Парсим календарь..."):
                parser = SoccerlandParser()
                matches = parser.parse_fixtures()
                
                if matches:
                    # Сохраняем в БД
                    season_id = db.get_or_create_season("2026-2027")
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, match in enumerate(matches):
                        status_text.text(f"Загружаем матч {i+1}/{len(matches)}")
                        
                        # Создаём тур
                        round_id = db.create_round(
                            season_id=season_id,
                            round_number=match["round"]
                        )
                        
                        # Получаем ID команд
                        home_id = db.get_team_id_by_name(match["home_team"])
                        away_id = db.get_team_id_by_name(match["away_team"])
                        
                        if home_id and away_id:
                            db.create_match(
                                round_id=round_id,
                                home_team_id=home_id,
                                away_team_id=away_id,
                                match_date=match["match_date"],
                                match_time=match["match_time"]
                            )
                        
                        progress_bar.progress((i + 1) / len(matches))
                    
                    status_text.text("✅ Загрузка завершена!")
                    st.success(f"✅ Загружено {len(matches)} матчей")
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
                    
                    # Показываем первые 10 матчей
                    st.subheader("📋 Примеры загруженных матчей")
                    st.dataframe(
                        df.head(10),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.error("❌ Не удалось загрузить календарь")
    
    with col2:
        # Альтернатива: ручная загрузка
        st.subheader("📤 Или загрузите вручную")
        
        uploaded_file = st.file_uploader(
            "CSV файл с календарём",
            type=["csv"],
            key="manual_upload"
        )
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                required_cols = ['round', 'home_team', 'away_team', 'match_date']
                
                if all(col in df.columns for col in required_cols):
                    st.success(f"✅ Файл загружен ({len(df)} матчей)")
                    
                    if st.button("Загрузить в БД", use_container_width=True):
                        # Загружаем...
                        pass
                else:
                    st.error(f"❌ Требуются колонки: {', '.join(required_cols)}")
            except Exception as e:
                st.error(f"❌ Ошибка чтения файла: {e}")
        
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
                label="Скачать шаблон",
                data=csv,
                file_name="rpl_calendar_template.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()

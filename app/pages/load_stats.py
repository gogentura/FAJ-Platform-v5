import streamlit as st
from app.parsers.nb_bet_parser import NBBetParser, load_match_stats_to_db
from app.database import FAJDatabase

def main():
    st.set_page_config(page_title="Загрузка статистики", layout="wide")
    st.title("📊 Загрузка статистики матчей РПЛ")
    
    st.info("""
    Парсер автоматически найдёт все матчи на nb-bet.com и загрузит:
    - Результаты (счёт)
    - xG
    - Удары, удары в створ
    - Владение
    - Угловые
    - Жёлтые карточки
    - Точность передач
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Загрузить статистику 1-3 туров", use_container_width=True):
            with st.spinner("Парсим статистику..."):
                parser = NBBetParser()
                db = FAJDatabase()
                
                # Парсим туры 1-3
                all_matches = parser.parse_all_rounds([1, 2, 3])
                
                if all_matches:
                    st.success(f"✅ Найдено {len(all_matches)} матчей")
                    
                    # Показываем предпросмотр
                    st.subheader("📋 Предпросмотр")
                    for m in all_matches[:5]:
                        st.write(f"Тур {m['round']}: {m['home_team']} {m['home_goals']}:{m['away_goals']} {m['away_team']}")
                    
                    # Загружаем в БД
                    loaded = load_match_stats_to_db(all_matches, db)
                    st.success(f"✅ Загружено {loaded} матчей в БД")
                    st.balloons()
                else:
                    st.error("❌ Матчи не найдены")
    
    with col2:
        st.subheader("📊 Статистика после загрузки")
        
        if st.button("📊 Показать статистику", use_container_width=True):
            db = FAJDatabase()
            conn = db._get_connection()
            cursor = conn.cursor()
            
            # Количество матчей с результатами
            cursor.execute("SELECT COUNT(*) FROM match_results")
            results_count = cursor.fetchone()[0]
            st.metric("Матчей с результатами", results_count)
            
            # Количество матчей со статистикой
            cursor.execute("SELECT COUNT(DISTINCT match_id) FROM match_statistics")
            stats_count = cursor.fetchone()[0]
            st.metric("Матчей со статистикой", stats_count)
            
            conn.close()

if __name__ == "__main__":
    main()

import streamlit as st
from app.parsers.nb_bet_parser import NBBetParser, load_match_stats_to_db
from app.database import FAJDatabase

def main():
    st.set_page_config(page_title="Загрузка статистики", layout="wide")
    st.title("📊 Загрузка статистики матчей")
    
    if st.button("🚀 Загрузить статистику 1-3 туров"):
        with st.spinner("Парсим статистику..."):
            parser = NBBetParser()
            db = FAJDatabase()
            
            all_matches = parser.parse_all_rounds([1, 2, 3])
            
            if all_matches:
                st.success(f"✅ Найдено {len(all_matches)} матчей")
                
                loaded = load_match_stats_to_db(all_matches, db)
                st.success(f"✅ Загружено {loaded} матчей в БД")
                st.balloons()
            else:
                st.error("❌ Матчи не найдены")

if __name__ == "__main__":
    main()

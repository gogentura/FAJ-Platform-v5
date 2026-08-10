# smart_tables_test.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import streamlit as st
import requests
from bs4 import BeautifulSoup
import time

def main():
    st.set_page_config(page_title="Диагностика источников", layout="wide")
    st.title("🔍 Диагностика источников календаря РПЛ")
    
    # Проверяем три источника
    sources = {
        "Soccerland": {
            "url": "https://soccerland.ru/russia/premier-liga/2026-2027/calendar",
            "method": "get"
        },
        "Smart Tables": {
            "url": "https://smart-tables.ru/league/russia/premier_league",
            "method": "get"
        },
        "Soccer.ru": {
            "url": "https://www.soccer.ru/tournament/russia/results",
            "method": "get"
        }
    }
    
    results = {}
    
    for name, source in sources.items():
        with st.spinner(f"Проверяем {name}..."):
            try:
                response = requests.get(
                    source["url"],
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    timeout=10
                )
                
                results[name] = {
                    "status": response.status_code,
                    "ok": response.status_code == 200,
                    "size": len(response.text),
                    "preview": response.text[:500] if response.ok else "N/A"
                }
            except Exception as e:
                results[name] = {
                    "status": "ERROR",
                    "ok": False,
                    "error": str(e),
                    "size": 0
                }
    
    # Отображаем результаты
    st.header("📊 Результаты диагностики")
    
    for name, result in results.items():
        col1, col2, col3 = st.columns([2, 1, 3])
        
        with col1:
            if result.get("ok"):
                st.success(f"✅ {name}")
            else:
                st.error(f"❌ {name}")
        
        with col2:
            st.metric("Статус", result.get("status", "N/A"))
        
        with col3:
            if result.get("ok"):
                st.metric("Размер", f"{result['size']} байт")
                st.caption("✅ Страница загружена")
                
                # Ищем признаки календаря
                if "Зенит" in result["preview"] or "Спартак" in result["preview"]:
                    st.success("✅ Найдены команды РПЛ")
                if "Тур" in result["preview"]:
                    st.success("✅ Найдены туры")
            else:
                st.caption(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
    
    # Рекомендации
    st.header("🎯 Рекомендации")
    working_sources = [name for name, res in results.items() if res.get("ok")]
    
    if working_sources:
        st.success(f"✅ Работающие источники: {', '.join(working_sources)}")
        st.info(f"📝 Рекомендую использовать: {working_sources[0]}")
    else:
        st.error("❌ Нет работающих источников. Нужен другой подход.")
        
        # Предложение альтернативы
        st.warning("""
        ### 💡 Альтернативный подход:
        
        1. **Ручной ввод календаря** через Excel/CSV
        2. **Использовать API** (Football-Data.org)
        3. **Загрузить JSON** с готовыми матчами
        4. **Парсить другой сайт** (например, championat.com)
        """)
        
        # Кнопка для ручного ввода
        if st.button("📥 Загрузить календарь вручную"):
            st.session_state.show_manual_input = True

if __name__ == "__main__":
    main()

import streamlit as st
import requests

def main():
    st.title("🔍 Диагностика источников")
    
    urls = [
        ("Smart Tables", "https://smart-tables.ru/league/russia/premier_league"),
        ("Soccer.ru", "https://www.soccer.ru/tournament/russia/results")
    ]
    
    if st.button("Запустить проверку"):
        for name, url in urls:
            try:
                r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                st.write(f"**{name}**")
                st.write(f"Статус: {r.status_code}")
                st.write(f"Размер: {len(r.text)} байт")
                if "Тур" in r.text:
                    st.success("✅ Найдены туры")
                if "Зенит" in r.text or "Спартак" in r.text:
                    st.success("✅ Найдены команды")
                st.divider()
            except Exception as e:
                st.error(f"{name}: {e}")

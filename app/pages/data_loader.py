#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.1 - Загрузка данных
"""

import streamlit as st
from datetime import datetime

from app.database import FAJDatabase
from app.parsers.soccerland_parser import SoccerlandParser
from app.core.prediction_manager import get_prediction_manager


def main():
    st.title("📥 Загрузка данных")
    st.caption("Парсинг soccerland.ru, анализ и прогноз на тур")
    
    db = FAJDatabase()
    parser = SoccerlandParser()
    pm = get_prediction_manager()
    
    # =========================================================
    # 0. ДИАГНОСТИКА ПАРСЕРА (ПО КНОПКЕ)
    # =========================================================
    st.subheader("🔍 Диагностика парсера")
    
    if st.button("🔍 Проверить парсер", type="secondary"):
        with st.spinner("Проверка соединения с soccerland.ru..."):
            try:
                diagnostics = parser.diagnostics()
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Всего матчей", diagnostics.get('total_matches', 0))
                with col2:
                    st.metric("📅 Туров", diagnostics.get('total_rounds', 0))
                with col3:
                    st.metric("🏷️ Команд", diagnostics.get('team_count', 0))
                with col4:
                    status = diagnostics.get('status', 'UNKNOWN')
                    st.metric("📌 Статус", status)
                
                with st.expander("📋 Детали диагностики"):
                    st.write("**Матчи по турам:**")
                    rounds = diagnostics.get('rounds', {})
                    if rounds:
                        for r, count in sorted(rounds.items()):
                            st.write(f"  Тур {r}: {count} матчей")
                    else:
                        st.warning("⚠️ Матчи не найдены")
                    
                    st.write(f"**Завершено:** {diagnostics.get('finished', 0)}")
                    st.write(f"**Запланировано:** {diagnostics.get('scheduled', 0)}")
                    
                if diagnostics.get('status') != 'READY':
                    st.warning("⚠️ Парсер не готов. Возможно, сайт недоступен или изменилась структура.")
                    
            except Exception as e:
                st.error(f"❌ Ошибка диагностики: {e}")
    
    st.divider()
    
    # =========================================================
    # 1. СТАТИСТИКА БД
    # =========================================================
    st.subheader("📊 Статистика базы данных")
    
    status = db.get_status()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏷️ Команды", status['tables'].get('teams', 0))
    with col2:
        st.metric("⚽ Матчи", status['tables'].get('matches', 0))
    with col3:
        st.metric("📋 Паспорта", status['tables'].get('team_passports', 0))
    with col4:
        st.metric("📊 Прогнозы", status['tables'].get('predictions', 0))
    
    st.divider()
    
    # =========================================================
    # 2. ПАРСИНГ РАСПИСАНИЯ
    # =========================================================
    st.subheader("📥 Загрузка расписания")
    st.caption("Парсинг календаря с soccerland.ru и загрузка в БД")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        tour_to_load = st.number_input(
            "Номер тура для загрузки",
            min_value=1,
            max_value=30,
            value=4,
            step=1,
            key="tour_load"
        )
    with col2:
        if st.button("📥 Загрузить тур", type="primary", use_container_width=True):
            with st.spinner(f"🧠 Загрузка {tour_to_load} тура..."):
                try:
                    matches = parser.get_matches_by_tour(tour_to_load)
                    
                    if not matches:
                        st.warning("⚠️ Не удалось получить данные с soccerland.ru")
                    else:
                        loaded = parser.load_matches_to_db(matches, tour_to_load)
                        
                        if loaded > 0:
                            st.success(f"✅ Загружено матчей: {loaded}")
                        else:
                            st.info("ℹ️ Все матчи уже загружены")
                            
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # =========================================================
    # 3. РУЧНОЙ ВВОД МАТЧЕЙ
    # =========================================================
    st.subheader("✏️ Ручной ввод матчей")
    st.caption("Если парсер не работает, введите матчи вручную")
    
    with st.expander("📝 Ввести матчи тура вручную"):
        tour_manual = st.number_input(
            "Номер тура",
            min_value=1,
            max_value=30,
            value=4,
            step=1,
            key="manual_tour"
        )
        
        teams = db.get_teams()
        team_names = [t['name'] for t in teams] if teams else []
        
        if not team_names:
            st.warning("⚠️ Сначала загрузите команды через 'Синхронизацию'")
        else:
            num_matches = st.number_input("Количество матчей", min_value=1, max_value=16, value=8, step=1)
            
            matches_manual = []
            for i in range(int(num_matches)):
                st.write(f"**Матч {i+1}**")
                col1, col2 = st.columns(2)
                with col1:
                    home = st.selectbox(f"Хозяева {i+1}", team_names, key=f"manual_home_{i}")
                with col2:
                    away = st.selectbox(f"Гости {i+1}", team_names, key=f"manual_away_{i}")
                
                if home != away:
                    matches_manual.append({"home": home, "away": away})
                else:
                    st.warning(f"⚠️ Команды не могут совпадать в матче {i+1}")
            
            if st.button("💾 Сохранить матчи вручную", type="primary"):
                if matches_manual:
                    with st.spinner("Сохранение..."):
                        loaded = parser.load_matches_to_db(matches_manual, tour_manual)
                        st.success(f"✅ Сохранено матчей: {loaded}")
                        st.rerun()
                else:
                    st.warning("⚠️ Нет матчей для сохранения")
    
    st.divider()
    
    # =========================================================
    # 4. АНАЛИЗ СЫГРАННЫХ ТУРОВ
    # =========================================================
    st.subheader("🔬 Анализ сыгранных туров")
    st.caption("Обновление паспортов команд на основе результатов матчей")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        tour_to_analyze = st.number_input(
            "Номер тура для анализа",
            min_value=1,
            max_value=30,
            value=3,
            step=1,
            key="tour_analyze"
        )
    with col2:
        if st.button("🔬 Анализировать тур", type="primary", use_container_width=True):
            with st.spinner(f"🧠 Анализ {tour_to_analyze} тура..."):
                try:
                    result = parser.analyze_and_update(round_number=tour_to_analyze)
                    
                    if result['errors']:
                        for err in result['errors']:
                            st.warning(f"⚠️ {err}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Матчей", result['matches_analyzed'])
                    with col2:
                        st.metric("🔄 Команд обновлено", len(result['teams_updated']))
                    with col3:
                        st.metric("📅 Тур", result['round'])
                    
                    if result['matches_analyzed'] > 0:
                        st.success("✅ Анализ завершён")
                    else:
                        st.info("ℹ️ Нет завершённых матчей для анализа")
                        
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # =========================================================
    # 5. ПРОГНОЗ НА ТУР
    # =========================================================
    st.subheader("🎯 Прогноз на тур")
    st.caption("Автоматический прогноз на все матчи тура")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        tour_to_predict = st.number_input(
            "Номер тура для прогноза",
            min_value=1,
            max_value=30,
            value=4,
            step=1,
            key="tour_predict"
        )
    with col2:
        if st.button("🎯 Сделать прогноз", type="primary", use_container_width=True):
            with st.spinner(f"🧠 Прогноз на {tour_to_predict} тур..."):
                try:
                    matches = parser.get_matches_by_tour(tour_to_predict)
                    if matches:
                        parser.load_matches_to_db(matches, tour_to_predict)
                    
                    predictions = parser.predict_tour(round_number=tour_to_predict)
                    
                    if predictions:
                        st.success(f"✅ Прогнозов сделано: {len(predictions)}")
                        
                        for pred in predictions:
                            with st.container():
                                st.markdown("---")
                                col1, col2, col3 = st.columns([2, 1.5, 2])
                                
                                with col1:
                                    st.markdown(f"**🏠 {pred['home_team']}**")
                                    xg = pred['prediction'].get('xg', {})
                                    st.caption(f"xG: {xg.get('home', 0):.2f}")
                                
                                with col2:
                                    score = pred['prediction'].get('score', '0:0')
                                    prob = pred['prediction'].get('score_probability', 0)
                                    st.markdown(f"## {score}")
                                    st.caption(f"Вероятность: {prob:.1%}")
                                    
                                    probs = pred['prediction'].get('probability', {})
                                    st.caption(f"П1: {probs.get('home', 0):.1%} | X: {probs.get('draw', 0):.1%} | П2: {probs.get('away', 0):.1%}")
                                
                                with col3:
                                    st.markdown(f"**✈️ {pred['away_team']}**")
                                    st.caption(f"xG: {xg.get('away', 0):.2f}")
                                
                                with st.expander("📊 Детали"):
                                    st.json(pred['prediction'])
                    else:
                        st.info("ℹ️ Нет матчей для прогноза")
                        
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # =========================================================
    # 6. БЫСТРЫЙ ЗАПУСК
    # =========================================================
    st.subheader("🚀 Быстрый запуск")
    st.caption("Одна кнопка: загрузка + анализ + прогноз")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        fast_tour = st.number_input(
            "Тур",
            min_value=1,
            max_value=30,
            value=4,
            step=1,
            key="fast_tour"
        )
    with col2:
        if st.button("🚀 Полный цикл", type="primary", use_container_width=True):
            with st.spinner(f"🧠 Полный цикл для {fast_tour} тура..."):
                try:
                    result = parser.update_all(round_number=fast_tour)
                    
                    st.success("✅ Полный цикл завершён")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📥 Загружено", result['matches_loaded'])
                    with col2:
                        st.metric("🎯 Прогнозов", len(result['predictions']))
                    with col3:
                        st.metric("⚠️ Ошибок", len(result['errors']))
                    
                    if result['predictions']:
                        st.info(f"📊 Прогнозы на {fast_tour} тур готовы")
                        
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    main()

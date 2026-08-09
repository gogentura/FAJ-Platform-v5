#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.1 - Синхронизация
Управление данными: парсинг, анализ, обновление
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from app.database import FAJDatabase
from app.parsers.soccerland_parser import SoccerlandParser
from app.core.prediction_manager import get_prediction_manager


def main():
    st.title("🔄 Синхронизация данных")
    st.caption("Парсинг, анализ и обновление данных FAJ")
    
    db = FAJDatabase()
    parser = SoccerlandParser()
    pm = get_prediction_manager()
    
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
    st.caption("Парсинг календаря с championat.com и загрузка в БД")
    
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
                    upcoming = parser.get_upcoming_matches()
                    
                    if not upcoming:
                        st.warning("⚠️ Не удалось получить данные с championat.com")
                    else:
                        loaded = parser.load_matches_to_db(upcoming, tour_to_load)
                        
                        if loaded > 0:
                            st.success(f"✅ Загружено матчей: {loaded}")
                        else:
                            st.info("ℹ️ Все матчи уже загружены")
                            
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # =========================================================
    # 3. АНАЛИЗ СЫГРАННЫХ ТУРОВ
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
                        st.warning(f"⚠️ Ошибки: {result['errors']}")
                    
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
    # 4. ПРОГНОЗ НА ТУР
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
                    # Сначала загружаем матчи, если их нет
                    upcoming = parser.get_upcoming_matches()
                    if upcoming:
                        parser.load_matches_to_db(upcoming, tour_to_predict)
                    
                    # Делаем прогнозы
                    predictions = parser.predict_tour(round_number=tour_to_predict)
                    
                    if predictions:
                        st.success(f"✅ Прогнозов сделано: {len(predictions)}")
                        
                        for pred in predictions:
                            with st.container():
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
                                
                                st.divider()
                    else:
                        st.info("ℹ️ Нет матчей для прогноза")
                        
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    # =========================================================
    # 5. БЫСТРЫЙ ЗАПУСК (ВСЁ ВМЕСТЕ)
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
    
    st.divider()
    
    # =========================================================
    # 6. СУЩЕСТВУЮЩАЯ ЛОГИКА (если была)
    # =========================================================
    # Если в старом sync.py был какой-то код, он остаётся здесь
    # Я добавил новый функционал, не удаляя старый


if __name__ == "__main__":
    main()

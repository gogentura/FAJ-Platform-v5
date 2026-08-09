#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Страница прогнозов на тур
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from app.core.prediction_manager import get_prediction_manager
from app.parsers.soccerland_parser import SoccerlandParser
from app.database import FAJDatabase


def main():
    st.title("📊 Прогнозы на тур")
    st.caption("Автоматические прогнозы FAJ на предстоящие матчи")
    
    # Инициализация
    db = FAJDatabase()
    pm = get_prediction_manager()
    parser = SoccerlandParser()
    
    # Выбор тура
    st.subheader("🎯 Выбор тура")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        tour = st.number_input("Номер тура", min_value=1, max_value=30, value=4, step=1)
    with col2:
        if st.button("🔄 Обновить прогнозы", type="primary"):
            with st.spinner("🧠 Загрузка и прогнозирование..."):
                # 1. Загружаем расписание тура
                upcoming = parser.get_upcoming_matches()
                if upcoming:
                    loaded = parser.load_matches_to_db(upcoming, tour)
                    st.info(f"📥 Загружено матчей: {loaded}")
                
                # 2. Делаем прогнозы
                predictions = parser.predict_tour(tour)
                st.success(f"✅ Прогнозов сделано: {len(predictions)}")
                st.session_state['predictions'] = predictions
    
    # Отображение прогнозов
    st.subheader(f"📋 Прогнозы на {tour} тур")
    
    if 'predictions' in st.session_state and st.session_state['predictions']:
        predictions = st.session_state['predictions']
        
        for pred in predictions:
            with st.container():
                st.markdown("---")
                col1, col2, col3 = st.columns([2, 1, 2])
                
                with col1:
                    st.metric("🏠 Хозяева", pred['home_team'])
                    xg = pred['prediction'].get('xg', {})
                    st.caption(f"xG: {xg.get('home', 0):.2f}")
                
                with col2:
                    score = pred['prediction'].get('score', '0:0')
                    prob = pred['prediction'].get('score_probability', 0)
                    st.markdown(f"## {score}")
                    st.caption(f"Вероятность: {prob:.1%}")
                    
                    # Исход
                    probs = pred['prediction'].get('probability', {})
                    st.caption(f"П1: {probs.get('home', 0):.1%} | X: {probs.get('draw', 0):.1%} | П2: {probs.get('away', 0):.1%}")
                
                with col3:
                    st.metric("✈️ Гости", pred['away_team'])
                    st.caption(f"xG: {xg.get('away', 0):.2f}")
                
                # Детали
                with st.expander("📊 Детали прогноза"):
                    st.json(pred['prediction'])
    else:
        st.info("ℹ️ Нет прогнозов. Нажмите 'Обновить прогнозы' для загрузки.")

if __name__ == "__main__":
    main()

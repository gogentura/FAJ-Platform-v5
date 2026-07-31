#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0
Professional Analytics Dashboard
"""

import streamlit as st
import pandas as pd
from app.prediction import FAJPrediction
from app.learning_db import LearningDB

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="FAJ Platform 10.0",
    page_icon="⚽",
    layout="wide"
)

# =====================================================
# INIT
# =====================================================
@st.cache_resource
def get_engine():
    return FAJPrediction()

@st.cache_resource
def get_learning_db():
    return LearningDB()

engine = get_engine()
learning_db = get_learning_db()

# =====================================================
# STYLE
# =====================================================
st.markdown("""
<style>
    .main-header {
        font-size: 32px;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-header {
        color: #9ca3af;
        font-size: 16px;
        margin-bottom: 20px;
    }
    .prediction-card {
        background: rgba(30, 30, 50, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #f3f4f6;
    }
    .metric-label {
        color: #9ca3af;
        font-size: 14px;
    }
    .best-bet {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 12px;
        padding: 12px 20px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================
# HEADER
# =====================================================
st.markdown('<div class="main-header">⚽ FAJ PLATFORM 10.0</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Adaptive Football Intelligence — Самообучающаяся система прогнозирования</div>', unsafe_allow_html=True)

# =====================================================
# NAVIGATION
# =====================================================
page = st.radio(
    "",
    ["🏠 Матч-центр", "📊 Сравнение", "🧠 Обучение", "📘 Команды", "⚙️ Система"],
    horizontal=True
)

st.divider()

# =====================================================
# PAGE: МАТЧ-ЦЕНТР
# =====================================================
if page == "🏠 Матч-центр":
    st.markdown("### 🏟 Центр прогнозирования")
    
    teams = learning_db.get_all_teams()
    
    col1, col2 = st.columns(2)
    with col1:
        home = st.selectbox("🏠 Домашняя команда", teams, key="home")
    with col2:
        away = st.selectbox("✈️ Гостевая команда", [t for t in teams if t != home], key="away")
    
    if st.button("🔮 Рассчитать прогноз", use_container_width=True, type="primary"):
        with st.spinner("FAJ анализирует матч..."):
            result = engine.predict_match(home, away)
        
        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            # Основная карточка прогноза
            st.markdown(f"""
            <div class="prediction-card">
                <h2 style="text-align:center; color:#f3f4f6; margin:0;">
                    {home} ⚔️ {away}
                </h2>
                <p style="text-align:center; color:#9ca3af;">FAJ Prediction v{result['version']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 3 колонки: вероятности
            col1, col2, col3 = st.columns(3)
            probs = result['probability']
            
            with col1:
                st.markdown(f"""
                <div style="text-align:center; padding:12px; background:rgba(16,185,129,0.1); border-radius:12px;">
                    <div style="font-size:32px; font-weight:700; color:#10b981;">{probs['P1']}%</div>
                    <div style="color:#9ca3af;">Победа {home}</div>
                    <div style="background:#374151; height:4px; border-radius:2px; margin-top:8px;">
                        <div style="background:#10b981; height:4px; border-radius:2px; width:{probs['P1']}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style="text-align:center; padding:12px; background:rgba(245,158,11,0.1); border-radius:12px;">
                    <div style="font-size:32px; font-weight:700; color:#f59e0b;">{probs['X']}%</div>
                    <div style="color:#9ca3af;">Ничья</div>
                    <div style="background:#374151; height:4px; border-radius:2px; margin-top:8px;">
                        <div style="background:#f59e0b; height:4px; border-radius:2px; width:{probs['X']}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div style="text-align:center; padding:12px; background:rgba(239,68,68,0.1); border-radius:12px;">
                    <div style="font-size:32px; font-weight:700; color:#ef4444;">{probs['P2']}%</div>
                    <div style="color:#9ca3af;">Победа {away}</div>
                    <div style="background:#374151; height:4px; border-radius:2px; margin-top:8px;">
                        <div style="background:#ef4444; height:4px; border-radius:2px; width:{probs['P2']}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.divider()
            
            # xG
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"⚽ xG {home}", result['xg']['home_xg'])
            with col2:
                st.metric(f"⚽ xG {away}", result['xg']['away_xg'])
            
            # Дополнительные метрики
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Уверенность", f"{result['confidence']}%")
            with col2:
                st.metric("⚽ Тотал > 2.5", f"{result['total_over25']}%")
            with col3:
                st.metric("🤝 Обе забьют", f"{result['btts']}%")
            with col4:
                st.markdown(f"""
                <div class="best-bet">
                    <div style="color:#9ca3af; font-size:12px;">ЛУЧШАЯ СТАВКА</div>
                    <div style="color:#10b981; font-weight:700; font-size:16px;">{result['best_bet']}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Топ-5 счетов
            st.markdown("### 🎯 Самые вероятные счета")
            score_df = pd.DataFrame(result['top_scores'])
            score_df.columns = ["Счет", "Вероятность %"]
            st.dataframe(score_df, hide_index=True, use_container_width=True)
            
            # Объяснение
            with st.expander("🧠 Почему FAJ выбрал такой прогноз"):
                st.write(result['explanation'])

# =====================================================
# PAGE: СРАВНЕНИЕ
# =====================================================
elif page == "📊 Сравнение":
    st.markdown("### 📊 Сравнение прогнозов FAJ vs Эксперт")
    
    summary = learning_db.get_comparison_summary()
    if summary.empty:
        st.info("Нет данных для сравнения. Добавьте прогнозы и результаты.")
    else:
        st.dataframe(summary, use_container_width=True, hide_index=True)
        
        # Статистика точности
        stats = learning_db.calculate_accuracy()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего матчей", stats['total'])
        with col2:
            st.metric("FAJ (исход)", f"{stats['faj']}%")
        with col3:
            st.metric("Эксперт (исход)", f"{stats['expert']}%")
        with col4:
            st.metric("FAJ (точный счет)", f"{stats['faj_score']}%")

# =====================================================
# PAGE: ОБУЧЕНИЕ
# =====================================================
elif page == "🧠 Обучение":
    st.markdown("### 🧠 Самообучение модели")
    
    stats = learning_db.get_learning_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 Записей в памяти", stats['total_records'])
    with col2:
        st.metric("🏟 Команд в БД", stats['teams_count'])
    with col3:
        st.metric("⚖️ Обновлений весов", stats['weights_updates'])
    with col4:
        st.metric("📅 Последнее обновление", stats['last_update'][:16] if stats['last_update'] else "—")
    
    st.divider()
    
    # История весов
    weights_df = learning_db.get_weights_history_df()
    if not weights_df.empty:
        st.markdown("### ⚖️ История изменения весов")
        st.dataframe(weights_df, use_container_width=True, hide_index=True)
    
    # Память обучения
    if learning_db.memory:
        st.markdown("### 📋 Последние записи обучения")
        memory_df = pd.DataFrame(learning_db.memory[-10:])
        st.dataframe(memory_df, use_container_width=True, hide_index=True)

# =====================================================
# PAGE: КОМАНДЫ
# =====================================================
elif page == "📘 Команды":
    st.markdown("### 📘 Паспорта команд")
    
    teams = learning_db.get_all_teams()
    selected = st.selectbox("Выберите команду", teams)
    
    if selected:
        passport = learning_db.get_team_passport(selected)
        if passport:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"## {selected}")
                st.json(passport)
            with col2:
                # Визуализация показателей
                df = pd.DataFrame({
                    "Показатель": list(passport.keys()),
                    "Значение": list(passport.values())
                })
                st.bar_chart(df.set_index("Показатель"))

# =====================================================
# PAGE: СИСТЕМА
# =====================================================
elif page == "⚙️ Система":
    st.markdown("### ⚙️ Системная информация")
    
    stats = learning_db.get_learning_stats()
    weights = learning_db.get_current_weights()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Версия платформы", "10.0")
    with col2:
        st.metric("Команд в системе", stats['teams_count'])
    with col3:
        st.metric("Записей памяти", stats['total_records'])
    
    st.divider()
    st.markdown("### ⚖️ Текущие веса модели")
    st.json(weights)

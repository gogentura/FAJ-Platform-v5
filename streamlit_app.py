#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Streamlit Dashboard
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from app.faj_core import FAJCore


st.set_page_config(page_title="FAJ Platform 10.0", page_icon="⚽", layout="wide")


@st.cache_resource
def get_core():
    return FAJCore()


core = get_core()


st.markdown("""
<style>
    .main-header { font-size: 32px; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .sub-header { color: #9ca3af; font-size: 16px; margin-bottom: 20px; }
    .prediction-card { background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .best-bet { background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 12px 20px; text-align: center; }
    .success-box { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 12px; padding: 16px; }
</style>
""", unsafe_allow_html=True)


st.markdown('<div class="main-header">⚽ FAJ PLATFORM 10.0</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Adaptive Football Intelligence — Самообучающаяся система прогнозирования</div>', unsafe_allow_html=True)


# =====================================================
# НАВИГАЦИЯ
# =====================================================
page = st.radio(
    "",
    ["🏠 Матч-центр", "📊 Сравнение", "🧠 Обучение", "📘 Команды", "⚙️ Система", "📥 Загрузка данных"],
    horizontal=True
)
st.divider()


teams = core.get_all_teams()


# =====================================================
# СЛОВАРЬ ПЕРЕВОДА ПОКАЗАТЕЛЕЙ
# =====================================================
TRANSLATE = {
    "attack": "⚔️ Атака",
    "defense": "🛡 Защита",
    "control": "🎯 Контроль мяча",
    "efficiency": "📊 Эффективность",
    "mentality": "🧠 Ментальность",
    "tempo": "⚡ Темп",
    "press": "🔥 Прессинг",
    "transition": "🔄 Переходы",
    "flexibility": "🔄 Гибкость",
    "coach": "👔 Тренер",
    "form": "📈 Форма",
    "depth": "👥 Глубина состава",
    "home_rating": "🏠 Сила дома",
    "away_rating": "✈️ Сила выезда"
}


# =====================================================
# ФУНКЦИЯ ЗАГРУЗКИ ДАННЫХ 1-ГО ТУРА
# =====================================================
def load_tour1_to_comparison():
    DATA_DIR = "data"
    TOUR1_FILE = os.path.join(DATA_DIR, "tour1_results.json")
    COMPARISON_FILE = os.path.join(DATA_DIR, "comparison_log.json")
    
    def load_json(filename):
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_json(filename, data):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_outcome(score):
        if not score or score == "-":
            return None
        try:
            h, a = map(int, score.split(':'))
            if h > a:
                return "П1"
            elif h == a:
                return "X"
            else:
                return "П2"
        except:
            return None
    
    tour1 = load_json(TOUR1_FILE)
    comparison = load_json(COMPARISON_FILE)
    
    if not tour1:
        return {"status": "error", "message": "Файл tour1_results.json не найден или пуст"}
    
    existing_matches = {r.get('match') for r in comparison}
    new_records = 0
    
    for match, data in tour1.items():
        if match in existing_matches:
            continue
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        actual = data.get('actual', '—')
        
        faj_outcome = get_outcome(faj_pred)
        expert_outcome = get_outcome(expert_pred)
        actual_outcome = get_outcome(actual)
        
        record = {
            'match': match,
            'faj_pred': faj_pred,
            'expert_pred': expert_pred,
            'actual': actual,
            'faj_outcome': faj_outcome,
            'expert_outcome': expert_outcome,
            'actual_outcome': actual_outcome,
            'faj_correct': faj_outcome == actual_outcome,
            'expert_correct': expert_outcome == actual_outcome,
            'faj_score_correct': faj_pred == actual,
            'expert_score_correct': expert_pred == actual,
            'timestamp': datetime.now().isoformat()
        }
        
        comparison.append(record)
        new_records += 1
    
    if new_records > 0:
        save_json(COMPARISON_FILE, comparison)
    
    return {
        "status": "success",
        "new_records": new_records,
        "total_records": len(comparison)
    }


# =====================================================
# СТРАНИЦА: ЗАГРУЗКА ДАННЫХ
# =====================================================
if page == "📥 Загрузка данных":
    st.markdown("### 📥 Загрузка данных в систему")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="prediction-card">
            <h4 style="color: #f3f4f6; margin-top: 0;">📊 Данные 1-го тура</h4>
            <p style="color: #9ca3af;">Загрузить прогнозы и результаты 1-го тура в систему для сравнения.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="prediction-card">
            <h4 style="color: #f3f4f6; margin-top: 0;">📋 Что будет загружено</h4>
            <p style="color: #9ca3af; font-size: 14px;">
                ✅ Прогнозы FAJ<br>
                ✅ Экспертные прогнозы<br>
                ✅ Фактические результаты<br>
                ✅ Сравнение исходов
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    if st.button("📥 Загрузить данные 1-го тура", use_container_width=True, type="primary"):
        with st.spinner("Загрузка данных..."):
            result = load_tour1_to_comparison()
        
        if result["status"] == "error":
            st.error(f"❌ {result['message']}")
        else:
            st.markdown(f"""
            <div class="success-box">
                <h4 style="color: #10b981; margin: 0;">✅ Данные успешно загружены!</h4>
                <p style="color: #d1d5db; margin: 8px 0 0 0;">
                    Добавлено новых записей: <strong>{result['new_records']}</strong><br>
                    Всего записей в системе: <strong>{result['total_records']}</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.success("Перейдите в раздел '📊 Сравнение' чтобы увидеть данные!")
    
    st.divider()
    
    # Показываем текущее состояние
    st.markdown("### 📊 Текущее состояние")
    comparison_file = os.path.join("data", "comparison_log.json")
    if os.path.exists(comparison_file):
        with open(comparison_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        st.metric("Записей в сравнении", len(data))
    else:
        st.info("Файл comparison_log.json ещё не создан")


# =====================================================
# СТРАНИЦА: МАТЧ-ЦЕНТР
# =====================================================
elif page == "🏠 Матч-центр":
    st.markdown("### 🏟 Центр прогнозирования")
    
    if not teams:
        st.warning("Нет команд в базе данных")
        st.stop()
    
    col1, col2 = st.columns(2)
    with col1:
        home = st.selectbox("🏠 Домашняя команда", teams, key="home")
    with col2:
        away_options = [t for t in teams if t != home]
        away = st.selectbox("✈️ Гостевая команда", away_options if away_options else teams, key="away")
    
    if st.button("🔮 Рассчитать прогноз", use_container_width=True, type="primary"):
        with st.spinner("FAJ анализирует матч..."):
            result = core.predict_match(home, away)
        
        if result["status"] == "error":
            st.error(f"❌ {result['message']}")
        else:
            data = result["data"]
            
            st.markdown(f"""
            <div class="prediction-card">
                <h2 style="text-align:center; color:#f3f4f6; margin:0;">{home} ⚔️ {away}</h2>
                <p style="text-align:center; color:#9ca3af;">FAJ Prediction v{data.get('version', '10.0')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            probs = data.get('probability', {'P1': 0, 'X': 0, 'P2': 0})
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"Победа {home}", f"{probs.get('P1', 0)}%")
            with col2:
                st.metric("Ничья", f"{probs.get('X', 0)}%")
            with col3:
                st.metric(f"Победа {away}", f"{probs.get('P2', 0)}%")
            
            st.divider()
            xg = data.get('xg', {'home_xg': 0, 'away_xg': 0})
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"⚽ xG {home}", xg.get('home_xg', 0))
            with col2:
                st.metric(f"⚽ xG {away}", xg.get('away_xg', 0))
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Уверенность", f"{data.get('confidence', 0)}%")
            with col2:
                st.metric("⚽ Тотал > 2.5", f"{data.get('total_over25', 0)}%")
            with col3:
                st.metric("🤝 Обе забьют", f"{data.get('btts', 0)}%")
            with col4:
                st.markdown(f"""
                <div class="best-bet">
                    <div style="color:#9ca3af; font-size:12px;">ЛУЧШАЯ СТАВКА</div>
                    <div style="color:#10b981; font-weight:700; font-size:16px;">{data.get('best_bet', '—')}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("### 🎯 Самые вероятные счета")
            top_scores = data.get('top_scores', [])
            if top_scores:
                st.dataframe(pd.DataFrame(top_scores), hide_index=True, use_container_width=True)
            
            with st.expander("🧠 Почему FAJ выбрал такой прогноз"):
                st.write(data.get('explanation', 'Нет объяснения'))


# =====================================================
# СТРАНИЦА: СРАВНЕНИЕ
# =====================================================
elif page == "📊 Сравнение":
    st.markdown("### 📊 Сравнение прогнозов FAJ vs Эксперт")
    
    summary = core.learning_db.get_comparison_summary()
    if summary.empty:
        st.info("Нет данных для сравнения. Загрузите данные 1-го тура через раздел '📥 Загрузка данных'.")
    else:
        st.dataframe(summary, use_container_width=True, hide_index=True)
        stats = core.learning_db.calculate_accuracy()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего матчей", stats.get('total', 0))
        with col2:
            st.metric("FAJ (исход)", f"{stats.get('faj', 0)}%")
        with col3:
            st.metric("Эксперт (исход)", f"{stats.get('expert', 0)}%")
        with col4:
            st.metric("FAJ (точный счёт)", f"{stats.get('faj_score', 0)}%")


# =====================================================
# СТРАНИЦА: ОБУЧЕНИЕ
# =====================================================
elif page == "🧠 Обучение":
    st.markdown("### 🧠 Самообучение модели")
    
    stats = core.learning_db.get_learning_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 Записей в памяти", stats.get('total_records', 0))
    with col2:
        st.metric("🏟 Команд в БД", stats.get('teams_count', 0))
    with col3:
        st.metric("⚖️ Обновлений весов", stats.get('weights_updates', 0))
    with col4:
        last = stats.get('last_update', '—')
        st.metric("📅 Последнее обновление", last[:16] if last and last != '—' else '—')
    
    weights_df = core.learning_db.get_weights_history_df()
    if not weights_df.empty:
        st.markdown("### ⚖️ История весов")
        st.dataframe(weights_df, use_container_width=True, hide_index=True)


# =====================================================
# СТРАНИЦА: КОМАНДЫ (с русским переводом)
# =====================================================
elif page == "📘 Команды":
    st.markdown("### 📘 Паспорта команд")
    
    if teams:
        selected = st.selectbox("Выберите команду", teams)
        if selected:
            passport = core.get_team_passport(selected)
            if passport:
                st.markdown(f"## {selected}")
                
                # Отображаем показатели в две колонки с русскими названиями
                col1, col2 = st.columns(2)
                items = list(passport.items())
                mid = len(items) // 2
                
                with col1:
                    for key, value in items[:mid]:
                        label = TRANSLATE.get(key, key)
                        st.metric(label, value)
                
                with col2:
                    for key, value in items[mid:]:
                        label = TRANSLATE.get(key, key)
                        st.metric(label, value)
                
                # Визуализация
                st.divider()
                st.markdown("### 📊 Профиль команды")
                df = pd.DataFrame({
                    "Показатель": [TRANSLATE.get(k, k) for k in passport.keys()],
                    "Значение": list(passport.values())
                })
                st.bar_chart(df.set_index("Показатель"))
            else:
                st.warning(f"Нет данных для команды {selected}")
    else:
        st.warning("Нет команд в базе")


# =====================================================
# СТРАНИЦА: СИСТЕМА
# =====================================================
elif page == "⚙️ Система":
    st.markdown("### ⚙️ Системная информация")
    status = core.status()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Версия", status.get('version', '10.0'))
    with col2:
        st.metric("Команд", status.get('teams', 0))
    with col3:
        st.metric("Записей памяти", status.get('memory', 0))
    
    st.divider()
    st.markdown("### ⚖️ Текущие веса")
    st.json(core.learning_db.get_current_weights())


st.divider()
st.caption("⚽ FAJ Platform 10.0 | Adaptive Football Intelligence")

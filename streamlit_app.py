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

# =====================================================
# КОНСТАНТЫ
# =====================================================
DATA_DIR = "data"

# =====================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С JSON
# =====================================================

def load_json(filename):
    """Безопасная загрузка JSON-файла"""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return {} if "passports" in filename or "tour" in filename or "config" in filename else []
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {} if "passports" in filename or "tour" in filename or "config" in filename else []
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return {} if "passports" in filename or "tour" in filename or "config" in filename else []

def save_json(filename, data):
    """Сохранение JSON-файла"""
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# =====================================================
# ФУНКЦИИ ДЛЯ ДАННЫХ
# =====================================================

def get_outcome(score):
    """Определение исхода по счёту"""
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

def get_all_teams():
    """Получить список всех команд"""
    passports = load_json("passports_2026.json")
    return list(passports.keys())

def get_team_passport(team_name):
    """Получить паспорт команды"""
    passports = load_json("passports_2026.json")
    return passports.get(team_name, {})

def load_tour1_to_comparison():
    """Загрузка данных 1-го тура в comparison_log"""
    tour1 = load_json("tour1_results.json")
    comparison = load_json("comparison_log.json")
    
    if not tour1:
        return {"status": "error", "message": "Файл tour1_results.json не найден или пуст"}
    
    existing = {r.get('match') for r in comparison}
    new_records = 0
    
    for match, data in tour1.items():
        if match in existing:
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
        save_json("comparison_log.json", comparison)
    
    return {
        "status": "success",
        "new_records": new_records,
        "total_records": len(comparison)
    }

def get_comparison_summary():
    """Получить сводку сравнения"""
    comparison = load_json("comparison_log.json")
    if not comparison:
        return pd.DataFrame()
    df = pd.DataFrame(comparison)
    cols = ['match', 'faj_pred', 'expert_pred', 'actual', 
            'faj_correct', 'expert_correct', 'faj_score_correct', 'expert_score_correct']
    return df[[c for c in cols if c in df.columns]]

def calculate_accuracy():
    """Рассчитать точность прогнозов"""
    comparison = load_json("comparison_log.json")
    if not comparison:
        return {"total": 0, "faj": 0, "expert": 0, "faj_score": 0, "expert_score": 0}
    
    total = len(comparison)
    faj_correct = sum(1 for r in comparison if r.get('faj_correct', False))
    expert_correct = sum(1 for r in comparison if r.get('expert_correct', False))
    faj_score_correct = sum(1 for r in comparison if r.get('faj_score_correct', False))
    expert_score_correct = sum(1 for r in comparison if r.get('expert_score_correct', False))
    
    return {
        "total": total,
        "faj": round(faj_correct / total * 100, 1) if total > 0 else 0,
        "expert": round(expert_correct / total * 100, 1) if total > 0 else 0,
        "faj_score": round(faj_score_correct / total * 100, 1) if total > 0 else 0,
        "expert_score": round(expert_score_correct / total * 100, 1) if total > 0 else 0
    }

def run_training():
    """Запуск обучения на 1-м туре"""
    comparison = load_json("comparison_log.json")
    weights = load_json("weights_history.json")
    memory = load_json("learning_memory.json")
    
    if not comparison:
        return {"status": "error", "message": "Нет данных для обучения. Загрузите данные 1-го тура."}
    
    errors = []
    for record in comparison:
        if not record.get('faj_correct', False):
            errors.append({
                'match': record.get('match'),
                'faj_pred': record.get('faj_pred'),
                'actual': record.get('actual'),
                'faj_outcome': record.get('faj_outcome'),
                'actual_outcome': record.get('actual_outcome')
            })
    
    if not errors:
        return {"status": "info", "message": "Ошибок нет! Модель уже идеальна."}
    
    if weights:
        last_weights = weights[-1].get('weights', {})
    else:
        last_weights = {
            "attack": 0.18, "defense": 0.18, "control": 0.15,
            "efficiency": 0.12, "mentality": 0.10, "tempo": 0.07,
            "press": 0.05, "transition": 0.05, "flexibility": 0.05,
            "coach": 0.05
        }
    
    new_weights = last_weights.copy()
    
    attack_errors = sum(1 for e in errors if e.get('faj_outcome') == "П1" and e.get('actual_outcome') != "П1")
    defense_errors = sum(1 for e in errors if e.get('faj_outcome') == "П2" and e.get('actual_outcome') != "П2")
    total_errors = len(errors)
    
    new_weights["attack"] = max(0.10, new_weights.get("attack", 0.18) - 0.02 * (attack_errors / max(total_errors, 1)))
    new_weights["defense"] = max(0.10, new_weights.get("defense", 0.18) - 0.02 * (defense_errors / max(total_errors, 1)))
    new_weights["form"] = min(0.20, new_weights.get("form", 0.10) + 0.02 * (total_errors / 8))
    new_weights["mentality"] = min(0.15, new_weights.get("mentality", 0.10) + 0.01)
    
    total_weight = sum(new_weights.values())
    for k in new_weights:
        new_weights[k] = round(new_weights[k] / total_weight, 3)
    
    new_record = {
        "version": f"10.{len(weights)}",
        "timestamp": datetime.now().isoformat(),
        "weights": new_weights,
        "reason": f"Корректировка после 1-го тура (ошибок: {total_errors})",
        "errors_analyzed": total_errors,
        "attack_errors": attack_errors,
        "defense_errors": defense_errors
    }
    weights.append(new_record)
    save_json("weights_history.json", weights)
    
    memory_record = {
        "type": "training",
        "tour": 1,
        "errors_found": total_errors,
        "weights_updated": new_weights,
        "timestamp": datetime.now().isoformat()
    }
    memory.append(memory_record)
    save_json("learning_memory.json", memory)
    
    return {
        "status": "success",
        "errors_analyzed": total_errors,
        "new_weights": new_weights,
        "version": new_record["version"]
    }

# =====================================================
# ПЕРЕВОД ПОКАЗАТЕЛЕЙ
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
# НАСТРОЙКА СТРАНИЦЫ
# =====================================================
st.set_page_config(page_title="FAJ Platform 10.0", page_icon="⚽", layout="wide")

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
    ["🏠 Матч-центр", "📊 Сравнение", "🧠 Обучение", "📘 Команды", "⚙️ Система", "📥 Загрузка данных", "📡 API Тест"],
    horizontal=True
)
st.divider()

teams = get_all_teams()

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
    
    comparison = load_json("comparison_log.json")
    st.metric("Записей в сравнении", len(comparison))

# =====================================================
# СТРАНИЦА: СРАВНЕНИЕ
# =====================================================
elif page == "📊 Сравнение":
    st.markdown("### 📊 Сравнение прогнозов FAJ vs Эксперт")
    
    summary = get_comparison_summary()
    if summary.empty:
        st.info("Нет данных для сравнения. Загрузите данные 1-го тура через раздел '📥 Загрузка данных'.")
    else:
        rename_map = {
            'match': 'Матч',
            'faj_pred': 'Прогноз FAJ',
            'expert_pred': 'Прогноз эксперта',
            'actual': 'Факт',
            'faj_correct': 'FAJ совпал?',
            'expert_correct': 'Эксперт совпал?',
            'faj_score_correct': 'FAJ точный счёт?',
            'expert_score_correct': 'Эксперт точный счёт?'
        }
        summary = summary.rename(columns=rename_map)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        
        stats = calculate_accuracy()
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
    
    memory = load_json("learning_memory.json")
    weights = load_json("weights_history.json")
    comparison = load_json("comparison_log.json")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Записей в памяти", len(memory))
    with col2:
        st.metric("⚖️ Обновлений весов", len(weights))
    with col3:
        st.metric("📊 Сравнений", len(comparison))
    
    st.divider()
    
    if st.button("🧠 Запустить обучение на 1-м туре", use_container_width=True, type="primary"):
        with st.spinner("Анализ ошибок и корректировка весов..."):
            result = run_training()
        
        if result["status"] == "error":
            st.error(f"❌ {result['message']}")
        elif result["status"] == "info":
            st.info(f"ℹ️ {result['message']}")
        else:
            st.markdown(f"""
            <div class="success-box">
                <h4 style="color: #10b981; margin: 0;">✅ Обучение завершено!</h4>
                <p style="color: #d1d5db; margin: 8px 0 0 0;">
                    Проанализировано ошибок: <strong>{result['errors_analyzed']}</strong><br>
                    Новая версия весов: <strong>{result['version']}</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### ⚖️ Новые веса")
            st.json(result['new_weights'])
    
    st.divider()
    
    if weights:
        st.markdown("### ⚖️ Последние веса")
        st.json(weights[-1].get('weights', {}))
        
        st.markdown("### 📋 История изменений")
        df_weights = pd.DataFrame(weights)
        st.dataframe(df_weights, use_container_width=True, hide_index=True)

# =====================================================
# СТРАНИЦА: КОМАНДЫ
# =====================================================
elif page == "📘 Команды":
    st.markdown("### 📘 Паспорта команд")
    
    if teams:
        selected = st.selectbox("Выберите команду", teams)
        if selected:
            passport = get_team_passport(selected)
            if passport:
                st.markdown(f"## {selected}")
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
# СТРАНИЦА: СИСТЕМА (С БД И API СТАТИСТИКОЙ)
# =====================================================
elif page == "⚙️ Система":
    st.markdown("### ⚙️ Системная информация")
    
    from app.database import FAJDatabase
    
    db = FAJDatabase()
    db_status = db.get_status()
    
    comparison = load_json("comparison_log.json")
    passports = load_json("passports_2026.json")
    memory = load_json("learning_memory.json")
    weights = load_json("weights_history.json")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Версия", "10.0")
    with col2:
        st.metric("Команд в БД", db_status.get('teams', 0))
    with col3:
        st.metric("Матчей в БД", db_status.get('matches', 0))
    with col4:
        st.metric("Записей журнала", db_status.get('journal', 0))
    
    st.divider()
    
    api_stats = db.get_api_stats_today()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("API Football запросов сегодня", api_stats.get('football_api', 0))
    with col2:
        st.metric("Football-data запросов сегодня", api_stats.get('football_data', 0))
    with col3:
        remaining = max(0, 100 - api_stats.get('football_api', 0))
        st.metric("Осталось (API Football)", remaining)
    
    st.divider()
    
    st.markdown("### ⚖️ Текущие веса")
    if weights:
        st.json(weights[-1].get('weights', {}))
    else:
        st.info("Нет сохранённых весов")
    
    st.divider()
    st.markdown("### 📊 Статистика точности")
    stats = calculate_accuracy()
    st.json(stats)
    
    st.divider()
    
    with st.expander("🗄️ Информация о базе данных"):
        st.json(db_status)
        st.caption(f"Путь к БД: {db_status.get('db_path', '—')}")

# =====================================================
# СТРАНИЦА: МАТЧ-ЦЕНТР
# =====================================================
elif page == "🏠 Матч-центр":
    st.markdown("### 🏟 Центр прогнозирования — 2-й тур РПЛ")
    
    if not teams:
        st.warning("Нет команд в базе данных")
        st.stop()
    
    from app.faj_match_engine import FAJMatchEngine
    engine = FAJMatchEngine()
    
    tour2 = load_json("tour2_predictions.json")
    
    if not tour2:
        st.warning("Нет данных для 2-го тура. Проверьте файл tour2_predictions.json")
        st.stop()
    
    st.markdown("### 📊 Прогнозы на 2-й тур")
    
    matches_data = []
    for match, data in tour2.items():
        if '-' in match:
            home, away = match.split('-')
        else:
            home, away = match.split('–')
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        xg_home = data.get('xg_home', '—')
        xg_away = data.get('xg_away', '—')
        
        faj_outcome = get_outcome(faj_pred) if faj_pred != '—' else '—'
        
        if faj_outcome == "П1":
            best_bet = f"Победа {home}"
        elif faj_outcome == "П2":
            best_bet = f"Победа {away}"
        elif faj_outcome == "X":
            best_bet = "Ничья"
        else:
            best_bet = "—"
        
        matches_data.append({
            "Матч": f"{home} – {away}",
            "Прогноз FAJ": faj_pred,
            "Ваш прогноз": expert_pred,
            "xG хозяев": xg_home,
            "xG гостей": xg_away,
            "Лучшая ставка": best_bet
        })
    
    df_matches = pd.DataFrame(matches_data)
    st.dataframe(df_matches, use_container_width=True, hide_index=True)
    
    st.divider()
    
    st.markdown("### 🔍 Детальный прогноз по матчу")
    
    match_options = list(tour2.keys())
    selected_match = st.selectbox("Выберите матч для детального прогноза", match_options)
    
    if selected_match:
        data = tour2[selected_match]
        
        if '-' in selected_match:
            home, away = selected_match.split('-')
        else:
            home, away = selected_match.split('–')
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        
        home_passport = get_team_passport(home)
        away_passport = get_team_passport(away)
        
        if home_passport and away_passport:
            result = engine.predict_match(home_passport, away_passport)
            
            st.markdown(f"""
            <div class="prediction-card">
                <h2 style="text-align:center; color:#f3f4f6; margin:0;">{home} ⚔️ {away}</h2>
                <p style="text-align:center; color:#9ca3af;">FAJ Prediction v6.9</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"Победа {home}", f"{result['home_win']}%")
            with col2:
                st.metric("Ничья", f"{result['draw']}%")
            with col3:
                st.metric(f"Победа {away}", f"{result['away_win']}%")
            
            st.divider()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"⚽ xG {home}", result['xg_home'])
                st.metric(f"🏠 Сила {home}", result['home_power'])
            with col2:
                st.metric(f"⚽ xG {away}", result['xg_away'])
                st.metric(f"✈️ Сила {away}", result['away_power'])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Уверенность", f"{result['confidence']}%")
            with col2:
                st.metric("⚽ Тотал > 2.5", f"{result['over25']}%")
            with col3:
                st.metric("🤝 Обе забьют", f"{result['btts']}%")
            with col4:
                st.metric("📉 Риск", result['risk'])
            
            st.markdown("### 🎯 Самые вероятные счета")
            if result['top_scores']:
                st.dataframe(pd.DataFrame(result['top_scores']), hide_index=True, use_container_width=True)
            
            with st.expander("🧠 Почему FAJ выбрал такой прогноз"):
                st.write(f"""
                Анализ матча {home} vs {away} на основе:
                
                1. **Сила команд**: {home} {result['home_power']} vs {away} {result['away_power']}
                2. **xG**: {home} {result['xg_home']} vs {away} {result['xg_away']}
                3. **Вероятности**: П1 {result['home_win']}% | X {result['draw']}% | П2 {result['away_win']}%
                4. **Уверенность модели**: {result['confidence']}%
                5. **Ключевые факторы**:
                   - {'Домашнее преимущество' if result['xg_home'] > result['xg_away'] else 'Гостевой фактор'}
                   - {'Атакующий стиль' if result['xg_home'] > 1.5 else 'Сбалансированная игра'}
                """)
            
            if expert_pred != '—':
                st.divider()
                st.markdown("### 📊 Сравнение прогнозов")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("FAJ", faj_pred)
                with col2:
                    st.metric("Ваш прогноз", expert_pred)
        else:
            st.warning(f"Нет паспортов для команд {home} или {away}")

# =====================================================
# СТРАНИЦА: API ТЕСТ
# =====================================================
elif page == "📡 API Тест":
    st.markdown("### 📡 Тест подключения API")
    
    from app.api.football_api import FootballAPI
    from app.api.football_data import FootballDataAPI
    from app.api.ids import IDs
    from app.config import Config
    
    football_api = FootballAPI()
    football_data = FootballDataAPI()
    
    # Статус токенов
    st.markdown("#### 🔑 Статус токенов")
    col1, col2 = st.columns(2)
    with col1:
        if football_api.is_ready():
            st.success("✅ API Football токен настроен")
        else:
            st.error("❌ API Football токен НЕ настроен")
    with col2:
        if football_data.is_ready():
            st.success("✅ Football-data токен настроен")
        else:
            st.error("❌ Football-data токен НЕ настроен")
    
    st.divider()
    
    # Счётчик запросов
    if "api_requests" not in st.session_state:
        st.session_state.api_requests = 0
    
    st.markdown("#### 📊 Счётчик запросов")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("API Football запросов сегодня", st.session_state.api_requests)
    with col2:
        st.metric("Лимит", f"{Config.MAX_REQUESTS_PER_DAY}")
    with col3:
        remaining = max(0, Config.MAX_REQUESTS_PER_DAY - st.session_state.api_requests)
        st.metric("Осталось", remaining)
    
    st.divider()
    
    # Тест API Football по команде
    st.markdown("#### ⚽ Тест API Football (по команде)")
    
    team_options = IDs.get_all_teams()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_team = st.selectbox("Выберите команду для теста", team_options)
    with col2:
        league_for_team = st.selectbox("Лига", ["RPL", "EPL", "LALIGA", "UCL"])
    
    if st.button("🔍 Получить статистику команды", use_container_width=True):
        with st.spinner(f"Запрос статистики для {selected_team}..."):
            result = football_api.get_team_stats_by_name(selected_team, league_for_team)
            st.session_state.api_requests += 1
        
        if result.get("error"):
            st.error(f"❌ Ошибка: {result.get('message')}")
            if result.get("status_code"):
                st.write(f"Код ошибки: {result['status_code']}")
        else:
            st.success(f"✅ Статистика для {selected_team} получена")
            stats = result.get("response", {})
            if stats:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🏟 Матчей", stats.get("fixtures", {}).get("played", {}).get("total", "—"))
                    st.metric("⚽ Голов забито", stats.get("goals", {}).get("for", {}).get("total", {}).get("total", "—"))
                with col2:
                    st.metric("✅ Побед", stats.get("fixtures", {}).get("wins", {}).get("total", "—"))
                    st.metric("⚽ Голов пропущено", stats.get("goals", {}).get("against", {}).get("total", {}).get("total", "—"))
                with col3:
                    st.metric("🤝 Ничьих", stats.get("fixtures", {}).get("draws", {}).get("total", "—"))
                    st.metric("📊 xG", stats.get("goals", {}).get("for", {}).get("average", {}).get("total", "—"))
                
                with st.expander("📋 Полная статистика"):
                    st.json(stats)
            else:
                st.warning("Нет данных по команде")
    
    st.divider()
    
    # Последние матчи команды
    st.markdown("#### 🏟 Последние матчи команды")
    
    if st.button("📅 Получить последние матчи", use_container_width=True):
        with st.spinner(f"Запрос матчей для {selected_team}..."):
            result = football_api.get_team_fixtures(selected_team, league_for_team, last=5, status="FT")
            st.session_state.api_requests += 1
        
        if result.get("error"):
            st.error(f"❌ Ошибка: {result.get('message')}")
        else:
            fixtures = result.get("response", [])
            st.success(f"✅ Получено матчей: {len(fixtures)}")
            
            if fixtures:
                match_data = []
                for fixture in fixtures[:5]:
                    home = fixture.get("teams", {}).get("home", {}).get("name", "?")
                    away = fixture.get("teams", {}).get("away", {}).get("name", "?")
                    home_goals = fixture.get("goals", {}).get("home")
                    away_goals = fixture.get("goals", {}).get("away")
                    date = fixture.get("fixture", {}).get("date", "")[:10]
                    
                    if home_goals is not None and away_goals is not None:
                        score = f"{home_goals}:{away_goals}"
                    else:
                        score = "—"
                    
                    match_data.append({
                        "Дата": date,
                        "Хозяева": home,
                        "Гости": away,
                        "Счёт": score
                    })
                
                st.dataframe(pd.DataFrame(match_data), use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Тест Football-data
    st.markdown("#### 📊 Тест Football-data.org")
    
    col1, col2 = st.columns(2)
    with col1:
        fd_league = st.selectbox("Турнир", ["RPL", "EPL", "LALIGA", "UCL"], key="fd_league")
    with col2:
        fd_season = st.number_input("Сезон (Football-data)", value=2026, min_value=2020, max_value=2026, key="fd_season")
    
    if st.button("📊 Получить таблицу из Football-data", use_container_width=True):
        with st.spinner("Запрос к Football-data..."):
            result = football_data.get_league_standings(fd_league, fd_season)
        
        if result.get("error"):
            st.error(f"❌ Ошибка: {result.get('message')}")
            if result.get("status_code"):
                st.write(f"Код ошибки: {result['status_code']}")
        else:
            standings = result.get("standings", [])
            if standings:
                st.success("✅ Получена таблица")
                table_data = []
                for item in standings:
                    if isinstance(item, dict) and "table" in item:
                        for team in item.get("table", [])[:10]:
                            table_data.append({
                                "Место": team.get("position"),
                                "Команда": team.get("team", {}).get("name"),
                                "Игры": team.get("playedGames"),
                                "Победы": team.get("won"),
                                "Ничьи": team.get("draw"),
                                "Поражения": team.get("lost"),
                                "Очки": team.get("points")
                            })
                if table_data:
                    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
            else:
                st.warning("Нет данных таблицы")
    
    st.divider()
    
    with st.expander("ℹ️ О лимитах API"):
        st.markdown("""
        **API Football**
        - Лимит: 100 запросов в день (бесплатный тариф)
        - 1 запрос = 1 команда / 1 матч
        - Для 16 команд РПЛ нужно 16 запросов
        
        **Football-data.org**
        - Лимит: 10 запросов в минуту (бесплатный тариф)
        - 1 запрос = вся таблица / все матчи тура
        
        **Рекомендация для FAJ**
        - Football-data: загружаем историю (1-2 запроса за тур)
        - API Football: обновляем только нужные команды (5-10 запросов за тур)
        """)

# =====================================================
# FOOTER
# =====================================================
st.divider()
st.caption("⚽ FAJ Platform 10.0 | Adaptive Football Intelligence")

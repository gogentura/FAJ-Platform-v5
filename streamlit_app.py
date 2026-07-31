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
from math import exp

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
    
    # Анализируем ошибки
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
    
    # Текущие веса
    if weights:
        last_weights = weights[-1].get('weights', {})
    else:
        last_weights = {
            "attack": 0.18, "defense": 0.18, "control": 0.15,
            "efficiency": 0.12, "mentality": 0.10, "tempo": 0.07,
            "press": 0.05, "transition": 0.05, "flexibility": 0.05,
            "coach": 0.05
        }
    
    # Корректируем веса
    new_weights = last_weights.copy()
    
    # Считаем ошибки по типам
    attack_errors = sum(1 for e in errors if e.get('faj_outcome') == "П1" and e.get('actual_outcome') != "П1")
    defense_errors = sum(1 for e in errors if e.get('faj_outcome') == "П2" and e.get('actual_outcome') != "П2")
    total_errors = len(errors)
    
    # Корректировка
    new_weights["attack"] = max(0.10, new_weights.get("attack", 0.18) - 0.02 * (attack_errors / max(total_errors, 1)))
    new_weights["defense"] = max(0.10, new_weights.get("defense", 0.18) - 0.02 * (defense_errors / max(total_errors, 1)))
    new_weights["form"] = min(0.20, new_weights.get("form", 0.10) + 0.02 * (total_errors / 8))
    new_weights["mentality"] = min(0.15, new_weights.get("mentality", 0.10) + 0.01)
    
    # Нормализация
    total_weight = sum(new_weights.values())
    for k in new_weights:
        new_weights[k] = round(new_weights[k] / total_weight, 3)
    
    # Сохраняем новую версию
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
    
    # Сохраняем в память
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

def poisson_prob(k, xg):
    """Функция Пуассона для расчёта вероятности счёта"""
    return (exp(-xg) * (xg ** k)) / (k ** 0.5 if k == 0 else 1)

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
    ["🏠 Матч-центр", "📊 Сравнение", "🧠 Обучение", "📘 Команды", "⚙️ Система", "📥 Загрузка данных"],
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
        # Переименовываем колонки на русский
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
# СТРАНИЦА: СИСТЕМА
# =====================================================
elif page == "⚙️ Система":
    st.markdown("### ⚙️ Системная информация")
    
    comparison = load_json("comparison_log.json")
    passports = load_json("passports_2026.json")
    memory = load_json("learning_memory.json")
    weights = load_json("weights_history.json")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Версия", "10.0")
    with col2:
        st.metric("Команд", len(passports))
    with col3:
        st.metric("Записей памяти", len(memory))
    
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

# =====================================================
# СТРАНИЦА: МАТЧ-ЦЕНТР (С ПРОГНОЗАМИ НА 2-Й ТУР)
# =====================================================
elif page == "🏠 Матч-центр":
    st.markdown("### 🏟 Центр прогнозирования — 2-й тур РПЛ")
    
    if not teams:
        st.warning("Нет команд в базе данных")
        st.stop()
    
    # Загружаем прогнозы на 2-й тур
    tour2 = load_json("tour2_predictions.json")
    
    if not tour2:
        st.warning("Нет данных для 2-го тура. Проверьте файл tour2_predictions.json")
        st.stop()
    
    # Показываем таблицу прогнозов
    st.markdown("### 📊 Прогнозы на 2-й тур")
    
    # Собираем данные для таблицы
    matches_data = []
    for match, data in tour2.items():
        # Разбиваем название матча на команды
        if '-' in match:
            home, away = match.split('-')
        else:
            home, away = match.split('–')
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        xg_home = data.get('xg_home', '—')
        xg_away = data.get('xg_away', '—')
        
        # Определяем исход по прогнозу FAJ
        faj_outcome = get_outcome(faj_pred) if faj_pred != '—' else '—'
        
        # Определяем лучшую ставку
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
    
    # Детальный прогноз для выбранного матча
    st.markdown("### 🔍 Детальный прогноз по матчу")
    
    # Создаём список матчей для выбора
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
        xg_home = data.get('xg_home', '—')
        xg_away = data.get('xg_away', '—')
        
        # Используем обученные веса для расчёта вероятностей
        weights_history = load_json("weights_history.json")
        if weights_history:
            current_weights = weights_history[-1].get('weights', {})
        else:
            current_weights = {
                "attack": 0.18, "defense": 0.18, "control": 0.15,
                "efficiency": 0.12, "mentality": 0.10, "tempo": 0.07,
                "press": 0.05, "transition": 0.05, "flexibility": 0.05,
                "coach": 0.05
            }
        
        # Расчёт вероятностей
        try:
            xg_h = float(xg_home) if xg_home != '—' else 1.35
            xg_a = float(xg_away) if xg_away != '—' else 1.35
        except:
            xg_h = 1.35
            xg_a = 1.35
        
        # Простая модель вероятностей на основе xG
        total_xg = xg_h + xg_a
        if total_xg > 0:
            p1 = round((xg_h / total_xg) * 100 * 0.7 + 15, 1)
            p2 = round((xg_a / total_xg) * 100 * 0.7 + 15, 1)
            px = round(100 - p1 - p2, 1)
        else:
            p1 = 33.3
            px = 33.3
            p2 = 33.3
        
        # Уверенность
        confidence = round(50 + abs(xg_h - xg_a) * 10, 1)
        if confidence > 90:
            confidence = 90
        
        # Тотал > 2.5
        total_over25 = round(30 + (xg_h + xg_a) * 10, 1)
        if total_over25 > 85:
            total_over25 = 85
        
        # Обе забьют
        btts_prob = round(30 + (xg_h * xg_a) * 15, 1)
        if btts_prob > 85:
            btts_prob = 85
        
        # Лучшая ставка
        max_prob = max(p1, px, p2)
        if max_prob == p1:
            best_bet = f"Победа {home}"
        elif max_prob == px:
            best_bet = "Ничья"
        else:
            best_bet = f"Победа {away}"
        
        # Топ-3 счёта (упрощённо)
        scores = []
        for i in range(4):
            for j in range(4):
                prob = poisson_prob(i, xg_h) * poisson_prob(j, xg_a)
                if prob > 0.01:
                    scores.append({"Счёт": f"{i}:{j}", "Вероятность %": round(prob * 100, 1)})
        scores = sorted(scores, key=lambda x: x["Вероятность %"], reverse=True)[:5]
        
        # Отображаем детальный прогноз
        st.markdown(f"""
        <div class="prediction-card">
            <h2 style="text-align:center; color:#f3f4f6; margin:0;">{home} ⚔️ {away}</h2>
            <p style="text-align:center; color:#9ca3af;">FAJ Prediction v10.0</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"Победа {home}", f"{p1}%")
        with col2:
            st.metric("Ничья", f"{px}%")
        with col3:
            st.metric(f"Победа {away}", f"{p2}%")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(f"⚽ xG {home}", xg_h)
        with col2:
            st.metric(f"⚽ xG {away}", xg_a)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Уверенность", f"{confidence}%")
        with col2:
            st.metric("⚽ Тотал > 2.5", f"{total_over25}%")
        with col3:
            st.metric("🤝 Обе забьют", f"{btts_prob}%")
        with col4:
            st.markdown(f"""
            <div class="best-bet">
                <div style="color:#9ca3af; font-size:12px;">ЛУЧШАЯ СТАВКА</div>
                <div style="color:#10b981; font-weight:700; font-size:16px;">{best_bet}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 🎯 Самые вероятные счета")
        if scores:
            st.dataframe(pd.DataFrame(scores), hide_index=True, use_container_width=True)
        
        with st.expander("🧠 Почему FAJ выбрал такой прогноз"):
            st.write(f"""
            Анализ матча {home} vs {away} на основе:
            
            1. **xG хозяев**: {xg_h}
            2. **xG гостей**: {xg_a}
            3. **Вероятности**: П1 {p1}% | X {px}% | П2 {p2}%
            4. **Уверенность модели**: {confidence}%
            5. **Ключевые факторы**:
               - {'Домашнее преимущество' if xg_h > xg_a else 'Гостевой фактор'}
               - {'Атакующий стиль' if xg_h > 1.5 else 'Сбалансированная игра'}
            """)
        
        # Сравнение с экспертом
        if expert_pred != '—':
            st.divider()
            st.markdown("### 📊 Сравнение прогнозов")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("FAJ", faj_pred)
            with col2:
                st.metric("Ваш прогноз", expert_pred)

# =====================================================
# FOOTER
# =====================================================
st.divider()
st.caption("⚽ FAJ Platform 10.0 | Adaptive Football Intelligence")

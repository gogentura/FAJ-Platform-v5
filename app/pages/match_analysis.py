#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Match Laboratory — Диагностика прогнозов
Показывает реальные данные из Prediction Pipeline
Никаких пересчётов — только визуализация
"""

import streamlit as st
import pandas as pd

from app.core.prediction_manager import get_prediction_manager
from app.database import get_connection
from app.config import config


def main():
    st.title("🔬 FAJ Match Laboratory")
    st.caption("Диагностика прогноза — реальные данные из Pipeline")

    # Загрузка команд
    try:
        conn = get_connection()
        teams_df = pd.read_sql("SELECT id, name FROM teams ORDER BY name", conn)
        conn.close()
    except Exception:
        teams_df = pd.DataFrame()

    if teams_df.empty:
        st.warning("⚠️ Нет команд. Сначала загрузите данные через 'Синхронизацию'.")
        return

    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("🏠 Хозяева", teams_df['name'].tolist(), key="lab_home")
    with col2:
        away_team = st.selectbox("✈️ Гости", teams_df['name'].tolist(), key="lab_away")

    if st.button("🔬 Запустить диагностику", type="primary"):
        if home_team == away_team:
            st.error("❌ Команды не могут совпадать")
            return

        with st.spinner("🧠 Анализ матча..."):
            try:
                pm = get_prediction_manager()
                if pm is None:
                    st.error("❌ Prediction Manager не загружен")
                    return

                result = pm.predict(home_team, away_team, league="RPL")

                if result.get('status') == 'error':
                    st.error(f"❌ {result.get('message')}")
                    return

                # ============================================================
                # ЗАГРУЗКА ПАСПОРТОВ
                # ============================================================
                # Используем passport_manager из prediction_manager
                passport_manager = getattr(pm, 'passport_manager', None)
                if passport_manager is None:
                    st.warning("⚠️ Passport Manager не доступен, использую заглушки")
                    home_passport = {}
                    away_passport = {}
                else:
                    home_passport = passport_manager.get_current_passport_by_name(home_team)
                    away_passport = passport_manager.get_current_passport_by_name(away_team)

                # Защита от None
                home_passport = home_passport or {}
                away_passport = away_passport or {}

                # ============================================================
                # 1. FAJ Rating (из паспортов)
                # ============================================================
                home_rating = home_passport.get("faj_rating", 0)
                away_rating = away_passport.get("faj_rating", 0)

                st.subheader("⭐ FAJ Rating")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"🏠 {home_team}", f"{home_rating:.0f}")
                with col2:
                    diff = away_rating - home_rating
                    st.metric("📊 Разница", f"{diff:+.0f}")
                with col3:
                    st.metric(f"✈️ {away_team}", f"{away_rating:.0f}")

                # ============================================================
                # 2. ДЕТАЛИ ПАСПОРТОВ (исправлено для Arrow)
                # ============================================================
                st.subheader("📋 Сравнение параметров")

                params = ['attack', 'defense', 'control', 'goalkeeper', 'form', 'squad_quality', 'coach_factor']

                data = []
                total_home = 0
                total_away = 0
                count = 0

                for key in params:
                    h_val = home_passport.get(key, 50)
                    a_val = away_passport.get(key, 50)
                    total_home += h_val
                    total_away += a_val
                    count += 1
                    data.append({
                        "Параметр": key.capitalize(),
                        home_team: h_val,
                        away_team: a_val,
                        "Разница": a_val - h_val
                    })

                # Теперь добавим строку со средними значениями (числами, а не строкой)
                if count > 0:
                    avg_home = total_home / count
                    avg_away = total_away / count
                    data.append({
                        "Параметр": "📊 СРЕДНЕЕ",
                        home_team: avg_home,
                        away_team: avg_away,
                        "Разница": avg_away - avg_home
                    })

                # Преобразуем в DataFrame и показываем
                df_params = pd.DataFrame(data)
                # Убедимся, что числовые колонки имеют тип float
                for col in [home_team, away_team, "Разница"]:
                    df_params[col] = pd.to_numeric(df_params[col], errors='coerce')

                st.dataframe(df_params, use_container_width=True, hide_index=True)

                # ============================================================
                # 3. XG РАСЧЁТ
                # ============================================================
                st.subheader("⚽ XG Engine")

                xg = result.get('xg', {})
                diagnostic = result.get('diagnostic', {})

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Среднее xG", f"{config.XG_LEAGUE_MEAN:.2f}")
                with col2:
                    raw_home = diagnostic.get('raw_xg_home', xg.get('home', 0))
                    st.metric("🏠 Raw xG", f"{raw_home:.2f}", delta=f"→ {xg.get('home', 0):.2f}")
                with col3:
                    raw_away = diagnostic.get('raw_xg_away', xg.get('away', 0))
                    st.metric("✈️ Raw xG", f"{raw_away:.2f}", delta=f"→ {xg.get('away', 0):.2f}")

                if diagnostic:
                    st.write("**🔧 Факторы xG (из Pipeline):**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"🏠 Home Advantage: {diagnostic.get('home_advantage', 1.12):.2f}")
                        st.write(f"🏠 Attack Factor: {diagnostic.get('home_attack_factor', 1.0):.2f}")
                        st.write(f"✈️ Defense Factor: {diagnostic.get('away_defense_factor', 1.0):.2f}")
                        st.write(f"🏠 Home Form: {diagnostic.get('home_form', 1.0):.2f}")
                        st.write(f"🏠 Home Control: {diagnostic.get('home_control_factor', 1.0):.2f}")
                    with col2:
                        st.write(f"✈️ Attack Factor: {diagnostic.get('away_attack_factor', 1.0):.2f}")
                        st.write(f"🏠 Defense Factor: {diagnostic.get('home_defense_factor', 1.0):.2f}")
                        st.write(f"🏠 GK Factor: {diagnostic.get('home_keeper_factor', 1.0):.2f}")
                        st.write(f"✈️ Away Form: {diagnostic.get('away_form', 1.0):.2f}")
                        st.write(f"✈️ Away Control: {diagnostic.get('away_control_factor', 1.0):.2f}")

                # ============================================================
                # 4. АНАЛИТИЧЕСКИЙ РАЗБОР ПРЕИМУЩЕСТВ
                # ============================================================
                st.subheader("📊 Аналитический разбор преимуществ")

                home_advantages = []
                away_advantages = []

                # На основе параметров
                for key in ['attack', 'defense', 'control', 'goalkeeper', 'squad_quality']:
                    h_val = home_passport.get(key, 50)
                    a_val = away_passport.get(key, 50)
                    if a_val - h_val > 3:
                        away_advantages.append(f"{key.capitalize()}: +{a_val - h_val:.0f}")
                    elif h_val - a_val > 3:
                        home_advantages.append(f"{key.capitalize()}: +{h_val - a_val:.0f}")

                # Домашний фактор
                home_advantages.append("🏠 Домашний фактор: +12%")

                # Форма
                home_form = home_passport.get('form', 50)
                away_form = away_passport.get('form', 50)
                if home_form > away_form:
                    home_advantages.append(f"📈 Форма: +{(home_form - away_form)*0.2:.0f}%")
                elif away_form > home_form:
                    away_advantages.append(f"📈 Форма: +{(away_form - home_form)*0.2:.0f}%")

                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**🏠 Преимущества {home_team}:**")
                    if home_advantages:
                        for adv in home_advantages:
                            st.write(f"  ✅ {adv}")
                    else:
                        st.write("  ⚖️ Нет явных преимуществ")

                with col2:
                    st.write(f"**✈️ Преимущества {away_team}:**")
                    if away_advantages:
                        for adv in away_advantages:
                            st.write(f"  ✅ {adv}")
                    else:
                        st.write("  ⚖️ Нет явных преимуществ")

                # ============================================================
                # 5. ДИАГНОСТИКА РАСХОЖДЕНИЯ
                # ============================================================
                st.subheader("🔎 Диагностика расхождения")

                rating_diff = away_rating - home_rating

                if rating_diff > 10 and xg.get('away', 0) <= xg.get('home', 0) * 1.1:
                    st.warning(f"""
                    **⚠️ FAJ Rating показывает преимущество {away_team} (+{rating_diff:.0f}), но xG почти равный.**

                    **Возможные причины:**
                    - 🏠 Домашний фактор компенсирует разницу (+12%)
                    - 📊 Отсутствие реальной формы команд
                    - 🔄 Адаптация {away_team} к гостевому матчу
                    - 🧠 Модель недооценивает {home_team} или переоценивает {away_team}
                    """)
                elif rating_diff > 5:
                    st.info(f"ℹ️ {away_team} сильнее по рейтингу (+{rating_diff:.0f}), но домашний фактор {home_team} частично компенсирует разницу.")
                else:
                    st.success("✅ Матч сбалансирован. Прогноз выглядит обоснованным.")

                # ============================================================
                # 6. ВЕРОЯТНОСТИ
                # ============================================================
                st.subheader("📈 Вероятности")

                prob = result.get('probability', {})
                prob_df = pd.DataFrame({
                    'Исход': ['Победа хозяев', 'Ничья', 'Победа гостей'],
                    'Вероятность': [prob.get('home', 0), prob.get('draw', 0), prob.get('away', 0)]
                })
                # Убедимся, что колонка "Вероятность" числовая
                prob_df['Вероятность'] = pd.to_numeric(prob_df['Вероятность'], errors='coerce')
                st.bar_chart(prob_df.set_index('Исход'))

                # ============================================================
                # 7. ИТОГОВЫЙ ПРОГНОЗ
                # ============================================================
                st.subheader("🎯 Итоговый прогноз")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("🏠 xG", f"{xg.get('home', 0):.2f}")
                with col2:
                    st.success(f"**{result.get('score', '0:0')}**")
                    st.caption(f"Вероятность: {result.get('score_probability', 0):.1%}")
                with col3:
                    st.metric("✈️ xG", f"{xg.get('away', 0):.2f}")

                # Уверенность и риск
                col1, col2 = st.columns(2)
                with col1:
                    conf = result.get('confidence', {})
                    st.metric("📊 Уверенность", f"{conf.get('overall', 0):.1%}")
                with col2:
                    risk = result.get('risk', {})
                    st.metric("⚠️ Риск", f"{risk.get('score', 0):.1f}")

                # ============================================================
                # 8. ПОЛНЫЙ JSON
                # ============================================================
                with st.expander("📋 Полный результат (JSON)"):
                    st.json(result)

            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
                import traceback
                st.code(traceback.format_exc())

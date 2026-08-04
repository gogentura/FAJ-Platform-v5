#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Загрузка данных
"""

import streamlit as st

from app.database import FAJDatabase


def render():
    st.title("📥 Загрузка данных")
    st.caption("Управление данными для обучения")

    db = FAJDatabase()

    # =========================================================
    # СТАТУС
    # =========================================================
    col1, col2 = st.columns(2)

    with col1:
        gold_count = db.get_gold_count()
        st.metric("📊 gold_dataset", gold_count)

    with col2:
        learning_count = db.get_learning_count()
        st.metric("📝 learning_records", learning_count)

    st.divider()

    # =========================================================
    # ЗАГРУЗКА ТЕСТОВОГО МАТЧА
    # =========================================================
    st.subheader("🧪 Загрузить тестовый матч")

    if st.button("📥 Загрузить тестовый матч (Краснодар — Зенит)", use_container_width=True):
        with st.spinner("Загрузка..."):
            gold_id = db.add_to_gold({
                'match_id': 1,
                'home_team': 'Краснодар',
                'away_team': 'Зенит',
                'match_date': '30.07.2026',
                'model_version': '1.0',
                'faj_score': '1:2',
                'faj_xg_home': 1.25,
                'faj_xg_away': 1.65,
                'faj_btts': 1,
                'faj_total_25': 1,
                'faj_total_35': 0,
                'faj_confidence': 68,
                'faj_rating_home': 90.0,
                'faj_rating_away': 91.5,
                'faj_pir_home': 7.8,
                'faj_pir_away': 8.3,
                'expert_score': '1:2',
                'expert_reasoning': 'разница качества состава'
            })

            db.update_gold_actual(gold_id, {
                'actual_score': '2:2',
                'actual_xg_home': 1.80,
                'actual_xg_away': 1.90,
                'actual_btts': 1,
                'actual_total_25': 1,
                'actual_total_35': 1,
                'actual_home_goals': 2,
                'actual_away_goals': 2
            })

            st.success(f"✅ Тестовый матч загружен! ID: {gold_id}")
            st.rerun()

    st.divider()

    # =========================================================
    # АУДИТ И ОТЧЁТ
    # =========================================================
    st.subheader("🔍 Анализ и обучение")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Запустить аудит", use_container_width=True):
            with st.spinner("Аудит..."):
                from app.audit_engine import audit_all_pending
                results = audit_all_pending()
                st.success(f"✅ Аудировано {len(results)} матчей")
                st.rerun()

    with col2:
        if st.button("📊 Показать отчёт", use_container_width=True):
            with st.spinner("Формируем отчёт..."):
                from app.learning_engine import get_learning_report
                report = get_learning_report()
                if report['status'] == 'no_errors':
                    st.info("✅ Нет ошибок для анализа")
                else:
                    st.write(f"**Всего ошибок:** {report['total_errors']}")
                    st.write(f"**Critical:** {report['critical']}")
                    for rec in report['recommendations']:
                        st.write(f"- {rec['priority']} {rec['title']}")


if __name__ == "__main__":
    render()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED
Страница прогноза тура
============================================================

НАЗНАЧЕНИЕ:
    - Показать доступные туры
    - Получить матчи через FAJDatabase / MatchManager
    - Вызвать PredictionManager
    - Сохранить прогнозы через существующий pipeline

ПРИНЦИПЫ:
    - Только через FAJDatabase и менеджеры
    - Никакого прямого SQL
    - Не менять календарь и результаты
"""

import streamlit as st
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.core.prediction_manager import get_prediction_manager


def main():
    st.title("🧠 Прогноз тура")
    st.caption("Просмотр и сохранение прогнозов FAJ для выбранного тура")

    db = FAJDatabase()
    match_mgr = MatchManager(db)
    pred_mgr = get_prediction_manager()

    # ============================================================
    # 1. Выбор сезона и тура
    # ============================================================

    seasons = db.get_seasons()

    if not seasons:
        st.warning("⚠️ Нет сезонов в базе данных")
        return

    # Ищем сезон РПЛ 2026/27
    season_options = {}
    for s in seasons:
        name = s.get("name", "")
        if "РПЛ" in name or "2026" in name:
            season_options[name] = s["id"]

    if not season_options:
        st.warning("⚠️ Сезон РПЛ 2026/27 не найден")
        return

    selected_season_name = st.selectbox(
        "Сезон",
        options=list(season_options.keys()),
        index=0,
    )

    season_id = season_options[selected_season_name]

    # ============================================================
    # 2. Получение туров
    # ============================================================

    rounds = db.get_rounds(season_id)

    if not rounds:
        st.info("ℹ️ В этом сезоне ещё нет туров")
        return

    # Формируем список туров с информацией о матчах
    round_options = {}
    for r in rounds:
        round_num = r["round_number"]
        matches = match_mgr.get_round_matches(r["id"])
        match_count = len(matches)
        round_options[f"Тур {round_num} ({match_count} матчей)"] = r["id"]

    selected_round_label = st.selectbox(
        "Тур",
        options=list(round_options.keys()),
        index=0,
    )

    round_id = round_options[selected_round_label]

    # ============================================================
    # 3. Получение матчей тура
    # ============================================================

    matches = match_mgr.get_round_matches(round_id)

    if not matches:
        st.info("ℹ️ В этом туре нет матчей")
        return

    st.subheader(f"📋 Матчи тура — {len(matches)}")

    # ============================================================
    # 4. Отображение матчей и прогнозов
    # ============================================================

    # Кнопка для расчёта прогнозов
    if st.button("🔮 Рассчитать прогнозы FAJ для всех матчей", type="primary"):
        with st.spinner("Прогнозирование..."):
            predictions = pred_mgr.predict_round(round_id)

            if predictions:
                st.success(f"✅ Прогнозы сохранены: {len(predictions)} матчей")
            else:
                st.warning("⚠️ Прогнозы не были созданы")

    st.divider()

    # ============================================================
    # 5. Отображение существующих прогнозов
    # ============================================================

    st.subheader("📊 Существующие прогнозы")

    for match in matches:
        match_id = match["id"]

        home = db.get_team(match["home_team_id"])
        away = db.get_team(match["away_team_id"])

        home_name = home["name"] if home else "?"
        away_name = away["name"] if away else "?"

        status = match.get("status", "scheduled")

        # Получаем прогнозы для матча
        preds = db.get_predictions_by_match(match_id)

        with st.expander(f"⚽ {home_name} — {away_name} ({status})"):

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**FAJ Прогноз**")

                if preds:
                    latest = preds[0]  # последний
                    home_win = latest.get("home_win", 0.0) * 100
                    draw = latest.get("draw", 0.0) * 100
                    away_win = latest.get("away_win", 0.0) * 100

                    st.metric("П1", f"{home_win:.1f}%")
                    st.metric("X", f"{draw:.1f}%")
                    st.metric("П2", f"{away_win:.1f}%")

                    confidence = latest.get("confidence", 0)
                    st.metric("Уверенность", f"{confidence}%")

                    if latest.get("btts"):
                        st.metric("BTTS", f"{latest['btts']*100:.1f}%")

                    if latest.get("over25"):
                        st.metric("ТБ 2.5", f"{latest['over25']*100:.1f}%")

                    st.caption(f"Модель: {latest.get('model_version', 'N/A')}")
                    st.caption(f"Создан: {latest.get('created_at', 'N/A')[:16]}")

                else:
                    st.info("Нет прогнозов")

            with col2:
                st.markdown("**🧑‍💼 Прогноз Директора**")

                # Здесь можно добавить форму для ввода прогноза Директора
                # Используем expert_predictions через db.save_expert_prediction()

                st.info("Форма для прогноза Директора будет добавлена")

    # ============================================================
    # 6. Кнопка возврата
    # ============================================================

    st.divider()

    if st.button("⬅️ Назад к управлению турами"):
        st.session_state.page = "tour_manager"
        st.rerun()


if __name__ == "__main__":
    main()

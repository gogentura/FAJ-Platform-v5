#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED
Страница ввода фактических результатов
============================================================

НАЗНАЧЕНИЕ:
    - Выбрать тур/матчи
    - Ввести фактические счета
    - Передать их в ResultManager.save_result()
    - Обеспечить повторный импорт без дублей

ПРИНЦИПЫ:
    - Только через FAJDatabase и менеджеры
    - Никакого прямого SQL
    - Не удалять исторические факты
    - Не трогать прогнозы
"""

import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.result_manager import ResultManager


def main():
    st.title("📥 Факты тура")
    st.caption("Ввод фактических результатов матчей")

    db = FAJDatabase()
    match_mgr = MatchManager(db)
    result_mgr = ResultManager(db)

    # ============================================================
    # 1. Выбор сезона и тура
    # ============================================================

    seasons = db.get_seasons()

    if not seasons:
        st.warning("⚠️ Нет сезонов в базе данных")
        return

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
    # 4. Отображение матчей с формами для ввода результатов
    # ============================================================

    results_updated = 0
    results_skipped = 0

    for match in matches:
        match_id = match["id"]

        home = db.get_team(match["home_team_id"])
        away = db.get_team(match["away_team_id"])

        home_name = home["name"] if home else "?"
        away_name = away["name"] if away else "?"

        status = match.get("status", "scheduled")

        # Проверяем существующий результат
        existing_result = result_mgr.get_result(match_id)

        with st.expander(f"⚽ {home_name} — {away_name} ({status})"):

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**{home_name} (Хозяева)**")
                home_goals = st.number_input(
                    f"Голы",
                    min_value=0,
                    max_value=20,
                    value=existing_result["home_goals"] if existing_result else 0,
                    key=f"home_{match_id}",
                    step=1,
                    label_visibility="collapsed",
                )

            with col2:
                st.markdown(f"**{away_name} (Гости)**")
                away_goals = st.number_input(
                    f"Голы",
                    min_value=0,
                    max_value=20,
                    value=existing_result["away_goals"] if existing_result else 0,
                    key=f"away_{match_id}",
                    step=1,
                    label_visibility="collapsed",
                )

            # Показываем статус результата
            if existing_result:
                status_text = existing_result.get("fact_status", "pending")
                if status_text == "locked":
                    st.warning("🔒 Результат заблокирован — изменение невозможно")
                else:
                    st.info(f"Существующий результат: {existing_result['home_goals']}:{existing_result['away_goals']}")
            else:
                st.info("Нет сохранённого результата")

            # Кнопка сохранения
            col_save, col_lock = st.columns(2)

            with col_save:
                if st.button(
                    f"💾 Сохранить",
                    key=f"save_{match_id}",
                    disabled=existing_result and existing_result.get("fact_status") == "locked",
                    use_container_width=True,
                ):
                    if home_goals == 0 and away_goals == 0:
                        # Спрашиваем подтверждение для 0:0
                        if not st.session_state.get(f"confirm_zero_{match_id}", False):
                            st.session_state[f"confirm_zero_{match_id}"] = True
                            st.warning("⚠️ Счёт 0:0 — нажмите ещё раз для подтверждения")
                        else:
                            try:
                                success = result_mgr.save_result(
                                    match_id=match_id,
                                    home_goals=home_goals,
                                    away_goals=away_goals,
                                    lock=False,
                                )
                                if success:
                                    st.success(f"✅ Результат сохранён: {home_goals}:{away_goals}")
                                    st.session_state[f"confirm_zero_{match_id}"] = False
                                    results_updated += 1
                                    st.rerun()
                                else:
                                    st.error("❌ Ошибка сохранения результата")
                            except Exception as e:
                                st.error(f"❌ Ошибка: {e}")
                    else:
                        try:
                            success = result_mgr.save_result(
                                match_id=match_id,
                                home_goals=home_goals,
                                away_goals=away_goals,
                                lock=False,
                            )
                            if success:
                                st.success(f"✅ Результат сохранён: {home_goals}:{away_goals}")
                                results_updated += 1
                                st.rerun()
                            else:
                                st.error("❌ Ошибка сохранения результата")
                        except Exception as e:
                            st.error(f"❌ Ошибка: {e}")

            # Кнопка блокировки (если результат уже есть)
            with col_lock:
                if existing_result and existing_result.get("fact_status") != "locked":
                    if st.button(
                        f"🔒 Заблокировать",
                        key=f"lock_{match_id}",
                        use_container_width=True,
                    ):
                        try:
                            success = result_mgr.lock_result(match_id)
                            if success:
                                st.success("✅ Результат заблокирован")
                                st.rerun()
                            else:
                                st.error("❌ Ошибка блокировки")
                        except Exception as e:
                            st.error(f"❌ Ошибка: {e}")

    # ============================================================
    # 5. Статистика по туру
    # ============================================================

    st.divider()

    # Подсчёт заполненных результатов
    filled = 0
    locked = 0
    total = len(matches)

    for match in matches:
        result = result_mgr.get_result(match["id"])
        if result:
            filled += 1
            if result.get("fact_status") == "locked":
                locked += 1

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Всего матчей", total)

    with col2:
        if total > 0:
            st.metric("Заполнено", filled, delta=f"{filled/total*100:.0f}%")
        else:
            st.metric("Заполнено", filled)

    with col3:
        st.metric("Заблокировано", locked)

    # ============================================================
    # 6. Кнопка перехода к завершению тура
    # ============================================================

    if filled == total and total > 0:
        st.success("✅ Все матчи тура имеют результаты")

        if st.button("🏁 Перейти к завершению тура", type="primary"):
            st.session_state.page = "round_complete"
            st.rerun()
    else:
        if total > 0:
            st.info(f"ℹ️ Заполнено {filled}/{total} матчей. Заполните все для завершения тура.")

    # ============================================================
    # 7. Кнопка возврата
    # ============================================================

    if st.button("⬅️ Назад к управлению турами"):
        st.session_state.page = "tour_manager"
        st.rerun()


if __name__ == "__main__":
    main()

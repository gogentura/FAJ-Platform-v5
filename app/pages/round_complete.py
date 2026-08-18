#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED
Страница завершения тура
============================================================

НАЗНАЧЕНИЕ:
    - Проверить полноту фактов
    - Показать сравнение прогнозов с фактами
    - Запустить обучение через Learning Engine
    - Связать с FAJ Cycle

ПРИНЦИПЫ:
    - Не создавать календарь
    - Не пересчитывать прогнозы
    - Не менять результаты
    - Только чтение данных и запуск обучения
"""

import streamlit as st
from datetime import datetime

from app.database import FAJDatabase


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def get_round_matches(db: FAJDatabase, round_id: int):
    """Получает матчи тура с именами команд."""
    matches = db.get_matches(round_id)
    result = []
    for match in matches:
        match_data = dict(match)
        home = db.get_team(match_data.get("home_team_id"))
        away = db.get_team(match_data.get("away_team_id"))
        match_data["home_name"] = home["name"] if home else "?"
        match_data["away_name"] = away["name"] if away else "?"
        result.append(match_data)
    return result


def get_expert_predictions(db: FAJDatabase, match_id: int):
    """Получает экспертные прогнозы для матча."""
    try:
        return db.get_expert_predictions(match_id)
    except AttributeError:
        # Если метода нет — пробуем SQL напрямую
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM expert_predictions
                WHERE match_id = ?
                ORDER BY created_at DESC
            """, (match_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def get_latest_prediction(db: FAJDatabase, match_id: int):
    """Получает последний прогноз FAJ для матча."""
    pred = db.get_latest_prediction(match_id)
    return dict(pred) if pred else None


def get_match_result(db: FAJDatabase, match_id: int):
    """Получает результат матча."""
    result = db.get_match_result(match_id)
    return dict(result) if result else None


def is_result_locked(db: FAJDatabase, match_id: int) -> bool:
    """Проверяет, заблокирован ли результат."""
    try:
        return db.is_result_locked(match_id)
    except AttributeError:
        result = get_match_result(db, match_id)
        return result and result.get("fact_status") == "locked"


def get_active_season(db: FAJDatabase):
    """Возвращает активный сезон РПЛ."""
    seasons = db.get_seasons()
    for season in seasons:
        data = dict(season)
        league = data.get("league", "")
        name = data.get("name", "")
        status = data.get("status", "")
        if league == "РПЛ" and (status == "active" or "2026" in name):
            return data
    # Fallback — последний сезон РПЛ
    for season in reversed(seasons):
        data = dict(season)
        if data.get("league") == "РПЛ":
            return data
    return None


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ СТРАНИЦЫ
# ============================================================

def main():
    st.title("🏁 Тур сыгран")
    st.caption("Завершение тура, сравнение прогнозов и обучение")

    db = FAJDatabase()

    # ============================================================
    # 1. Выбор сезона и тура
    # ============================================================

    season = get_active_season(db)

    if not season:
        st.warning("⚠️ Активный сезон РПЛ не найден")
        return

    season_id = season["id"]

    # ============================================================
    # 2. Получение туров с матчами
    # ============================================================

    rounds = db.get_rounds(season_id)

    if not rounds:
        st.info("ℹ️ В этом сезоне ещё нет туров")
        return

    # Формируем список туров, у которых есть матчи
    round_options = {}
    for r in rounds:
        r_data = dict(r)
        round_num = r_data.get("round_number")
        if round_num is None:
            continue
        matches = get_round_matches(db, r_data["id"])
        if matches:
            match_count = len(matches)
            round_options[f"Тур {round_num} ({match_count} матчей)"] = r_data["id"]

    if not round_options:
        st.info("ℹ️ Нет туров с матчами")
        return

    selected_round_label = st.selectbox(
        "Тур",
        options=list(round_options.keys()),
        index=0,
    )

    round_id = round_options[selected_round_label]

    # ============================================================
    # 3. Получение матчей тура и проверка полноты фактов
    # ============================================================

    matches = get_round_matches(db, round_id)

    if not matches:
        st.info("ℹ️ В этом туре нет матчей")
        return

    # Проверяем наличие результатов у всех матчей
    all_filled = True
    filled_count = 0
    locked_count = 0
    match_statuses = []

    for match in matches:
        match_id = match["id"]
        result = get_match_result(db, match_id)

        home_name = match.get("home_name", "?")
        away_name = match.get("away_name", "?")

        has_result = result is not None
        is_locked = is_result_locked(db, match_id)

        if has_result:
            filled_count += 1
        else:
            all_filled = False

        if is_locked:
            locked_count += 1

        match_statuses.append({
            "match_id": match_id,
            "home": home_name,
            "away": away_name,
            "has_result": has_result,
            "is_locked": is_locked,
            "result": result,
            "status": match.get("status", "scheduled"),
        })

    total = len(matches)

    # ============================================================
    # 4. Отображение статуса тура
    # ============================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Всего матчей", total)

    with col2:
        pct = f"{filled_count/total*100:.0f}%" if total > 0 else "0%"
        st.metric("С результатами", filled_count, delta=pct)

    with col3:
        st.metric("Заблокировано", locked_count)

    with col4:
        status_color = "🟢" if all_filled else "🔴"
        st.metric("Готов к завершению", status_color)

    # ============================================================
    # 5. Отображение статуса каждого матча
    # ============================================================

    st.subheader("📋 Статус матчей")

    for ms in match_statuses:
        icon = "✅" if ms["has_result"] else "❌"
        lock_icon = "🔒" if ms["is_locked"] else "🔓" if ms["has_result"] else "⏳"
        result_text = f"{ms['result']['home_goals']}:{ms['result']['away_goals']}" if ms["has_result"] else "Нет результата"
        st.write(f"{icon} {ms['home']} — {ms['away']}  |  {lock_icon} {result_text}")

    st.divider()

    # ============================================================
    # 6. Сравнение прогнозов с фактами
    # ============================================================

    if all_filled:
        st.subheader("📊 Сравнение прогнозов с фактами")

        # Получаем прогнозы для всех матчей
        predictions_data = []

        for match in matches:
            match_id = match["id"]
            result = get_match_result(db, match_id)

            if not result:
                continue

            home_name = match.get("home_name", "?")
            away_name = match.get("away_name", "?")

            # Получаем прогнозы FAJ
            faj_pred = get_latest_prediction(db, match_id)

            # Получаем прогнозы Директора (expert_predictions)
            expert_preds = get_expert_predictions(db, match_id)
            expert_latest = expert_preds[0] if expert_preds else None

            actual_home = result["home_goals"]
            actual_away = result["away_goals"]

            # Определяем исход
            if actual_home > actual_away:
                actual_winner = "home"
            elif actual_home < actual_away:
                actual_winner = "away"
            else:
                actual_winner = "draw"

            # Сравнение FAJ
            if faj_pred:
                faj_home = faj_pred.get("home_win", 0.0)
                faj_draw = faj_pred.get("draw", 0.0)
                faj_away = faj_pred.get("away_win", 0.0)

                if faj_home >= faj_draw and faj_home >= faj_away:
                    faj_predicted = "home"
                elif faj_away >= faj_home and faj_away >= faj_draw:
                    faj_predicted = "away"
                else:
                    faj_predicted = "draw"

                faj_correct = faj_predicted == actual_winner
            else:
                faj_correct = None

            # Сравнение Директора
            if expert_latest:
                expert_score = expert_latest.get("score", "")
                try:
                    if ":" in expert_score:
                        parts = expert_score.split(":")
                        expert_home = int(parts[0].strip())
                        expert_away = int(parts[1].strip())
                        if expert_home > expert_away:
                            expert_predicted = "home"
                        elif expert_home < expert_away:
                            expert_predicted = "away"
                        else:
                            expert_predicted = "draw"
                        expert_correct = expert_predicted == actual_winner
                    else:
                        expert_correct = None
                except (ValueError, IndexError):
                    expert_correct = None
            else:
                expert_correct = None

            predictions_data.append({
                "home": home_name,
                "away": away_name,
                "actual": f"{actual_home}:{actual_away}",
                "faj_correct": faj_correct,
                "expert_correct": expert_correct,
                "faj_score": faj_pred.get("predicted_score") if faj_pred else None,
                "expert_score": expert_latest.get("score") if expert_latest else None,
            })

        # Показываем таблицу сравнения
        for pd in predictions_data:
            faj_icon = "✅" if pd["faj_correct"] is True else "❌" if pd["faj_correct"] is False else "❓"
            expert_icon = "✅" if pd["expert_correct"] is True else "❌" if pd["expert_correct"] is False else "❓"
            faj_score_display = pd["faj_score"] or "—"
            expert_score_display = pd["expert_score"] or "—"

            st.write(
                f"⚽ {pd['home']} — {pd['away']}  |  "
                f"Факт: {pd['actual']}  |  "
                f"FAJ: {faj_score_display} {faj_icon}  |  "
                f"Директор: {expert_score_display} {expert_icon}"
            )

        # Подсчёт статистики
        faj_correct_count = sum(1 for pd in predictions_data if pd["faj_correct"] is True)
        expert_correct_count = sum(1 for pd in predictions_data if pd["expert_correct"] is True)
        faj_total = sum(1 for pd in predictions_data if pd["faj_correct"] is not None)
        expert_total = sum(1 for pd in predictions_data if pd["expert_correct"] is not None)

        col1, col2 = st.columns(2)

        with col1:
            st.metric("FAJ точность", f"{faj_correct_count}/{faj_total}" if faj_total > 0 else "Нет данных")

        with col2:
            st.metric("Директор точность", f"{expert_correct_count}/{expert_total}" if expert_total > 0 else "Нет данных")

    # ============================================================
    # 7. Кнопка завершения тура и обучения
    # ============================================================

    st.divider()

    if all_filled:
        st.success("✅ Все матчи тура имеют результаты. Можно завершить тур.")

        if st.button("🧠 Запустить обучение", type="primary"):
            with st.spinner("Обучение..."):
                try:
                    from app.learning_engine import run_learning

                    learning_result = run_learning(force=False)

                    if learning_result.get("success"):
                        st.success("✅ Обучение завершено успешно")

                        if learning_result.get("skipped"):
                            st.info("ℹ️ Обучение было пропущено (нет новых данных)")
                        else:
                            st.info(
                                f"📊 Проанализировано матчей: {learning_result.get('matches_analyzed', 0)}\n"
                                f"📊 Найдено закономерностей: {learning_result.get('patterns_found', 0)}\n"
                                f"📊 Изменено параметров: {learning_result.get('parameters_changed', 0)}"
                            )
                    else:
                        errors = learning_result.get('errors', ['Неизвестная ошибка'])
                        st.error(f"❌ Ошибка обучения: {errors[0] if errors else 'Неизвестная ошибка'}")

                except Exception as e:
                    st.error(f"❌ Ошибка при запуске обучения: {e}")

        # Кнопка перехода к следующему туру
        if st.button("➡️ Перейти к следующему туру"):
            st.session_state.page = "tour_manager"
            st.rerun()

    else:
        st.warning(f"⚠️ Заполнено {filled_count}/{total} матчей. Заполните все результаты перед завершением тура.")

    # ============================================================
    # 8. Кнопка возврата
    # ============================================================

    st.divider()

    if st.button("⬅️ Назад к фактам тура"):
        st.session_state.page = "import_facts"
        st.rerun()


if __name__ == "__main__":
    main()

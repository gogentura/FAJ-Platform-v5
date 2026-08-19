#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1 — MEMORY HARDENED
PREDICT ROUND v3.1
============================================================

НАЗНАЧЕНИЕ:
    Страница прогнозов тура.

ЦИКЛ:
    Управление туром
        ↓
    выбранный тур
        ↓
    матчи из SQLite
        ↓
    FAJ PredictionManager
        ↓
    прогноз каждого матча
        ↓
    сохранение FAJ-прогноза
        ↓
    ввод и сохранение прогноза Директора

СТРАНИЦА НЕ ОТВЕЧАЕТ ЗА:
    - создание матчей;
    - удаление матчей;
    - календарь;
    - результаты;
    - обучение;
    - изменение паспортов;
    - изменение математической модели.

ВАЖНО:
    sqlite3.Row всегда преобразуется в dict перед использованием .get().
    Экспертный прогноз сохраняется в БД (expert_predictions).
============================================================
"""

from __future__ import annotations

import logging
import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.core.prediction_manager import get_prediction_manager


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def row_dict(row):
    """Безопасно преобразует sqlite3.Row / dict в dict."""
    if row is None:
        return None

    if isinstance(row, dict):
        return row

    try:
        return dict(row)
    except Exception:
        return None


def team_name(db: FAJDatabase, team_id) -> str:
    """Получает название команды."""
    try:
        team = db.get_team(team_id)

        if team is None:
            return "?"

        team = row_dict(team)

        if not team:
            return "?"

        return str(team.get("name", "?"))

    except Exception:
        return "?"


def percent(value) -> float:
    """Безопасно переводит вероятность в проценты."""
    try:
        value = float(value or 0)

        # PredictionManager хранит вероятности 0..1
        if value <= 1:
            return value * 100

        return value

    except (TypeError, ValueError):
        return 0.0


def probability_value(value) -> float:
    """Возвращает вероятность в диапазоне 0..1."""
    try:
        value = float(value or 0)

        if value > 1:
            value /= 100

        return max(0.0, min(1.0, value))

    except (TypeError, ValueError):
        return 0.0


def format_probability(value) -> str:
    return f"{percent(value):.1f}%"


def get_latest_prediction(db: FAJDatabase, match_id: int):
    """Возвращает последний сохранённый прогноз FAJ."""
    try:
        predictions = db.get_predictions_by_match(match_id)

        if not predictions:
            return None

        rows = [row_dict(p) for p in predictions]
        rows = [p for p in rows if p]

        if not rows:
            return None

        return rows[0]

    except Exception:
        return None


def get_top_scores(db: FAJDatabase, prediction_id: int):
    """
    Получает Top-5 счетов.

    Основной источник — prediction_scores.
    Если метода отсутствует, возвращается пустой список.
    """
    if not prediction_id:
        return []

    try:
        if not hasattr(db, "get_prediction_scores"):
            return []

        scores = db.get_prediction_scores(prediction_id)

        result = []

        for score in scores or []:
            score = row_dict(score)

            if score:
                result.append(score)

        result.sort(
            key=lambda x: float(x.get("probability", 0) or 0),
            reverse=True,
        )

        return result[:5]

    except Exception:
        return []


def score_from_prediction(prediction: dict):
    """
    Пытается определить основной вероятный счёт.

    Приоритет:
        1. prediction["most_likely_score"]
        2. prediction["predicted_score"]
        3. prediction["score"]
    """
    for key in (
        "most_likely_score",
        "predicted_score",
        "score",
    ):
        value = prediction.get(key)

        if value:
            return str(value)

    return "—"


def render_probability_columns(prediction: dict):
    """Показывает П1 / X / П2."""

    probability = prediction.get("probability", {})

    if not isinstance(probability, dict):
        probability = {}

    home = probability.get("home", prediction.get("home_win", 0))
    draw = probability.get("draw", prediction.get("draw", 0))
    away = probability.get("away", prediction.get("away_win", 0))

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("П1", format_probability(home))

    with c2:
        st.metric("X", format_probability(draw))

    with c3:
        st.metric("П2", format_probability(away))


def render_prediction_card(
    db: FAJDatabase,
    match: dict,
    prediction: dict | None,
):
    """Полная карточка прогноза."""

    match_id = match.get("id")

    home = team_name(db, match.get("home_team_id"))
    away = team_name(db, match.get("away_team_id"))

    st.markdown("---")

    st.subheader(f"⚽ {home} — {away}")

    if not prediction:
        st.warning("FAJ-прогноз для этого матча ещё не сохранён.")
        return

    if prediction.get("status") == "error":
        st.error(
            f"❌ Ошибка прогноза: "
            f"{prediction.get('message', 'Неизвестная ошибка')}"
        )
        return

    # --------------------------------------------------------
    # P1 / X / P2
    # --------------------------------------------------------

    render_probability_columns(prediction)

    # --------------------------------------------------------
    # Основной прогноз
    # --------------------------------------------------------

    st.markdown("### 🎯 Основной прогноз")

    score = score_from_prediction(prediction)

    probability = prediction.get("probability", {})
    if not isinstance(probability, dict):
        probability = {}

    home_probability = probability_value(
        probability.get("home", prediction.get("home_win", 0))
    )
    draw_probability = probability_value(
        probability.get("draw", prediction.get("draw", 0))
    )
    away_probability = probability_value(
        probability.get("away", prediction.get("away_win", 0))
    )

    outcomes = {
        "П1": home_probability,
        "X": draw_probability,
        "П2": away_probability,
    }

    main_outcome = max(outcomes, key=outcomes.get)

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Исход",
            main_outcome,
            f"{percent(outcomes[main_outcome]):.1f}%",
        )

    with c2:
        st.metric(
            "Вероятный счёт",
            score,
        )

    # --------------------------------------------------------
    # TOP-5
    # --------------------------------------------------------

    st.markdown("### 🏆 Топ-5 вероятных счетов")

    prediction_id = prediction.get("prediction_id") or prediction.get("id")

    top_scores = get_top_scores(db, prediction_id)

    # Если database.py не предоставляет отдельный getter,
    # пробуем использовать данные самого результата.
    if not top_scores:
        extended = prediction.get("extended", {})

        if isinstance(extended, dict):
            raw_scores = extended.get("top_scores", [])

            if isinstance(raw_scores, list):
                top_scores = [
                    row_dict(score)
                    for score in raw_scores
                    if row_dict(score)
                ]

    if top_scores:

        table_data = []

        for index, score_data in enumerate(top_scores[:5], start=1):

            score_text = score_data.get("score")

            if not score_text:
                score_text = (
                    f"{score_data.get('home', 0)}:"
                    f"{score_data.get('away', 0)}"
                )

            table_data.append(
                {
                    "№": index,
                    "Счёт": score_text,
                    "Вероятность": format_probability(
                        score_data.get("probability", 0)
                    ),
                }
            )

        st.table(table_data)

    else:
        st.info("Top-5 счетов пока недоступен.")

    # --------------------------------------------------------
    # BTTS / TOTALS
    # --------------------------------------------------------

    st.markdown("### 📊 Дополнительные рынки")

    extended = prediction.get("extended", {})

    if not isinstance(extended, dict):
        extended = {}

    btts = extended.get("btts", {})
    total = extended.get("total", {})

    if not isinstance(btts, dict):
        btts = {}

    if not isinstance(total, dict):
        total = {}

    btts_yes = probability_value(
        btts.get("yes", prediction.get("btts", 0))
    )

    over25 = probability_value(
        total.get(
            "over_2_5",
            prediction.get("over25", 0),
        )
    )

    over35 = probability_value(
        total.get(
            "over_3_5",
            prediction.get("over35", 0),
        )
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Обе забьют",
            "ДА" if btts_yes >= 0.5 else "НЕТ",
            format_probability(btts_yes),
        )

    with c2:
        st.metric(
            "ТБ 2.5",
            "ДА" if over25 >= 0.5 else "НЕТ",
            format_probability(over25),
        )

    with c3:
        st.metric(
            "ТБ 3.5",
            "ДА" if over35 >= 0.5 else "НЕТ",
            format_probability(over35),
        )

    # --------------------------------------------------------
    # CONFIDENCE / RISK
    # --------------------------------------------------------

    st.markdown("### 🛡️ Качество прогноза")

    confidence = prediction.get("confidence", 0)

    if isinstance(confidence, dict):
        confidence = confidence.get(
            "overall",
            confidence.get("value", 0),
        )

    try:
        confidence = float(confidence)

        if confidence <= 1:
            confidence *= 100

    except (TypeError, ValueError):
        confidence = 0

    risk = prediction.get("risk")

    if isinstance(risk, dict):
        risk = (
            risk.get("level")
            or risk.get("label")
            or risk.get("overall")
        )

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Уверенность",
            f"{confidence:.0f}%",
        )

    with c2:
        st.metric(
            "Риск",
            str(risk) if risk else "—",
        )

    # --------------------------------------------------------
    # MODEL INFO
    # --------------------------------------------------------

    model_version = (
        prediction.get("model_version")
        or prediction.get("version")
        or "FAJ"
    )

    st.caption(
        f"Модель: {model_version}"
        + (
            f" • prediction_id: {prediction_id}"
            if prediction_id
            else ""
        )
    )

    # --------------------------------------------------------
    # EXPERT — С СОХРАНЕНИЕМ В БД
    # --------------------------------------------------------

    st.markdown("### 🧑‍💼 Прогноз Директора")

    expert_key = f"expert_score_{match_id}"

    existing_expert = st.session_state.get(
        expert_key,
        "",
    )

    # Проверяем, есть ли уже сохранённый экспертный прогноз в БД
    try:
        existing_expert_db = db.get_expert_predictions(match_id)
        if existing_expert_db and not existing_expert:
            first = row_dict(existing_expert_db[0])
            if first:
                existing_expert = first.get("score", "")
                st.session_state[expert_key] = existing_expert
    except Exception:
        pass

    expert_score = st.text_input(
        "Ваш счёт",
        value=existing_expert,
        placeholder="Например: 2:1",
        key=f"expert_input_{match_id}",
    )

    expert_comment = st.text_input(
        "Комментарий (опционально)",
        value="",
        placeholder="Краткое обоснование...",
        key=f"expert_comment_{match_id}",
    )

    expert_confidence = st.slider(
        "Уверенность эксперта, %",
        min_value=0,
        max_value=100,
        value=50,
        key=f"expert_confidence_{match_id}",
    )

    if expert_score:
        st.session_state[expert_key] = expert_score

        if ":" in expert_score:
            parts = expert_score.split(":", 1)

            try:
                home_score = int(parts[0].strip())
                away_score = int(parts[1].strip())

                if home_score >= 0 and away_score >= 0:
                    st.success(
                        f"Эксперт: **{home_score}:{away_score}**"
                    )

                    # ===== СОХРАНЕНИЕ В БД =====
                    try:
                        # Проверяем, есть ли уже запись
                        existing = db.get_expert_predictions(match_id)
                        if not existing:
                            db.save_expert_prediction(
                                match_id=match_id,
                                expert_name="Директор",
                                score=expert_score,
                                comment=expert_comment,
                                confidence=expert_confidence,
                            )
                            logger.info(
                                f"Экспертный прогноз сохранён: "
                                f"match_id={match_id}, score={expert_score}"
                            )
                            st.success("✅ Прогноз эксперта сохранён в БД")
                        else:
                            st.info("ℹ️ Прогноз эксперта уже сохранён в БД")
                    except Exception as e:
                        logger.error(
                            f"Ошибка сохранения экспертного прогноза: {e}"
                        )
                        st.warning(f"⚠️ Ошибка сохранения: {e}")
                    # =====================================

            except ValueError:
                st.warning(
                    "Введите счёт в формате 2:1"
                )

    st.caption(
        "Прогноз Директора является отдельной экспертной линией "
        "и не изменяет автоматически прогноз FAJ."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🧠 Прогнозы")

    st.caption(
        "FAJ прогнозирует только матчи, которые уже созданы "
        "в Управлении туром."
    )

    db = FAJDatabase()
    match_mgr = MatchManager(db)
    pred_mgr = get_prediction_manager()

    # ========================================================
    # 1. SEASONS
    # ========================================================

    seasons_raw = db.get_seasons()

    seasons = [
        row_dict(s)
        for s in seasons_raw or []
    ]

    seasons = [
        s for s in seasons
        if s
    ]

    if not seasons:
        st.warning("⚠️ В базе нет сезонов.")
        return

    # ========================================================
    # 2. LEAGUE / SEASON
    # ========================================================

    league_names = []

    for season in seasons:

        league = season.get("league")

        if league and league not in league_names:
            league_names.append(league)

    if not league_names:
        league_names = ["РПЛ"]

    # РПЛ первой
    if "РПЛ" in league_names:
        league_names.remove("РПЛ")
        league_names.insert(0, "РПЛ")

    selected_league = st.selectbox(
        "Лига",
        league_names,
        key="predict_league",
    )

    league_seasons = [
        s
        for s in seasons
        if s.get("league") == selected_league
    ]

    if not league_seasons:
        st.warning(
            f"⚠️ Для лиги {selected_league} "
            "сезонов не найдено."
        )
        return

    season_options = {
        str(s.get("name", s.get("id"))): s.get("id")
        for s in league_seasons
    }

    selected_season_name = st.selectbox(
        "Сезон",
        list(season_options.keys()),
        key="predict_season",
    )

    season_id = season_options[selected_season_name]

    # ========================================================
    # 3. ROUNDS
    # ========================================================

    rounds_raw = db.get_rounds(season_id)

    rounds = [
        row_dict(r)
        for r in rounds_raw or []
    ]

    rounds = [
        r for r in rounds
        if r
    ]

    if not rounds:
        st.info(
            "ℹ️ В выбранном сезоне пока нет созданных туров."
        )
        return

    round_options = {}

    for r in rounds:

        round_id = r.get("id")
        round_number = r.get("round_number")

        matches = match_mgr.get_round_matches(
            round_id
        )

        round_options[
            f"Тур {round_number} — {len(matches)} матч."
        ] = round_id

    selected_round_label = st.selectbox(
        "Тур",
        list(round_options.keys()),
        key="predict_round",
    )

    round_id = round_options[
        selected_round_label
    ]

    # ========================================================
    # 4. MATCHES
    # ========================================================

    matches_raw = match_mgr.get_round_matches(
        round_id
    )

    matches = [
        row_dict(m)
        for m in matches_raw or []
    ]

    matches = [
        m for m in matches
        if m
    ]

    if not matches:
        st.info(
            "ℹ️ В выбранном туре ещё нет матчей."
        )
        return

    st.markdown(
        f"### 📋 Тур — {len(matches)} матчей"
    )

    # ========================================================
    # 5. ROUND STATUS
    # ========================================================

    existing_predictions = 0

    for match in matches:

        prediction = get_latest_prediction(
            db,
            match.get("id"),
        )

        if prediction:
            existing_predictions += 1

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Матчей",
            len(matches),
        )

    with c2:
        st.metric(
            "Прогнозов FAJ",
            f"{existing_predictions}/{len(matches)}",
        )

    # ========================================================
    # 6. CALCULATE
    # ========================================================

    st.divider()

    if st.button(
        "🔮 РАССЧИТАТЬ ПРОГНОЗЫ FAJ",
        type="primary",
        use_container_width=True,
    ):

        progress = st.progress(0)
        status_box = st.empty()

        results = []

        for index, match in enumerate(matches):

            home = team_name(
                db,
                match.get("home_team_id"),
            )

            away = team_name(
                db,
                match.get("away_team_id"),
            )

            status_box.info(
                f"Расчёт {index + 1}/{len(matches)}: "
                f"{home} — {away}"
            )

            try:
                result = pred_mgr.predict_by_match_id(
                    int(match["id"])
                )

                results.append(result)

            except Exception as exc:

                results.append(
                    {
                        "status": "error",
                        "match_id": match.get("id"),
                        "home_team": home,
                        "away_team": away,
                        "message": str(exc),
                    }
                )

            progress.progress(
                (index + 1) / len(matches)
            )

        status_box.empty()

        success_count = sum(
            1
            for result in results
            if result.get("status") != "error"
        )

        error_count = len(results) - success_count

        if error_count == 0:

            st.success(
                f"✅ FAJ рассчитал и сохранил "
                f"прогнозы всех {success_count} матчей."
            )

        else:

            st.warning(
                f"⚠️ Сохранено прогнозов: "
                f"{success_count}. "
                f"Ошибок: {error_count}."
            )

            for result in results:

                if result.get("status") == "error":

                    st.error(
                        f"{result.get('home_team', '?')} — "
                        f"{result.get('away_team', '?')}: "
                        f"{result.get('message', 'Ошибка')}"
                    )

        st.rerun()

    # ========================================================
    # 7. CARDS
    # ========================================================

    st.divider()

    st.subheader("📊 Карточки прогнозов")

    for match in matches:

        match_id = match.get("id")

        prediction = get_latest_prediction(
            db,
            match_id,
        )

        render_prediction_card(
            db=db,
            match=match,
            prediction=prediction,
        )

    # ========================================================
    # 8. BACK
    # ========================================================

    st.divider()

    if st.button(
        "⬅️ Управление туром",
        use_container_width=True,
    ):

        st.session_state.page = "tour_manager"
        st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

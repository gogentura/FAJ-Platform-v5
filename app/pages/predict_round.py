#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1 — MEMORY HARDENED
PREDICT ROUND v3.7
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
    сохранение FAJ-прогноза (через кнопку "Рассчитать прогнозы FAJ")
        ↓
    ввод и сохранение прогноза Директора
        ↓
    СОХРАНЕНИЕ В GITHUB (новая кнопка)

СТРАНИЦА НЕ ОТВЕЧАЕТ ЗА:
    - создание матчей;
    - удаление матчей;
    - календарь;
    - результаты;
    - обучение;
    - изменение паспортов;
    - изменение математической модели.

ИСПРАВЛЕНИЯ v3.7:
    1. Отображение Math Most Likely Score
    2. Отображение FAJ Final Score
    3. Отображение FAJ Confidence
    4. Отображение Decision Factors (разворачиваемый блок)
    5. Исправлена передача db в faj_score_from_prediction()
    6. Убрана дублирующая кнопка (устаревшая)
    7. Две кнопки: "Рассчитать прогнозы FAJ" и "Пересчитать все прогнозы"
"""

from __future__ import annotations

import logging
import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.core.prediction_manager import get_prediction_manager
from app.services.team_mapping import get_team_mapping_service
from app.services.match_context import (
    get_match_context_service,
    MatchContextError,
    MatchContextService,
)

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

# ============================================================
# GET LATEST PREDICTION
# ============================================================

def get_latest_prediction(db: FAJDatabase, match_id: int):
    """Возвращает последний сохранённый прогноз FAJ."""
    try:
        predictions = db.get_predictions_by_match(match_id, include_history=False)
        if not predictions:
            return None
        rows = [row_dict(p) for p in predictions]
        rows = [p for p in rows if p]
        if not rows:
            return None
        return rows[0]
    except Exception:
        return None

# ============================================================
# GET TOP SCORES
# ============================================================

def get_top_scores(db: FAJDatabase, prediction_id: int, score_type: str = "math"):
    """
    Получает Top-5 счетов.

    Args:
        db: FAJDatabase
        prediction_id: ID прогноза
        score_type: "math" или "faj"
    """
    if not prediction_id:
        return []

    try:
        if not hasattr(db, "get_prediction_scores"):
            return []

        scores = db.get_prediction_scores(prediction_id, score_type=score_type)

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

# ============================================================
# MATH SCORE FROM PREDICTION
# ============================================================

def math_score_from_prediction(db: FAJDatabase, prediction: dict) -> str:
    """
    Возвращает Math Most Likely Score.

    Источник истины (приоритет):
        1. prediction["math_most_likely_score"]
        2. prediction["most_likely_score"]
        3. prediction["predicted_score"]
        4. prediction["score"]
        5. prediction_scores (rank=1, score_type="math")
        6. extended.top_scores[0]
    """
    if not prediction:
        return "—"

    # 1-4. Явные поля prediction
    for key in (
        "math_most_likely_score",
        "most_likely_score",
        "predicted_score",
        "score",
    ):
        value = prediction.get(key)
        if value:
            return str(value)

    # 5. prediction_scores (math)
    try:
        prediction_id = prediction.get("prediction_id") or prediction.get("id")
        if prediction_id and hasattr(db, "get_prediction_scores"):
            scores = db.get_prediction_scores(prediction_id, score_type="math")
            rows = [row_dict(row) for row in (scores or []) if row_dict(row)]
            if rows:
                rows.sort(key=lambda x: float(x.get("probability", 0) or 0), reverse=True)
                score = rows[0].get("score")
                if score:
                    return str(score)
    except Exception as exc:
        logger.debug("Ошибка чтения prediction_scores (math): %s", exc)

    # 6. extended.top_scores
    extended = prediction.get("extended", {})
    if isinstance(extended, dict):
        top_scores = extended.get("top_scores", [])
        if isinstance(top_scores, list) and top_scores:
            first = row_dict(top_scores[0])
            if first:
                score = first.get("score")
                if score:
                    return str(score)
                home = first.get("home")
                away = first.get("away")
                if home is not None and away is not None:
                    return f"{home}:{away}"

    return "—"

# ============================================================
# MATH PROBABILITY FROM PREDICTION
# ============================================================

def math_probability_from_prediction(prediction: dict) -> float:
    """Возвращает вероятность Math Most Likely Score."""
    if not prediction:
        return 0.0

    # 1. math_score_probability
    value = prediction.get("math_score_probability")
    if value is not None:
        return probability_value(value)

    # 2. score_probability
    value = prediction.get("score_probability")
    if value is not None:
        return probability_value(value)

    return 0.0

# ============================================================
# FAJ SCORE FROM PREDICTION (ИСПРАВЛЕНО: db передаётся)
# ============================================================

def faj_score_from_prediction(db: FAJDatabase, prediction: dict) -> str:
    """
    Возвращает FAJ Final Score.

    Источник истины (приоритет):
        1. prediction["faj_final_score"]
        2. extended["faj_final_score"]
        3. prediction_scores (rank=1, score_type="faj")
    """
    if not prediction:
        return "—"

    # 1. faj_final_score
    faj_score = prediction.get("faj_final_score")
    if faj_score:
        return str(faj_score)

    # 2. extended.faj_final_score
    extended = prediction.get("extended", {})
    if isinstance(extended, dict):
        faj_score = extended.get("faj_final_score")
        if faj_score:
            return str(faj_score)

    # 3. prediction_scores (faj)
    try:
        prediction_id = prediction.get("prediction_id") or prediction.get("id")
        if prediction_id and hasattr(db, "get_prediction_scores"):
            scores = db.get_prediction_scores(prediction_id, score_type="faj")
            rows = [row_dict(row) for row in (scores or []) if row_dict(row)]
            if rows:
                rows.sort(key=lambda x: float(x.get("probability", 0) or 0), reverse=True)
                score = rows[0].get("score")
                if score:
                    return str(score)
    except Exception as exc:
        logger.debug("Ошибка чтения prediction_scores (faj): %s", exc)

    return "—"

# ============================================================
# FAJ CONFIDENCE FROM PREDICTION
# ============================================================

def faj_confidence_from_prediction(prediction: dict) -> float:
    """Возвращает FAJ Confidence."""
    if not prediction:
        return 0.0

    confidence = prediction.get("faj_confidence")
    if confidence is not None:
        return probability_value(confidence)

    return 0.0

# ============================================================
# FAJ DECISION FACTORS FROM PREDICTION
# ============================================================

def faj_decision_factors_from_prediction(prediction: dict) -> dict:
    """Возвращает Decision Factors."""
    if not prediction:
        return {}

    factors = prediction.get("decision_factors")
    if isinstance(factors, dict):
        return factors

    return {}

# ============================================================
# LEGACY: SCORE FROM PREDICTION (оставлен для совместимости)
# ============================================================

def score_from_prediction(db: FAJDatabase, prediction: dict) -> str:
    """
    Возвращает наиболее вероятный точный счёт (LEGACY).

    Используется для обратной совместимости.
    Рекомендуется использовать math_score_from_prediction().
    """
    return math_score_from_prediction(db, prediction)

# ============================================================
# RISK LEVEL
# ============================================================

def get_risk_level(prediction: dict) -> str:
    """
    Возвращает уровень риска прогноза FAJ.

    Приоритет:
        1. prediction["risk"]
        2. prediction["extended"]["risk"]
        3. расчёт по П1/X/П2

    Никогда не возвращает "—", если есть хотя бы базовые вероятности FAJ.
    """
    if not prediction:
        return "Высокий"

    # --------------------------------------------------------
    # 1. RISK В ОСНОВНОМ PREDICTION
    # --------------------------------------------------------
    risk = prediction.get("risk")
    if isinstance(risk, dict):
        risk = (
            risk.get("level")
            or risk.get("label")
            or risk.get("overall")
            or risk.get("value")
        )
    if risk:
        return str(risk)

    # --------------------------------------------------------
    # 2. RISK В EXTENDED
    # --------------------------------------------------------
    extended = prediction.get("extended", {})
    if isinstance(extended, dict):
        risk = extended.get("risk")
        if isinstance(risk, dict):
            risk = (
                risk.get("level")
                or risk.get("label")
                or risk.get("overall")
                or risk.get("value")
            )
        if risk:
            return str(risk)

    # --------------------------------------------------------
    # 3. ВЕРОЯТНОСТИ
    # --------------------------------------------------------
    probability = prediction.get("probability", {})
    if not isinstance(probability, dict):
        probability = {}

    home = probability_value(
        probability.get(
            "home",
            prediction.get("home_win")
        )
    )
    draw = probability_value(
        probability.get(
            "draw",
            prediction.get("draw")
        )
    )
    away = probability_value(
        probability.get(
            "away",
            prediction.get("away_win")
        )
    )

    probabilities = [home, draw, away]

    # --------------------------------------------------------
    # 4. ПРОВЕРКА ДАННЫХ
    # --------------------------------------------------------
    if max(probabilities) <= 0:
        return "Высокий"

    max_prob = max(probabilities)

    # --------------------------------------------------------
    # 5. РИСК ПО УВЕРЕННОСТИ И РАЗБРОСУ
    # --------------------------------------------------------
    sorted_probs = sorted(probabilities, reverse=True)
    first = sorted_probs[0]
    second = sorted_probs[1]
    margin = first - second

    if first >= 0.65 and margin >= 0.25:
        return "Низкий"

    if first >= 0.50 and margin >= 0.10:
        return "Средний"

    return "Высокий"

# ============================================================
# SCOUT / ADDITIONAL STATISTICS
# ============================================================

def get_scout_context(
    db: FAJDatabase,
    match: dict,
) -> dict:
    """
    Ручное получение дополнительной статистики из внешнего API.

    ВАЖНО:
        - не меняет prediction
        - не меняет passport
        - не меняет rating
        - не пишет в SQLite
        - не участвует автоматически в PredictionManager
        - только READ-ONLY
    """
    try:
        mapping = get_team_mapping_service()
    except Exception as exc:
        logger.exception("Cannot initialize TeamMappingService")
        return {
            "status": "error",
            "message": f"Ошибка инициализации маппинга: {exc}",
        }

    home_name = team_name(db, match.get("home_team_id"))
    away_name = team_name(db, match.get("away_team_id"))

    if not home_name or not away_name:
        return {
            "status": "error",
            "message": "Не удалось определить названия команд",
        }

    # Определяем лигу для поиска
    league = match.get("competition") or match.get("league") or "РПЛ"

    try:
        home_api_id = mapping.get_api_id(home_name, league=league)
        away_api_id = mapping.get_api_id(away_name, league=league)

        if not home_api_id:
            return {
                "status": "error",
                "message": f"API ID не найден для: {home_name}",
            }

        if not away_api_id:
            return {
                "status": "error",
                "message": f"API ID не найден для: {away_name}",
            }

        # Получаем контекст через MatchContextService
        context_service = get_match_context_service()
        context = context_service.get_match_context(
            home_team_id=home_api_id,
            away_team_id=away_api_id,
            h2h_last=10,
            form_last=5,
        )

        return {
            "status": "success",
            "home_name": home_name,
            "away_name": away_name,
            "home_api_id": home_api_id,
            "away_api_id": away_api_id,
            "context": context,
            "summary": context_service.build_director_summary(context),
        }

    except MatchContextError as exc:
        logger.warning("MatchContextError: %s", exc)
        return {
            "status": "error",
            "message": str(exc),
        }

    except Exception as exc:
        logger.exception("Unexpected error in get_scout_context")
        return {
            "status": "error",
            "message": f"Ошибка получения статистики: {exc}",
        }

def render_scout_block(scout_result: dict):
    """Отображает Scout-статистику в карточке матча."""
    if not scout_result:
        return

    if scout_result.get("status") == "error":
        st.warning(f"⚠️ {scout_result.get('message', 'Ошибка API')}")
        return

    summary = scout_result.get("summary", {})
    if not summary:
        st.info("Статистика недоступна")
        return

    h2h = summary.get("h2h", {})
    home_form = summary.get("home_form", {})
    home_at_home = summary.get("home_at_home", {})
    away_form = summary.get("away_form", {})
    away_away = summary.get("away_away", {})

    # Строки формы
    home_form_str = MatchContextService.form_string(home_form)
    away_form_str = MatchContextService.form_string(away_form)

    st.markdown("### 📊 Дополнительная статистика (Scout)")
    st.caption(
        "Данные получены вручную из внешнего API. "
        "Они не изменяют прогноз FAJ, рейтинг или паспорт."
    )

    # H2H
    if h2h.get("matches", 0) > 0:
        st.markdown("**История личных встреч**")
        h2h_col1, h2h_col2, h2h_col3, h2h_col4 = st.columns(4)
        with h2h_col1:
            st.metric("Матчей", h2h.get("matches", 0))
        with h2h_col2:
            st.metric("Победы хозяев", h2h.get("home_wins", 0))
        with h2h_col3:
            st.metric("Ничьи", h2h.get("draws", 0))
        with h2h_col4:
            st.metric("Победы гостей", h2h.get("away_wins", 0))

        c1, c2 = st.columns(2)
        with c1:
            st.metric(
                "Голы хозяев (в среднем)",
                f"{h2h.get('home_goals_avg', 0):.2f}",
            )
        with c2:
            st.metric(
                "Голы гостей (в среднем)",
                f"{h2h.get('away_goals_avg', 0):.2f}",
            )

    # Форма команд
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**{scout_result.get('home_name', 'Хозяева')}**")
        st.metric("Последние 5 матчей", home_form_str)
        if home_at_home.get("matches", 0) > 0:
            st.metric(
                "Дома (последние 5)",
                f"{home_at_home.get('wins', 0)}W "
                f"{home_at_home.get('draws', 0)}D "
                f"{home_at_home.get('losses', 0)}L",
                f"Голы: {home_at_home.get('goals_for', 0)}–"
                f"{home_at_home.get('goals_against', 0)}",
            )

    with col2:
        st.markdown(f"**{scout_result.get('away_name', 'Гости')}**")
        st.metric("Последние 5 матчей", away_form_str)
        if away_away.get("matches", 0) > 0:
            st.metric(
                "В гостях (последние 5)",
                f"{away_away.get('wins', 0)}W "
                f"{away_away.get('draws', 0)}D "
                f"{away_away.get('losses', 0)}L",
                f"Голы: {away_away.get('goals_for', 0)}–"
                f"{away_away.get('goals_against', 0)}",
            )

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

# ============================================================
# RENDER FAJ FINAL SCORE BLOCK
# ============================================================

def render_faj_final_score_block(
    db: FAJDatabase,
    prediction: dict,
):
    """
    Отображает блок с Math Most Likely Score и FAJ Final Score.
    """
    if not prediction:
        return

    # Получаем оба счёта
    math_score = math_score_from_prediction(db, prediction)
    math_prob = math_probability_from_prediction(prediction)
    faj_score = faj_score_from_prediction(db, prediction)  # ← ИСПРАВЛЕНО
    faj_conf = faj_confidence_from_prediction(prediction)
    decision_factors = faj_decision_factors_from_prediction(prediction)

    st.markdown("### 🎯 Прогноз точного счёта")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📐 Math Most Likely Score")
        st.markdown(
            f"<h2 style='text-align: center;'>"
            f"{math_score}"
            f"</h2>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Вероятность: {format_probability(math_prob)}"
        )
        st.caption(
            "Математически наиболее вероятный счёт "
            "по распределению Poisson/Monte Carlo"
        )

    with col2:
        st.markdown("#### 🧠 FAJ Final Score")
        st.markdown(
            f"<h2 style='text-align: center; color: #FF6B00;'>"
            f"{faj_score}"
            f"</h2>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Уверенность FAJ: {format_probability(faj_conf)}"
        )
        st.caption(
            "Решение FAJ с учётом рейтинга, паспорта, "
            "формы и домашнего преимущества"
        )

    # ============================================================
    # DECISION FACTORS (разворачиваемый блок)
    # ============================================================

    if decision_factors:
        with st.expander("📋 Основания FAJ"):
            # Rating
            rating = decision_factors.get("rating", {})
            if rating:
                st.write("**Рейтинг:**")
                st.write(f"  Хозяева: {rating.get('home', '—')}")
                st.write(f"  Гости: {rating.get('away', '—')}")
                st.write(f"  Разница: {rating.get('delta', '—')}")

            # Passport
            passport = decision_factors.get("passport", {})
            if passport:
                st.write("**Паспорт:**")
                st.write(f"  Атака хозяев: {passport.get('home_attack', '—')}")
                st.write(f"  Защита гостей: {passport.get('away_defense', '—')}")
                st.write(f"  Атака гостей: {passport.get('away_attack', '—')}")
                st.write(f"  Защита хозяев: {passport.get('home_defense', '—')}")

            # Last Match
            last_match = decision_factors.get("last_match", {})
            if last_match:
                st.write("**Последний матч:**")
                st.write(f"  Хозяева: {last_match.get('home_result', '—')}")
                st.write(f"  Гости: {last_match.get('away_result', '—')}")

            # Form
            form = decision_factors.get("form", {})
            if form:
                st.write("**Форма (последние 5 матчей):**")
                st.write(f"  Хозяева: {form.get('home_points', '—')} очков")
                st.write(f"  Гости: {form.get('away_points', '—')} очков")

            # Home Advantage
            home_adv = decision_factors.get("home_advantage", {})
            if home_adv:
                st.write("**Домашнее преимущество:**")
                st.write(f"  Коэффициент: {home_adv.get('configured_value', '—')}")

            # History
            history = decision_factors.get("history", {})
            if history:
                st.write("**История:**")
                st.write(f"  Матчей: {history.get('count', 0)}")
                st.write(f"  Вес: {history.get('weight', 0):.2f}")

            # Selected Candidate
            selected = decision_factors.get("selected_candidate", {})
            if selected:
                st.write("**Выбранный кандидат:**")
                st.write(f"  Счёт: {selected.get('score', '—')}")
                st.write(f"  Math вероятность: {format_probability(selected.get('math_probability', 0))}")
                st.write(f"  FAJ вероятность: {format_probability(selected.get('faj_probability', 0))}")

    # ============================================================
    # FAJ SCORE RANKING
    # ============================================================

    faj_ranking = prediction.get("faj_score_ranking", [])
    if faj_ranking:
        with st.expander("🏆 FAJ Score Ranking (Топ-5)"):
            table_data = []
            for item in faj_ranking[:5]:
                table_data.append({
                    "Ранг": item.get("rank", "—"),
                    "Счёт": item.get("score", "—"),
                    "Math Prob": format_probability(item.get("math_probability", 0)),
                    "FAJ Score": f"{item.get('faj_score', 0):.4f}",
                })
            if table_data:
                st.table(table_data)

# ============================================================
# RENDER PREDICTION CARD
# ============================================================

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
    # FAJ Final Score Block
    # --------------------------------------------------------

    render_faj_final_score_block(db, prediction)

    # --------------------------------------------------------
    # TOP-5 MATH (для обратной совместимости)
    # --------------------------------------------------------

    st.markdown("### 🏆 Топ-5 математических счетов")

    prediction_id = prediction.get("prediction_id") or prediction.get("id")

    top_scores = get_top_scores(db, prediction_id, score_type="math")

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

    risk = get_risk_level(prediction)

    # FAJ Confidence
    faj_conf = faj_confidence_from_prediction(prediction)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Уверенность (Math)",
            f"{confidence:.0f}%",
        )

    with c2:
        st.metric(
            "Уверенность (FAJ)",
            format_probability(faj_conf),
        )

    with c3:
        st.metric(
            "Риск",
            risk,
        )

    # --------------------------------------------------------
    # MODEL INFO
    # --------------------------------------------------------

    model_version = (
        prediction.get("model_version")
        or prediction.get("version")
        or "FAJ"
    )

    engine_version = prediction.get("engine_version", "—")

    st.caption(
        f"Модель: {model_version}"
        + (f" • Engine: {engine_version}" if engine_version else "")
        + (f" • prediction_id: {prediction_id}" if prediction_id else "")
    )

    # ============================================================
    # SCOUT / ADDITIONAL STATISTICS
    # ============================================================

    st.markdown("### 🔎 Дополнительная статистика")

    scout_key = f"scout_stats_{match_id}"

    if scout_key not in st.session_state:
        st.session_state[scout_key] = None

    col_scout1, col_scout2 = st.columns([3, 1])

    with col_scout1:
        st.caption(
            "Получить дополнительную статистику из внешнего API: "
            "H2H, последние матчи, домашняя/выездная форма."
        )

    with col_scout2:
        if st.button(
            "📊 Получить статистику",
            key=f"scout_button_{match_id}",
            use_container_width=True,
        ):
            with st.spinner("Получение внешней статистики..."):
                scout_result = get_scout_context(db, match)
                st.session_state[scout_key] = scout_result

    scout_result = st.session_state.get(scout_key)

    if scout_result:
        render_scout_block(scout_result)

    # ============================================================
    # EXPERT — С СОХРАНЕНИЕМ В БД
    # ============================================================

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
    predictions_data = {}

    for match in matches:
        match_id = match.get("id")
        prediction = get_latest_prediction(db, match_id)

        if prediction:
            existing_predictions += 1
            predictions_data[match_id] = prediction
        else:
            predictions_data[match_id] = None

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
    # 6. КНОПКА: РАССЧИТАТЬ ПРОГНОЗЫ FAJ (ОСНОВНАЯ)
    # ========================================================

    st.divider()

    col_calc1, col_calc2, col_calc3 = st.columns([1, 2, 1])

    with col_calc2:
        if existing_predictions == len(matches):
            st.success("✅ Все прогнозы FAJ уже рассчитаны")
        else:
            if st.button(
                "🔮 РАССЧИТАТЬ ПРОГНОЗЫ FAJ",
                type="primary",
                use_container_width=True,
            ):
                progress = st.progress(0)
                status_box = st.empty()

                saved_count = 0
                failed_count = 0

                for index, match in enumerate(matches):
                    match_id = match.get("id")
                    home = team_name(db, match.get("home_team_id"))
                    away = team_name(db, match.get("away_team_id"))

                    # Пропускаем уже сохранённые
                    if predictions_data.get(match_id):
                        saved_count += 1
                        progress.progress((index + 1) / len(matches))
                        continue

                    status_box.info(
                        f"Расчёт {index + 1}/{len(matches)}: "
                        f"{home} — {away}"
                    )

                    try:
                        result = pred_mgr.predict_by_match_id(
                            int(match["id"])
                        )

                        if result.get("status") != "error":
                            saved_count += 1
                            # Обновляем данные для карточки
                            predictions_data[match_id] = result
                        else:
                            failed_count += 1
                            logger.error(
                                f"Ошибка прогноза для матча {match_id}: "
                                f"{result.get('message', 'Неизвестная ошибка')}"
                            )

                    except Exception as exc:
                        failed_count += 1
                        logger.error(
                            f"Ошибка прогноза для матча {match_id}: {exc}"
                        )

                    progress.progress((index + 1) / len(matches))

                status_box.empty()

                if failed_count == 0:
                    st.success(
                        f"✅ FAJ рассчитал прогнозы для всех {saved_count} матчей."
                    )
                    st.rerun()
                else:
                    st.warning(
                        f"⚠️ Рассчитано: {saved_count}. "
                        f"Ошибок: {failed_count}."
                    )

    # ========================================================
    # 7. КНОПКА: ПЕРЕСЧИТАТЬ ВСЕ ПРОГНОЗЫ (ПРИНУДИТЕЛЬНЫЙ)
    # ========================================================

    st.divider()

    col_force1, col_force2, col_force3 = st.columns([1, 2, 1])

    with col_force2:
        if st.button(
            "🔄 ПЕРЕСЧИТАТЬ ВСЕ ПРОГНОЗЫ",
            type="secondary",
            use_container_width=True,
        ):
            st.warning(
                "⚠️ Будут пересчитаны ВСЕ матчи тура. "
                "Старые прогнозы останутся в истории, "
                "но текущие будут заменены новыми."
            )

            progress = st.progress(0)
            status_box = st.empty()

            saved_count = 0
            failed_count = 0

            for index, match in enumerate(matches):
                match_id = match.get("id")
                home = team_name(db, match.get("home_team_id"))
                away = team_name(db, match.get("away_team_id"))

                status_box.info(
                    f"Пересчёт {index + 1}/{len(matches)}: "
                    f"{home} — {away}"
                )

                try:
                    # Принудительно пересчитываем
                    result = pred_mgr.predict_by_match_id(
                        int(match["id"])
                    )

                    if result.get("status") != "error":
                        saved_count += 1
                        predictions_data[match_id] = result
                    else:
                        failed_count += 1
                        logger.error(
                            f"Ошибка пересчёта матча {match_id}: "
                            f"{result.get('message', 'Неизвестная ошибка')}"
                        )

                except Exception as exc:
                    failed_count += 1
                    logger.error(
                        f"Ошибка пересчёта матча {match_id}: {exc}"
                    )

                progress.progress((index + 1) / len(matches))

            status_box.empty()

            if failed_count == 0:
                st.success(
                    f"✅ Все {saved_count} прогнозов пересчитаны и сохранены."
                )
                st.rerun()
            else:
                st.warning(
                    f"⚠️ Пересчитано: {saved_count}. "
                    f"Ошибок: {failed_count}."
                )

    # ========================================================
    # 8. CARDS
    # ========================================================

    st.divider()

    st.subheader("📊 Карточки прогнозов")

    for match in matches:
        match_id = match.get("id")
        prediction = predictions_data.get(match_id)

        render_prediction_card(
            db=db,
            match=match,
            prediction=prediction,
        )

    # ========================================================
    # 9. SAVE DATABASE TO GITHUB
    # ========================================================

    st.divider()
    st.subheader("💾 Сохранение прогнозов")
    st.caption(
        "После расчёта всех прогнозов FAJ и ввода прогнозов Директора "
        "сохраните текущую базу в GitHub."
    )

    if st.button(
        "💾 СОХРАНИТЬ ПРОГНОЗЫ ТУРА В GITHUB",
        type="primary",
        use_container_width=True,
    ):
        try:
            from app.github_db_sync import save_database_to_github
            result = save_database_to_github()
            st.success(
                f"✅ Прогнозы тура сохранены в GitHub. "
                f"Размер базы: {result.get('size', 0):,} байт."
            )
            logger.info(
                "PREDICTION ROUND SAVED TO GITHUB | %s",
                result,
            )
        except Exception as exc:
            logger.exception(
                "Ошибка сохранения прогнозов тура в GitHub"
            )
            st.error(
                f"❌ Ошибка сохранения базы в GitHub: {exc}"
            )

    # ========================================================
    # 10. BACK
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

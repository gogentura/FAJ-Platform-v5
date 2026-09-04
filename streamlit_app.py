#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PREDICTOR — Streamlit Interface
====================================

Чистый интерфейс для FAJ Personal Prediction Brain.

Функции:
    - Выбор турнира (из FAJ Club Ratings)
    - Выбор команд
    - Ввод URL-адресов Soccer365 (до 6 на команду)
    - Сбор статистики
    - Генерация прогноза
    - Отображение карточки прогноза

Архитектура:
    UI (Streamlit)
        ↓
    faj_predictor.py
        ↓
    FAJBrain (form_model + form_win + defence + goal_model + corners + cards)
        ↓
    Прогноз
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from app.database import FAJDatabase
from app.parsers.soccer365_parser import Soccer365Parser
from app.core.faj_brain import FAJBrain
from app.faj_club_ratings import (
    get_all_tournaments,
    get_all_teams,
    get_team_rating,
)
from app.core.form_context import build_form_context


# ============================================================
# CONFIG
# ============================================================

PAGE_TITLE = "FAJ — Персональный прогноз"
PAGE_ICON = "⚽"
LAYOUT = "wide"

MAX_HISTORY_MATCHES = 6
MAX_ANALYSIS_MATCHES = 6

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE / PARSER
# ============================================================

@st.cache_resource
def get_database() -> FAJDatabase:
    return FAJDatabase()


@st.cache_resource
def get_soccer365_parser() -> Soccer365Parser:
    return Soccer365Parser()


@st.cache_resource
def get_faj_brain() -> FAJBrain:
    return FAJBrain()


# ============================================================
# HELPERS
# ============================================================

def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("ё", "е")


def pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def num(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def parse_score(score: Any) -> tuple[Optional[int], Optional[int]]:
    if not score:
        return None, None
    text = str(score).strip().replace("–", "-").replace(":", "-")
    parts = text.split("-")
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return None, None


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# SESSION STATE
# ============================================================

def init_state() -> None:
    defaults = {
        "faj_competition": None,
        "faj_matches": [],
        "faj_collected": {},
        "faj_predictions": {},
        "faj_form_context": {},
        "faj_session_id": None,
        "faj_selected_match": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_workspace() -> None:
    st.session_state.faj_competition = None
    st.session_state.faj_matches = []
    st.session_state.faj_collected = {}
    st.session_state.faj_predictions = {}
    st.session_state.faj_form_context = {}
    st.session_state.faj_session_id = None
    st.session_state.faj_selected_match = None


def create_match_slot() -> Dict[str, Any]:
    return {
        "home_name": None,
        "away_name": None,
        "match_date": date.today().isoformat(),
        "urls_home": [""] * MAX_HISTORY_MATCHES,
        "urls_away": [""] * MAX_HISTORY_MATCHES,
    }


def add_match() -> None:
    if len(st.session_state.faj_matches) >= MAX_ANALYSIS_MATCHES:
        st.warning(f"Можно добавить максимум {MAX_ANALYSIS_MATCHES} матчей.")
        return
    st.session_state.faj_matches.append(create_match_slot())


def remove_match(index: int) -> None:
    if 0 <= index < len(st.session_state.faj_matches):
        st.session_state.faj_matches.pop(index)
        st.session_state.faj_collected.pop(index, None)
        st.session_state.faj_predictions.pop(index, None)
        st.session_state.faj_form_context.pop(index, None)


# ============================================================
# TEAM MANAGEMENT
# ============================================================

def load_teams(league: Optional[str] = None) -> List[str]:
    try:
        teams = get_all_teams(league)
        return list(teams) if teams else []
    except Exception:
        logger.exception("Ошибка загрузки команд")
        return []


def get_or_create_team(db: FAJDatabase, team_name: str, league: str) -> Optional[int]:
    try:
        teams = db.get_teams(league=league)
        for team in teams:
            if team.get("name") == team_name:
                return team.get("id")
        
        with db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO teams (name, league)
                VALUES (?, ?)
                ON CONFLICT(name, league) DO UPDATE SET active = 1
                RETURNING id
            """, (team_name, league))
            row = cursor.fetchone()
            return row["id"] if row else None
    except Exception as exc:
        logger.exception("Ошибка получения/создания команды: %s", exc)
        return None


# ============================================================
# PARSING
# ============================================================

def parse_soccer365(url: str) -> Dict[str, Any]:
    parser = get_soccer365_parser()
    return parser.parse(url.strip())


def build_history_record(parsed: Dict[str, Any]) -> Dict[str, Any]:
    stats = parsed.get("stats", {})
    home_goals, away_goals = parse_score(parsed.get("score"))
    
    return {
        "home_team": parsed.get("home_team"),
        "away_team": parsed.get("away_team"),
        "match_date": parsed.get("match_date"),
        "score": parsed.get("score"),
        "home_goals": home_goals,
        "away_goals": away_goals,
        "xg": {"home": stats.get("home_xg"), "away": stats.get("away_xg")},
        "shots": {"home": stats.get("home_shots"), "away": stats.get("away_shots")},
        "shots_on_target": {"home": stats.get("home_shots_on_target"), "away": stats.get("away_shots_on_target")},
        "possession": {"home": stats.get("home_possession"), "away": stats.get("away_possession")},
        "home_corners": stats.get("home_corners"),
        "away_corners": stats.get("away_corners"),
        "home_yellow_cards": stats.get("home_yellow_cards"),
        "away_yellow_cards": stats.get("away_yellow_cards"),
        "source_url": parsed.get("source_url"),
        "quality": parsed.get("quality", 0.0),
        "source": "Soccer365",
    }


def validate_parsed_match(parsed: Dict[str, Any], selected_team: str) -> tuple[bool, str]:
    home = parsed.get("home_team")
    away = parsed.get("away_team")
    if not home or not away:
        return False, "Не удалось определить команды."
    target = normalize_name(selected_team)
    if target != normalize_name(home) and target != normalize_name(away):
        return False, f"Матч {home} — {away} не содержит {selected_team}."
    return True, f"{home} — {away}"


def _parse_date(value: Any):
    """Упрощённый парсер даты."""
    if value is None:
        return None
    import re
    text = str(value).strip()
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    return None


def collect_team_history(
    team_name: str,
    urls: List[str],
    forecast_date: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    clean_urls = [url.strip() for url in urls if url and url.strip()]
    clean_urls = list(dict.fromkeys(clean_urls))
    
    records: List[Dict[str, Any]] = []
    errors: List[str] = []
    
    forecast_date_obj = _parse_date(forecast_date) if forecast_date else None
    if forecast_date and not forecast_date_obj:
        errors.append(f"Некорректная дата прогноза: {forecast_date}")
        return records, errors
    
    for position, url in enumerate(clean_urls, start=1):
        try:
            parsed = parse_soccer365(url)
        except Exception as exc:
            errors.append(f"{position}. {exc}")
            continue
        
        if parsed.get("error"):
            errors.append(f"{position}. {parsed.get('error')}")
            continue
        
        valid, message = validate_parsed_match(parsed, team_name)
        if not valid:
            errors.append(f"{position}. {message}")
            continue
        
        record = build_history_record(parsed)
        match_date = record.get("match_date")
        if not match_date:
            errors.append(f"{position}. Не удалось определить дату матча.")
            continue
        
        match_date_obj = _parse_date(match_date)
        if not match_date_obj:
            errors.append(f"{position}. Некорректная дата матча: {match_date}")
            continue
        
        if forecast_date_obj and match_date_obj >= forecast_date_obj:
            errors.append(f"{position}. Матч от {match_date} не является прошлым относительно {forecast_date}.")
            continue
        
        records.append(record)
    
    return records[:MAX_HISTORY_MATCHES], errors


# ============================================================
# UI — PREDICTION CARD
# ============================================================

def render_prediction_card(prediction: Dict[str, Any]) -> None:
    home = prediction.get("home_team", "Хозяева")
    away = prediction.get("away_team", "Гости")
    
    st.markdown("---")
    st.markdown(f"## ⚽ {home} — {away}")
    
    # 1. MAIN OUTCOME
    st.subheader("1. Главный исход")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(f"🏠 {home}", pct(prediction.get("home_win_probability")))
    with c2:
        st.metric("🤝 Ничья", pct(prediction.get("draw_probability")))
    with c3:
        st.metric(f"✈️ {away}", pct(prediction.get("away_win_probability")))
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Уверенность FAJ", pct(prediction.get("confidence")))
    with c2:
        st.metric("Риск", prediction.get("risk", "—"))
    
    # 2. GOALS
    st.subheader("2. Голы")
    btts = prediction.get("btts_probability")
    over25 = prediction.get("over25_probability")
    over35 = prediction.get("over35_probability")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Обе забьют", "ДА" if btts is not None and btts >= 0.5 else "НЕТ")
        st.caption(f"Вероятность: {pct(btts)}")
    with c2:
        st.metric("ТБ 2.5", "ДА" if over25 is not None and over25 >= 0.5 else "НЕТ")
        st.caption(f"Вероятность: {pct(over25)}")
    with c3:
        st.metric("ТБ 3.5", "ДА" if over35 is not None and over35 >= 0.5 else "НЕТ")
        st.caption(f"Вероятность: {pct(over35)}")
    
    # 3. SCORES
    st.subheader("3. Наиболее вероятные точные счета")
    scores = prediction.get("scores", [])
    cols = st.columns(max(1, len(scores)))
    for idx, item in enumerate(scores):
        with cols[idx]:
            st.markdown(f"### {item.get('score', '—')}")
    
    # 4. CORNERS
    st.subheader("4. Угловые")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Всего", num(prediction.get("corners_expected")))
    with c2:
        st.metric(home, num(prediction.get("home_corners_expected")))
    with c3:
        st.metric(away, num(prediction.get("away_corners_expected")))
    
    st.write(f"**Диапазон:** {prediction.get('corners_range', '—')}")
    
    corner_lines = prediction.get("corners_lines", {})
    cols = st.columns(4)
    for col, line in zip(cols, ["7.5", "8.5", "9.5", "10.5"]):
        with col:
            st.metric(f"ТБ {line}", pct(corner_lines.get(line)))
    
    # 5. CARDS
    st.subheader("5. Карточки")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Всего", num(prediction.get("cards_expected")))
    with c2:
        st.metric(home, num(prediction.get("home_cards_expected")))
    with c3:
        st.metric(away, num(prediction.get("away_cards_expected")))
    
    st.write(f"**Диапазон:** {prediction.get('cards_range', '—')}")
    
    card_lines = prediction.get("cards_lines", {})
    cols = st.columns(3)
    for col, line in zip(cols, ["2.5", "3.5", "4.5"]):
        with col:
            st.metric(f"ТБ {line}", pct(card_lines.get(line)))
    
    # 6. ANALYSIS
    st.subheader("6. Аналитический вывод FAJ")
    st.info(prediction.get("analysis", "Аналитический вывод пока недоступен."))


# ============================================================
# UI — MATCH SETUP
# ============================================================

def render_match_setup(index: int, match: Dict[str, Any], team_names: List[str]) -> None:
    st.markdown(f"### Матч {index + 1}")
    
    home_current = match.get("home_name") or (team_names[0] if team_names else "")
    if home_current not in team_names:
        home_current = team_names[0] if team_names else ""
    
    away_options = [name for name in team_names if name != home_current]
    away_current = match.get("away_name") or (away_options[0] if away_options else "")
    if away_current not in away_options and away_options:
        away_current = away_options[0]
    
    c1, c2 = st.columns(2)
    with c1:
        selected_home = st.selectbox("🏠 Хозяева", team_names, index=team_names.index(home_current) if home_current in team_names else 0, key=f"home_{index}")
    with c2:
        available_away = [name for name in team_names if name != selected_home]
        if not available_away:
            st.warning("Нужно минимум две команды.")
            return
        selected_away = st.selectbox("✈️ Гости", available_away, index=available_away.index(away_current) if away_current in available_away else 0, key=f"away_{index}")
    
    match["home_name"] = selected_home
    match["away_name"] = selected_away
    
    # Date
    current_date = match.get("match_date")
    try:
        default_date = date.fromisoformat(current_date) if current_date else date.today()
    except (TypeError, ValueError):
        default_date = date.today()
    forecast_date = st.date_input("📅 Дата матча", value=default_date, key=f"date_{index}")
    match["match_date"] = forecast_date.isoformat()
    
    # URLs
    st.markdown("#### 🔗 Ссылки на Soccer365")
    
    col_home, col_away = st.columns(2)
    with col_home:
        st.markdown(f"**🏠 {selected_home}**")
        for i in range(MAX_HISTORY_MATCHES):
            match["urls_home"][i] = st.text_input(
                f"Матч {i+1}",
                value=match["urls_home"][i],
                key=f"home_url_{index}_{i}",
                placeholder="https://soccer365.ru/..."
            )
    
    with col_away:
        st.markdown(f"**✈️ {selected_away}**")
        for i in range(MAX_HISTORY_MATCHES):
            match["urls_away"][i] = st.text_input(
                f"Матч {i+1}",
                value=match["urls_away"][i],
                key=f"away_url_{index}_{i}",
                placeholder="https://soccer365.ru/..."
            )
    
    # Buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 Собрать статистику", key=f"collect_{index}", use_container_width=True):
            collect_and_store_match(index, match)
    with c2:
        if st.button("🧠 Получить прогноз", key=f"predict_{index}", use_container_width=True):
            generate_prediction(index, match)
    
    # Status
    collected = st.session_state.faj_collected.get(index)
    if collected:
        st.success(f"✅ Собрано: {len(collected.get('home_records', []))} матчей")
        
        # Show data summary
        home_records = collected.get("home_records", [])
        away_records = collected.get("away_records", [])
        
        c1, c2 = st.columns(2)
        with c1:
            render_data_summary(selected_home, home_records)
        with c2:
            render_data_summary(selected_away, away_records)
        
        if collected.get("errors"):
            with st.expander("⚠️ Сообщения сбора"):
                for error in collected["errors"]:
                    st.warning(error)
    
    # Form Context
    form_data = st.session_state.faj_form_context.get(index)
    if form_data:
        render_form_context_card(selected_home, selected_away, form_data.get("home"), form_data.get("away"))
    
    # Prediction
    prediction = st.session_state.faj_predictions.get(index)
    if prediction:
        render_prediction_card(prediction)
    
    # Remove button
    if len(st.session_state.faj_matches) > 1:
        if st.button("🗑 Удалить матч", key=f"remove_{index}"):
            remove_match(index)
            st.rerun()


def render_data_summary(team_name: str, records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    
    goals_for = []
    goals_against = []
    corners = []
    cards = []
    
    for record in records:
        # Определяем сторону команды
        if record.get("home_team") == team_name:
            gf = record.get("home_goals")
            ga = record.get("away_goals")
            corner = record.get("home_corners")
            card = record.get("home_yellow_cards")
        else:
            gf = record.get("away_goals")
            ga = record.get("home_goals")
            corner = record.get("away_corners")
            card = record.get("away_yellow_cards")
        
        if gf is not None:
            goals_for.append(gf)
        if ga is not None:
            goals_against.append(ga)
        if corner is not None:
            corners.append(corner)
        if card is not None:
            cards.append(card)
    
    def avg(vals):
        return sum(vals) / len(vals) if vals else None
    
    st.markdown(f"**{team_name}**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Матчей", len(records))
    with c2:
        st.metric("Голы за матч", num(avg(goals_for)))
    with c3:
        st.metric("Угловые", num(avg(corners)) if corners else "—")
    with c4:
        st.metric("Карточки", num(avg(cards)) if cards else "—")
    
    # Quality
    quality = sum(r.get("quality", 0) for r in records) / len(records) if records else 0
    st.caption(f"Качество данных: {quality * 100:.0f}%")


def render_form_context_card(
    home_team: str,
    away_team: str,
    home_context: Optional[Dict[str, Any]],
    away_context: Optional[Dict[str, Any]],
) -> None:
    home_context = home_context or {}
    away_context = away_context or {}
    
    st.markdown("### 📊 Форма перед матчем")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(f"**🏠 {home_team}**")
        form = home_context.get("form", [])
        if form:
            st.markdown(f"**Форма:** {'-'.join(str(x) for x in form[:6])}")
        
        xg = home_context.get("xg_avg")
        xga = home_context.get("xga_avg")
        st.metric("xG", num(xg))
        st.metric("xGA", num(xga))
    
    with c2:
        st.markdown(f"**✈️ {away_team}**")
        form = away_context.get("form", [])
        if form:
            st.markdown(f"**Форма:** {'-'.join(str(x) for x in form[:6])}")
        
        xg = away_context.get("xg_avg")
        xga = away_context.get("xga_avg")
        st.metric("xG", num(xg))
        st.metric("xGA", num(xga))


def _percent_to_fraction(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value) / 100.0
    except (TypeError, ValueError):
        return None


def _get_corners_range(expected: Optional[float]) -> str:
    if expected is None:
        return "—"
    if expected < 8:
        return "7–9"
    if expected < 10:
        return "8–10"
    if expected < 12:
        return "9–11"
    return "10–12+"


def _get_cards_range(expected: Optional[float]) -> str:
    if expected is None:
        return "—"
    if expected < 3:
        return "2–3"
    if expected < 4:
        return "3–4"
    if expected < 5:
        return "4–5"
    return "5+"


def build_prediction(
    home_team: str,
    away_team: str,
    history_home: List[Dict[str, Any]],
    history_away: List[Dict[str, Any]],
    home_form_context: Optional[Dict[str, Any]] = None,
    away_form_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    brain = get_faj_brain()
    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=history_home,
        away_matches=history_away,
        home_form_context=home_form_context,
        away_form_context=away_form_context,
    )
    
    return {
        "model_version": result.get("calculation_meta", {}).get("brain_version", "FAJ-BRAIN"),
        "home_team": result.get("home_team", home_team),
        "away_team": result.get("away_team", away_team),
        "home_win_probability": _percent_to_fraction(result.get("home_win_probability")),
        "draw_probability": _percent_to_fraction(result.get("draw_probability")),
        "away_win_probability": _percent_to_fraction(result.get("away_win_probability")),
        "confidence": _percent_to_fraction(result.get("confidence")),
        "risk": result.get("risk", "—"),
        "btts": result.get("btts"),
        "btts_probability": _percent_to_fraction(result.get("btts_probability")),
        "over25": result.get("over25"),
        "over25_probability": _percent_to_fraction(result.get("over25_probability")),
        "over35": result.get("over35"),
        "over35_probability": _percent_to_fraction(result.get("over35_probability")),
        "home_xg_internal": result.get("home_xg"),
        "away_xg_internal": result.get("away_xg"),
        "scores": [
            {"score": result.get("most_likely_score", "—")},
            {"score": result.get("second_likely_score", "—")},
            {"score": result.get("third_likely_score", "—")},
        ],
        "corners_expected": result.get("corners_expected"),
        "home_corners_expected": result.get("home_corners_expected"),
        "away_corners_expected": result.get("away_corners_expected"),
        "corners_lines": {
            "7.5": _percent_to_fraction(result.get("over75_corners_probability")),
            "8.5": _percent_to_fraction(result.get("over85_corners_probability")),
            "9.5": _percent_to_fraction(result.get("over95_corners_probability")),
            "10.5": _percent_to_fraction(result.get("over105_corners_probability")),
        },
        "corners_range": _get_corners_range(result.get("corners_expected")),
        "cards_expected": result.get("cards_expected"),
        "home_cards_expected": result.get("home_cards_expected"),
        "away_cards_expected": result.get("away_cards_expected"),
        "cards_lines": {
            "2.5": _percent_to_fraction(result.get("over25_cards_probability")),
            "3.5": _percent_to_fraction(result.get("over35_cards_probability")),
            "4.5": _percent_to_fraction(result.get("over45_cards_probability")),
        },
        "cards_range": _get_cards_range(result.get("cards_expected")),
        "analysis": result.get("conclusion", "Аналитический вывод пока недоступен."),
        "home_form_context": home_form_context,
        "away_form_context": away_form_context,
        "brain_result": result,
    }


# ============================================================
# COLLECTION + PREDICTION
# ============================================================

def collect_and_store_match(index: int, match: Dict[str, Any]) -> None:
    home_name = match.get("home_name")
    away_name = match.get("away_name")
    tournament = st.session_state.faj_competition
    forecast_date = match.get("match_date")
    
    if not home_name or not away_name:
        st.error("Сначала выберите обе команды.")
        return
    if not tournament:
        st.error("Не выбран турнир.")
        return
    
    db = get_database()
    
    home_id = get_or_create_team(db, home_name, tournament)
    away_id = get_or_create_team(db, away_name, tournament)
    if home_id is None or away_id is None:
        st.error("Не удалось загрузить команды.")
        return
    
    all_errors = []
    
    with st.status("Собираю данные Soccer365...", expanded=True):
        st.write(f"🏠 {home_name}")
        home_records, home_errors = collect_team_history(
            home_name, match.get("urls_home", []), forecast_date
        )
        all_errors.extend([f"{home_name}: {e}" for e in home_errors])
        st.write(f"Получено матчей: {len(home_records)}")
        
        st.write(f"✈️ {away_name}")
        away_records, away_errors = collect_team_history(
            away_name, match.get("urls_away", []), forecast_date
        )
        all_errors.extend([f"{away_name}: {e}" for e in away_errors])
        st.write(f"Получено матчей: {len(away_records)}")
    
    st.session_state.faj_collected[index] = {
        "home_records": home_records,
        "away_records": away_records,
        "errors": all_errors,
    }
    
    # Build FormContext
    if home_records and away_records:
        home_form_context = build_form_context(
            team_name=home_name,
            records=home_records,
            limit=MAX_HISTORY_MATCHES,
        )
        away_form_context = build_form_context(
            team_name=away_name,
            records=away_records,
            limit=MAX_HISTORY_MATCHES,
        )
        st.session_state.faj_form_context[index] = {
            "home": home_form_context,
            "away": away_form_context,
        }
    
    st.success(f"Сбор завершён: {len(home_records)} матчей для {home_name}, {len(away_records)} для {away_name}.")
    st.rerun()


def generate_prediction(index: int, match: Dict[str, Any]) -> None:
    collected = st.session_state.faj_collected.get(index)
    if not collected:
        st.warning("Сначала соберите статистику.")
        return
    
    home_name = match.get("home_name")
    away_name = match.get("away_name")
    if not home_name or not away_name:
        st.error("Не выбраны команды.")
        return
    
    home_records = collected.get("home_records", [])
    away_records = collected.get("away_records", [])
    
    if len(home_records) < 3 or len(away_records) < 3:
        st.warning(f"Рекомендуется минимум 3 матча. Сейчас: {len(home_records)} и {len(away_records)}.")
    
    # FormContext
    home_form_context = build_form_context(
        team_name=home_name,
        records=home_records,
        limit=MAX_HISTORY_MATCHES,
    )
    away_form_context = build_form_context(
        team_name=away_name,
        records=away_records,
        limit=MAX_HISTORY_MATCHES,
    )
    
    st.session_state.faj_form_context[index] = {
        "home": home_form_context,
        "away": away_form_context,
    }
    
    prediction = build_prediction(
        home_team=home_name,
        away_team=away_name,
        history_home=home_records,
        history_away=away_records,
        home_form_context=home_form_context,
        away_form_context=away_form_context,
    )
    
    st.session_state.faj_predictions[index] = prediction
    st.success("FAJ сформировал прогноз.")
    st.rerun()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    init_state()
    
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)
    
    # Header
    st.markdown("# ⚽ FAJ Predictor")
    st.markdown("Персональная футбольная аналитическая платформа")
    
    db = get_database()
    
    # Tournament
    st.subheader("1. Турнир")
    tournaments = get_all_tournaments()
    
    tournament = st.selectbox(
        "Выберите турнир",
        tournaments,
        index=tournaments.index(st.session_state.faj_competition) if st.session_state.faj_competition in tournaments else 0,
    )
    
    if st.session_state.faj_competition != tournament:
        st.session_state.faj_competition = tournament
        st.session_state.faj_matches = []
        st.session_state.faj_collected = {}
        st.session_state.faj_predictions = {}
        st.session_state.faj_form_context = {}
    
    # Teams
    team_names = load_teams(tournament)
    if not team_names:
        st.warning(f"В реестре FAJ пока нет команд для турнира «{tournament}».")
        return
    
    # Matches
    st.subheader("2. Матчи для анализа")
    st.caption(f"Можно подготовить до {MAX_ANALYSIS_MATCHES} матчей.")
    
    if not st.session_state.faj_matches:
        add_match()
    
    for index, match in enumerate(st.session_state.faj_matches):
        with st.container(border=True):
            render_match_setup(index, match, team_names)
    
    # Add match
    if len(st.session_state.faj_matches) < MAX_ANALYSIS_MATCHES:
        if st.button("＋ Добавить матч", use_container_width=True):
            add_match()
            st.rerun()
    
    # Reset
    st.divider()
    if st.button("♻️ Начать новый анализ", use_container_width=True):
        reset_workspace()
        st.rerun()


if __name__ == "__main__":
    main()

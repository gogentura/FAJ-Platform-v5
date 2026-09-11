#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PREDICTOR — Streamlit Interface
====================================

Чистый интерфейс для FAJ Personal Prediction Brain.

Функции:
    - Выбор турнира (из FAJ Club Ratings)
    - Выбор команд
    - FAJ Club Rating
    - FAJ Pair Rating 60..100
    - Ввод URL-адресов Soccer365 (до 6 на команду)
    - Сбор статистики
    - Генерация прогноза
    - Winner Signal
    - Отображение карточки прогноза

Архитектура:
    UI (Streamlit)
        ↓
    streamlit_app.py
        ↓
    FAJBrain
        ↓
    FormModel + FormWin + Defence + GoalModel
        ↓
    ProbabilityModel + ScorePredictor
        ↓
    CornersModel + CardsModel
        ↓
    Winner Signal
        ↑
    Pair Rating

ВАЖНО:
    Club Rating — структурный рейтинг клуба.
    Он только отображается и не влияет на расчёт.

    Pair Rating — рейтинг конкретной пары перед матчем.
    Он НЕ изменяет:
        - xG
        - GoalModel
        - Poisson
        - BTTS
        - totals
        - score distribution

    Pair Rating используется только для Winner Signal.
"""

from __future__ import annotations

import logging
from datetime import date
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
from app.core.pair_rating import calculate_pair_rating


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
# DATABASE / PARSER / BRAIN
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

        # ====================================================
        # PAIR RATING
        # ====================================================
        "home_pair_rating": 80,
        "away_pair_rating": 80,

        "urls_home": [""] * MAX_HISTORY_MATCHES,
        "urls_away": [""] * MAX_HISTORY_MATCHES,
    }


def add_match() -> None:
    if len(st.session_state.faj_matches) >= MAX_ANALYSIS_MATCHES:
        st.warning(
            f"Можно добавить максимум {MAX_ANALYSIS_MATCHES} матчей."
        )
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


def get_or_create_team(
    db: FAJDatabase,
    team_name: str,
    league: str,
) -> Optional[int]:
    try:
        teams = db.get_teams(league=league)

        for team in teams:
            if team.get("name") == team_name:
                return team.get("id")

        with db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO teams (name, league)
                VALUES (?, ?)
                ON CONFLICT(name, league)
                DO UPDATE SET active = 1
                RETURNING id
                """,
                (team_name, league),
            )

            row = cursor.fetchone()
            return row["id"] if row else None

    except Exception as exc:
        logger.exception(
            "Ошибка получения/создания команды: %s",
            exc,
        )
        return None


# ============================================================
# PARSING
# ============================================================

def parse_soccer365(url: str) -> Dict[str, Any]:
    parser = get_soccer365_parser()
    return parser.parse(url.strip())


def build_history_record(
    parsed: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Преобразует сырой результат Soccer365
    в единый factual history record.

    ВАЖНО:
        - только факты;
        - ничего не рассчитываем;
        - None сохраняется как None;
        - prediction / learning сюда не попадают.
    """

    stats = parsed.get("stats", {})

    if not isinstance(stats, dict):
        stats = {}

    home_goals, away_goals = parse_score(
        parsed.get("score")
    )

    return {
        # ====================================================
        # IDENTITY
        # ====================================================

        "home_team": parsed.get("home_team"),
        "away_team": parsed.get("away_team"),
        "match_date": parsed.get("match_date"),
        "score": parsed.get("score"),

        # ====================================================
        # GOALS
        # ====================================================

        "home_goals": home_goals,
        "away_goals": away_goals,

        # ====================================================
        # XG
        # ====================================================

        "xg": {
            "home": stats.get("home_xg"),
            "away": stats.get("away_xg"),
        },

        # ====================================================
        # SHOTS
        # ====================================================

        "shots": {
            "home": stats.get("home_shots"),
            "away": stats.get("away_shots"),
        },

        "shots_on_target": {
            "home": stats.get("home_shots_on_target"),
            "away": stats.get("away_shots_on_target"),
        },

        "blocked_shots": {
            "home": stats.get("home_blocked_shots"),
            "away": stats.get("away_blocked_shots"),
        },

        # ====================================================
        # CHANCES
        # ====================================================

        "big_chances": {
            "home": stats.get("home_big_chances"),
            "away": stats.get("away_big_chances"),
        },

        # ====================================================
        # POSSESSION
        # ====================================================

        "possession": {
            "home": stats.get("home_possession"),
            "away": stats.get("away_possession"),
        },

        # ====================================================
        # PASSES
        # ====================================================

        "passes": {
            "home": stats.get("home_total_passes"),
            "away": stats.get("away_total_passes"),
        },

        "pass_accuracy": {
            "home": stats.get("home_pass_accuracy"),
            "away": stats.get("away_pass_accuracy"),
        },

        # ====================================================
        # PROGRESSION
        # ====================================================

        "crosses": {
            "home": stats.get("home_crosses"),
            "away": stats.get("away_crosses"),
        },

        "throw_ins": {
            "home": stats.get("home_throw_ins"),
            "away": stats.get("away_throw_ins"),
        },

        # ====================================================
        # DISCIPLINE / GAME CONTROL
        # ====================================================

        "fouls": {
            "home": stats.get("home_fouls"),
            "away": stats.get("away_fouls"),
        },

        "offsides": {
            "home": stats.get("home_offsides"),
            "away": stats.get("away_offsides"),
        },

        "yellow_cards": {
            "home": stats.get("home_yellow_cards"),
            "away": stats.get("away_yellow_cards"),
        },

        "red_cards": {
            "home": stats.get("home_red_cards"),
            "away": stats.get("away_red_cards"),
        },

        # ====================================================
        # CORNERS
        # ====================================================

        "corners": {
            "home": stats.get("home_corners"),
            "away": stats.get("away_corners"),
        },

        # Legacy-compatible fields

        "home_corners": stats.get("home_corners"),
        "away_corners": stats.get("away_corners"),

        "home_yellow_cards": stats.get(
            "home_yellow_cards"
        ),
        "away_yellow_cards": stats.get(
            "away_yellow_cards"
        ),

        # ====================================================
        # RAW FACTUAL STATS
        # ====================================================

        "stats": dict(stats),

        # ====================================================
        # META
        # ====================================================

        "source_url": parsed.get("source_url"),

        "quality": parsed.get(
            "quality",
            parsed.get("data_quality", 0.0),
        ),

        "source": "Soccer365",

        "parser_version": parsed.get(
            "parser_version"
        ),
    }


def validate_parsed_match(
    parsed: Dict[str, Any],
    selected_team: str,
) -> tuple[bool, str]:

    home = parsed.get("home_team")
    away = parsed.get("away_team")

    if not home or not away:
        return False, "Не удалось определить команды."

    target = normalize_name(selected_team)

    if (
        target != normalize_name(home)
        and target != normalize_name(away)
    ):
        return (
            False,
            f"Матч {home} — {away} "
            f"не содержит {selected_team}.",
        )

    return True, f"{home} — {away}"


def _parse_date(value: Any):
    """Упрощённый парсер даты."""

    if value is None:
        return None

    import re

    text = str(value).strip()

    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        text,
    )

    if match:
        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except ValueError:
            return None

    match = re.search(
        r"(\d{2})\.(\d{2})\.(\d{4})",
        text,
    )

    if match:
        try:
            return date(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
            )
        except ValueError:
            return None

    return None


def collect_team_history(
    team_name: str,
    urls: List[str],
    forecast_date: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[str]]:

    clean_urls = [
        url.strip()
        for url in urls
        if url and url.strip()
    ]

    clean_urls = list(dict.fromkeys(clean_urls))

    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    forecast_date_obj = (
        _parse_date(forecast_date)
        if forecast_date
        else None
    )

    if forecast_date and not forecast_date_obj:
        errors.append(
            f"Некорректная дата прогноза: {forecast_date}"
        )
        return records, errors

    for position, url in enumerate(
        clean_urls,
        start=1,
    ):
        try:
            parsed = parse_soccer365(url)
        except Exception as exc:
            errors.append(f"{position}. {exc}")
            continue

        if parsed.get("error"):
            errors.append(
                f"{position}. {parsed.get('error')}"
            )
            continue

        valid, message = validate_parsed_match(
            parsed,
            team_name,
        )

        if not valid:
            errors.append(
                f"{position}. {message}"
            )
            continue

        record = build_history_record(parsed)

        # ====================================================
        # TEAM METADATA
        # ====================================================

        record["team"] = team_name
        record["team_name"] = team_name

        # ====================================================
        # VENUE
        # ====================================================

        if (
            normalize_name(parsed.get("home_team"))
            == normalize_name(team_name)
        ):
            record["is_home"] = True
            record["venue"] = "home"

        elif (
            normalize_name(parsed.get("away_team"))
            == normalize_name(team_name)
        ):
            record["is_home"] = False
            record["venue"] = "away"

        else:
            errors.append(
                f"{position}. "
                f"Не удалось определить сторону "
                f"{team_name}."
            )
            continue

        # ====================================================
        # DATE
        # ====================================================

        match_date = record.get("match_date")

        if not match_date:
            errors.append(
                f"{position}. "
                f"Не удалось определить дату матча."
            )
            continue

        match_date_obj = _parse_date(match_date)

        if not match_date_obj:
            errors.append(
                f"{position}. "
                f"Некорректная дата матча: "
                f"{match_date}"
            )
            continue

        if (
            forecast_date_obj
            and match_date_obj >= forecast_date_obj
        ):
            errors.append(
                f"{position}. "
                f"Матч от {match_date} "
                f"не является прошлым "
                f"относительно {forecast_date}."
            )
            continue

        records.append(record)

    # ========================================================
    # CANONICAL HISTORY ORDER
    # ========================================================

    records.sort(
        key=lambda item: (
            _parse_date(item.get("match_date"))
            or date.min
        )
    )

    # Последние 6 матчей:
    # oldest → newest

    records = records[-MAX_HISTORY_MATCHES:]

    return records, errors


# ============================================================
# WINNER SIGNAL
# ============================================================

def calculate_winner_signal(
    home_team: str,
    away_team: str,
    home_probability: Optional[float],
    away_probability: Optional[float],
    draw_probability: Optional[float],
    pair: Optional[Any],
) -> Dict[str, Any]:
    """
    Winner Signal.

    Источники:

        GoalModel + ProbabilityModel
                    ↓
              model_favorite

        Pair Rating
                    ↓
             pair direction

        оба сигнала
                    ↓
             Winner Signal

    Pair Rating НЕ меняет вероятности.
    """

    # --------------------------------------------------------
    # Model favorite
    # --------------------------------------------------------
    #
    # Вероятности здесь уже в долях:
    # 0.00 .. 1.00
    #
    # Правило равенства:
    # HOME → AWAY → DRAW
    #
    # --------------------------------------------------------

    if (
        home_probability is not None
        and away_probability is not None
        and draw_probability is not None
    ):
        if (
            home_probability >= away_probability
            and home_probability >= draw_probability
        ):
            model_favorite = home_team

        elif (
            away_probability >= home_probability
            and away_probability >= draw_probability
        ):
            model_favorite = away_team

        else:
            model_favorite = "DRAW"

    else:
        model_favorite = "DRAW"

    # --------------------------------------------------------
    # No Pair Rating
    # --------------------------------------------------------

    if pair is None:
        return {
            "model_favorite": model_favorite,
            "pair_direction": None,
            "pair_team": None,
            "pair_strength": None,
            "agreement": "MODEL_ONLY",
            "final_winner": model_favorite,
        }

    # --------------------------------------------------------
    # Model says DRAW
    # --------------------------------------------------------

    if model_favorite == "DRAW":
        return {
            "model_favorite": model_favorite,
            "pair_direction": pair.winner_direction,
            "pair_team": pair.direction_team,
            "pair_strength": pair.direction_strength,
            "agreement": "MODEL_ONLY",
            "final_winner": "DRAW",
        }

    # --------------------------------------------------------
    # Pair Rating neutral
    # --------------------------------------------------------

    if pair.winner_direction == "NEUTRAL":
        return {
            "model_favorite": model_favorite,
            "pair_direction": pair.winner_direction,
            "pair_team": pair.direction_team,
            "pair_strength": pair.direction_strength,
            "agreement": "PAIR_NEUTRAL",
            "final_winner": model_favorite,
        }

    # --------------------------------------------------------
    # Signals agree
    # --------------------------------------------------------

    if pair.direction_team == model_favorite:
        return {
            "model_favorite": model_favorite,
            "pair_direction": pair.winner_direction,
            "pair_team": pair.direction_team,
            "pair_strength": pair.direction_strength,
            "agreement": "AGREE",
            "final_winner": model_favorite,
        }

    # --------------------------------------------------------
    # Signals conflict
    # --------------------------------------------------------

    return {
        "model_favorite": model_favorite,
        "pair_direction": pair.winner_direction,
        "pair_team": pair.direction_team,
        "pair_strength": pair.direction_strength,
        "agreement": "CONFLICT",
        "final_winner": "CONFLICT",
    }


# ============================================================
# UI — PREDICTION CARD
# ============================================================

def render_prediction_card(
    prediction: Dict[str, Any],
) -> None:

    home = prediction.get(
        "home_team",
        "Хозяева",
    )

    away = prediction.get(
        "away_team",
        "Гости",
    )

    st.markdown("---")
    st.markdown(
        f"## ⚽ {home} — {away}"
    )

    # ========================================================
    # WINNER SIGNAL
    # ========================================================

    st.subheader("🧠 Winner Signal")

    winner_signal = prediction.get(
        "winner_signal",
        {},
    )

    model_favorite = winner_signal.get(
        "model_favorite",
        "—",
    )

    pair_direction = winner_signal.get(
        "pair_direction",
        "—",
    )

    pair_team = winner_signal.get(
        "pair_team",
        "—",
    )

    pair_strength = winner_signal.get(
        "pair_strength",
        "—",
    )

    agreement = winner_signal.get(
        "agreement",
        "—",
    )

    final_winner = winner_signal.get(
        "final_winner",
        "—",
    )

    pair_rating = prediction.get(
        "pair_rating",
        {},
    ) or {}

    home_pair = pair_rating.get(
        "home_rating",
        "—",
    )

    away_pair = pair_rating.get(
        "away_rating",
        "—",
    )

    st.markdown(
        f"""
**Pair Rating:** 🏠 {home_pair} | ✈️ {away_pair}

**Model favorite:** {model_favorite}

**Pair direction:** {pair_direction}

**Direction team:** {pair_team}

**Strength:** {pair_strength}
"""
    )

    if agreement == "AGREE":
        st.success(
            f"AGREE — оба сигнала указывают на "
            f"{final_winner}"
        )

    elif agreement == "CONFLICT":
        st.error(
            f"CONFLICT — модель: {model_favorite}, "
            f"Pair Rating: {pair_team}"
        )

    elif agreement == "PAIR_NEUTRAL":
        st.info(
            f"PAIR_NEUTRAL — Pair Rating нейтрален. "
            f"Направление модели: {final_winner}"
        )

    else:
        st.info(
            f"MODEL_ONLY — направление модели: "
            f"{final_winner}"
        )

    st.markdown(
        f"### Итоговое направление: {final_winner}"
    )

    # ========================================================
    # 1. MAIN OUTCOME
    # ========================================================

    st.subheader("1. Главный исход")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            f"🏠 {home}",
            pct(
                prediction.get(
                    "home_win_probability"
                )
            ),
        )

    with c2:
        st.metric(
            "🤝 Ничья",
            pct(
                prediction.get(
                    "draw_probability"
                )
            ),
        )

    with c3:
        st.metric(
            f"✈️ {away}",
            pct(
                prediction.get(
                    "away_win_probability"
                )
            ),
        )

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Уверенность FAJ",
            pct(
                prediction.get(
                    "confidence"
                )
            ),
        )

    with c2:
        st.metric(
            "Риск",
            prediction.get(
                "risk",
                "—",
            ),
        )

    # ========================================================
    # 2. GOALS
    # ========================================================

    st.subheader("2. Голы")

    btts = prediction.get(
        "btts_probability"
    )

    over25 = prediction.get(
        "over25_probability"
    )

    over35 = prediction.get(
        "over35_probability"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Обе забьют",
            "ДА"
            if btts is not None and btts >= 0.5
            else "НЕТ",
        )

        st.caption(
            f"Вероятность: {pct(btts)}"
        )

    with c2:
        st.metric(
            "ТБ 2.5",
            "ДА"
            if over25 is not None
            and over25 >= 0.5
            else "НЕТ",
        )

        st.caption(
            f"Вероятность: {pct(over25)}"
        )

    with c3:
        st.metric(
            "ТБ 3.5",
            "ДА"
            if over35 is not None
            and over35 >= 0.5
            else "НЕТ",
        )

        st.caption(
            f"Вероятность: {pct(over35)}"
        )

    # ========================================================
    # 3. SCORES
    # ========================================================

    st.subheader(
        "3. Наиболее вероятные точные счета"
    )

    scores = prediction.get(
        "scores",
        [],
    )

    cols = st.columns(
        max(1, len(scores))
    )

    for idx, item in enumerate(scores):
        with cols[idx]:
            st.markdown(
                f"### {item.get('score', '—')}"
            )

    # ========================================================
    # 4. CORNERS
    # ========================================================

    st.subheader("4. Угловые")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Всего",
            num(
                prediction.get(
                    "corners_expected"
                )
            ),
        )

    with c2:
        st.metric(
            home,
            num(
                prediction.get(
                    "home_corners_expected"
                )
            ),
        )

    with c3:
        st.metric(
            away,
            num(
                prediction.get(
                    "away_corners_expected"
                )
            ),
        )

    st.write(
        f"**Диапазон:** "
        f"{prediction.get('corners_range', '—')}"
    )

    corner_lines = prediction.get(
        "corners_lines",
        {},
    )

    cols = st.columns(4)

    for col, line in zip(
        cols,
        ["7.5", "8.5", "9.5", "10.5"],
    ):
        with col:
            st.metric(
                f"ТБ {line}",
                pct(
                    corner_lines.get(line)
                ),
            )

    # ========================================================
    # 5. CARDS
    # ========================================================

    st.subheader("5. Карточки")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Всего",
            num(
                prediction.get(
                    "cards_expected"
                )
            ),
        )

    with c2:
        st.metric(
            home,
            num(
                prediction.get(
                    "home_cards_expected"
                )
            ),
        )

    with c3:
        st.metric(
            away,
            num(
                prediction.get(
                    "away_cards_expected"
                )
            ),
        )

    st.write(
        f"**Диапазон:** "
        f"{prediction.get('cards_range', '—')}"
    )

    card_lines = prediction.get(
        "cards_lines",
        {},
    )

    cols = st.columns(3)

    for col, line in zip(
        cols,
        ["2.5", "3.5", "4.5"],
    ):
        with col:
            st.metric(
                f"ТБ {line}",
                pct(
                    card_lines.get(line)
                ),
            )

    # ========================================================
    # 6. ANALYSIS
    # ========================================================

    st.subheader(
        "6. Аналитический вывод FAJ"
    )

    st.info(
        prediction.get(
            "analysis",
            "Аналитический вывод пока недоступен.",
        )
    )


# ============================================================
# UI — MATCH SETUP
# ============================================================

def render_match_setup(
    index: int,
    match: Dict[str, Any],
    team_names: List[str],
) -> None:

    st.markdown(
        f"### Матч {index + 1}"
    )

    # ========================================================
    # TEAM SELECTION
    # ========================================================

    home_current = (
        match.get("home_name")
        or (
            team_names[0]
            if team_names
            else ""
        )
    )

    if home_current not in team_names:
        home_current = (
            team_names[0]
            if team_names
            else ""
        )

    away_options = [
        name
        for name in team_names
        if name != home_current
    ]

    away_current = (
        match.get("away_name")
        or (
            away_options[0]
            if away_options
            else ""
        )
    )

    if (
        away_current not in away_options
        and away_options
    ):
        away_current = away_options[0]

    c1, c2 = st.columns(2)

    with c1:
        selected_home = st.selectbox(
            "🏠 Хозяева",
            team_names,
            index=(
                team_names.index(home_current)
                if home_current in team_names
                else 0
            ),
            key=f"home_{index}",
        )

    with c2:
        available_away = [
            name
            for name in team_names
            if name != selected_home
        ]

        if not available_away:
            st.warning(
                "Нужно минимум две команды."
            )
            return

        selected_away = st.selectbox(
            "✈️ Гости",
            available_away,
            index=(
                available_away.index(
                    away_current
                )
                if away_current in available_away
                else 0
            ),
            key=f"away_{index}",
        )

    match["home_name"] = selected_home
    match["away_name"] = selected_away

    # ========================================================
    # CLUB RATING
    # ========================================================

    st.markdown(
        "#### ⭐ FAJ Club Rating"
    )

    club_c1, club_c2 = st.columns(2)

    with club_c1:
        home_club_rating = get_team_rating(
            selected_home
        )

        st.metric(
            f"🏠 {selected_home}",
            (
                home_club_rating
                if home_club_rating is not None
                else "—"
            ),
        )

    with club_c2:
        away_club_rating = get_team_rating(
            selected_away
        )

        st.metric(
            f"✈️ {selected_away}",
            (
                away_club_rating
                if away_club_rating is not None
                else "—"
            ),
        )

    st.caption(
        "Club Rating — структурный рейтинг FAJ. "
        "В текущей версии только отображается."
    )

    # ========================================================
    # PAIR RATING
    # ========================================================

    st.markdown(
        "#### 🧠 FAJ Pair Rating"
    )

    pair_c1, pair_c2 = st.columns(2)

    with pair_c1:
        home_pair_rating = st.number_input(
            f"{selected_home} — рейтинг пары",
            min_value=60,
            max_value=100,
            value=int(
                match.get(
                    "home_pair_rating",
                    80,
                )
            ),
            step=1,
            key=f"home_pair_{index}",
        )

    with pair_c2:
        away_pair_rating = st.number_input(
            f"{selected_away} — рейтинг пары",
            min_value=60,
            max_value=100,
            value=int(
                match.get(
                    "away_pair_rating",
                    80,
                )
            ),
            step=1,
            key=f"away_pair_{index}",
        )

    match["home_pair_rating"] = (
        home_pair_rating
    )

    match["away_pair_rating"] = (
        away_pair_rating
    )

    pair_preview = calculate_pair_rating(
        home_rating=int(home_pair_rating),
        away_rating=int(away_pair_rating),
        home_team=selected_home,
        away_team=selected_away,
    )

    if pair_preview.winner_direction == "NEUTRAL":
        st.info(
            "Pair Rating: NEUTRAL"
        )
    else:
        st.caption(
            f"Направление пары: "
            f"{pair_preview.direction_team} "
            f"({pair_preview.direction_strength})"
        )

    # ========================================================
    # DATE
    # ========================================================

    current_date = match.get(
        "match_date"
    )

    try:
        default_date = (
            date.fromisoformat(current_date)
            if current_date
            else date.today()
        )
    except (
        TypeError,
        ValueError,
    ):
        default_date = date.today()

    forecast_date = st.date_input(
        "📅 Дата матча",
        value=default_date,
        key=f"date_{index}",
    )

    match["match_date"] = (
        forecast_date.isoformat()
    )

    # ========================================================
    # URLS
    # ========================================================

    st.markdown(
        "#### 🔗 Ссылки на Soccer365"
    )

    col_home, col_away = st.columns(2)

    with col_home:
        st.markdown(
            f"**🏠 {selected_home}**"
        )

        for i in range(
            MAX_HISTORY_MATCHES
        ):
            match["urls_home"][i] = (
                st.text_input(
                    f"Матч {i + 1}",
                    value=match[
                        "urls_home"
                    ][i],
                    key=(
                        f"home_url_"
                        f"{index}_{i}"
                    ),
                    placeholder=(
                        "https://soccer365.ru/..."
                    ),
                )
            )

    with col_away:
        st.markdown(
            f"**✈️ {selected_away}**"
        )

        for i in range(
            MAX_HISTORY_MATCHES
        ):
            match["urls_away"][i] = (
                st.text_input(
                    f"Матч {i + 1}",
                    value=match[
                        "urls_away"
                    ][i],
                    key=(
                        f"away_url_"
                        f"{index}_{i}"
                    ),
                    placeholder=(
                        "https://soccer365.ru/..."
                    ),
                )
            )

    # ========================================================
    # BUTTONS
    # ========================================================

    c1, c2 = st.columns(2)

    with c1:
        if st.button(
            "📥 Собрать статистику",
            key=f"collect_{index}",
            use_container_width=True,
        ):
            collect_and_store_match(
                index,
                match,
            )

    with c2:
        if st.button(
            "🧠 Получить прогноз",
            key=f"predict_{index}",
            use_container_width=True,
        ):
            generate_prediction(
                index,
                match,
            )

    # ========================================================
    # STATUS
    # ========================================================

    collected = (
        st.session_state.faj_collected.get(
            index
        )
    )

    if collected:
        st.success(
            f"✅ Собрано: "
            f"{len(collected.get('home_records', []))} "
            f"матчей"
        )

        home_records = collected.get(
            "home_records",
            [],
        )

        away_records = collected.get(
            "away_records",
            [],
        )

        c1, c2 = st.columns(2)

        with c1:
            render_data_summary(
                selected_home,
                home_records,
            )

        with c2:
            render_data_summary(
                selected_away,
                away_records,
            )

        if collected.get("errors"):
            with st.expander(
                "⚠️ Сообщения сбора"
            ):
                for error in collected[
                    "errors"
                ]:
                    st.warning(error)

    # ========================================================
    # FORM CONTEXT
    # ========================================================

    form_data = (
        st.session_state.faj_form_context.get(
            index
        )
    )

    if form_data:
        render_form_context_card(
            selected_home,
            selected_away,
            form_data.get("home"),
            form_data.get("away"),
        )

    # ========================================================
    # PREDICTION
    # ========================================================

    prediction = (
        st.session_state.faj_predictions.get(
            index
        )
    )

    if prediction:
        render_prediction_card(
            prediction
        )

    # ========================================================
    # REMOVE
    # ========================================================

    if len(
        st.session_state.faj_matches
    ) > 1:

        if st.button(
            "🗑 Удалить матч",
            key=f"remove_{index}",
        ):
            remove_match(index)
            st.rerun()


# ============================================================
# DATA SUMMARY
# ============================================================

def render_data_summary(
    team_name: str,
    records: List[Dict[str, Any]],
) -> None:

    if not records:
        return

    goals_for = []
    goals_against = []
    corners = []
    cards = []

    for record in records:

        if (
            normalize_name(
                record.get("home_team")
            )
            == normalize_name(team_name)
        ):
            gf = record.get(
                "home_goals"
            )

            ga = record.get(
                "away_goals"
            )

            corner = record.get(
                "home_corners"
            )

            card = record.get(
                "home_yellow_cards"
            )

        else:
            gf = record.get(
                "away_goals"
            )

            ga = record.get(
                "home_goals"
            )

            corner = record.get(
                "away_corners"
            )

            card = record.get(
                "away_yellow_cards"
            )

        if gf is not None:
            goals_for.append(gf)

        if ga is not None:
            goals_against.append(ga)

        if corner is not None:
            corners.append(corner)

        if card is not None:
            cards.append(card)

    def avg(vals):
        return (
            sum(vals) / len(vals)
            if vals
            else None
        )

    st.markdown(
        f"**{team_name}**"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Матчей",
            len(records),
        )

    with c2:
        st.metric(
            "Голы за матч",
            num(
                avg(goals_for)
            ),
        )

    with c3:
        st.metric(
            "Угловые",
            (
                num(avg(corners))
                if corners
                else "—"
            ),
        )

    with c4:
        st.metric(
            "Карточки",
            (
                num(avg(cards))
                if cards
                else "—"
            ),
        )

    quality = (
        sum(
            r.get(
                "quality",
                0,
            )
            for r in records
        )
        / len(records)
        if records
        else 0
    )

    st.caption(
        f"Качество данных: "
        f"{quality * 100:.0f}%"
    )


# ============================================================
# FORM CONTEXT CARD
# ============================================================

def render_form_context_card(
    home_team: str,
    away_team: str,
    home_context: Optional[
        Dict[str, Any]
    ],
    away_context: Optional[
        Dict[str, Any]
    ],
) -> None:

    """
    Отображает FormContext v1.7.
    """

    home_context = (
        home_context or {}
    )

    away_context = (
        away_context or {}
    )

    st.markdown(
        "### 📊 Форма перед матчем"
    )

    def format_form(
        context: Dict[str, Any],
    ) -> str:

        form = context.get(
            "form"
        )

        if isinstance(form, str):
            text = form.strip()

            if text:
                return text

        if isinstance(
            form,
            (list, tuple),
        ):
            values = []

            mapping = {
                "W": "В",
                "WIN": "В",
                "D": "Н",
                "DRAW": "Н",
                "L": "П",
                "LOSS": "П",
                "В": "В",
                "Н": "Н",
                "П": "П",
            }

            for item in form[:6]:
                value = (
                    str(item)
                    .strip()
                    .upper()
                )

                values.append(
                    mapping.get(
                        value,
                        value,
                    )
                )

            if values:
                return "-".join(values)

        return "—"

    def format_number(
        value: Any,
    ) -> str:

        if value is None:
            return "—"

        try:
            return f"{float(value):.2f}"
        except (
            TypeError,
            ValueError,
        ):
            return "—"

    def home_away_record(
        context: Dict[str, Any],
    ) -> tuple[str, str]:

        home = context.get(
            "home",
            {},
        )

        away = context.get(
            "away",
            {},
        )

        if not isinstance(
            home,
            dict,
        ):
            home = {}

        if not isinstance(
            away,
            dict,
        ):
            away = {}

        home_text = (
            f"{home.get('wins', 0)}-"
            f"{home.get('draws', 0)}-"
            f"{home.get('losses', 0)}"
        )

        away_text = (
            f"{away.get('wins', 0)}-"
            f"{away.get('draws', 0)}-"
            f"{away.get('losses', 0)}"
        )

        return (
            home_text,
            away_text,
        )

    home_form = format_form(
        home_context
    )

    away_form = format_form(
        away_context
    )

    home_xg = home_context.get(
        "xg"
    )

    if home_xg is None:
        home_xg = home_context.get(
            "xg_avg"
        )

    home_xga = home_context.get(
        "xga"
    )

    if home_xga is None:
        home_xga = home_context.get(
            "xga_avg"
        )

    away_xg = away_context.get(
        "xg"
    )

    if away_xg is None:
        away_xg = away_context.get(
            "xg_avg"
        )

    away_xga = away_context.get(
        "xga"
    )

    if away_xga is None:
        away_xga = away_context.get(
            "xga_avg"
        )

    home_home, home_away = (
        home_away_record(
            home_context
        )
    )

    away_home, away_away = (
        home_away_record(
            away_context
        )
    )

    c1, c2 = st.columns(2)

    # ========================================================
    # HOME
    # ========================================================

    with c1:

        st.markdown(
            f"**🏠 {home_team}**"
        )

        st.markdown(
            f"**Форма:** `{home_form}`"
        )

        st.caption(
            f"Дома: {home_home}  ·  "
            f"В гостях: {home_away}"
        )

        metric1, metric2 = st.columns(2)

        with metric1:
            st.metric(
                "xG",
                format_number(
                    home_xg
                ),
            )

        with metric2:
            st.metric(
                "xGA",
                format_number(
                    home_xga
                ),
            )

    # ========================================================
    # AWAY
    # ========================================================

    with c2:

        st.markdown(
            f"**✈️ {away_team}**"
        )

        st.markdown(
            f"**Форма:** `{away_form}`"
        )

        st.caption(
            f"Дома: {away_home}  ·  "
            f"В гостях: {away_away}"
        )

        metric1, metric2 = st.columns(2)

        with metric1:
            st.metric(
                "xG",
                format_number(
                    away_xg
                ),
            )

        with metric2:
            st.metric(
                "xGA",
                format_number(
                    away_xga
                ),
            )


# ============================================================
# PROBABILITY HELPERS
# ============================================================

def _percent_to_fraction(
    value: Optional[float],
) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value) / 100.0
    except (
        TypeError,
        ValueError,
    ):
        return None


def _get_corners_range(
    expected: Optional[float],
) -> str:

    if expected is None:
        return "—"

    if expected < 8:
        return "7–9"

    if expected < 10:
        return "8–10"

    if expected < 12:
        return "9–11"

    return "10–12+"


def _get_cards_range(
    expected: Optional[float],
) -> str:

    if expected is None:
        return "—"

    if expected < 3:
        return "2–3"

    if expected < 4:
        return "3–4"

    if expected < 5:
        return "4–5"

    return "5+"


# ============================================================
# BUILD PREDICTION
# ============================================================

def build_prediction(
    home_team: str,
    away_team: str,
    history_home: List[Dict[str, Any]],
    history_away: List[Dict[str, Any]],
    home_form_context: Optional[
        Dict[str, Any]
    ] = None,
    away_form_context: Optional[
        Dict[str, Any]
    ] = None,
    home_pair_rating: Optional[int] = None,
    away_pair_rating: Optional[int] = None,
) -> Dict[str, Any]:

    brain = get_faj_brain()

    # ========================================================
    # BRAIN
    # ========================================================

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=history_home,
        away_matches=history_away,
    )

    # ========================================================
    # PROBABILITIES
    # ========================================================

    home_probability = (
        _percent_to_fraction(
            result.get(
                "home_win_probability"
            )
        )
    )

    draw_probability = (
        _percent_to_fraction(
            result.get(
                "draw_probability"
            )
        )
    )

    away_probability = (
        _percent_to_fraction(
            result.get(
                "away_win_probability"
            )
        )
    )

    # ========================================================
    # PAIR RATING
    # ========================================================

    pair = None

    if (
        home_pair_rating is not None
        and away_pair_rating is not None
    ):
        pair = calculate_pair_rating(
            home_rating=int(
                home_pair_rating
            ),
            away_rating=int(
                away_pair_rating
            ),
            home_team=home_team,
            away_team=away_team,
        )

    # ========================================================
    # WINNER SIGNAL
    # ========================================================

    winner_signal = (
        calculate_winner_signal(
            home_team=home_team,
            away_team=away_team,
            home_probability=home_probability,
            away_probability=away_probability,
            draw_probability=draw_probability,
            pair=pair,
        )
    )

    # ========================================================
    # CLUB RATING
    # ========================================================

    club_rating = {
        "home": get_team_rating(
            home_team
        ),
        "away": get_team_rating(
            away_team
        ),
    }

    # ========================================================
    # FINAL PREDICTION OBJECT
    # ========================================================

    return {
        "model_version": (
            result.get(
                "calculation_meta",
                {},
            ).get(
                "brain_version",
                "FAJ-BRAIN",
            )
        ),

        "home_team": result.get(
            "home_team",
            home_team,
        ),

        "away_team": result.get(
            "away_team",
            away_team,
        ),

        # ----------------------------------------------------
        # MAIN PROBABILITIES
        # ----------------------------------------------------

        "home_win_probability": (
            home_probability
        ),

        "draw_probability": (
            draw_probability
        ),

        "away_win_probability": (
            away_probability
        ),

        "confidence": (
            _percent_to_fraction(
                result.get(
                    "confidence"
                )
            )
        ),

        "risk": result.get(
            "risk",
            "—",
        ),

        # ----------------------------------------------------
        # GOALS
        # ----------------------------------------------------

        "btts": result.get(
            "btts"
        ),

        "btts_probability": (
            _percent_to_fraction(
                result.get(
                    "btts_probability"
                )
            )
        ),

        "over25": result.get(
            "over25"
        ),

        "over25_probability": (
            _percent_to_fraction(
                result.get(
                    "over25_probability"
                )
            )
        ),

        "over35": result.get(
            "over35"
        ),

        "over35_probability": (
            _percent_to_fraction(
                result.get(
                    "over35_probability"
                )
            )
        ),

        "home_xg_internal": result.get(
            "home_xg"
        ),

        "away_xg_internal": result.get(
            "away_xg"
        ),

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        "scores": [
            {
                "score": result.get(
                    "most_likely_score",
                    "—",
                )
            },
            {
                "score": result.get(
                    "second_likely_score",
                    "—",
                )
            },
            {
                "score": result.get(
                    "third_likely_score",
                    "—",
                )
            },
        ],

        # ----------------------------------------------------
        # CORNERS
        # ----------------------------------------------------

        "corners_expected": result.get(
            "corners_expected"
        ),

        "home_corners_expected": result.get(
            "home_corners_expected"
        ),

        "away_corners_expected": result.get(
            "away_corners_expected"
        ),

        "corners_lines": {
            "7.5": _percent_to_fraction(
                result.get(
                    "over75_corners_probability"
                )
            ),

            "8.5": _percent_to_fraction(
                result.get(
                    "over85_corners_probability"
                )
            ),

            "9.5": _percent_to_fraction(
                result.get(
                    "over95_corners_probability"
                )
            ),

            "10.5": _percent_to_fraction(
                result.get(
                    "over105_corners_probability"
                )
            ),
        },

        "corners_range": (
            _get_corners_range(
                result.get(
                    "corners_expected"
                )
            )
        ),

        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------

        "cards_expected": result.get(
            "cards_expected"
        ),

        "home_cards_expected": result.get(
            "home_cards_expected"
        ),

        "away_cards_expected": result.get(
            "away_cards_expected"
        ),

        "cards_lines": {
            "2.5": _percent_to_fraction(
                result.get(
                    "over25_cards_probability"
                )
            ),

            "3.5": _percent_to_fraction(
                result.get(
                    "over35_cards_probability"
                )
            ),

            "4.5": _percent_to_fraction(
                result.get(
                    "over45_cards_probability"
                )
            ),
        },

        "cards_range": (
            _get_cards_range(
                result.get(
                    "cards_expected"
                )
            )
        ),

        # ----------------------------------------------------
        # ANALYSIS
        # ----------------------------------------------------

        "analysis": result.get(
            "conclusion",
            "Аналитический вывод "
            "пока недоступен.",
        ),

        # ----------------------------------------------------
        # FORM
        # ----------------------------------------------------

        "home_form_context": (
            home_form_context
        ),

        "away_form_context": (
            away_form_context
        ),

        # ----------------------------------------------------
        # CLUB RATING
        # ----------------------------------------------------

        "club_rating": club_rating,

        # ----------------------------------------------------
        # PAIR RATING
        # ----------------------------------------------------

        "pair_rating": (
            pair.to_dict()
            if pair
            else None
        ),

        # ----------------------------------------------------
        # WINNER SIGNAL
        # ----------------------------------------------------

        "winner_signal": winner_signal,

        # ----------------------------------------------------
        # RAW BRAIN RESULT
        # ----------------------------------------------------

        "brain_result": result,
    }


# ============================================================
# COLLECTION + PREDICTION
# ============================================================

def collect_and_store_match(
    index: int,
    match: Dict[str, Any],
) -> None:

    home_name = match.get(
        "home_name"
    )

    away_name = match.get(
        "away_name"
    )

    tournament = (
        st.session_state.faj_competition
    )

    forecast_date = match.get(
        "match_date"
    )

    if not home_name or not away_name:
        st.error(
            "Сначала выберите обе команды."
        )
        return

    if not tournament:
        st.error(
            "Не выбран турнир."
        )
        return

    db = get_database()

    home_id = get_or_create_team(
        db,
        home_name,
        tournament,
    )

    away_id = get_or_create_team(
        db,
        away_name,
        tournament,
    )

    if (
        home_id is None
        or away_id is None
    ):
        st.error(
            "Не удалось загрузить команды."
        )
        return

    all_errors = []

    with st.status(
        "Собираю данные Soccer365...",
        expanded=True,
    ):

        st.write(
            f"🏠 {home_name}"
        )

        home_records, home_errors = (
            collect_team_history(
                home_name,
                match.get(
                    "urls_home",
                    [],
                ),
                forecast_date,
            )
        )

        all_errors.extend(
            [
                f"{home_name}: {e}"
                for e in home_errors
            ]
        )

        st.write(
            f"Получено матчей: "
            f"{len(home_records)}"
        )

        st.write(
            f"✈️ {away_name}"
        )

        away_records, away_errors = (
            collect_team_history(
                away_name,
                match.get(
                    "urls_away",
                    [],
                ),
                forecast_date,
            )
        )

        all_errors.extend(
            [
                f"{away_name}: {e}"
                for e in away_errors
            ]
        )

        st.write(
            f"Получено матчей: "
            f"{len(away_records)}"
        )

    st.session_state.faj_collected[
        index
    ] = {
        "home_records": home_records,
        "away_records": away_records,
        "errors": all_errors,
    }

    # ========================================================
    # FORM CONTEXT
    # ========================================================

    if (
        home_records
        and away_records
    ):

        home_form_context = (
            build_form_context(
                team_name=home_name,
                records=home_records,
                limit=MAX_HISTORY_MATCHES,
            )
        )

        away_form_context = (
            build_form_context(
                team_name=away_name,
                records=away_records,
                limit=MAX_HISTORY_MATCHES,
            )
        )

        st.session_state.faj_form_context[
            index
        ] = {
            "home": home_form_context,
            "away": away_form_context,
        }

    st.success(
        f"Сбор завершён: "
        f"{len(home_records)} матчей "
        f"для {home_name}, "
        f"{len(away_records)} "
        f"для {away_name}."
    )

    st.rerun()


def generate_prediction(
    index: int,
    match: Dict[str, Any],
) -> None:

    collected = (
        st.session_state.faj_collected.get(
            index
        )
    )

    if not collected:
        st.warning(
            "Сначала соберите статистику."
        )
        return

    home_name = match.get(
        "home_name"
    )

    away_name = match.get(
        "away_name"
    )

    if not home_name or not away_name:
        st.error(
            "Не выбраны команды."
        )
        return

    home_records = collected.get(
        "home_records",
        [],
    )

    away_records = collected.get(
        "away_records",
        [],
    )

    if (
        len(home_records) < 3
        or len(away_records) < 3
    ):
        st.warning(
            f"Рекомендуется минимум "
            f"3 матча. Сейчас: "
            f"{len(home_records)} "
            f"и {len(away_records)}."
        )

    # ========================================================
    # FORM CONTEXT
    # ========================================================

    home_form_context = (
        build_form_context(
            team_name=home_name,
            records=home_records,
            limit=MAX_HISTORY_MATCHES,
        )
    )

    away_form_context = (
        build_form_context(
            team_name=away_name,
            records=away_records,
            limit=MAX_HISTORY_MATCHES,
        )
    )

    st.session_state.faj_form_context[
        index
    ] = {
        "home": home_form_context,
        "away": away_form_context,
    }

    # ========================================================
    # PAIR RATING
    # ========================================================

    home_pair_rating = match.get(
        "home_pair_rating"
    )

    away_pair_rating = match.get(
        "away_pair_rating"
    )

    # ========================================================
    # PREDICTION
    # ========================================================

    prediction = build_prediction(
        home_team=home_name,
        away_team=away_name,
        history_home=home_records,
        history_away=away_records,
        home_form_context=home_form_context,
        away_form_context=away_form_context,
        home_pair_rating=home_pair_rating,
        away_pair_rating=away_pair_rating,
    )

    st.session_state.faj_predictions[
        index
    ] = prediction

    st.success(
        "FAJ сформировал прогноз."
    )

    st.rerun()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
    )

    init_state()

    # ========================================================
    # HEADER
    # ========================================================

    st.markdown(
        "# ⚽ FAJ Predictor"
    )

    st.markdown(
        "Персональная футбольная "
        "аналитическая платформа"
    )

    db = get_database()

    # ========================================================
    # TOURNAMENT
    # ========================================================

    st.subheader("1. Турнир")

    tournaments = (
        get_all_tournaments()
    )

    tournament = st.selectbox(
        "Выберите турнир",
        tournaments,
        index=(
            tournaments.index(
                st.session_state.faj_competition
            )
            if (
                st.session_state.faj_competition
                in tournaments
            )
            else 0
        ),
    )

    if (
        st.session_state.faj_competition
        != tournament
    ):

        st.session_state.faj_competition = (
            tournament
        )

        st.session_state.faj_matches = []
        st.session_state.faj_collected = {}
        st.session_state.faj_predictions = {}
        st.session_state.faj_form_context = {}

    # ========================================================
    # TEAMS
    # ========================================================

    team_names = load_teams(
        tournament
    )

    if not team_names:
        st.warning(
            f"В реестре FAJ пока нет "
            f"команд для турнира "
            f"«{tournament}»."
        )
        return

    # ========================================================
    # MATCHES
    # ========================================================

    st.subheader(
        "2. Матчи для анализа"
    )

    st.caption(
        f"Можно подготовить до "
        f"{MAX_ANALYSIS_MATCHES} матчей."
    )

    if not st.session_state.faj_matches:
        add_match()

    for index, match in enumerate(
        st.session_state.faj_matches
    ):

        with st.container(
            border=True
        ):
            render_match_setup(
                index,
                match,
                team_names,
            )

    # ========================================================
    # ADD MATCH
    # ========================================================

    if (
        len(
            st.session_state.faj_matches
        )
        < MAX_ANALYSIS_MATCHES
    ):

        if st.button(
            "＋ Добавить матч",
            use_container_width=True,
        ):
            add_match()
            st.rerun()

    # ========================================================
    # RESET
    # ========================================================

    st.divider()

    if st.button(
        "♻️ Начать новый анализ",
        use_container_width=True,
    ):
        reset_workspace()
        st.rerun()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()

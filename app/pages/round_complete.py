#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ROUND COMPLETE v1.2
============================================================

Назначение:
    Итоговый отчёт завершённого тура.

ЦЕПОЧКА:

    IMPORT FACTS
          ↓
    MATCH RESULTS
          ↓
    ROUND COMPLETE
          ↓
    СРАВНЕНИЕ FAJ / ДИРЕКТОР / ФАКТ
          ↓
    ТУРНИРНАЯ ТАБЛИЦА
          ↓
    LEARNING ENGINE
          ↓
    NEXT ROUND

ПРИНЦИПЫ:

    SQLite only
    database.py — единственный источник данных
    Только чтение фактов и прогнозов
    Никаких DELETE
    Никаких DROP
    Не изменяет результаты
    Не создаёт календарь
    Не пересчитывает прогнозы
    Обучение запускается отдельно

ОЦЕНКА ПРОГНОЗА:

    🎯 Точный счёт
    🟢 Почти угадал счёт
    🟡 Угадан исход
    🔴 Не угадан
    ⚪ Нет прогноза

============================================================
ИЗМЕНЕНИЯ V1.2
============================================================

1. Добавлен диагностический блок для поиска прогнозов FAJ
2. Показывает количество прогнозов в predictions и match_predictions
3. Помогает определить, где хранятся прогнозы FAJ
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ROUND_COMPLETE_VERSION = "1.2"

DEFAULT_DB_PATH = "data/faj.db"

LEAGUES = [
    "РПЛ",
    "АПЛ",
    "Ла Лига",
    "Лига чемпионов",
]


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_database() -> FAJDatabase:
    return FAJDatabase()


# ============================================================
# SAFE HELPERS
# ============================================================

def object_to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    try:
        return dict(value)
    except Exception:
        pass

    if hasattr(value, "__dict__"):
        try:
            return dict(value.__dict__)
        except Exception:
            pass

    return {}


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def clean_score(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    if ":" not in text:
        return None

    parts = text.split(":", 1)

    if len(parts) != 2:
        return None

    home = safe_int(parts[0].strip())
    away = safe_int(parts[1].strip())

    if home is None or away is None:
        return None

    if home < 0 or away < 0:
        return None

    return f"{home}:{away}"


def score_to_tuple(value: Any) -> Tuple[Optional[int], Optional[int]]:
    score = clean_score(value)

    if score is None:
        return None, None

    home, away = score.split(":")

    return safe_int(home), safe_int(away)


def winner_from_score(
    home_goals: Optional[int],
    away_goals: Optional[int],
) -> Optional[str]:

    if home_goals is None or away_goals is None:
        return None

    if home_goals > away_goals:
        return "home"

    if home_goals < away_goals:
        return "away"

    return "draw"


def winner_label(value: Optional[str]) -> str:
    return {
        "home": "П1",
        "draw": "X",
        "away": "П2",
    }.get(value, "—")


# ============================================================
# SCORE ACCURACY
# ============================================================

def score_accuracy(
    predicted_score: Optional[str],
    actual_score: Optional[str],
) -> str:

    predicted_home, predicted_away = score_to_tuple(predicted_score)
    actual_home, actual_away = score_to_tuple(actual_score)

    if (
        predicted_home is None
        or predicted_away is None
        or actual_home is None
        or actual_away is None
    ):
        return "⚪ Нет прогноза"

    # --------------------------------------------------------
    # EXACT
    # --------------------------------------------------------

    if (
        predicted_home == actual_home
        and predicted_away == actual_away
    ):
        return "🎯 Точный счёт"

    # --------------------------------------------------------
    # NEAR
    # --------------------------------------------------------

    home_error = abs(predicted_home - actual_home)
    away_error = abs(predicted_away - actual_away)

    if home_error <= 1 and away_error <= 1:
        return "🟢 Почти угадал"

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    predicted_winner = winner_from_score(
        predicted_home,
        predicted_away,
    )

    actual_winner = winner_from_score(
        actual_home,
        actual_away,
    )

    if predicted_winner == actual_winner:
        return "🟡 Угадан исход"

    return "🔴 Не угадан"


def score_accuracy_rank(status: str) -> int:
    """
    Используется для итоговой статистики.

    4 = точный счёт
    3 = почти
    2 = исход
    1 = не угадан
    0 = нет прогноза
    """

    if status == "🎯 Точный счёт":
        return 4

    if status == "🟢 Почти угадал":
        return 3

    if status == "🟡 Угадан исход":
        return 2

    if status == "🔴 Не угадан":
        return 1

    return 0


# ============================================================
# PREDICTION HELPERS
# ============================================================

def extract_prediction_score(
    prediction: Dict[str, Any],
) -> Optional[str]:

    if not prediction:
        return None

    fields = (
        "predicted_score",
        "score",
        "faj_score",
        "most_likely_score",
        "prediction_score",
        "exact_score",
    )

    for field in fields:
        value = prediction.get(field)

        if value is None:
            continue

        score = clean_score(value)

        if score:
            return score

    return None


def get_expert_score(
    expert: Optional[Dict[str, Any]],
) -> Optional[str]:

    if not expert:
        return None

    for field in (
        "score",
        "expert_score",
        "predicted_score",
    ):
        value = expert.get(field)

        if value is None:
            continue

        score = clean_score(value)

        if score:
            return score

    return None


def prediction_winner(
    prediction_score: Optional[str],
) -> Optional[str]:

    home, away = score_to_tuple(prediction_score)

    return winner_from_score(home, away)


# ============================================================
# DATABASE ACCESS
# ============================================================

def get_round_matches(
    db: FAJDatabase,
    round_id: int,
) -> List[Dict[str, Any]]:

    try:
        matches = db.get_matches(round_id)
    except Exception as exc:
        logger.exception("Ошибка получения матчей тура")
        st.error(f"Ошибка получения матчей: {exc}")
        return []

    result = []

    for match in matches or []:

        match_data = object_to_dict(match)

        if not match_data:
            continue

        home_id = match_data.get("home_team_id")
        away_id = match_data.get("away_team_id")

        try:
            home = db.get_team(home_id)
        except Exception:
            home = None

        try:
            away = db.get_team(away_id)
        except Exception:
            away = None

        home_data = object_to_dict(home)
        away_data = object_to_dict(away)

        match_data["home_name"] = (
            home_data.get("name")
            or match_data.get("home_team_name")
            or "?"
        )

        match_data["away_name"] = (
            away_data.get("name")
            or match_data.get("away_team_name")
            or "?"
        )

        result.append(match_data)

    return result


def get_match_result(
    db: FAJDatabase,
    match_id: int,
) -> Optional[Dict[str, Any]]:

    try:
        result = db.get_match_result(match_id)
    except Exception as exc:
        logger.warning(
            "Ошибка получения результата %s: %s",
            match_id,
            exc,
        )
        return None

    if not result:
        return None

    return object_to_dict(result)


# ============================================================
# get_latest_prediction — ИСПРАВЛЕНА ВЕРСИЯ
# ============================================================

def get_latest_prediction(
    db: FAJDatabase,
    match_id: int,
) -> Optional[Dict[str, Any]]:

    """
    Получает последний прогноз FAJ для матча.

    ПОРЯДОК ПОИСКА:
        1. predictions (полные прогнозы с вероятностями)
        2. match_predictions (xG/lambda слой)

    ВАЖНО:
        prediction_manager.save_prediction() сохраняет в predictions
        match_manager.save_match_prediction() сохраняет в match_predictions

    ОБА ИСТОЧНИКА МОГУТ СОДЕРЖАТЬ ПРОГНОЗЫ.
    """

    # --------------------------------------------------------
    # 1. ПЫТАЕМСЯ ПОЛУЧИТЬ ИЗ predictions
    # --------------------------------------------------------

    try:
        prediction = db.get_latest_prediction(match_id)
        if prediction:
            data = object_to_dict(prediction)
            if data:
                logger.debug(
                    "FAJ prediction found in predictions for match_id=%s",
                    match_id
                )
                return data
    except Exception as exc:
        logger.debug(
            "get_latest_prediction from predictions failed for match_id=%s: %s",
            match_id,
            exc
        )

    # --------------------------------------------------------
    # 2. ПЫТАЕМСЯ ПОЛУЧИТЬ ИЗ match_predictions
    # --------------------------------------------------------

    try:
        match_pred = db.get_match_prediction(match_id)
        if match_pred:
            data = object_to_dict(match_pred)
            if data:
                logger.debug(
                    "FAJ prediction found in match_predictions for match_id=%s",
                    match_id
                )

                # Преобразуем в формат, ожидаемый round_complete
                # match_predictions содержит xG, но НЕ содержит счёт
                # Поэтому predicted_score остаётся None
                return {
                    "id": data.get("id"),
                    "match_id": data.get("match_id"),
                    "home_xg": data.get("xg_home"),
                    "away_xg": data.get("xg_away"),
                    "predicted_score": None,   # Нет счёта в match_predictions
                    "score": None,
                    "faj_xg_home": data.get("xg_home"),
                    "faj_xg_away": data.get("xg_away"),
                    "model_version": data.get("model_version", "v12.1"),
                    "source": "match_predictions",
                    "prediction_status": "active",
                }
    except Exception as exc:
        logger.debug(
            "get_match_prediction from match_predictions failed for match_id=%s: %s",
            match_id,
            exc
        )

    logger.debug(
        "No FAJ prediction found for match_id=%s in predictions or match_predictions",
        match_id
    )

    return None


def get_latest_expert(
    db: FAJDatabase,
    match_id: int,
) -> Optional[Dict[str, Any]]:

    try:
        predictions = db.get_expert_predictions(match_id)
    except Exception as exc:
        logger.warning(
            "Ошибка получения экспертного прогноза %s: %s",
            match_id,
            exc,
        )
        return None

    if not predictions:
        return None

    return object_to_dict(predictions[0])


def is_result_locked(
    db: FAJDatabase,
    match_id: int,
) -> bool:

    try:
        return bool(db.is_result_locked(match_id))
    except Exception:
        result = get_match_result(db, match_id)

        if not result:
            return False

        return result.get("fact_status") == "locked"


# ============================================================
# SEASONS
# ============================================================

def get_seasons_for_league(
    db: FAJDatabase,
    league: str,
) -> List[Dict[str, Any]]:

    try:
        seasons = db.get_seasons()
    except Exception as exc:
        st.error(f"Ошибка получения сезонов: {exc}")
        return []

    result = []

    for season in seasons or []:

        data = object_to_dict(season)

        if data.get("league") == league:
            result.append(data)

    return result


def season_label(season: Dict[str, Any]) -> str:

    name = season.get("name")

    if name:
        return str(name)

    season_id = season.get("id")

    return f"Сезон {season_id}"


# ============================================================
# ROUND SELECTION
# ============================================================

def get_rounds_for_season(
    db: FAJDatabase,
    season_id: int,
) -> List[Dict[str, Any]]:

    try:
        rounds = db.get_rounds(season_id)
    except Exception as exc:
        st.error(f"Ошибка получения туров: {exc}")
        return []

    result = []

    for round_item in rounds or []:

        data = object_to_dict(round_item)

        if data.get("id") is None:
            continue

        if data.get("round_number") is None:
            continue

        result.append(data)

    result.sort(
        key=lambda x: safe_int(x.get("round_number")) or 0
    )

    return result


# ============================================================
# ROUND REPORT
# ============================================================

def build_match_report(
    db: FAJDatabase,
    match: Dict[str, Any],
) -> Dict[str, Any]:

    match_id = safe_int(match.get("id"))

    result = (
        get_match_result(db, match_id)
        if match_id is not None
        else None
    )

    prediction = (
        get_latest_prediction(db, match_id)
        if match_id is not None
        else None
    )

    expert = (
        get_latest_expert(db, match_id)
        if match_id is not None
        else None
    )

    result = result or {}
    prediction = prediction or {}

    actual_home = safe_int(result.get("home_goals"))
    actual_away = safe_int(result.get("away_goals"))

    actual_score = None

    if actual_home is not None and actual_away is not None:
        actual_score = f"{actual_home}:{actual_away}"

    faj_score = extract_prediction_score(prediction)
    expert_score = get_expert_score(expert)

    actual_winner = winner_from_score(
        actual_home,
        actual_away,
    )

    faj_winner = prediction_winner(faj_score)
    expert_winner = prediction_winner(expert_score)

    faj_accuracy = score_accuracy(
        faj_score,
        actual_score,
    )

    expert_accuracy = score_accuracy(
        expert_score,
        actual_score,
    )

    return {
        "match_id": match_id,
        "home": match.get("home_name", "?"),
        "away": match.get("away_name", "?"),

        "actual_score": actual_score,
        "actual_winner": actual_winner,

        "faj_score": faj_score,
        "faj_winner": faj_winner,
        "faj_accuracy": faj_accuracy,

        "expert_score": expert_score,
        "expert_winner": expert_winner,
        "expert_accuracy": expert_accuracy,

        "prediction": prediction,
        "expert": expert,
        "result": result,

        "locked": (
            is_result_locked(db, match_id)
            if match_id is not None
            else False
        ),
    }


# ============================================================
# STANDINGS
# ============================================================

def update_standing(
    standings: Dict[int, Dict[str, Any]],
    team_id: int,
    team_name: str,
    goals_for: int,
    goals_against: int,
) -> None:

    if team_id not in standings:

        standings[team_id] = {
            "team_id": team_id,
            "team": team_name,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "points": 0,
        }

    row = standings[team_id]

    row["played"] += 1
    row["gf"] += goals_for
    row["ga"] += goals_against
    row["gd"] = row["gf"] - row["ga"]

    if goals_for > goals_against:

        row["wins"] += 1
        row["points"] += 3

    elif goals_for == goals_against:

        row["draws"] += 1
        row["points"] += 1

    else:

        row["losses"] += 1


def build_standings(
    db: FAJDatabase,
    matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    standings: Dict[int, Dict[str, Any]] = {}

    for match in matches:

        match_id = safe_int(match.get("id"))

        if match_id is None:
            continue

        result = get_match_result(db, match_id)

        if not result:
            continue

        home_goals = safe_int(result.get("home_goals"))
        away_goals = safe_int(result.get("away_goals"))

        if home_goals is None or away_goals is None:
            continue

        home_id = safe_int(match.get("home_team_id"))
        away_id = safe_int(match.get("away_team_id"))

        if home_id is None or away_id is None:
            continue

        home_name = match.get("home_name", "?")
        away_name = match.get("away_name", "?")

        update_standing(
            standings,
            home_id,
            home_name,
            home_goals,
            away_goals,
        )

        update_standing(
            standings,
            away_id,
            away_name,
            away_goals,
            home_goals,
        )

    rows = list(standings.values())

    rows.sort(
        key=lambda x: (
            -x["points"],
            -x["gd"],
            -x["gf"],
            x["team"].lower(),
        )
    )

    for index, row in enumerate(rows, start=1):
        row["position"] = index

    return rows


def render_standings(
    db: FAJDatabase,
    matches: List[Dict[str, Any]],
) -> None:

    st.subheader("🏆 Турнирная таблица")

    standings = build_standings(db, matches)

    if not standings:

        st.info(
            "Недостаточно фактических результатов "
            "для построения таблицы."
        )

        return

    table = []

    for row in standings:

        table.append(
            {
                "#": row["position"],
                "Команда": row["team"],
                "И": row["played"],
                "В": row["wins"],
                "Н": row["draws"],
                "П": row["losses"],
                "ЗМ": row["gf"],
                "ПМ": row["ga"],
                "РМ": row["gd"],
                "О": row["points"],
            }
        )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# ROUND SUMMARY
# ============================================================

def calculate_summary(
    reports: List[Dict[str, Any]],
) -> Dict[str, Any]:

    summary = {
        "matches": len(reports),

        "faj_exact": 0,
        "faj_near": 0,
        "faj_result": 0,
        "faj_wrong": 0,
        "faj_missing": 0,

        "expert_exact": 0,
        "expert_near": 0,
        "expert_result": 0,
        "expert_wrong": 0,
        "expert_missing": 0,
    }

    for report in reports:

        faj = report["faj_accuracy"]
        expert = report["expert_accuracy"]

        if faj == "🎯 Точный счёт":
            summary["faj_exact"] += 1

        elif faj == "🟢 Почти угадал":
            summary["faj_near"] += 1

        elif faj == "🟡 Угадан исход":
            summary["faj_result"] += 1

        elif faj == "🔴 Не угадан":
            summary["faj_wrong"] += 1

        else:
            summary["faj_missing"] += 1

        if expert == "🎯 Точный счёт":
            summary["expert_exact"] += 1

        elif expert == "🟢 Почти угадал":
            summary["expert_near"] += 1

        elif expert == "🟡 Угадан исход":
            summary["expert_result"] += 1

        elif expert == "🔴 Не угадан":
            summary["expert_wrong"] += 1

        else:
            summary["expert_missing"] += 1

    return summary


def render_summary(
    reports: List[Dict[str, Any]],
) -> None:

    summary = calculate_summary(reports)

    st.subheader("📊 Итоги тура")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown("### 🤖 FAJ")

        st.metric(
            "🎯 Точный счёт",
            summary["faj_exact"],
        )

        st.metric(
            "🟢 Почти угадал",
            summary["faj_near"],
        )

        st.metric(
            "🟡 Угадан исход",
            summary["faj_result"],
        )

        st.metric(
            "🔴 Не угадан",
            summary["faj_wrong"],
        )

    with col2:

        st.markdown("### 🧠 Директор")

        st.metric(
            "🎯 Точный счёт",
            summary["expert_exact"],
        )

        st.metric(
            "🟢 Почти угадал",
            summary["expert_near"],
        )

        st.metric(
            "🟡 Угадан исход",
            summary["expert_result"],
        )

        st.metric(
            "🔴 Не угадан",
            summary["expert_wrong"],
        )


# ============================================================
# MATCH REPORT CARD
# ============================================================

def render_match_report(
    report: Dict[str, Any],
    index: int,
) -> None:

    home = report["home"]
    away = report["away"]

    st.markdown(
        f"### ⚽ {home} — {away}"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown("**🤖 FAJ**")

        st.write(
            f"Прогноз: **{report['faj_score'] or '—'}**"
        )

        st.write(
            f"Исход: **{winner_label(report['faj_winner'])}**"
        )

        st.write(report["faj_accuracy"])

    with col2:

        st.markdown("**🧠 Директор**")

        st.write(
            f"Прогноз: **{report['expert_score'] or '—'}**"
        )

        st.write(
            f"Исход: **{winner_label(report['expert_winner'])}**"
        )

        st.write(report["expert_accuracy"])

    with col3:

        st.markdown("**🏁 ФАКТ**")

        st.metric(
            "Счёт",
            report["actual_score"] or "—",
        )

        st.write(
            f"Исход: **{winner_label(report['actual_winner'])}**"
        )

        if report["locked"]:
            st.success("🔒 LOCKED")
        else:
            st.warning("🔓 Не заблокирован")

    prediction = report.get("prediction") or {}
    result = report.get("result") or {}

    # --------------------------------------------------------
    # XG
    # --------------------------------------------------------

    faj_home_xg = (
        prediction.get("home_xg")
        if prediction.get("home_xg") is not None
        else prediction.get("faj_xg_home")
    )

    faj_away_xg = (
        prediction.get("away_xg")
        if prediction.get("away_xg") is not None
        else prediction.get("faj_xg_away")
    )

    actual_home_xg = result.get("home_xg")
    actual_away_xg = result.get("away_xg")

    if (
        faj_home_xg is not None
        or faj_away_xg is not None
        or actual_home_xg is not None
        or actual_away_xg is not None
    ):

        st.markdown("**🎯 xG**")

        xg_col1, xg_col2 = st.columns(2)

        with xg_col1:
            st.write(
                f"FAJ: "
                f"{faj_home_xg if faj_home_xg is not None else '—'}"
                f" : "
                f"{faj_away_xg if faj_away_xg is not None else '—'}"
            )

        with xg_col2:
            st.write(
                f"Факт: "
                f"{actual_home_xg if actual_home_xg is not None else '—'}"
                f" : "
                f"{actual_away_xg if actual_away_xg is not None else '—'}"
            )

    # --------------------------------------------------------
    # MATCH STATISTICS
    # --------------------------------------------------------

    statistic_fields = [
        ("Владение", "home_possession", "away_possession"),
        ("Удары", "home_shots", "away_shots"),
        (
            "Удары в створ",
            "home_shots_on_target",
            "away_shots_on_target",
        ),
        ("Угловые", "home_corners", "away_corners"),
        ("Передачи", "home_total_passes", "away_total_passes"),
        (
            "Точность передач",
            "home_pass_accuracy",
            "away_pass_accuracy",
        ),
        (
            "Точные передачи",
            "home_accurate_passes",
            "away_accurate_passes",
        ),
        ("Отборы", "home_tackles", "away_tackles"),
    ]

    rows = []

    for name, home_key, away_key in statistic_fields:

        home_value = result.get(home_key)
        away_value = result.get(away_key)

        if home_value is None and away_value is None:
            continue

        rows.append(
            {
                "Показатель": name,
                home: home_value if home_value is not None else "—",
                away: away_value if away_value is not None else "—",
            }
        )

    if rows:

        with st.expander("📊 Статистика матча"):

            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
            )

    st.divider()


# ============================================================
# LEARNING
# ============================================================

def run_learning() -> Any:

    from app.learning_engine import run_learning

    # Исправлено: убран db_path
    return run_learning(force=False)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title="FAJ — Тур завершён",
        page_icon="🏁",
        layout="wide",
    )

    st.title("🏁 Тур завершён")

    st.caption(
        f"FAJ Platform {APP_VERSION} | "
        f"Round Complete {ROUND_COMPLETE_VERSION}"
    )

    db = get_database()

    # ========================================================
    # LEAGUE
    # ========================================================

    league = st.selectbox(
        "🏆 Лига",
        LEAGUES,
        key="round_complete_league",
    )

    # ========================================================
    # SEASON
    # ========================================================

    seasons = get_seasons_for_league(
        db,
        league,
    )

    if not seasons:

        st.warning(
            f"Для лиги «{league}» сезоны не найдены."
        )

        return

    season_map = {
        season_label(season): season
        for season in seasons
    }

    selected_season_label = st.selectbox(
        "📅 Сезон",
        list(season_map.keys()),
        key="round_complete_season",
    )

    selected_season = season_map[
        selected_season_label
    ]

    season_id = safe_int(
        selected_season.get("id")
    )

    if season_id is None:

        st.error("Не удалось определить ID сезона.")

        return

    # ========================================================
    # ROUNDS
    # ========================================================

    rounds = get_rounds_for_season(
        db,
        season_id,
    )

    if not rounds:

        st.info(
            "В выбранном сезоне пока нет туров."
        )

        return

    round_map = {}

    for round_item in rounds:

        round_number = safe_int(
            round_item.get("round_number")
        )

        if round_number is None:
            continue

        round_id = safe_int(
            round_item.get("id")
        )

        if round_id is None:
            continue

        round_map[
            f"Тур {round_number}"
        ] = round_id

    if not round_map:

        st.info("Туры не найдены.")

        return

    selected_round_label = st.selectbox(
        "🔢 Тур",
        list(round_map.keys()),
        key="round_complete_round",
    )

    round_id = round_map[
        selected_round_label
    ]

    # ========================================================
    # HEADER
    # ========================================================

    st.markdown("---")

    st.markdown(
        f"## {league} — {selected_round_label}"
    )

    # ========================================================
    # MATCHES
    # ========================================================

    matches = get_round_matches(
        db,
        round_id,
    )

    if not matches:

        st.warning(
            "В выбранном туре матчи не найдены."
        )

        return

    # ========================================================
    # FACT COMPLETENESS
    # ========================================================

    reports = []

    filled_count = 0
    locked_count = 0

    for match in matches:

        report = build_match_report(
            db,
            match,
        )

        reports.append(report)

        if report["actual_score"] is not None:
            filled_count += 1

        if report["locked"]:
            locked_count += 1

    total_matches = len(matches)

    all_filled = (
        filled_count == total_matches
        and total_matches > 0
    )

    # ========================================================
    # STATUS
    # ========================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Матчей",
            total_matches,
        )

    with col2:
        st.metric(
            "Факты",
            f"{filled_count}/{total_matches}",
        )

    with col3:
        st.metric(
            "LOCK",
            f"{locked_count}/{total_matches}",
        )

    with col4:

        if all_filled:
            st.success("🟢 Тур готов")
        else:
            st.error("🔴 Тур не завершён")

    # ========================================================
    # ДИАГНОСТИКА: ГДЕ ПРОГНОЗЫ?
    # ========================================================

    st.markdown("---")
    st.subheader("🔍 Диагностика прогнозов")

    for match in matches:
        match_id = safe_int(match.get("id"))
        if match_id is None:
            continue
        
        # Проверяем predictions
        try:
            preds = db.get_predictions_by_match(match_id)
            preds_count = len(preds) if preds else 0
        except Exception:
            preds_count = 0
        
        # Проверяем match_predictions
        try:
            match_preds = db.get_match_predictions(match_id)
            match_preds_count = len(match_preds) if match_preds else 0
        except Exception:
            match_preds_count = 0
        
        home = match.get("home_name", "?")
        away = match.get("away_name", "?")
        
        st.write(
            f"**{home} — {away}** | "
            f"predictions: {preds_count} | "
            f"match_predictions: {match_preds_count}"
        )
        
        # Если есть прогнозы в predictions — покажем первый
        if preds_count > 0:
            try:
                first = object_to_dict(preds[0])
                st.write(
                    f"  → predictions[0]: "
                    f"П1={first.get('home_win', '—')} | "
                    f"X={first.get('draw', '—')} | "
                    f"П2={first.get('away_win', '—')}"
                )
            except Exception:
                pass
        
        # Если есть прогнозы в match_predictions — покажем первый
        if match_preds_count > 0:
            try:
                first = object_to_dict(match_preds[0])
                st.write(
                    f"  → match_predictions[0]: "
                    f"xG {first.get('xg_home', '—')} — {first.get('xg_away', '—')}"
                )
            except Exception:
                pass

    st.markdown("---")

    # ========================================================
    # MATCH REPORTS
    # ========================================================

    if not all_filled:

        st.warning(
            f"⚠️ Не все фактические результаты внесены: "
            f"{filled_count}/{total_matches}."
        )

        st.info(
            "Сначала завершите ввод фактов на странице "
            "«Импорт фактов»."
        )

    st.subheader("📋 Матчи тура")

    for index, report in enumerate(reports):

        render_match_report(
            report,
            index,
        )

    # ========================================================
    # SUMMARY
    #

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================
FAJ Platform v12.1
IMPORT FACTS
===========================================================
Назначение:
    Импорт фактических результатов и статистики матчей.
ЦЕПОЧКА:
    Тур
      ↓
    Матчи
      ↓
    Ссылка на матч
      ↓
    RPL Statistics Parser
      ↓
    Факт
      ↓
    FAJ Prediction
      ↓
    Expert Prediction
      ↓
    Validation
      ↓
    Gold Dataset
      ↓
    Lock
      ↓
    Learning Engine
ПРИНЦИПЫ:
    - SQLite only
    - database.py — единственный слой работы с БД
    - никаких прямых SQL
    - ничего не удаляется
    - существующие результаты не перезаписываются,
      если они уже locked
    - None != 0
    - экспертный прогноз можно вводить вручную
    - обучение запускается только отдельной кнопкой
===========================================================
"""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import requests
import streamlit as st
from bs4 import BeautifulSoup
from app.database import FAJDatabase
from app.parsers.rpl_stats_parser import RPLStatsParser
from app.parsers.rpl_normalizer import normalize_team_names
from app.config import config
logger = logging.getLogger(__name__)
# ============================================================
# CONFIG
# ============================================================
PAGE_TITLE = "FAJ — Импорт фактов"
PARSER_VERSION = "v1.0"
DEFAULT_EXPERT_NAME = "Директор"
FINISHED_STATUSES = {
    "finished",
    "completed",
    "played",
    "ft",
    "ended",
    "full time",
}
# ============================================================
# DATABASE
# ============================================================
@st.cache_resource
def get_database() -> FAJDatabase:
    return FAJDatabase()
# ============================================================
# HELPERS
# ============================================================
def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(
            str(value).replace(",", ".")
        )
    except (TypeError, ValueError):
        return None
def _format_score(
    home: Optional[int],
    away: Optional[int],
) -> str:
    if home is None or away is None:
        return "—"
    return f"{home}:{away}"
def _winner_from_score(
    home: Optional[int],
    away: Optional[int],
) -> Optional[str]:
    if home is None or away is None:
        return None
    if home > away:
        return "home"
    if home < away:
        return "away"
    return "draw"
def _btts_from_score(
    home: Optional[int],
    away: Optional[int],
) -> Optional[int]:
    if home is None or away is None:
        return None
    return int(
        home > 0 and away > 0
    )
def _over25_from_score(
    home: Optional[int],
    away: Optional[int],
) -> Optional[int]:
    if home is None or away is None:
        return None
    return int(
        (home + away) > 2.5
    )
def _over35_from_score(
    home: Optional[int],
    away: Optional[int],
) -> Optional[int]:
    if home is None or away is None:
        return None
    return int(
        (home + away) > 3.5
    )
def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = re.sub(
        r"\s+",
        " ",
        text,
    )
    return text.strip()
# ============================================================
# MATCH SCORE FROM URL
# ============================================================
def parse_score_from_url(
    url: str,
) -> Optional[Tuple[int, int]]:
    """
    Получает счёт непосредственно со страницы матча.
    Используется как дополнительный механизм,
    потому что RPLStatsParser отвечает за статистику,
    а не за результат.
    """
    if not url:
        return None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/128.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )
        text = _clean_text(
            soup.get_text(
                " ",
                strip=True,
            )
        )
        patterns = [
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
        ]
        for pattern in patterns:
            matches = re.findall(
                pattern,
                text,
            )
            for home, away in matches:
                home_goals = _safe_int(home)
                away_goals = _safe_int(away)
                if (
                    home_goals is None
                    or away_goals is None
                ):
                    continue
                # Защита от случайного совпадения
                # с годами, временем и т.п.
                if (
                    0 <= home_goals <= 15
                    and 0 <= away_goals <= 15
                ):
                    return (
                        home_goals,
                        away_goals,
                    )
    except Exception as exc:
        logger.warning(
            "Cannot parse score from URL: %s",
            exc,
        )
    return None
# ============================================================
# FAJ PREDICTION HELPERS
# ============================================================
def _get_prediction_score(
    prediction: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Получает именно прогнозируемый счёт.
    НИКОГДА не превращает вероятности
    home_win/draw/away_win в счёт.
    """
    if not prediction:
        return None
    candidates = [
        prediction.get("predicted_score"),
        prediction.get("score"),
        prediction.get("exact_score"),
        prediction.get("most_likely_score"),
        prediction.get("predicted_result"),
    ]
    for value in candidates:
        if value is None:
            continue
        value = str(value).strip()
        if re.match(
            r"^\d{1,2}\s*[:\-]\s*\d{1,2}$",
            value,
        ):
            value = value.replace(
                "-",
                ":",
            )
            return value
    return None
def _get_prediction_xg(
    prediction: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    home_xg = prediction.get(
        "predicted_home_xg"
    )
    if home_xg is None:
        home_xg = prediction.get(
            "home_xg"
        )
    if home_xg is None:
        home_xg = prediction.get(
            "xg_home"
        )
    away_xg = prediction.get(
        "predicted_away_xg"
    )
    if away_xg is None:
        away_xg = prediction.get(
            "away_xg"
        )
    if away_xg is None:
        away_xg = prediction.get(
            "xg_away"
        )
    return (
        _safe_float(home_xg),
        _safe_float(away_xg),
    )
def _get_prediction_probability(
    prediction: Dict[str, Any],
) -> Tuple[float, float, float]:
    home = _safe_float(
        prediction.get("home_win")
    )
    draw = _safe_float(
        prediction.get("draw")
    )
    away = _safe_float(
        prediction.get("away_win")
    )
    return (
        home if home is not None else 0.0,
        draw if draw is not None else 0.0,
        away if away is not None else 0.0,
    )
def _prediction_winner(
    prediction: Dict[str, Any],
) -> Optional[str]:
    home, draw, away = (
        _get_prediction_probability(
            prediction
        )
    )
    values = {
        "home": home,
        "draw": draw,
        "away": away,
    }
    return max(
        values,
        key=values.get,
    )
def _prediction_btts(
    prediction: Dict[str, Any],
) -> Optional[int]:
    value = prediction.get("btts")
    if value is None:
        extended = prediction.get(
            "extended",
            {},
        )
        if isinstance(
            extended,
            dict,
        ):
            btts = extended.get(
                "btts",
                {},
            )
            if isinstance(
                btts,
                dict,
            ):
                value = btts.get(
                    "yes"
                )
    value = _safe_float(value)
    if value is None:
        return None
    return int(
        value >= 0.5
    )
def _prediction_over25(
    prediction: Dict[str, Any],
) -> Optional[int]:
    value = prediction.get(
        "over25"
    )
    if value is None:
        value = prediction.get(
            "over_2_5"
        )
    if value is None:
        extended = prediction.get(
            "extended",
            {},
        )
        if isinstance(
            extended,
            dict,
        ):
            total = extended.get(
                "total",
                {},
            )
            if isinstance(
                total,
                dict,
            ):
                value = total.get(
                    "over_2_5"
                )
    value = _safe_float(value)
    if value is None:
        return None
    return int(
        value >= 0.5
    )
def _prediction_confidence(
    prediction: Dict[str, Any],
) -> int:
    confidence = prediction.get(
        "confidence",
        50,
    )
    if isinstance(
        confidence,
        dict,
    ):
        confidence = confidence.get(
            "overall",
            0.5,
        )
    confidence = _safe_float(
        confidence
    )
    if confidence is None:
        return 50
    if confidence <= 1.0:
        confidence *= 100
    return int(
        max(
            0,
            min(
                confidence,
                100,
            ),
        )
    )
# ============================================================
# EXPERT HELPERS
# ============================================================
def _expert_score(
    expert: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not expert:
        return None
    candidates = [
        expert.get("score"),
        expert.get("expert_score"),
        expert.get("predicted_score"),
    ]
    for value in candidates:
        if value is None:
            continue
        value = str(value).strip()
        if re.match(
            r"^\d{1,2}\s*[:\-]\s*\d{1,2}$",
            value,
        ):
            return value.replace(
                "-",
                ":",
            )
    return None
def _parse_score_string(
    score: Optional[str],
) -> Tuple[
    Optional[int],
    Optional[int],
]:
    if not score:
        return None, None
    match = re.match(
        r"^\s*(\d{1,2})\s*[:\-]\s*(\d{1,2})\s*$",
        str(score),
    )
    if not match:
        return None, None
    return (
        _safe_int(match.group(1)),
        _safe_int(match.group(2)),
    )
# ============================================================
# MATCH DATA
# ============================================================
def get_rounds(
    db: FAJDatabase,
    season_id: Optional[int],
) -> List[Dict[str, Any]]:
    try:
        if season_id is not None:
            return db.get_rounds(
                season_id
            )
        return db.get_rounds()
    except Exception as exc:
        logger.exception(
            "Cannot get rounds: %s",
            exc,
        )
        return []
def get_current_season_id(
    db: FAJDatabase,
) -> Optional[int]:
    try:
        seasons = db.get_seasons()
        for season in seasons:
            name = str(
                season.get(
                    "name",
                    "",
                )
            )
            if (
                "2026-2027" in name
                or "2026/2027" in name
            ):
                return season.get(
                    "id"
                )
    except Exception as exc:
        logger.exception(
            "Cannot detect season: %s",
            exc,
        )
    return None
def get_round_matches(
    db: FAJDatabase,
    round_id: int,
) -> List[Dict[str, Any]]:
    matches = []
    try:
        raw_matches = db.get_matches(
            round_id
        )
        for match in raw_matches:
            item = dict(
                match
            )
            home = db.get_team(
                item.get(
                    "home_team_id"
                )
            )
            away = db.get_team(
                item.get(
                    "away_team_id"
                )
            )
            item["home_team"] = (
                home.get("name")
                if home
                else None
            )
            item["away_team"] = (
                away.get("name")
                if away
                else None
            )
            matches.append(
                item
            )
    except Exception as exc:
        logger.exception(
            "Cannot get round matches: %s",
            exc,
        )
    return matches
# ============================================================
# FETCH FACTS
# ============================================================
def fetch_match_facts(
    url: str,
) -> Optional[Dict[str, Any]]:
    if not url:
        return None
    url = url.strip()
    if not (
        url.startswith(
            "http://"
        )
        or url.startswith(
            "https://"
        )
    ):
        raise ValueError(
            "Ссылка должна начинаться с http:// или https://"
        )
    stats_parser = RPLStatsParser()
    stats = (
        stats_parser.parse_match_page(
            url
        )
    )
    score = parse_score_from_url(
        url
    )
    result = {
        "url": url,
        "home_goals": None,
        "away_goals": None,
        "stats": stats or {},
        "parser_source": url,
        "parser_version": PARSER_VERSION,
        "data_quality": 0.0,
    }
    if score:
        result[
            "home_goals"
        ] = score[0]
        result[
            "away_goals"
        ] = score[1]
    quality_fields = [
        result.get(
            "home_goals"
        ),
        result.get(
            "away_goals"
        ),
    ]
    stats_dict = result.get(
        "stats",
        {},
    )
    for key in (
        "home_xg",
        "away_xg",
        "home_shots",
        "away_shots",
        "home_shots_on_target",
        "away_shots_on_target",
        "home_possession",
        "away_possession",
        "home_corners",
        "away_corners",
        "home_yellow_cards",
        "away_yellow_cards",
    ):
        quality_fields.append(
            stats_dict.get(
                key
            )
        )
    available = sum(
        value is not None
        for value in quality_fields
    )
    total = len(
        quality_fields
    )
    result[
        "data_quality"
    ] = (
        available / total
        if total
        else 0.0
    )
    return result
# ============================================================
# SAVE FACTS
# ============================================================
def save_match_facts(
    db: FAJDatabase,
    match: Dict[str, Any],
    fact: Dict[str, Any],
    expert_name: str,
    expert_score: Optional[str],
    expert_comment: str,
    expert_confidence: int,
) -> Dict[str, Any]:
    match_id = match.get(
        "id"
    )
    if not match_id:
        raise ValueError(
            "У матча отсутствует ID"
        )
    home_goals = fact.get(
        "home_goals"
    )
    away_goals = fact.get(
        "away_goals"
    )
    if (
        home_goals is None
        or away_goals is None
    ):
        raise ValueError(
            "Не удалось определить фактический счёт."
        )
    # --------------------------------------------------------
    # LOCK CHECK
    # --------------------------------------------------------
    try:
        if db.is_result_locked(
            match_id
        ):
            raise ValueError(
                "Результат этого матча уже защищён (LOCK)."
            )
    except AttributeError:
        pass
    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------
    db.update_result(
        match_id=match_id,
        home_score=home_goals,
        away_score=away_goals,
        lock=False,
    )
    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------
    stats = dict(
        fact.get(
            "stats",
            {},
        )
    )
    stats[
        "parser_source"
    ] = fact.get(
        "parser_source"
    )
    stats[
        "parser_version"
    ] = fact.get(
        "parser_version",
        PARSER_VERSION,
    )
    stats[
        "data_quality"
    ] = fact.get(
        "data_quality",
        0.0,
    )
    db.update_match_stats(
        match_id,
        stats,
    )
    # --------------------------------------------------------
    # EXPERT
    # --------------------------------------------------------
    expert_id = None
    if expert_score:
        expert_id = (
            db.save_expert_prediction(
                match_id=match_id,
                expert_name=(
                    expert_name
                    or DEFAULT_EXPERT_NAME
                ),
                score=expert_score,
                comment=(
                    expert_comment
                    or ""
                ),
                confidence=int(
                    max(
                        0,
                        min(
                            expert_confidence,
                            100,
                        ),
                    )
                ),
            )
        )
    # --------------------------------------------------------
    # FAJ PREDICTION
    # --------------------------------------------------------
    faj_prediction = (
        db.get_latest_prediction(
            match_id
        )
    )
    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------
    validation_id = None
    if faj_prediction:
        prediction_id = (
            faj_prediction.get(
                "id"
            )
        )
        faj_score = (
            _get_prediction_score(
                faj_prediction
            )
        )
        predicted_home_xg, predicted_away_xg = (
            _get_prediction_xg(
                faj_prediction
            )
        )
        probability_home, probability_draw, probability_away = (
            _get_prediction_probability(
                faj_prediction
            )
        )
        predicted_winner = (
            _prediction_winner(
                faj_prediction
            )
        )
        predicted_btts = (
            _prediction_btts(
                faj_prediction
            )
        )
        predicted_over25 = (
            _prediction_over25(
                faj_prediction
            )
        )
        actual_winner = (
            _winner_from_score(
                home_goals,
                away_goals,
            )
        )
        actual_btts = (
            _btts_from_score(
                home_goals,
                away_goals,
            )
        )
        actual_over25 = (
            _over25_from_score(
                home_goals,
                away_goals,
            )
        )
        score_probability = (
            faj_prediction.get(
                "score_probability",
                0.0,
            )
        )
        confidence = (
            _prediction_confidence(
                faj_prediction
            )
        )
        risk = _safe_float(
            faj_prediction.get(
                "risk",
                0.0,
            )
        )
        if risk is None:
            risk = 0.0
        validation_data = {
            "match_id": match_id,
            "prediction_id": prediction_id,
            "match_prediction_id": (
                faj_prediction.get(
                    "match_prediction_id"
                )
            ),
            "predicted_score": (
                faj_score
            ),
            "actual_score": (
                _format_score(
                    home_goals,
                    away_goals,
                )
            ),
            "predicted_home_xg": (
                predicted_home_xg
            ),
            "actual_home_xg": (
                stats.get(
                    "home_xg"
                )
            ),
            "predicted_away_xg": (
                predicted_away_xg
            ),
            "actual_away_xg": (
                stats.get(
                    "away_xg"
                )
            ),
            "predicted_winner": (
                predicted_winner
            ),
            "actual_winner": (
                actual_winner
            ),
            "predicted_probability_home": (
                probability_home
            ),
            "predicted_probability_draw": (
                probability_draw
            ),
            "predicted_probability_away": (
                probability_away
            ),
            "score_probability": (
                score_probability
            ),
            "confidence": confidence,
            "risk": risk,
            "predicted_btts": (
                predicted_btts
            ),
            "actual_btts": (
                actual_btts
            ),
            "predicted_over25": (
                predicted_over25
            ),
            "actual_over25": (
                actual_over25
            ),
            "model_version": (
                faj_prediction.get(
                    "model_version",
                    getattr(
                        config,
                        "MODEL_VERSION",
                        "v12.1",
                    ),
                )
            ),
            "passport_version": (
                faj_prediction.get(
                    "passport_version",
                    "",
                )
            ),
            "parser_version": (
                fact.get(
                    "parser_version",
                    PARSER_VERSION,
                )
            ),
        }
        try:
            validation_id = (
                db.add_prediction_validation(
                    validation_data
                )
            )
        except Exception as exc:
            logger.exception(
                "Validation save failed: %s",
                exc,
            )
    # --------------------------------------------------------
    # GOLD DATASET
    # --------------------------------------------------------
    gold_id = None
    home_team = (
        match.get(
            "home_team"
        )
        or ""
    )
    away_team = (
        match.get(
            "away_team"
        )
        or ""
    )
    actual_score = _format_score(
        home_goals,
        away_goals,
    )
    faj_score = None
    if faj_prediction:
        faj_score = (
            _get_prediction_score(
                faj_prediction
            )
        )
    expert_score_value = (
        expert_score
    )
    gold_data = {
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "match_date": (
            match.get(
                "date"
            )
            or match.get(
                "match_date"
            )
        ),
        "model_version": (
            faj_prediction.get(
                "model_version",
                getattr(
                    config,
                    "MODEL_VERSION",
                    "v12.1",
                ),
            )
            if faj_prediction
            else getattr(
                config,
                "MODEL_VERSION",
                "v12.1",
            )
        ),
        "faj_score": faj_score,
        "faj_xg_home": (
            _get_prediction_xg(
                faj_prediction
            )[0]
            if faj_prediction
            else None
        ),
        "faj_xg_away": (
            _get_prediction_xg(
                faj_prediction
            )[1]
            if faj_prediction
            else None
        ),
        "faj_btts": (
            _prediction_btts(
                faj_prediction
            )
            if faj_prediction
            else None
        ),
        "faj_total_25": (
            _prediction_over25(
                faj_prediction
            )
            if faj_prediction
            else None
        ),
        "faj_total_35": (
            faj_prediction.get(
                "over35"
            )
            if faj_prediction
            else None
        ),
        "faj_confidence": (
            _prediction_confidence(
                faj_prediction
            )
            if faj_prediction
            else None
        ),
        "faj_rating_home": (
            faj_prediction.get(
                "home_rating"
            )
            if faj_prediction
            else None
        ),
        "faj_rating_away": (
            faj_prediction.get(
                "away_rating"
            )
            if faj_prediction
            else None
        ),
        "faj_pir_home": (
            faj_prediction.get(
                "home_pir"
            )
            if faj_prediction
            else None
        ),
        "faj_pir_away": (
            faj_prediction.get(
                "away_pir"
            )
            if faj_prediction
            else None
        ),
        "faj_style_home": (
            faj_prediction.get(
                "home_style"
            )
            if faj_prediction
            else None
        ),
        "faj_style_away": (
            faj_prediction.get(
                "away_style"
            )
            if faj_prediction
            else None
        ),
        "expert_score": (
            expert_score_value
        ),
        "expert_reasoning": (
            expert_comment
            or ""
        ),
        "actual_score": actual_score,
        "actual_xg_home": (
            stats.get(
                "home_xg"
            )
        ),
        "actual_xg_away": (
            stats.get(
                "away_xg"
            )
        ),
        "actual_btts": (
            _btts_from_score(
                home_goals,
                away_goals,
            )
        ),
        "actual_total_25": (
            _over25_from_score(
                home_goals,
                away_goals,
            )
        ),
        "actual_total_35": (
            _over35_from_score(
                home_goals,
                away_goals,
            )
        ),
        "actual_home_goals": (
            home_goals
        ),
        "actual_away_goals": (
            away_goals
        ),
        "status": "completed",
    }
    try:
        gold_id = db.upsert_gold(
            gold_data
        )
    except Exception as exc:
        logger.exception(
            "Gold save failed: %s",
            exc,
        )
    # --------------------------------------------------------
    # LOCK
    # --------------------------------------------------------
    try:
        db.lock_match_result(
            match_id
        )
    except Exception as exc:
        logger.warning(
            "Could not lock result %s: %s",
            match_id,
            exc,
        )
    if gold_id:
        try:
            db.lock_gold(
                gold_id
            )
        except Exception as exc:
            logger.warning(
                "Could not lock gold %s: %s",
                gold_id,
                exc,
            )
    return {
        "match_id": match_id,
        "expert_id": expert_id,
        "validation_id": validation_id,
        "gold_id": gold_id,
        "actual_score": actual_score,
        "faj_score": faj_score,
        "expert_score": expert_score_value,
    }
# ============================================================
# UI — FACT CARD
# ============================================================
def render_stats(
    stats: Dict[str, Any],
) -> None:
    st.markdown(
        "#### 📊 Статистика"
    )
    fields = [
        (
            "xG",
            "home_xg",
            "away_xg",
        ),
        (
            "Удары",
            "home_shots",
            "away_shots",
        ),
        (
            "Удары в створ",
            "home_shots_on_target",
            "away_shots_on_target",
        ),
        (
            "Владение %",
            "home_possession",
            "away_possession",
        ),
        (
            "Угловые",
            "home_corners",
            "away_corners",
        ),
        (
            "ЖК",
            "home_yellow_cards",
            "away_yellow_cards",
        ),
    ]
    for title, home_key, away_key in fields:
        home_value = stats.get(
            home_key
        )
        away_value = stats.get(
            away_key
        )
        col1, col2, col3 = st.columns(
            [2, 1, 1]
        )
        with col1:
            st.write(title)
        with col2:
            st.write(
                "—"
                if home_value is None
                else str(home_value)
            )
        with col3:
            st.write(
                "—"
                if away_value is None
                else str(away_value)
            )
def render_comparison(
    match: Dict[str, Any],
    fact: Optional[Dict[str, Any]],
    prediction: Optional[Dict[str, Any]],
    expert: Optional[Dict[str, Any]],
) -> None:
    st.markdown(
        "#### 🔎 Факт vs FAJ vs Эксперт"
    )
    home = match.get(
        "home_team",
        "Хозяева",
    )
    away = match.get(
        "away_team",
        "Гости",
    )
    faj_score = (
        _get_prediction_score(
            prediction
        )
        if prediction
        else None
    )
    expert_score = (
        _expert_score(
            expert
        )
        if expert
        else None
    )
    fact_score = None
    if fact:
        fact_score = _format_score(
            fact.get(
                "home_goals"
            ),
            fact.get(
                "away_goals"
            ),
        )
    st.table(
        [
            {
                "Источник": "Факт",
                home: fact_score or "—",
                away: "",
            },
            {
                "Источник": "FAJ",
                home: faj_score or "—",
                away: "",
            },
            {
                "Источник": "Эксперт",
                home: expert_score or "—",
                away: "",
            },
        ]
    )
# ============================================================
# UI — MAIN
# ============================================================
def main():
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="📥",
        layout="wide",
    )
    st.title(
        "📥 FAJ — Импорт фактов"
    )
    st.caption(
        "Результаты → статистика → эксперт → validation → Gold → обучение"
    )
    db = get_database()
    # ========================================================
    # SEASON
    # ========================================================
    season_id = get_current_season_id(
        db
    )
    if season_id is None:
        st.error(
            "❌ Сезон 2026-2027 не найден в БД."
        )
        st.stop()
    rounds = get_rounds(
        db,
        season_id,
    )
    if not rounds:
        st.warning(
            "⚠️ В БД нет туров."
        )
        st.info(
            "Сначала необходимо загрузить календарь туров."
        )
        st.stop()
    # ========================================================
    # ROUND SELECTOR
    # ========================================================
    round_options = {
        int(
            r.get(
                "round_number"
            )
        ): r.get(
            "id"
        )
        for r in rounds
        if r.get(
            "round_number"
        ) is not None
    }
    round_numbers = sorted(
        round_options.keys()
    )
    default_round = (
        st.session_state.get(
            "selected_round",
            round_numbers[0],
        )
    )
    if default_round not in round_options:
        default_round = round_numbers[0]
    selected_round = st.selectbox(
        "🏟️ Тур",
        round_numbers,
        index=round_numbers.index(
            default_round
        ),
        format_func=lambda x: f"Тур {x}",
    )
    st.session_state[
        "selected_round"
    ] = selected_round
    round_id = round_options[
        selected_round
    ]
    matches = get_round_matches(
        db,
        round_id,
    )
    if not matches:
        st.warning(
            "В выбранном туре нет матчей."
        )
        st.stop()
    st.markdown(
        f"### Тур {selected_round} — {len(matches)} матчей"
    )
    # ========================================================
    # SESSION STATE
    # ========================================================
    if (
        "import_facts"
        not in st.session_state
    ):
        st.session_state[
            "import_facts"
        ] = {}
    facts_state = st.session_state[
        "import_facts"
    ]
    # ========================================================
    # MATCH CARDS
    # ========================================================
    for index, match in enumerate(
        matches
    ):
        match_id = match.get(
            "id"
        )
        home_team = match.get(
            "home_team",
            "—",
        )
        away_team = match.get(
            "away_team",
            "—",
        )
        key_prefix = (
            f"fact_{match_id}"
        )
        if key_prefix not in facts_state:
            facts_state[
                key_prefix
            ] = {}
        state = facts_state[
            key_prefix
        ]
        st.divider()
        st.subheader(
            f"{index + 1}. {home_team} — {away_team}"
        )
        # ----------------------------------------------------
        # CURRENT RESULT STATUS
        # ----------------------------------------------------
        try:
            existing_result = (
                db.get_match_result(
                    match_id
                )
            )
        except Exception:
            existing_result = None
        if existing_result:
            existing_home = (
                existing_result.get(
                    "home_goals"
                )
            )
            existing_away = (
                existing_result.get(
                    "away_goals"
                )
            )
            if (
                existing_home is not None
                and existing_away is not None
            ):
                st.success(
                    f"Факт в БД: "
                    f"{existing_home}:{existing_away}"
                )
        try:
            locked = db.is_result_locked(
                match_id
            )
        except Exception:
            locked = False
        if locked:
            st.warning(
                "🔒 Результат уже LOCK. Изменение запрещено."
            )
        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------
        url = st.text_input(
            "🔗 Ссылка на страницу матча",
            value=state.get(
                "url",
                "",
            ),
            key=f"{key_prefix}_url",
            disabled=locked,
            placeholder="https://...",
        )
        state[
            "url"
        ] = url
        # ----------------------------------------------------
        # FETCH
        # ----------------------------------------------------
        fetch_col, status_col = st.columns(
            [1, 3]
        )
        with fetch_col:
            fetch_clicked = st.button(
                "📥 Забрать данные",
                key=f"{key_prefix}_fetch",
                disabled=(
                    locked
                    or not url
                ),
                use_container_width=True,
            )
        with status_col:
            if state.get(
                "fetched"
            ):
                st.success(
                    "Данные загружены. Проверьте перед сохранением."
                )
        if fetch_clicked:
            with st.spinner(
                "Получаю данные со страницы..."
            ):
                try:
                    fact = fetch_match_facts(
                        url
                    )
                    if not fact:
                        st.error(
                            "Не удалось получить данные."
                        )
                    else:
                        state[
                            "fact"
                        ] = fact
                        state[
                            "fetched"
                        ] = True
                        st.success(
                            "Данные получены."
                        )
                except Exception as exc:
                    logger.exception(
                        "Fact import error"
                    )
                    st.error(
                        f"Ошибка: {exc}"
                    )
        # ----------------------------------------------------
        # DISPLAY FETCHED DATA
        # ----------------------------------------------------
        fact = state.get(
            "fact"
        )
        if fact:
            score_col1, score_col2, score_col3 = st.columns(
                3
            )
            with score_col1:
                st.metric(
                    "Фактический счёт",
                    _format_score(
                        fact.get(
                            "home_goals"
                        ),
                        fact.get(
                            "away_goals"
                        ),
                    ),
                )
            with score_col2:
                st.metric(
                    "Качество данных",
                    f"{fact.get('data_quality', 0) * 100:.0f}%",
                )
            with score_col3:
                st.metric(
                    "Источник",
                    "URL",
                )
            render_stats(
                fact.get(
                    "stats",
                    {},
                )
            )
        # ----------------------------------------------------
        # FAJ PREDICTION
        # ----------------------------------------------------
        try:
            faj_prediction = (
                db.get_latest_prediction(
                    match_id
                )
            )
        except Exception:
            faj_prediction = None
        # ----------------------------------------------------
        # EXPERT PREDICTION
        # ----------------------------------------------------
        try:
            expert_predictions = (
                db.get_expert_predictions(
                    match_id
                )
            )
        except AttributeError:
            expert_predictions = []
        except Exception:
            expert_predictions = []
        latest_expert = None
        if expert_predictions:
            latest_expert = dict(
                expert_predictions[0]
            )
        # ----------------------------------------------------
        # COMPARISON
        # ----------------------------------------------------
        if (
            fact
            or faj_prediction
            or latest_expert
        ):
            render_comparison(
                match=match,
                fact=fact,
                prediction=faj_prediction,
                expert=latest_expert,
            )
        # ----------------------------------------------------
        # EXPERT INPUT
        # ----------------------------------------------------
        st.markdown(
            "#### 🧠 Прогноз эксперта"
        )
        expert_col1, expert_col2 = st.columns(
            [2, 1]
        )
        with expert_col1:
            expert_score = st.text_input(
                "Счёт эксперта",
                value=state.get(
                    "expert_score",
                    (
                        _expert_score(
                            latest_expert
                        )
                        if latest_expert
                        else ""
                    ),
                ),
                key=f"{key_prefix}_expert_score",
                disabled=locked,
                placeholder="Например: 2:1",
            )
        with expert_col2:
            expert_confidence = st.slider(
                "Уверенность, %",
                min_value=0,
                max_value=100,
                value=int(
                    state.get(
                        "expert_confidence",
                        (
                            latest_expert.get(
                                "confidence",
                                50,
                            )
                            if latest_expert
                            else 50
                        ),
                    )
                ),
                key=f"{key_prefix}_expert_confidence",
                disabled=locked,
            )
        expert_comment = st.text_area(
            "Комментарий эксперта",
            value=state.get(
                "expert_comment",
                (
                    latest_expert.get(
                        "comment",
                        "",
                    )
                    if latest_expert
                    else ""
                ),
            ),
            key=f"{key_prefix}_expert_comment",
            disabled=locked,
            placeholder=(
                "Краткое объяснение прогноза..."
            ),
        )
        state[
            "expert_score"
        ] = expert_score
        state[
            "expert_confidence"
        ] = expert_confidence
        state[
            "expert_comment"
        ] = expert_comment
        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------
        save_clicked = st.button(
            "✅ Сохранить факты",
            key=f"{key_prefix}_save",
            disabled=(
                locked
                or not fact
                or fact.get(
                    "home_goals"
                ) is None
                or fact.get(
                    "away_goals"
                ) is None
            ),
            use_container_width=True,
        )
        if save_clicked:
            try:
                expert_score_clean = (
                    expert_score.strip()
                    if expert_score
                    else None
                )
                if expert_score_clean:
                    eh, ea = (
                        _parse_score_string(
                            expert_score_clean
                        )
                    )
                    if (
                        eh is None
                        or ea is None
                    ):
                        raise ValueError(
                            "Прогноз эксперта должен быть в формате 2:1"
                        )
                    expert_score_clean = (
                        f"{eh}:{ea}"
                    )
                saved = save_match_facts(
                    db=db,
                    match=match,
                    fact=fact,
                    expert_name=DEFAULT_EXPERT_NAME,
                    expert_score=(
                        expert_score_clean
                    ),
                    expert_comment=(
                        expert_comment
                    ),
                    expert_confidence=(
                        expert_confidence
                    ),
                )
                state[
                    "saved"
                ] = True
                st.success(
                    "✅ Факты сохранены."
                )
                st.write(
                    {
                        "match_id": saved[
                            "match_id"
                        ],
                        "validation_id": saved[
                            "validation_id"
                        ],
                        "gold_id": saved[
                            "gold_id"
                        ],
                        "FAJ": saved[
                            "faj_score"
                        ],
                        "Эксперт": saved[
                            "expert_score"
                        ],
                        "Факт": saved[
                            "actual_score"
                        ],
                    }
                )
                st.rerun()
            except Exception as exc:
                logger.exception(
                    "Save facts error"
                )
                st.error(
                    f"❌ Не удалось сохранить: {exc}"
                )
    # ========================================================
    # LEARNING
    # ========================================================
    st.divider()
    st.header(
        "🧠 Обучение FAJ"
    )
    st.write(
        f"После сохранения фактов тура {selected_round} "
        "можно запустить пакетное обучение."
    )
    learning_col1, learning_col2 = st.columns(
        2
    )
    with learning_col1:
        if st.button(
            "🧠 Обучение",
            key="run_learning",
            use_container_width=True,
        ):
            try:
                from app.learning_engine import (
                    run_learning
                )
                # ------------------------------------------------
                # ВАЖНО:
                # обучение запускается отдельно от импорта.
                # Оно получает уже сохранённые факты.
                # ------------------------------------------------
                result = run_learning(
                    db_path=str(
                        getattr(
                            config,
                            "DB_PATH",
                            "data/faj.db",
                        )
                    ),
                    force=False,
                )
                st.success(
                    "🧠 Обучение завершено."
                )
                if result is not None:
                    st.json(
                        result
                    )
            except Exception as exc:
                logger.exception(
                    "Learning error"
                )
                st.error(
                    f"❌ Ошибка обучения: {exc}"
                )
    with learning_col2:
        st.info(
            "Обучение не выполняется автоматически "
            "при сохранении каждого матча. "
            "Сначала сохраняется весь тур, затем "
            "запускается пакетное обучение."
        )
# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()

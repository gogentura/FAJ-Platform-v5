#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Brain — Data Contract

Единый контракт данных между:

    старый FAJ
        ↓
    historical records
        ↓
    form_context / form_model
        ↓
    новые математические модели
        ↓
    FAJ Brain
        ↓
    prediction / analysis / UI

ВАЖНО:

1. Этот файл НЕ считает.
2. Этот файл НЕ делает прогноз.
3. Этот файл НЕ получает данные из Soccer365.
4. Этот файл НЕ обращается к database.py.
5. Этот файл НЕ изменяет старые модели.

Его задача — определить, какие данные Brain имеет право
получать и какие данные он должен возвращать.

Принцип:

    DATA → CONTRACT → MODEL → BRAIN

Если модель получает данные, которых нет в контракте,
это архитектурная ошибка.

Если модель сама начинает собирать данные,
это архитектурная ошибка.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# BASIC TYPES
# ============================================================

Number = Optional[float]


# ============================================================
# MATCH RECORD
# ============================================================

@dataclass(frozen=True)
class MatchRecord:
    """
    Нормализованная информация об одном прошлом матче.

    Это математическая единица истории.

    Источник обычно:
        Soccer365 parser
            ↓
        faj_predictor.build_history_record()
            ↓
        MatchRecord
    """

    home_team: str
    away_team: str

    home_goals: Optional[int]
    away_goals: Optional[int]

    match_date: Optional[str] = None

    # -------------------------
    # xG
    # -------------------------

    home_xg: Number = None
    away_xg: Number = None

    # -------------------------
    # shots
    # -------------------------

    home_shots: Number = None
    away_shots: Number = None

    home_shots_on_target: Number = None
    away_shots_on_target: Number = None

    # -------------------------
    # possession
    # -------------------------

    home_possession: Number = None
    away_possession: Number = None

    # -------------------------
    # corners
    # -------------------------

    home_corners: Number = None
    away_corners: Number = None

    # -------------------------
    # cards
    # -------------------------

    home_yellow_cards: Number = None
    away_yellow_cards: Number = None

    # -------------------------
    # fouls
    # -------------------------

    home_fouls: Number = None
    away_fouls: Number = None

    # -------------------------
    # big chances
    # -------------------------

    home_big_chances: Number = None
    away_big_chances: Number = None

    # -------------------------
    # passes
    # -------------------------

    home_passes: Number = None
    away_passes: Number = None

    home_pass_accuracy: Number = None
    away_pass_accuracy: Number = None

    # -------------------------
    # quality / provenance
    # -------------------------

    quality: Number = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    parser_version: Optional[str] = None


# ============================================================
# TEAM FORM CONTEXT
# ============================================================

@dataclass(frozen=True)
class FormContext:
    """
    Контекст последних матчей команды.

    Это уже не просто сырые данные.

    Здесь находятся признаки, которые были получены
    из истории, но ещё НЕ являются прогнозом.

    Важно:
        FormContext != FormModel

    FormContext:
        описывает прошлое.

    FormModel:
        интерпретирует прошлое математически.
    """

    team: str

    # -------------------------
    # Recent results
    # -------------------------

    results: Tuple[str, ...] = ()

    wins: int = 0
    draws: int = 0
    losses: int = 0

    points: int = 0

    # -------------------------
    # Home / Away
    # -------------------------

    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0

    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    # -------------------------
    # Goals
    # -------------------------

    goals_for_avg: Number = None
    goals_against_avg: Number = None

    # -------------------------
    # xG
    # -------------------------

    xg_avg: Number = None
    xga_avg: Number = None

    # -------------------------
    # Corners
    # -------------------------

    corners_for_avg: Number = None
    corners_against_avg: Number = None

    # -------------------------
    # Possession
    # -------------------------

    possession_avg: Number = None

    # -------------------------
    # Cards / aggression
    # -------------------------

    cards_avg: Number = None
    fouls_avg: Number = None

    # -------------------------
    # Match difficulty
    # -------------------------

    difficulty: Tuple[str, ...] = ()

    # -------------------------
    # Derived context flags
    # -------------------------

    consecutive_away_matches: int = 0

    consecutive_wins: int = 0

    home_unbeaten_count: int = 0

    away_wins_recent: int = 0


# ============================================================
# FORM MODEL OUTPUT
# ============================================================

@dataclass(frozen=True)
class FormModelResult:
    """
    Математическая интерпретация формы.

    Здесь уже разрешены формулы.

    Но конкретные формулы будут определены отдельно
    после тестирования.
    """

    form_score: Number = None

    attack_strength: Number = None

    defense_strength: Number = None

    home_strength: Number = None

    away_strength: Number = None

    trend: Optional[str] = None

    consistency: Number = None

    # -------------------------
    # Special effects
    # -------------------------

    dark_horse_effect: Number = None

    lukaku_effect: Number = None

    gladiator_effect: Number = None

    fortress_effect: Number = None

    leicester_effect: Number = None

    kepa_effect: Number = None

    haaland_effect: Number = None

    god_kiss_effect: Number = None


# ============================================================
# GOAL MODEL RESULT
# ============================================================

@dataclass(frozen=True)
class GoalModelResult:
    """
    Ожидаемые голы матча.

    Это НЕ счёт.

    home_xg / away_xg — математическое ожидание голов
    перед построением распределения счёта.
    """

    home_xg: Number = None
    away_xg: Number = None

    home_attack: Number = None
    away_attack: Number = None

    home_defense: Number = None
    away_defense: Number = None

    confidence: Number = None


# ============================================================
# SCORE MODEL RESULT
# ============================================================

@dataclass(frozen=True)
class ScoreModelResult:
    """
    Распределение вероятностей точных счетов.
    """

    distribution: Dict[str, float] = field(
        default_factory=dict
    )

    most_likely: Optional[str] = None

    second_likely: Optional[str] = None

    third_likely: Optional[str] = None


# ============================================================
# PROBABILITY MODEL RESULT
# ============================================================

@dataclass(frozen=True)
class ProbabilityModelResult:
    """
    Вероятности основных исходов.
    """

    home_win: Number = None
    draw: Number = None
    away_win: Number = None

    btts: Number = None

    over_15: Number = None
    over_25: Number = None
    over_35: Number = None

    under_15: Number = None
    under_25: Number = None
    under_35: Number = None


# ============================================================
# CORNERS MODEL RESULT
# ============================================================

@dataclass(frozen=True)
class CornersModelResult:
    """
    Прогноз угловых.
    """

    home_expected: Number = None
    away_expected: Number = None
    total_expected: Number = None

    over_75: Number = None
    over_85: Number = None
    over_95: Number = None
    over_105: Number = None


# ============================================================
# CARDS MODEL RESULT
# ============================================================

@dataclass(frozen=True)
class CardsModelResult:
    """
    Прогноз карточек.
    """

    home_expected: Number = None
    away_expected: Number = None
    total_expected: Number = None

    over_25: Number = None
    over_35: Number = None
    over_45: Number = None


# ============================================================
# ANALYTICAL RESULT
# ============================================================

@dataclass(frozen=True)
class AnalysisResult:
    """
    Человеческая интерпретация математического результата.
    """

    conclusion: str = ""

    key_factors: Tuple[str, ...] = ()

    risks: Tuple[str, ...] = ()

    positive_signals: Tuple[str, ...] = ()

    negative_signals: Tuple[str, ...] = ()

    confidence: Number = None


# ============================================================
# BRAIN INPUT
# ============================================================

@dataclass(frozen=True)
class BrainInput:
    """
    Полный вход нового FAJ Brain.

    Это главный входной контракт.
    """

    home_team: str

    away_team: str

    home_matches: Tuple[MatchRecord, ...]

    away_matches: Tuple[MatchRecord, ...]

    home_form: Optional[FormContext] = None

    away_form: Optional[FormContext] = None

    # Дополнительные данные старого FAJ.
    #
    # Пока не используем жёстко, но оставляем возможность
    # подключить существующие рейтинги / параметры / passport.
    home_team_data: Dict[str, Any] = field(
        default_factory=dict
    )

    away_team_data: Dict[str, Any] = field(
        default_factory=dict
    )

    model_parameters: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# BRAIN OUTPUT
# ============================================================

@dataclass(frozen=True)
class BrainOutput:
    """
    Полный результат работы Brain.

    Здесь объединяется всё:
        форма
        голы
        счёт
        вероятности
        угловые
        карточки
        аналитика
    """

    home_team: str

    away_team: str

    form_home: Optional[FormModelResult] = None

    form_away: Optional[FormModelResult] = None

    goals: Optional[GoalModelResult] = None

    score: Optional[ScoreModelResult] = None

    probabilities: Optional[ProbabilityModelResult] = None

    corners: Optional[CornersModelResult] = None

    cards: Optional[CardsModelResult] = None

    analysis: Optional[AnalysisResult] = None

    # -------------------------
    # Meta
    # -------------------------

    model_version: Optional[str] = None

    contract_version: str = "1.0"

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# CONTRACT HELPERS
# ============================================================

def result_to_points(result: str) -> int:
    """
    Преобразует результат команды в очки.

        В → 3
        Н → 1
        П → 0
    """

    normalized = str(result).strip().upper()

    if normalized == "В":
        return 3

    if normalized == "Н":
        return 1

    if normalized == "П":
        return 0

    return 0


def validate_match_record(
    record: MatchRecord,
) -> None:
    """
    Минимальная валидация одного матча.

    Ничего не исправляет.

    Если данные некорректны — выбрасывает ошибку.
    """

    if not record.home_team:
        raise ValueError(
            "MatchRecord: отсутствует home_team"
        )

    if not record.away_team:
        raise ValueError(
            "MatchRecord: отсутствует away_team"
        )

    if record.home_goals is not None:
        if record.home_goals < 0:
            raise ValueError(
                "MatchRecord: home_goals < 0"
            )

    if record.away_goals is not None:
        if record.away_goals < 0:
            raise ValueError(
                "MatchRecord: away_goals < 0"
            )


def validate_brain_input(
    data: BrainInput,
) -> None:
    """
    Проверяет вход Brain.

    ВАЖНО:
        функция ничего не меняет.
    """

    if not data.home_team:
        raise ValueError(
            "BrainInput: отсутствует home_team"
        )

    if not data.away_team:
        raise ValueError(
            "BrainInput: отсутствует away_team"
        )

    if data.home_team == data.away_team:
        raise ValueError(
            "BrainInput: home_team == away_team"
        )

    for record in data.home_matches:
        validate_match_record(record)

    for record in data.away_matches:
        validate_match_record(record)


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "MatchRecord",
    "FormContext",
    "FormModelResult",
    "GoalModelResult",
    "ScoreModelResult",
    "ProbabilityModelResult",
    "CornersModelResult",
    "CardsModelResult",
    "AnalysisResult",
    "BrainInput",
    "BrainOutput",
    "result_to_points",
    "validate_match_record",
    "validate_brain_input",
]

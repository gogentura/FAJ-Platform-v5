#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ BRAIN — DATA CONTRACT v2.0

Единый строгий контракт нового аналитического Brain.

Архитектура:

    FACTUAL HISTORY
          ↓
    MatchRecord
          ↓
    FormContext
          ↓
    PatternState
          ↓
    FormModel
          ↓
    GoalModel
          ↓
    ScoreModel
          ↓
    ProbabilityModel
          ↓
    AnalysisEngine
          ↓
    BrainOutput


ВАЖНО
-----

Этот файл:

    НЕ собирает данные
    НЕ парсит Soccer365
    НЕ обращается к database.py
    НЕ считает прогноз
    НЕ содержит математических формул эффектов

Его задача:

    определить ГРАНИЦУ данных нового Brain.

Принцип:

    DATA
      ↓
    CONTRACT
      ↓
    MODEL
      ↓
    BRAIN

Новый Brain работает с фиксированным историческим окном:

    6 последних завершённых матчей

Это НЕ означает, что источник обязан собрать только 6 матчей.
Источник может собрать больше.

Но в Brain рабочим контекстом являются последние 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# CONTRACT VERSION
# ============================================================

CONTRACT_VERSION = "2.0"

# Рабочее историческое окно Brain.
HISTORY_MATCHES = 6

# Допустимый размер рабочего окна.
MIN_HISTORY_MATCHES = 6
MAX_HISTORY_MATCHES = 6


# ============================================================
# BASIC TYPES
# ============================================================

Number = Optional[float]


# ============================================================
# ENUM-LIKE CONSTANTS
# ============================================================

RESULT_WIN = "В"
RESULT_DRAW = "Н"
RESULT_LOSS = "П"

VALID_RESULTS = (
    RESULT_WIN,
    RESULT_DRAW,
    RESULT_LOSS,
)

DIFFICULTY_EASY = "лёгкий"
DIFFICULTY_MEDIUM = "средний"
DIFFICULTY_HARD = "тяжёлый"

VALID_DIFFICULTIES = (
    DIFFICULTY_EASY,
    DIFFICULTY_MEDIUM,
    DIFFICULTY_HARD,
)


# ============================================================
# SPECIAL EFFECT NAMES
# ============================================================

EFFECT_DARK_HORSE = "dark_horse_effect"

EFFECT_LUKAKU = "lukaku_effect"

EFFECT_GLADIATOR = "gladiator_effect"

EFFECT_FORTRESS = "fortress_effect"

EFFECT_LEICESTER = "leicester_effect"

EFFECT_KEPA = "kepa_effect"

EFFECT_HAALAND = "haaland_effect"

EFFECT_GOD_KISS = "god_kiss_effect"


SPECIAL_EFFECTS = (
    EFFECT_DARK_HORSE,
    EFFECT_LUKAKU,
    EFFECT_GLADIATOR,
    EFFECT_FORTRESS,
    EFFECT_LEICESTER,
    EFFECT_KEPA,
    EFFECT_HAALAND,
    EFFECT_GOD_KISS,
)


# ============================================================
# ALLOWED VALUE RANGES
# ============================================================

# Goals
MIN_GOALS = 0
MAX_GOALS = 20

# xG
MIN_XG = 0.0
MAX_XG = 10.0

# Possession
MIN_POSSESSION = 0.0
MAX_POSSESSION = 100.0

# Shots
MIN_SHOTS = 0.0
MAX_SHOTS = 100.0

# Corners
MIN_CORNERS = 0.0
MAX_CORNERS = 30.0

# Cards
MIN_CARDS = 0.0
MAX_CARDS = 20.0

# Fouls
MIN_FOULS = 0.0
MAX_FOULS = 100.0

# Big chances
MIN_BIG_CHANCES = 0.0
MAX_BIG_CHANCES = 30.0

# Passes
MIN_PASSES = 0.0
MAX_PASSES = 1500.0

# Pass accuracy
MIN_PASS_ACCURACY = 0.0
MAX_PASS_ACCURACY = 100.0

# Quality
MIN_QUALITY = 0.0
MAX_QUALITY = 1.0

# Probability
MIN_PROBABILITY = 0.0
MAX_PROBABILITY = 1.0


# ============================================================
# MATCH RECORD
# ============================================================

@dataclass(frozen=True)
class MatchRecord:
    """
    Один завершённый фактический матч.

    Это атомарная единица истории Brain.

    ВАЖНО:

    MatchRecord содержит ФАКТЫ.

    Он не содержит:
        прогнозов
        вероятностей будущего
        специальных эффектов
        интерпретаций Brain

    Источник обычно:

        Soccer365
            ↓
        parser
            ↓
        build_history_record()
            ↓
        MatchRecord
    """

    home_team: str
    away_team: str

    home_goals: Optional[int]
    away_goals: Optional[int]

    match_date: Optional[str] = None

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    home_xg: Number = None
    away_xg: Number = None

    # --------------------------------------------------------
    # SHOTS
    # --------------------------------------------------------

    home_shots: Number = None
    away_shots: Number = None

    home_shots_on_target: Number = None
    away_shots_on_target: Number = None

    # --------------------------------------------------------
    # POSSESSION
    # --------------------------------------------------------

    home_possession: Number = None
    away_possession: Number = None

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

    home_corners: Number = None
    away_corners: Number = None

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    home_yellow_cards: Number = None
    away_yellow_cards: Number = None

    # --------------------------------------------------------
    # FOULS
    # --------------------------------------------------------

    home_fouls: Number = None
    away_fouls: Number = None

    # --------------------------------------------------------
    # BIG CHANCES
    # --------------------------------------------------------

    home_big_chances: Number = None
    away_big_chances: Number = None

    # --------------------------------------------------------
    # PASSES
    # --------------------------------------------------------

    home_passes: Number = None
    away_passes: Number = None

    home_pass_accuracy: Number = None
    away_pass_accuracy: Number = None

    # --------------------------------------------------------
    # DATA QUALITY / PROVENANCE
    # --------------------------------------------------------

    quality: Number = None

    source: Optional[str] = None

    source_url: Optional[str] = None

    parser_version: Optional[str] = None


# ============================================================
# FORM CONTEXT
# ============================================================

@dataclass(frozen=True)
class FormContext:
    """
    Исторический контекст команды.

    FormContext описывает ПРОШЛОЕ.

    Он НЕ является прогнозом.

    Он НЕ рассчитывает специальные эффекты.

    FormModel получает FormContext и интерпретирует его.
    """

    team: str

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    matches_count: int = 0

    results: Tuple[str, ...] = ()

    wins: int = 0
    draws: int = 0
    losses: int = 0

    points: int = 0

    # --------------------------------------------------------
    # HOME / AWAY
    # --------------------------------------------------------

    home_matches: int = 0
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0

    away_matches: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    goals_for_avg: Number = None
    goals_against_avg: Number = None

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    xg_avg: Number = None
    xga_avg: Number = None

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

    corners_for_avg: Number = None
    corners_against_avg: Number = None

    # --------------------------------------------------------
    # POSSESSION
    # --------------------------------------------------------

    possession_avg: Number = None

    # --------------------------------------------------------
    # CARDS / AGGRESSION
    # --------------------------------------------------------

    cards_avg: Number = None
    fouls_avg: Number = None

    # --------------------------------------------------------
    # MATCH DIFFICULTY
    # --------------------------------------------------------

    difficulty: Tuple[str, ...] = ()

    # --------------------------------------------------------
    # SEQUENCE CONTEXT
    # --------------------------------------------------------

    consecutive_away_matches: int = 0

    consecutive_wins: int = 0

    home_unbeaten_count: int = 0

    away_wins_recent: int = 0


# ============================================================
# PATTERN STATE
# ============================================================

@dataclass(frozen=True)
class PatternState:
    """
    Выявленные закономерности истории команды.

    Это промежуточный слой между:

        FormContext
            ↓
        PatternState
            ↓
        FormModel

    Здесь фиксируется:

        ЧТО ПРОИСХОДИТ

    Но не фиксируется окончательное:

        НАСКОЛЬКО ЭТО ВЛИЯЕТ НА ПРОГНОЗ

    Вес каждого эффекта будет определяться математическими
    моделями после отдельного тестирования.
    """

    # --------------------------------------------------------
    # MATCH SAMPLE
    # --------------------------------------------------------

    matches_count: int = 0

    # --------------------------------------------------------
    # RESULT PATTERNS
    # --------------------------------------------------------

    consecutive_wins: int = 0

    home_unbeaten_count: int = 0

    away_wins_recent: int = 0

    consecutive_away_matches: int = 0

    # --------------------------------------------------------
    # DIFFICULTY PATTERNS
    # --------------------------------------------------------

    hard_wins: int = 0

    hard_draws: int = 0

    hard_losses: int = 0

    medium_wins: int = 0

    medium_draws: int = 0

    medium_losses: int = 0

    easy_wins: int = 0

    easy_draws: int = 0

    easy_losses: int = 0

    # --------------------------------------------------------
    # SPECIAL EFFECT SIGNALS
    # --------------------------------------------------------

    dark_horse_signal: Number = None

    lukaku_signal: Number = None

    gladiator_signal: Number = None

    fortress_signal: Number = None

    leicester_signal: Number = None

    kepa_signal: Number = None

    haaland_signal: Number = None

    god_kiss_signal: Number = None


# ============================================================
# FORM MODEL RESULT
# ============================================================

@dataclass(frozen=True)
class FormModelResult:
    """
    Математическая интерпретация формы.

    Именно здесь будут находиться будущие формулы FAJ.

    Например:

        форма
        сила атаки
        сила обороны
        домашний фактор
        гостевой фактор
        сложность соперников
        специальные эффекты

    Веса и формулы пока НЕ фиксируются контрактом.
    """

    form_score: Number = None

    attack_strength: Number = None

    defense_strength: Number = None

    home_strength: Number = None

    away_strength: Number = None

    trend: Optional[str] = None

    consistency: Number = None

    # --------------------------------------------------------
    # SPECIAL EFFECTS
    # --------------------------------------------------------

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
    Ожидаемые голы.

    Это математическое ожидание результата,
    а не точный счёт.

    В будущем здесь будут объединяться:

        форма
        голы
        xG
        xGA
        реализация
        владение
        моменты
        домашний фактор
        специальные эффекты
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

    Модель может быть подключена позже.

    Контракт заранее готов.
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
    Главный вход нового FAJ Brain.

    В рабочем режиме:

        home_matches = 6
        away_matches = 6

    Старый FAJ может передавать дополнительные данные,
    но новые модели не должны слепо зависеть от них.
    """

    home_team: str

    away_team: str

    home_matches: Tuple[MatchRecord, ...]

    away_matches: Tuple[MatchRecord, ...]

    home_form: Optional[FormContext] = None

    away_form: Optional[FormContext] = None

    home_patterns: Optional[PatternState] = None

    away_patterns: Optional[PatternState] = None

    # --------------------------------------------------------
    # OLD FAJ DATA
    # --------------------------------------------------------

    home_team_data: Dict[str, Any] = field(
        default_factory=dict
    )

    away_team_data: Dict[str, Any] = field(
        default_factory=dict
    )

    # --------------------------------------------------------
    # MODEL PARAMETERS
    # --------------------------------------------------------

    model_parameters: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# BRAIN OUTPUT
# ============================================================

@dataclass(frozen=True)
class BrainOutput:
    """
    Полный результат нового FAJ Brain.
    """

    home_team: str

    away_team: str

    # --------------------------------------------------------
    # FORM
    # --------------------------------------------------------

    form_home: Optional[FormModelResult] = None

    form_away: Optional[FormModelResult] = None

    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    goals: Optional[GoalModelResult] = None

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score: Optional[ScoreModelResult] = None

    # --------------------------------------------------------
    # PROBABILITIES
    # --------------------------------------------------------

    probabilities: Optional[ProbabilityModelResult] = None

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

    corners: Optional[CornersModelResult] = None

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    cards: Optional[CardsModelResult] = None

    # --------------------------------------------------------
    # HUMAN ANALYSIS
    # --------------------------------------------------------

    analysis: Optional[AnalysisResult] = None

    # --------------------------------------------------------
    # META
    # --------------------------------------------------------

    model_version: Optional[str] = None

    contract_version: str = CONTRACT_VERSION

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# HELPERS
# ============================================================

def result_to_points(
    result: str,
) -> int:
    """
    В → 3
    Н → 1
    П → 0
    """

    normalized = str(result).strip().upper()

    if normalized == RESULT_WIN:
        return 3

    if normalized == RESULT_DRAW:
        return 1

    if normalized == RESULT_LOSS:
        return 0

    raise ValueError(
        f"Неизвестный результат команды: {result!r}"
    )


def _validate_range(
    value: Number,
    minimum: float,
    maximum: float,
    field_name: str,
) -> None:
    """
    Проверка числового диапазона.

    None разрешён:

        None = данных нет

    Это принципиально важно.

    Отсутствующие данные НЕ превращаются в 0.
    """

    if value is None:
        return

    if value < minimum or value > maximum:
        raise ValueError(
            f"{field_name} вне допустимого диапазона: "
            f"{value}. "
            f"Допустимо [{minimum}, {maximum}]"
        )


# ============================================================
# MATCH VALIDATION
# ============================================================

def validate_match_record(
    record: MatchRecord,
) -> None:
    """
    Строгая валидация одного MatchRecord.

    Ничего не исправляет.
    """

    if not record.home_team:
        raise ValueError(
            "MatchRecord: отсутствует home_team"
        )

    if not record.away_team:
        raise ValueError(
            "MatchRecord: отсутствует away_team"
        )

    _validate_range(
        record.home_goals,
        MIN_GOALS,
        MAX_GOALS,
        "home_goals",
    )

    _validate_range(
        record.away_goals,
        MIN_GOALS,
        MAX_GOALS,
        "away_goals",
    )

    _validate_range(
        record.home_xg,
        MIN_XG,
        MAX_XG,
        "home_xg",
    )

    _validate_range(
        record.away_xg,
        MIN_XG,
        MAX_XG,
        "away_xg",
    )

    _validate_range(
        record.home_shots,
        MIN_SHOTS,
        MAX_SHOTS,
        "home_shots",
    )

    _validate_range(
        record.away_shots,
        MIN_SHOTS,
        MAX_SHOTS,
        "away_shots",
    )

    _validate_range(
        record.home_shots_on_target,
        MIN_SHOTS,
        MAX_SHOTS,
        "home_shots_on_target",
    )

    _validate_range(
        record.away_shots_on_target,
        MIN_SHOTS,
        MAX_SHOTS,
        "away_shots_on_target",
    )

    _validate_range(
        record.home_possession,
        MIN_POSSESSION,
        MAX_POSSESSION,
        "home_possession",
    )

    _validate_range(
        record.away_possession,
        MIN_POSSESSION,
        MAX_POSSESSION,
        "away_possession",
    )

    _validate_range(
        record.home_corners,
        MIN_CORNERS,
        MAX_CORNERS,
        "home_corners",
    )

    _validate_range(
        record.away_corners,
        MIN_CORNERS,
        MAX_CORNERS,
        "away_corners",
    )

    _validate_range(
        record.home_yellow_cards,
        MIN_CARDS,
        MAX_CARDS,
        "home_yellow_cards",
    )

    _validate_range(
        record.away_yellow_cards,
        MIN_CARDS,
        MAX_CARDS,
        "away_yellow_cards",
    )

    _validate_range(
        record.home_fouls,
        MIN_FOULS,
        MAX_FOULS,
        "home_fouls",
    )

    _validate_range(
        record.away_fouls,
        MIN_FOULS,
        MAX_FOULS,
        "away_fouls",
    )

    _validate_range(
        record.home_big_chances,
        MIN_BIG_CHANCES,
        MAX_BIG_CHANCES,
        "home_big_chances",
    )

    _validate_range(
        record.away_big_chances,
        MIN_BIG_CHANCES,
        MAX_BIG_CHANCES,
        "away_big_chances",
    )

    _validate_range(
        record.home_passes,
        MIN_PASSES,
        MAX_PASSES,
        "home_passes",
    )

    _validate_range(
        record.away_passes,
        MIN_PASSES,
        MAX_PASSES,
        "away_passes",
    )

    _validate_range(
        record.home_pass_accuracy,
        MIN_PASS_ACCURACY,
        MAX_PASS_ACCURACY,
        "home_pass_accuracy",
    )

    _validate_range(
        record.away_pass_accuracy,
        MIN_PASS_ACCURACY,
        MAX_PASS_ACCURACY,
        "away_pass_accuracy",
    )

    _validate_range(
        record.quality,
        MIN_QUALITY,
        MAX_QUALITY,
        "quality",
    )


# ============================================================
# HISTORY VALIDATION
# ============================================================

def validate_history(
    matches: Tuple[MatchRecord, ...],
) -> None:
    """
    Проверяет рабочее историческое окно Brain.

    Brain работает только с 6 матчами.

    Если передано другое количество —
    это архитектурная ошибка входа.
    """

    count = len(matches)

    if count < MIN_HISTORY_MATCHES:
        raise ValueError(
            "Brain history недостаточна: "
            f"получено {count}, "
            f"требуется {MIN_HISTORY_MATCHES}"
        )

    if count > MAX_HISTORY_MATCHES:
        raise ValueError(
            "Brain history превышает рабочее окно: "
            f"получено {count}, "
            f"максимум {MAX_HISTORY_MATCHES}"
        )

    for record in matches:
        validate_match_record(record)


# ============================================================
# FORM CONTEXT VALIDATION
# ============================================================

def validate_form_context(
    context: FormContext,
) -> None:
    """
    Проверяет исторический FormContext.
    """

    if not context.team:
        raise ValueError(
            "FormContext: отсутствует team"
        )

    if context.matches_count < 0:
        raise ValueError(
            "FormContext: matches_count < 0"
        )

    if context.matches_count > HISTORY_MATCHES:
        raise ValueError(
            "FormContext: matches_count "
            f"({context.matches_count}) "
            f"> {HISTORY_MATCHES}"
        )

    if context.wins < 0:
        raise ValueError(
            "FormContext: wins < 0"
        )

    if context.draws < 0:
        raise ValueError(
            "FormContext: draws < 0"
        )

    if context.losses < 0:
        raise ValueError(
            "FormContext: losses < 0"
        )

    _validate_range(
        context.goals_for_avg,
        MIN_GOALS,
        MAX_GOALS,
        "goals_for_avg",
    )

    _validate_range(
        context.goals_against_avg,
        MIN_GOALS,
        MAX_GOALS,
        "goals_against_avg",
    )

    _validate_range(
        context.xg_avg,
        MIN_XG,
        MAX_XG,
        "xg_avg",
    )

    _validate_range(
        context.xga_avg,
        MIN_XG,
        MAX_XG,
        "xga_avg",
    )

    _validate_range(
        context.possession_avg,
        MIN_POSSESSION,
        MAX_POSSESSION,
        "possession_avg",
    )

    _validate_range(
        context.corners_for_avg,
        MIN_CORNERS,
        MAX_CORNERS,
        "corners_for_avg",
    )

    _validate_range(
        context.corners_against_avg,
        MIN_CORNERS,
        MAX_CORNERS,
        "corners_against_avg",
    )

    _validate_range(
        context.cards_avg,
        MIN_CARDS,
        MAX_CARDS,
        "cards_avg",
    )

    _validate_range(
        context.fouls_avg,
        MIN_FOULS,
        MAX_FOULS,
        "fouls_avg",
    )


# ============================================================
# BRAIN INPUT VALIDATION
# ============================================================

def validate_brain_input(
    data: BrainInput,
) -> None:
    """
    Полная проверка входа Brain.

    Ничего не меняет.
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

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    validate_history(
        data.home_matches
    )

    validate_history(
        data.away_matches
    )

    # --------------------------------------------------------
    # FORM
    # --------------------------------------------------------

    if data.home_form is not None:
        validate_form_context(
            data.home_form
        )

    if data.away_form is not None:
        validate_form_context(
            data.away_form
        )

    # --------------------------------------------------------
    # TEAM CONSISTENCY
    # --------------------------------------------------------

    for record in data.home_matches:

        if (
            record.home_team != data.home_team
            and record.away_team != data.home_team
        ):
            raise ValueError(
                "BrainInput: home_matches содержит "
                f"матч без команды {data.home_team}: "
                f"{record.home_team} — {record.away_team}"
            )

    for record in data.away_matches:

        if (
            record.home_team != data.away_team
            and record.away_team != data.away_team
        ):
            raise ValueError(
                "BrainInput: away_matches содержит "
                f"матч без команды {data.away_team}: "
                f"{record.home_team} — {record.away_team}"
            )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Version / history
    "CONTRACT_VERSION",
    "HISTORY_MATCHES",
    "MIN_HISTORY_MATCHES",
    "MAX_HISTORY_MATCHES",

    # Results
    "RESULT_WIN",
    "RESULT_DRAW",
    "RESULT_LOSS",
    "VALID_RESULTS",

    # Difficulty
    "DIFFICULTY_EASY",
    "DIFFICULTY_MEDIUM",
    "DIFFICULTY_HARD",
    "VALID_DIFFICULTIES",

    # Effects
    "EFFECT_DARK_HORSE",
    "EFFECT_LUKAKU",
    "EFFECT_GLADIATOR",
    "EFFECT_FORTRESS",
    "EFFECT_LEICESTER",
    "EFFECT_KEPA",
    "EFFECT_HAALAND",
    "EFFECT_GOD_KISS",
    "SPECIAL_EFFECTS",

    # Core structures
    "MatchRecord",
    "FormContext",
    "PatternState",

    # Model results
    "FormModelResult",
    "GoalModelResult",
    "ScoreModelResult",
    "ProbabilityModelResult",
    "CornersModelResult",
    "CardsModelResult",
    "AnalysisResult",

    # Brain
    "BrainInput",
    "BrainOutput",

    # Helpers
    "result_to_points",
    "validate_match_record",
    "validate_history",
    "validate_form_context",
    "validate_brain_input",
]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ BRAIN — DATA CONTRACT v3.0

Строгий контракт данных нового аналитического Brain.

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


ГЛАВНЫЙ ПРИНЦИП
---------------

MatchRecord
    = факты одного прошлого матча

FormContext
    = агрегированная история команды

PatternState
    = измеренные закономерности истории

FormModel
    = математическая интерпретация этих закономерностей


ВАЖНО
-----

Этот файл:

    НЕ парсит данные
    НЕ обращается к database.py
    НЕ считает прогноз
    НЕ рассчитывает специальные эффекты
    НЕ определяет веса моделей

Его задача:

    определить строгую границу данных Brain.


ИСТОРИЧЕСКОЕ ОКНО
-----------------

Рабочее окно Brain:

    6 последних завершённых матчей.

Источник может передать больше матчей,
но перед входом в Brain рабочий контекст
должен быть ограничен шестью последними матчами.
"""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


# ============================================================
# CONTRACT VERSION
# ============================================================

CONTRACT_VERSION = "3.0"

HISTORY_MATCHES = 6

MIN_HISTORY_MATCHES = 6
MAX_HISTORY_MATCHES = 6


# ============================================================
# BASIC TYPES
# ============================================================

Number = Optional[float]


# ============================================================
# RESULTS
# ============================================================

RESULT_WIN = "В"
RESULT_DRAW = "Н"
RESULT_LOSS = "П"

VALID_RESULTS = (
    RESULT_WIN,
    RESULT_DRAW,
    RESULT_LOSS,
)


# ============================================================
# DIFFICULTY
# ============================================================

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

# Probability / normalized score
MIN_PROBABILITY = 0.0
MAX_PROBABILITY = 1.0

# Generic normalized signal
MIN_SIGNAL = -1.0
MAX_SIGNAL = 1.0


# ============================================================
# MATCH RECORD
# ============================================================

@dataclass(frozen=True)
class MatchRecord:
    """
    Один завершённый фактический матч.

    MatchRecord содержит только факты.

    НЕ содержит:

        прогнозов
        будущих вероятностей
        специальных эффектов
        интерпретации Brain
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
    Агрегированный исторический контекст команды.

    FormContext отвечает на вопрос:

        ЧТО ПРОИЗОШЛО В ПОСЛЕДНИХ 6 МАТЧАХ?

    Он не отвечает на вопрос:

        ЧТО ПРОИЗОЙДЁТ В СЛЕДУЮЩЕМ МАТЧЕ?

    Это задача FormModel / GoalModel.
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
    Математическое описание закономерностей последних 6 матчей.

    PatternState НЕ является прогнозом.

    Он фиксирует:

        КАКОЙ ПАТТЕРН ОБНАРУЖЕН

    FormModel затем определяет:

        КАК ЭТОТ ПАТТЕРН ДОЛЖЕН ВЛИЯТЬ НА МОДЕЛЬ


    ВАЖНО
    -----

    Числовые поля здесь — признаки / сигналы.

    Они НЕ являются коэффициентами прогноза.

    Например:

        gladiator_signal = 1.0

    означает наличие сильного паттерна,

    но НЕ означает:

        +10% к победе.


    Веса будут определяться отдельно
    при тестировании математических моделей.
    """

    # ========================================================
    # SAMPLE
    # ========================================================

    matches_count: int = 0

    # ========================================================
    # RESULT STRUCTURE
    # ========================================================

    wins: int = 0
    draws: int = 0
    losses: int = 0

    points: int = 0

    win_rate: Number = None
    draw_rate: Number = None
    loss_rate: Number = None

    # ========================================================
    # RECENCY
    # ========================================================

    recent_wins: int = 0
    recent_draws: int = 0
    recent_losses: int = 0

    recent_points: int = 0

    # ========================================================
    # SEQUENCES
    # ========================================================

    consecutive_wins: int = 0

    consecutive_losses: int = 0

    consecutive_draws: int = 0

    consecutive_away_matches: int = 0

    # ========================================================
    # HOME STABILITY
    # ========================================================

    home_matches: int = 0

    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0

    home_unbeaten_count: int = 0

    home_unbeaten_rate: Number = None

    # ========================================================
    # AWAY PERFORMANCE
    # ========================================================

    away_matches: int = 0

    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    away_win_rate: Number = None

    # ========================================================
    # DIFFICULTY × RESULT
    # ========================================================

    hard_matches: int = 0

    hard_wins: int = 0
    hard_draws: int = 0
    hard_losses: int = 0

    medium_matches: int = 0

    medium_wins: int = 0
    medium_draws: int = 0
    medium_losses: int = 0

    easy_matches: int = 0

    easy_wins: int = 0
    easy_draws: int = 0
    easy_losses: int = 0

    # ========================================================
    # DIFFICULTY × PERFORMANCE
    # ========================================================

    hard_points: int = 0
    medium_points: int = 0
    easy_points: int = 0

    hard_points_rate: Number = None
    medium_points_rate: Number = None
    easy_points_rate: Number = None

    # ========================================================
    # DIFFICULTY PROFILE
    # ========================================================

    hard_match_ratio: Number = None

    medium_match_ratio: Number = None

    easy_match_ratio: Number = None

    # ========================================================
    # GOAL PATTERNS
    # ========================================================

    goals_for_avg: Number = None
    goals_against_avg: Number = None

    goal_difference_avg: Number = None

    # ========================================================
    # xG PATTERNS
    # ========================================================

    xg_avg: Number = None
    xga_avg: Number = None

    xg_difference_avg: Number = None

    # --------------------------------------------------------
    # REALISATION
    # --------------------------------------------------------

    goals_minus_xg: Number = None

    goals_to_xg_ratio: Number = None

    # --------------------------------------------------------
    # DEFENSIVE CONVERSION
    # --------------------------------------------------------

    goals_against_minus_xga: Number = None

    # ========================================================
    # STATISTICAL SIGNALS
    # ========================================================

    attack_signal: Number = None

    defense_signal: Number = None

    xg_signal: Number = None

    realization_signal: Number = None

    consistency_signal: Number = None

    trend_signal: Number = None

    # ========================================================
    # POSSESSION / CONTROL
    # ========================================================

    possession_avg: Number = None

    possession_trend: Number = None

    # ========================================================
    # CORNERS
    # ========================================================

    corners_for_avg: Number = None

    corners_against_avg: Number = None

    # ========================================================
    # AGGRESSION
    # ========================================================

    cards_avg: Number = None

    fouls_avg: Number = None

    aggression_signal: Number = None

    # ========================================================
    # SPECIAL EFFECT DETECTION SIGNALS
    # ========================================================

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
    Математическая интерпретация FormContext + PatternState.

    Здесь FormModel превращает историю в:

        силу формы
        силу атаки
        силу обороны
        домашнюю силу
        гостевую силу
        тренд
        стабильность

    А также определяет величину влияния специальных эффектов.

    Конкретные формулы будут разрабатываться отдельно.
    """

    form_score: Number = None

    attack_strength: Number = None

    defense_strength: Number = None

    home_strength: Number = None

    away_strength: Number = None

    trend: Optional[str] = None

    consistency: Number = None

    # --------------------------------------------------------
    # DIFFICULTY INTERPRETATION
    # --------------------------------------------------------

    hard_match_strength: Number = None

    medium_match_strength: Number = None

    easy_match_strength: Number = None

    difficulty_adjustment: Number = None

    # --------------------------------------------------------
    # GOAL / xG INTERPRETATION
    # --------------------------------------------------------

    goal_strength: Number = None

    xg_strength: Number = None

    realization_strength: Number = None

    defensive_xg_strength: Number = None

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
    Ожидаемые голы будущего матча.

    Это уже прогнозный слой.

    GoalModel получает:

        FormModelResult
        PatternState
        исторические xG
        исторические голы
        старые рейтинги FAJ
        домашний фактор
        специальные эффекты

    и рассчитывает ожидаемые голы.
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
    Вероятности исходов и тоталов.
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

    Пока модель может оставаться неподключённой.
    Контракт заранее поддерживает её.
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
    Человеческая интерпретация результата Brain.
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

        home_form = FormContext
        away_form = FormContext

        home_patterns = PatternState
        away_patterns = PatternState
    """

    home_team: str

    away_team: str

    home_matches: Tuple[MatchRecord, ...]

    away_matches: Tuple[MatchRecord, ...]

    # --------------------------------------------------------
    # HISTORICAL CONTEXT
    # --------------------------------------------------------

    home_form: Optional[FormContext] = None

    away_form: Optional[FormContext] = None

    # --------------------------------------------------------
    # PATTERN STATE
    # --------------------------------------------------------

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
    # ANALYSIS
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

def result_to_points(result: str) -> int:
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
    Проверка диапазона.

    None = данные отсутствуют.

    None никогда не превращается в 0.
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
    Строгая проверка MatchRecord.
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
    Brain работает с ровно 6 последними матчами.
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
    Проверка FormContext.
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
# PATTERN STATE VALIDATION
# ============================================================

def validate_pattern_state(
    pattern: PatternState,
) -> None:
    """
    Проверка PatternState.

    PatternState не должен содержать
    значения за пределами математического контракта.
    """

    if pattern.matches_count < 0:
        raise ValueError(
            "PatternState: matches_count < 0"
        )

    if pattern.matches_count > HISTORY_MATCHES:
        raise ValueError(
            "PatternState: matches_count "
            f"({pattern.matches_count}) "
            f"> {HISTORY_MATCHES}"
        )

    # --------------------------------------------------------
    # Counts
    # --------------------------------------------------------

    count_fields = (
        "wins",
        "draws",
        "losses",
        "recent_wins",
        "recent_draws",
        "recent_losses",
        "consecutive_wins",
        "consecutive_losses",
        "consecutive_draws",
        "consecutive_away_matches",
        "home_matches",
        "home_wins",
        "home_draws",
        "home_losses",
        "home_unbeaten_count",
        "away_matches",
        "away_wins",
        "away_draws",
        "away_losses",
        "hard_matches",
        "hard_wins",
        "hard_draws",
        "hard_losses",
        "medium_matches",
        "medium_wins",
        "medium_draws",
        "medium_losses",
        "easy_matches",
        "easy_wins",
        "easy_draws",
        "easy_losses",
    )

    for field_name in count_fields:
        value = getattr(pattern, field_name)

        if value < 0:
            raise ValueError(
                f"PatternState: {field_name} < 0"
            )

    # --------------------------------------------------------
    # Rates
    # --------------------------------------------------------

    rate_fields = (
        "win_rate",
        "draw_rate",
        "loss_rate",
        "home_unbeaten_rate",
        "away_win_rate",
        "hard_points_rate",
        "medium_points_rate",
        "easy_points_rate",
        "hard_match_ratio",
        "medium_match_ratio",
        "easy_match_ratio",
    )

    for field_name in rate_fields:
        _validate_range(
            getattr(pattern, field_name),
            MIN_PROBABILITY,
            MAX_PROBABILITY,
            field_name,
        )

    # --------------------------------------------------------
    # Statistical signals
    # --------------------------------------------------------

    signal_fields = (
        "attack_signal",
        "defense_signal",
        "xg_signal",
        "realization_signal",
        "consistency_signal",
        "trend_signal",
        "aggression_signal",
        "dark_horse_signal",
        "lukaku_signal",
        "gladiator_signal",
        "fortress_signal",
        "leicester_signal",
        "kepa_signal",
        "haaland_signal",
        "god_kiss_signal",
    )

    for field_name in signal_fields:
        _validate_range(
            getattr(pattern, field_name),
            MIN_SIGNAL,
            MAX_SIGNAL,
            field_name,
        )

    # --------------------------------------------------------
    # Statistical averages
    # --------------------------------------------------------

    _validate_range(
        pattern.goals_for_avg,
        MIN_GOALS,
        MAX_GOALS,
        "pattern.goals_for_avg",
    )

    _validate_range(
        pattern.goals_against_avg,
        MIN_GOALS,
        MAX_GOALS,
        "pattern.goals_against_avg",
    )

    _validate_range(
        pattern.xg_avg,
        MIN_XG,
        MAX_XG,
        "pattern.xg_avg",
    )

    _validate_range(
        pattern.xga_avg,
        MIN_XG,
        MAX_XG,
        "pattern.xga_avg",
    )

    _validate_range(
        pattern.possession_avg,
        MIN_POSSESSION,
        MAX_POSSESSION,
        "pattern.possession_avg",
    )

    _validate_range(
        pattern.corners_for_avg,
        MIN_CORNERS,
        MAX_CORNERS,
        "pattern.corners_for_avg",
    )

    _validate_range(
        pattern.corners_against_avg,
        MIN_CORNERS,
        MAX_CORNERS,
        "pattern.corners_against_avg",
    )

    _validate_range(
        pattern.cards_avg,
        MIN_CARDS,
        MAX_CARDS,
        "pattern.cards_avg",
    )

    _validate_range(
        pattern.fouls_avg,
        MIN_FOULS,
        MAX_FOULS,
        "pattern.fouls_avg",
    )


# ============================================================
# BRAIN INPUT VALIDATION
# ============================================================

def validate_brain_input(
    data: BrainInput,
) -> None:
    """
    Полная проверка входа Brain.
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
    # PATTERNS
    # --------------------------------------------------------

    if data.home_patterns is not None:
        validate_pattern_state(
            data.home_patterns
        )

    if data.away_patterns is not None:
        validate_pattern_state(
            data.away_patterns
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

    # --------------------------------------------------------
    # FORM TEAM CONSISTENCY
    # --------------------------------------------------------

    if data.home_form is not None:
        if data.home_form.team != data.home_team:
            raise ValueError(
                "BrainInput: home_form.team != home_team"
            )

    if data.away_form is not None:
        if data.away_form.team != data.away_team:
            raise ValueError(
                "BrainInput: away_form.team != away_team"
            )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [

    # --------------------------------------------------------
    # Version / history
    # --------------------------------------------------------

    "CONTRACT_VERSION",
    "HISTORY_MATCHES",
    "MIN_HISTORY_MATCHES",
    "MAX_HISTORY_MATCHES",

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    "RESULT_WIN",
    "RESULT_DRAW",
    "RESULT_LOSS",
    "VALID_RESULTS",

    # --------------------------------------------------------
    # Difficulty
    # --------------------------------------------------------

    "DIFFICULTY_EASY",
    "DIFFICULTY_MEDIUM",
    "DIFFICULTY_HARD",
    "VALID_DIFFICULTIES",

    # --------------------------------------------------------
    # Effects
    # --------------------------------------------------------

    "EFFECT_DARK_HORSE",
    "EFFECT_LUKAKU",
    "EFFECT_GLADIATOR",
    "EFFECT_FORTRESS",
    "EFFECT_LEICESTER",
    "EFFECT_KEPA",
    "EFFECT_HAALAND",
    "EFFECT_GOD_KISS",
    "SPECIAL_EFFECTS",

    # --------------------------------------------------------
    # Core structures
    # --------------------------------------------------------

    "MatchRecord",
    "FormContext",
    "PatternState",

    # --------------------------------------------------------
    # Model results
    # --------------------------------------------------------

    "FormModelResult",
    "GoalModelResult",
    "ScoreModelResult",
    "ProbabilityModelResult",
    "CornersModelResult",
    "CardsModelResult",
    "AnalysisResult",

    # --------------------------------------------------------
    # Brain
    # --------------------------------------------------------

    "BrainInput",
    "BrainOutput",

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    "result_to_points",
    "validate_match_record",
    "validate_history",
    "validate_form_context",
    "validate_pattern_state",
    "validate_brain_input",
]

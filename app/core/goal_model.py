#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
GOAL MODEL v2.0
============================================================

НАЗНАЧЕНИЕ
----------

GoalModel преобразует фактическую xG-историю команды из
FormContext в λ (ожидаемые голы). Это единственная задача
GoalModel.

ПОЧЕМУ v2.0, А НЕ v1.2
----------------------

v1.2 добавляла bounded evidence adjustment:

    λ = λ_base × (1 + 0.15 × attack_evidence_signal)

Это выглядело безопасным (±15%, никаких внешних рейтингов),
но по факту являлось:

    1. Скрытым калиброванным коэффициентом (0.15), подобранным
       на тех же 8 контрольных матчах, на которых потом
       проверялось "улучшение" — классическая утечка данных
       (data leakage), а не валидация.

    2. Формой "Form → coefficient → xG", которую сам контракт
       проекта прямо запрещает (см. п.4 исходного ТЗ).

    3. Не решала реальную проблему (недооценку разгромов,
       М8: λ 2.21 vs xG факт 6.65) — сама архитектура
       "±15% от базовой λ" структурно не может разогнать λ
       на порядок при экстремальных сериях.

v2.0 полностью убирает влияние evidence на λ. λ считается
ТОЛЬКО из xG:

    λHome = (Home_XGF_rec + Away_XGA_rec) / 2
    λAway = (Away_XGF_rec + Home_XGA_rec) / 2

Расчёт evidence (shots/SOT/big chances) из v1.2 СОХРАНЁН, но
переведён в чисто диагностический статус — он не трогает λ,
а экспонируется как готовые relative-сигналы для отдельного,
явно выделенного слоя WinnerState (см. winner_state.py),
который используется ТОЛЬКО для отображения фаворита и не
участвует в математике прогноза.

ГИБКОСТЬ БЕЗ СКРЫТЫХ КОЭФФИЦИЕНТОВ
-----------------------------------

Вместо того чтобы зашивать "агрессивность" в виде magic number
внутри формулы λ, v2.0 делает НАСТРАИВАЕМОЙ саму схему
взвешивания истории — открыто, как параметр конструктора,
а не как скрытый adjustment:

    temporal_weighting = "linear"       (по умолчанию, как в v1.0/v1.1)
    temporal_weighting = "quadratic"    (сильнее давит на recency)
    temporal_weighting = "exponential"  (ещё сильнее, growth настраивается)

По умолчанию поведение НЕ меняется (linear, как всегда). Более
агрессивные схемы существуют для будущих контролируемых
экспериментов на ОТДЕЛЬНОМ наборе матчей — они не включены
автоматически и не являются полученным "решением" разгромов,
только инструментом для его контролируемого исследования.

ВАЖНО
------

MISSING != 0. Diagnostic organs (FormWin/Defence/Control/
Anomaly/SpecialForm) по-прежнему НЕ участвуют в расчёте λ.
Не используется: FAJ Rating, рейтинг лиги, bookmaker odds,
future result, learning, Winner Override, home advantage
coefficient, geometric mean, finishing bonus.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


# ============================================================
# VERSION
# ============================================================

GOAL_MODEL_VERSION = "2.0"

DEFAULT_MAX_HISTORY = 6

DEFAULT_TEMPORAL_WEIGHTING = "linear"
DEFAULT_WEIGHTING_GROWTH = 1.5

VALID_WEIGHTING_SCHEMES = (
    "linear",
    "quadratic",
    "exponential",
)


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        text = str(value).strip()

        if not text:
            return None

        text = text.replace(",", ".")

        return float(text)

    except (TypeError, ValueError):
        return None


def _get_value(record: Any, *keys: str) -> Any:
    """
    Поддерживает dict / sqlite3.Row / object attributes.
    """

    if record is None:
        return None

    for key in keys:

        if isinstance(record, dict):
            if key in record:
                return record[key]

        try:
            if key in record.keys():
                return record[key]
        except (AttributeError, TypeError):
            pass

        try:
            return getattr(record, key)
        except AttributeError:
            pass

    return None


def _to_sequence(value: Any) -> List[Any]:

    if value is None:
        return []

    if isinstance(value, (list, tuple)):
        return list(value)

    return [value]


# ============================================================
# WEIGHTING SCHEMES
# ============================================================

def _weights_for(
    n: int,
    scheme: str = DEFAULT_TEMPORAL_WEIGHTING,
    growth: float = DEFAULT_WEIGHTING_GROWTH,
) -> List[float]:
    """
    Генерирует веса для позиций 1..n (oldest -> newest).

    Каждая схема — явная, документированная, не калиброванная
    под конкретные матчи. Разница со скрытым коэффициентом:
    здесь нет числа, подобранного так, чтобы "починить" один
    контрольный набор — это выбор МЕТОДА агрегации, известный
    заранее и одинаковый для всех матчей.

    linear:
        веса 1, 2, ..., n  (контракт v1.0/v1.1, по умолчанию)

    quadratic:
        веса 1^2, 2^2, ..., n^2 — сильнее давит на свежие матчи

    exponential:
        веса growth^0, growth^1, ..., growth^(n-1)
        growth > 1.0, по умолчанию 1.5
    """

    if n <= 0:
        return []

    positions = range(1, n + 1)

    if scheme == "quadratic":
        return [float(i) ** 2 for i in positions]

    if scheme == "exponential":
        g = growth if growth and growth > 1.0 else DEFAULT_WEIGHTING_GROWTH
        return [g ** (i - 1) for i in positions]

    # "linear" и любое нераспознанное значение -> безопасный дефолт
    return [float(i) for i in positions]


def weighted_mean(
    values: List[Optional[float]],
    weights: Optional[List[float]] = None,
) -> Optional[float]:
    """
    Recency-weighted mean.

    values предполагается oldest -> newest.

    None НЕ получает вес и не входит в denominator (Missing != 0).

    Если weights не переданы — используется linear-схема
    (обратная совместимость с v1.0/v1.1).
    """

    if not values:
        return None

    if weights is None:
        weights = _weights_for(len(values), "linear")

    numerator = 0.0
    denominator = 0.0

    for value, weight in zip(values, weights):

        number = _safe_float(value)

        if number is None:
            continue

        numerator += weight * number
        denominator += weight

    if denominator <= 0:
        return None

    return numerator / denominator


# ============================================================
# GOAL STATE
# ============================================================

@dataclass
class GoalState:

    model_version: str = GOAL_MODEL_VERSION

    home_team: Optional[str] = None
    away_team: Optional[str] = None

    # --------------------------------------------------------
    # PRIMARY xG STATE — единственный источник λ
    # --------------------------------------------------------

    home_xgf_rec: Optional[float] = None
    home_xga_rec: Optional[float] = None

    away_xgf_rec: Optional[float] = None
    away_xga_rec: Optional[float] = None

    # --------------------------------------------------------
    # FINAL LAMBDA — только xG, evidence НЕ применяется
    # --------------------------------------------------------

    home_lambda: Optional[float] = None
    away_lambda: Optional[float] = None

    total_lambda: Optional[float] = None

    # --------------------------------------------------------
    # DIAGNOSTIC-ONLY EVIDENCE (не влияет на λ)
    #
    # Сохранено из v1.2 как готовый материал для WinnerState.
    # --------------------------------------------------------

    home_shots_rec: Optional[float] = None
    away_shots_rec: Optional[float] = None

    home_sot_rec: Optional[float] = None
    away_sot_rec: Optional[float] = None

    home_big_chances_rec: Optional[float] = None
    away_big_chances_rec: Optional[float] = None

    home_attack_evidence_signal: Optional[float] = None
    away_attack_evidence_signal: Optional[float] = None

    # --------------------------------------------------------
    # SAMPLES / AVAILABILITY
    # --------------------------------------------------------

    home_xgf_sample: int = 0
    home_xga_sample: int = 0

    away_xgf_sample: int = 0
    away_xga_sample: int = 0

    home_matches: int = 0
    away_matches: int = 0

    home_lambda_available: bool = False
    away_lambda_available: bool = False

    calculation_valid: bool = False

    # --------------------------------------------------------
    # ARCHITECTURE TRANSPARENCY
    # --------------------------------------------------------

    architecture_notes: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# GOAL MODEL
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v2.0.

    Единственная математическая задача:

        FACT xG history -> recency-weighted XGF/XGA
                         -> λHome / λAway

    Evidence (shots/SOT/big chances) считается для диагностики,
    но НИКОГДА не изменяет λ. Любая будущая калиброванная
    коррекция λ должна жить в отдельном, явно одобренном
    модуле — не здесь и не как скрытый multiplier.
    """

    VERSION = GOAL_MODEL_VERSION
    MAX_HISTORY = DEFAULT_MAX_HISTORY

    def __init__(
        self,
        max_history: int = DEFAULT_MAX_HISTORY,
        temporal_weighting: str = DEFAULT_TEMPORAL_WEIGHTING,
        weighting_growth: float = DEFAULT_WEIGHTING_GROWTH,
    ) -> None:

        self.max_history = max(int(max_history), 1)

        if temporal_weighting not in VALID_WEIGHTING_SCHEMES:
            temporal_weighting = DEFAULT_TEMPORAL_WEIGHTING

        self.temporal_weighting = temporal_weighting
        self.weighting_growth = weighting_growth

    # ========================================================
    # HISTORY
    # ========================================================

    def _extract_history(self, context: Any, key: str) -> List[Optional[float]]:

        value = _get_value(context, key)
        values = _to_sequence(value)[: self.max_history]

        return [_safe_float(v) for v in values]

    def _weighted(self, values: List[Optional[float]]) -> Optional[float]:

        weights = _weights_for(
            len(values),
            self.temporal_weighting,
            self.weighting_growth,
        )

        return weighted_mean(values, weights)

    # ========================================================
    # XG
    # ========================================================

    def _calculate_xgf(self, context: Any) -> Optional[float]:
        return self._weighted(self._extract_history(context, "team_xg_history"))

    def _calculate_xga(self, context: Any) -> Optional[float]:
        return self._weighted(self._extract_history(context, "opponent_xg_history"))

    # ========================================================
    # DIAGNOSTIC-ONLY EVIDENCE (shots / SOT / big chances)
    # ========================================================

    def _calculate_shots(self, context: Any) -> Optional[float]:
        return self._weighted(self._extract_history(context, "shots_history"))

    def _calculate_shots_against(self, context: Any) -> Optional[float]:
        return self._weighted(self._extract_history(context, "shots_conceded_history"))

    def _calculate_sot(self, context: Any) -> Optional[float]:
        return self._weighted(self._extract_history(context, "shots_on_target_history"))

    def _calculate_sot_against(self, context: Any) -> Optional[float]:
        return self._weighted(
            self._extract_history(context, "shots_on_target_against_history")
        )

    def _calculate_big_chances(self, context: Any) -> Optional[float]:
        return self._weighted(self._extract_history(context, "big_chances_history"))

    def _calculate_big_chances_against(self, context: Any) -> Optional[float]:
        return self._weighted(
            self._extract_history(context, "big_chances_against_history")
        )

    @staticmethod
    def _normalized_difference(
        team_value: Optional[float],
        opponent_value: Optional[float],
    ) -> Optional[float]:
        """
        Симметричная нормализация в [-1, +1].

        (team - opponent) / (team + opponent)

        None != 0. Используется ТОЛЬКО как diagnostic evidence,
        не как вход в λ.
        """

        if team_value is None or opponent_value is None:
            return None

        denominator = team_value + opponent_value

        if denominator <= 0:
            return None

        signal = (team_value - opponent_value) / denominator

        return max(-1.0, min(1.0, signal))

    @staticmethod
    def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:

        if numerator is None or denominator is None:
            return None

        if denominator <= 0:
            return None

        return numerator / denominator

    @staticmethod
    def _mean_available(values: List[Optional[float]]) -> Optional[float]:

        available = [v for v in values if v is not None]

        if not available:
            return None

        return sum(available) / len(available)

    def _attack_evidence_signal(
        self,
        shots: Optional[float],
        opponent_shots_against: Optional[float],
        sot_per_shot: Optional[float],
        opponent_sot_against_per_shot: Optional[float],
        big_chances_per_shot: Optional[float],
        opponent_big_chances_against_per_shot: Optional[float],
    ) -> Optional[float]:
        """
        Диагностический композит трёх симметричных сигналов.

        Это готовое, но НЕ применяемое к λ значение — экспонируется
        только для WinnerState / будущего Confidence State.
        """

        shot_volume = self._normalized_difference(shots, opponent_shots_against)

        sot_quality = self._normalized_difference(
            sot_per_shot, opponent_sot_against_per_shot
        )

        big_chances_quality = self._normalized_difference(
            big_chances_per_shot, opponent_big_chances_against_per_shot
        )

        return self._mean_available([shot_volume, sot_quality, big_chances_quality])

    # ========================================================
    # LAMBDA (единственная точка, где считается λ)
    # ========================================================

    @staticmethod
    def _calculate_lambda(
        attack_xgf: Optional[float],
        opponent_xga: Optional[float],
    ) -> Optional[float]:

        if attack_xgf is None or opponent_xga is None:
            return None

        return (attack_xgf + opponent_xga) / 2.0

    # ========================================================
    # SAMPLES / MATCH COUNT
    # ========================================================

    def _count_available(self, values: List[Optional[float]]) -> int:
        return sum(1 for v in values if v is not None)

    def _get_matches_count(self, context: Any, fallback_key: str) -> int:

        value = _get_value(context, "matches_count")

        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            pass

        return len(self._extract_history(context, fallback_key))

    # ========================================================
    # MAIN CALCULATION
    # ========================================================

    def calculate(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> GoalState:

        if home_team is None:
            home_team = _get_value(home_context, "team", "home_team")

        if away_team is None:
            away_team = _get_value(away_context, "team", "away_team")

        # ----------------------------------------------------
        # xG -> λ (единственный вход)
        # ----------------------------------------------------

        home_xgf = self._calculate_xgf(home_context)
        home_xga = self._calculate_xga(home_context)

        away_xgf = self._calculate_xgf(away_context)
        away_xga = self._calculate_xga(away_context)

        home_lambda = self._calculate_lambda(home_xgf, away_xga)
        away_lambda = self._calculate_lambda(away_xgf, home_xga)

        total_lambda = (
            home_lambda + away_lambda
            if home_lambda is not None and away_lambda is not None
            else None
        )

        # ----------------------------------------------------
        # Diagnostic-only evidence (shots / SOT / big chances)
        # ----------------------------------------------------

        home_shots = self._calculate_shots(home_context)
        away_shots = self._calculate_shots(away_context)

        home_shots_against = self._calculate_shots_against(home_context)
        away_shots_against = self._calculate_shots_against(away_context)

        home_sot = self._calculate_sot(home_context)
        away_sot = self._calculate_sot(away_context)

        home_sot_against = self._calculate_sot_against(home_context)
        away_sot_against = self._calculate_sot_against(away_context)

        home_big_chances = self._calculate_big_chances(home_context)
        away_big_chances = self._calculate_big_chances(away_context)

        home_big_chances_against = self._calculate_big_chances_against(home_context)
        away_big_chances_against = self._calculate_big_chances_against(away_context)

        home_sot_per_shot = self._ratio(home_sot, home_shots)
        away_sot_per_shot = self._ratio(away_sot, away_shots)

        home_sot_against_per_shot = self._ratio(home_sot_against, home_shots_against)
        away_sot_against_per_shot = self._ratio(away_sot_against, away_shots_against)

        home_big_chances_per_shot = self._ratio(home_big_chances, home_shots)
        away_big_chances_per_shot = self._ratio(away_big_chances, away_shots)

        home_big_chances_against_per_shot = self._ratio(
            home_big_chances_against, home_shots_against
        )
        away_big_chances_against_per_shot = self._ratio(
            away_big_chances_against, away_shots_against
        )

        home_attack_evidence_signal = self._attack_evidence_signal(
            shots=home_shots,
            opponent_shots_against=away_shots_against,
            sot_per_shot=home_sot_per_shot,
            opponent_sot_against_per_shot=away_sot_against_per_shot,
            big_chances_per_shot=home_big_chances_per_shot,
            opponent_big_chances_against_per_shot=away_big_chances_against_per_shot,
        )

        away_attack_evidence_signal = self._attack_evidence_signal(
            shots=away_shots,
            opponent_shots_against=home_shots_against,
            sot_per_shot=away_sot_per_shot,
            opponent_sot_against_per_shot=home_sot_against_per_shot,
            big_chances_per_shot=away_big_chances_per_shot,
            opponent_big_chances_against_per_shot=home_big_chances_against_per_shot,
        )

        # ----------------------------------------------------
        # Samples / availability
        # ----------------------------------------------------

        home_xgf_sample = self._count_available(
            self._extract_history(home_context, "team_xg_history")
        )
        home_xga_sample = self._count_available(
            self._extract_history(home_context, "opponent_xg_history")
        )
        away_xgf_sample = self._count_available(
            self._extract_history(away_context, "team_xg_history")
        )
        away_xga_sample = self._count_available(
            self._extract_history(away_context, "opponent_xg_history")
        )

        home_matches = self._get_matches_count(home_context, "team_xg_history")
        away_matches = self._get_matches_count(away_context, "team_xg_history")

        home_lambda_available = home_lambda is not None
        away_lambda_available = away_lambda is not None

        calculation_valid = home_lambda_available and away_lambda_available

        architecture_notes = {
            "lambda_source": "xG only (team_xg_history / opponent_xg_history)",
            "evidence_applied_to_lambda": False,
            "evidence_signals_purpose": (
                "diagnostic only; consumed by WinnerState for display, "
                "never fed back into λ"
            ),
            "temporal_weighting": self.temporal_weighting,
            "temporal_weighting_growth": (
                self.weighting_growth
                if self.temporal_weighting == "exponential"
                else None
            ),
            "rollback_reason": (
                "v1.2 bounded evidence adjustment (±15%) violated Contract v1 "
                "(FORM -> coefficient -> xG pattern) and was calibrated on the "
                "same 8 matches used for its own validation (data leakage). "
                "Reverted in v2.0; blowout underestimation must be addressed "
                "by a separately validated module, not a hidden multiplier."
            ),
        }

        return GoalState(
            model_version=self.VERSION,
            home_team=str(home_team) if home_team is not None else None,
            away_team=str(away_team) if away_team is not None else None,
            home_xgf_rec=home_xgf,
            home_xga_rec=home_xga,
            away_xgf_rec=away_xgf,
            away_xga_rec=away_xga,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            total_lambda=total_lambda,
            home_shots_rec=home_shots,
            away_shots_rec=away_shots,
            home_sot_rec=home_sot,
            away_sot_rec=away_sot,
            home_big_chances_rec=home_big_chances,
            away_big_chances_rec=away_big_chances,
            home_attack_evidence_signal=home_attack_evidence_signal,
            away_attack_evidence_signal=away_attack_evidence_signal,
            home_xgf_sample=home_xgf_sample,
            home_xga_sample=home_xga_sample,
            away_xgf_sample=away_xgf_sample,
            away_xga_sample=away_xga_sample,
            home_matches=home_matches,
            away_matches=away_matches,
            home_lambda_available=home_lambda_available,
            away_lambda_available=away_lambda_available,
            calculation_valid=calculation_valid,
            architecture_notes=architecture_notes,
        )

    # ========================================================
    # DICT API / COMPATIBILITY
    # ========================================================

    def predict(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> Dict[str, Any]:

        state = self.calculate(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )

        return asdict(state)

    def calculate_goal_state(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> Dict[str, Any]:

        return self.predict(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )


# ============================================================
# SIMPLE FUNCTION API
# ============================================================

def calculate_goal_state(
    home_context: Any,
    away_context: Any,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    max_history: int = DEFAULT_MAX_HISTORY,
    temporal_weighting: str = DEFAULT_TEMPORAL_WEIGHTING,
) -> Dict[str, Any]:

    model = GoalModel(
        max_history=max_history,
        temporal_weighting=temporal_weighting,
    )

    return model.predict(
        home_context=home_context,
        away_context=away_context,
        home_team=home_team,
        away_team=away_team,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    home_context = {
        "team": "Зенит",
        "matches_count": 6,
        "team_xg_history": (1.00, 1.20, 1.40, 1.60, 1.80, 2.00),
        "opponent_xg_history": (1.40, 1.30, 1.20, 1.10, 1.00, 0.90),
    }

    away_context = {
        "team": "ЦСКА",
        "matches_count": 6,
        "team_xg_history": (1.20, 1.30, 1.40, 1.50, 1.60, 1.70),
        "opponent_xg_history": (1.60, 1.50, 1.40, 1.30, 1.20, 1.10),
    }

    result = GoalModel().calculate(home_context, away_context)

    print("GOAL MODEL v2.0")
    print("Home λ:", result.home_lambda)
    print("Away λ:", result.away_lambda)
    print("Evidence applied to λ:", result.architecture_notes["evidence_applied_to_lambda"])

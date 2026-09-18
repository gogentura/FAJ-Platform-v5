#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
GOAL MODEL v1.1
============================================================

НАЗНАЧЕНИЕ
----------

GoalModel преобразует фактическую историю команды
из FormContext в ожидаемый goal state.

v1.1 расширяет входной контракт:

    xG
    xGA
    shots
    shots conceded
    shots on target
    shots on target conceded
    big chances
    big chances conceded

ВАЖНО
------

v1.1 НЕ вводит произвольные коэффициенты.

Текущая λ остаётся контрольной:

    Home λ =
        (Home XGF_rec + Away XGA_rec) / 2

    Away λ =
        (Away XGF_rec + Home XGA_rec) / 2

Дополнительная статистика пока является
EVIDENCE STATE.

Она рассчитывается отдельно и НЕ изменяет λ.

Это сделано намеренно:

    1. сначала подключаем все фактические данные;
    2. проверяем их наличие и качество;
    3. анализируем связь с xG;
    4. только после математического аудита
       определяем способ влияния на λ.

НЕ используется:

    - FAJ Rating
    - рейтинг лиги
    - таблица
    - bookmaker odds
    - future result
    - learning
    - arbitrary multipliers
    - winner override
    - form multiplier
    - control multiplier
    - defence multiplier
    - geometric mean
    - finishing bonus
    - home advantage coefficient

MISSING != 0

None остаётся None.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


# ============================================================
# VERSION
# ============================================================

GOAL_MODEL_VERSION = "1.1"

DEFAULT_MAX_HISTORY = 6


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(
    value: Any,
) -> Optional[float]:

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


def _get_value(
    record: Any,
    *keys: str,
) -> Any:
    """
    Поддерживает:

        dict
        sqlite3.Row
        object attributes
    """

    if record is None:
        return None

    for key in keys:

        # ----------------------------------------------------
        # dict
        # ----------------------------------------------------

        if isinstance(record, dict):

            if key in record:
                return record[key]

        # ----------------------------------------------------
        # sqlite3.Row / mapping
        # ----------------------------------------------------

        try:

            if key in record.keys():

                return record[key]

        except (
            AttributeError,
            TypeError,
        ):

            pass

        # ----------------------------------------------------
        # object
        # ----------------------------------------------------

        try:

            return getattr(
                record,
                key,
            )

        except AttributeError:

            pass

    return None


# ============================================================
# HISTORY NORMALIZATION
# ============================================================

def _to_sequence(
    value: Any,
) -> List[Any]:

    if value is None:
        return []

    if isinstance(
        value,
        (list, tuple),
    ):
        return list(value)

    return [value]


# ============================================================
# RECENCY WEIGHTED MEAN
# ============================================================

def weighted_mean(
    values: List[Optional[float]],
) -> Optional[float]:
    """
    Temporal weighting:

        M1 = 1
        M2 = 2
        ...
        M6 = 6

    История должна приходить:

        oldest -> newest

    None НЕ превращается в 0.

    ВАЖНО:

    Индекс исходной временной позиции сохраняется.

    Например:

        [1.0, None, 3.0]

    использует веса:

        1 и 3

    а не:

        1 и 2

    Это сохраняет реальную временную позицию
    наблюдения.
    """

    weighted_sum = 0.0
    weight_sum = 0.0

    for index, value in enumerate(
        values,
        start=1,
    ):

        numeric = _safe_float(value)

        if numeric is None:
            continue

        weighted_sum += (
            numeric * index
        )

        weight_sum += index

    if weight_sum == 0:

        return None

    return (
        weighted_sum
        / weight_sum
    )


# ============================================================
# GOAL STATE
# ============================================================

@dataclass
class GoalState:

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    model_version: str

    home_team: Optional[str]

    away_team: Optional[str]

    # --------------------------------------------------------
    # PRIMARY xG STATE
    # --------------------------------------------------------

    home_xgf_rec: Optional[float]

    home_xga_rec: Optional[float]

    away_xgf_rec: Optional[float]

    away_xga_rec: Optional[float]

    # --------------------------------------------------------
    # GOAL LAMBDA
    # --------------------------------------------------------

    home_lambda: Optional[float]

    away_lambda: Optional[float]

    total_lambda: Optional[float]

    # ========================================================
    # ATTACK EVIDENCE
    # ========================================================

    home_shots_rec: Optional[float]

    away_shots_rec: Optional[float]

    home_sot_rec: Optional[float]

    away_sot_rec: Optional[float]

    home_big_chances_rec: Optional[float]

    away_big_chances_rec: Optional[float]

    # ========================================================
    # DEFENSIVE EVIDENCE
    # ========================================================

    home_shots_against_rec: Optional[float]

    away_shots_against_rec: Optional[float]

    home_sot_against_rec: Optional[float]

    away_sot_against_rec: Optional[float]

    home_big_chances_against_rec: Optional[float]

    away_big_chances_against_rec: Optional[float]

    # ========================================================
    # EVIDENCE DIFFERENTIALS
    # ========================================================

    home_shots_diff_rec: Optional[float]

    away_shots_diff_rec: Optional[float]

    home_sot_diff_rec: Optional[float]

    away_sot_diff_rec: Optional[float]

    home_big_chances_diff_rec: Optional[float]

    away_big_chances_diff_rec: Optional[float]

    # ========================================================
    # OPPORTUNITY RATIOS
    # ========================================================

    home_sot_per_shot: Optional[float]

    away_sot_per_shot: Optional[float]

    home_big_chances_per_shot: Optional[float]

    away_big_chances_per_shot: Optional[float]

    # ========================================================
    # SAMPLES
    # ========================================================

    home_xgf_sample: int

    home_xga_sample: int

    away_xgf_sample: int

    away_xga_sample: int

    home_shots_sample: int

    away_shots_sample: int

    home_sot_sample: int

    away_sot_sample: int

    home_big_chances_sample: int

    away_big_chances_sample: int

    # --------------------------------------------------------
    # MATCH COUNTS
    # --------------------------------------------------------

    home_matches: int

    away_matches: int

    # --------------------------------------------------------
    # AVAILABILITY
    # --------------------------------------------------------

    xg_available: bool

    shots_available: bool

    sot_available: bool

    big_chances_available: bool

    # --------------------------------------------------------
    # VALIDITY
    # --------------------------------------------------------

    calculation_valid: bool


# ============================================================
# GOAL MODEL
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v1.1.

    Главный принцип:

        xG остаётся первичной математической основой λ.

    Новые статистические ряды подключаются как
    evidence state, но пока не изменяют λ.
    """

    def __init__(
        self,
        max_history: int = DEFAULT_MAX_HISTORY,
    ):

        self.max_history = max(
            int(max_history),
            1,
        )

    # ========================================================
    # HISTORY
    # ========================================================

    def _extract_history(
        self,
        context: Any,
        key: str,
    ) -> List[Optional[float]]:
        """
        Извлекает историю из FormContext.

        Ожидаемый порядок:

            M1 -> M6

        oldest -> newest

        FormContext v1.9 уже ограничивает историю
        шестью матчами.

        Здесь сохраняем только защитное ограничение.
        """

        value = _get_value(
            context,
            key,
        )

        values = _to_sequence(
            value
        )

        # ----------------------------------------------------
        # Контракт FormContext:
        #
        # records уже canonical:
        # oldest -> newest
        #
        # Поэтому нельзя брать последние N
        # через [-N:], если контекст уже ограничен.
        # ----------------------------------------------------

        if len(values) > self.max_history:

            values = values[
                :self.max_history
            ]

        result: List[
            Optional[float]
        ] = []

        for value in values:

            result.append(
                _safe_float(value)
            )

        return result

    # ========================================================
    # XG
    # ========================================================

    def _calculate_xgf(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "team_xg_history",
            )
        )

    def _calculate_xga(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "opponent_xg_history",
            )
        )

    # ========================================================
    # ATTACK EVIDENCE
    # ========================================================

    def _calculate_shots(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "shots_history",
            )
        )

    def _calculate_sot(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "shots_on_target_history",
            )
        )

    def _calculate_big_chances(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "big_chances_history",
            )
        )

    # ========================================================
    # DEFENCE EVIDENCE
    # ========================================================

    def _calculate_shots_against(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "shots_conceded_history",
            )
        )

    def _calculate_sot_against(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "shots_on_target_against_history",
            )
        )

    def _calculate_big_chances_against(
        self,
        context: Any,
    ) -> Optional[float]:

        return weighted_mean(
            self._extract_history(
                context,
                "big_chances_against_history",
            )
        )

    # ========================================================
    # SAMPLE COUNT
    # ========================================================

    def _count_available(
        self,
        values: List[Optional[float]],
    ) -> int:

        return sum(
            1
            for value in values
            if value is not None
        )

    # ========================================================
    # MATCH COUNT
    # ========================================================

    def _get_matches_count(
        self,
        context: Any,
        fallback_key: str,
    ) -> int:

        value = _get_value(
            context,
            "matches_count",
        )

        try:

            if value is not None:

                return int(value)

        except (
            TypeError,
            ValueError,
        ):

            pass

        return len(
            self._extract_history(
                context,
                fallback_key,
            )
        )

    # ========================================================
    # LAMBDA
    # ========================================================

    def _calculate_lambda(
        self,
        attack_xgf: Optional[float],
        opponent_xga: Optional[float],
    ) -> Optional[float]:
        """
        КОНТРОЛЬНАЯ формула v1.0.

        λ =
            (attack XGF + opponent XGA) / 2

        Никаких дополнительных коэффициентов.
        """

        if (
            attack_xgf is None
            or opponent_xga is None
        ):

            return None

        return (
            attack_xgf
            + opponent_xga
        ) / 2.0

    # ========================================================
    # DIFFERENTIAL
    # ========================================================

    @staticmethod
    def _difference(
        attack: Optional[float],
        defence: Optional[float],
    ) -> Optional[float]:

        if (
            attack is None
            or defence is None
        ):

            return None

        return attack - defence

    # ========================================================
    # RATIO
    # ========================================================

    @staticmethod
    def _ratio(
        numerator: Optional[float],
        denominator: Optional[float],
    ) -> Optional[float]:

        if (
            numerator is None
            or denominator is None
        ):

            return None

        if denominator <= 0:

            return None

        return (
            numerator
            / denominator
        )

    # ========================================================
    # CALCULATE
    # ========================================================

    def calculate(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> GoalState:
        """
        Рассчитывает полный GoalState.

        ВАЖНО:

        Новые статистические данные рассчитываются
        и сохраняются в state.

        Они НЕ вмешиваются в λ.
        """

        # ====================================================
        # TEAM NAMES
        # ====================================================

        if home_team is None:

            home_team = _get_value(
                home_context,
                "team",
                "home_team",
            )

        if away_team is None:

            away_team = _get_value(
                away_context,
                "team",
                "away_team",
            )

        # ====================================================
        # PRIMARY XG
        # ====================================================

        home_xgf = self._calculate_xgf(
            home_context
        )

        home_xga = self._calculate_xga(
            home_context
        )

        away_xgf = self._calculate_xgf(
            away_context
        )

        away_xga = self._calculate_xga(
            away_context
        )

        # ====================================================
        # ATTACK EVIDENCE
        # ====================================================

        home_shots_values = (
            self._extract_history(
                home_context,
                "shots_history",
            )
        )

        away_shots_values = (
            self._extract_history(
                away_context,
                "shots_history",
            )
        )

        home_sot_values = (
            self._extract_history(
                home_context,
                "shots_on_target_history",
            )
        )

        away_sot_values = (
            self._extract_history(
                away_context,
                "shots_on_target_history",
            )
        )

        home_big_chances_values = (
            self._extract_history(
                home_context,
                "big_chances_history",
            )
        )

        away_big_chances_values = (
            self._extract_history(
                away_context,
                "big_chances_history",
            )
        )

        # ====================================================
        # DEFENCE EVIDENCE
        # ====================================================

        home_shots_against_values = (
            self._extract_history(
                home_context,
                "shots_conceded_history",
            )
        )

        away_shots_against_values = (
            self._extract_history(
                away_context,
                "shots_conceded_history",
            )
        )

        home_sot_against_values = (
            self._extract_history(
                home_context,
                "shots_on_target_against_history",
            )
        )

        away_sot_against_values = (
            self._extract_history(
                away_context,
                "shots_on_target_against_history",
            )
        )

        home_big_chances_against_values = (
            self._extract_history(
                home_context,
                "big_chances_against_history",
            )
        )

        away_big_chances_against_values = (
            self._extract_history(
                away_context,
                "big_chances_against_history",
            )
        )

        # ====================================================
        # RECENCY VALUES
        # ====================================================

        home_shots = weighted_mean(
            home_shots_values
        )

        away_shots = weighted_mean(
            away_shots_values
        )

        home_sot = weighted_mean(
            home_sot_values
        )

        away_sot = weighted_mean(
            away_sot_values
        )

        home_big_chances = weighted_mean(
            home_big_chances_values
        )

        away_big_chances = weighted_mean(
            away_big_chances_values
        )

        home_shots_against = weighted_mean(
            home_shots_against_values
        )

        away_shots_against = weighted_mean(
            away_shots_against_values
        )

        home_sot_against = weighted_mean(
            home_sot_against_values
        )

        away_sot_against = weighted_mean(
            away_sot_against_values
        )

        home_big_chances_against = weighted_mean(
            home_big_chances_against_values
        )

        away_big_chances_against = weighted_mean(
            away_big_chances_against_values
        )

        # ====================================================
        # EVIDENCE DIFFERENTIALS
        # ====================================================

        home_shots_diff = self._difference(
            home_shots,
            home_shots_against,
        )

        away_shots_diff = self._difference(
            away_shots,
            away_shots_against,
        )

        home_sot_diff = self._difference(
            home_sot,
            home_sot_against,
        )

        away_sot_diff = self._difference(
            away_sot,
            away_sot_against,
        )

        home_big_chances_diff = self._difference(
            home_big_chances,
            home_big_chances_against,
        )

        away_big_chances_diff = self._difference(
            away_big_chances,
            away_big_chances_against,
        )

        # ====================================================
        # OPPORTUNITY RATIOS
        # ====================================================

        home_sot_per_shot = self._ratio(
            home_sot,
            home_shots,
        )

        away_sot_per_shot = self._ratio(
            away_sot,
            away_shots,
        )

        home_big_chances_per_shot = self._ratio(
            home_big_chances,
            home_shots,
        )

        away_big_chances_per_shot = self._ratio(
            away_big_chances,
            away_shots,
        )

        # ====================================================
        # LAMBDA
        # ====================================================

        home_lambda = self._calculate_lambda(
            home_xgf,
            away_xga,
        )

        away_lambda = self._calculate_lambda(
            away_xgf,
            home_xga,
        )

        if (
            home_lambda is not None
            and away_lambda is not None
        ):

            total_lambda = (
                home_lambda
                + away_lambda
            )

        else:

            total_lambda = None

        # ====================================================
        # SAMPLES
        # ====================================================

        home_xgf_sample = (
            self._count_available(
                self._extract_history(
                    home_context,
                    "team_xg_history",
                )
            )
        )

        home_xga_sample = (
            self._count_available(
                self._extract_history(
                    home_context,
                    "opponent_xg_history",
                )
            )
        )

        away_xgf_sample = (
            self._count_available(
                self._extract_history(
                    away_context,
                    "team_xg_history",
                )
            )
        )

        away_xga_sample = (
            self._count_available(
                self._extract_history(
                    away_context,
                    "opponent_xg_history",
                )
            )
        )

        home_shots_sample = (
            self._count_available(
                home_shots_values
            )
        )

        away_shots_sample = (
            self._count_available(
                away_shots_values
            )
        )

        home_sot_sample = (
            self._count_available(
                home_sot_values
            )
        )

        away_sot_sample = (
            self._count_available(
                away_sot_values
            )
        )

        home_big_chances_sample = (
            self._count_available(
                home_big_chances_values
            )
        )

        away_big_chances_sample = (
            self._count_available(
                away_big_chances_values
            )
        )

        # ====================================================
        # MATCH COUNTS
        # ====================================================

        home_matches = (
            self._get_matches_count(
                home_context,
                "team_xg_history",
            )
        )

        away_matches = (
            self._get_matches_count(
                away_context,
                "team_xg_history",
            )
        )

        # ====================================================
        # AVAILABILITY
        # ====================================================

        xg_available = (
            home_xgf is not None
            and home_xga is not None
            and away_xgf is not None
            and away_xga is not None
        )

        shots_available = (
            home_shots_sample > 0
            and away_shots_sample > 0
        )

        sot_available = (
            home_sot_sample > 0
            and away_sot_sample > 0
        )

        big_chances_available = (
            home_big_chances_sample > 0
            and away_big_chances_sample > 0
        )

        # ====================================================
        # VALIDITY
        # ====================================================

        calculation_valid = (
            home_lambda is not None
            and away_lambda is not None
        )

        # ====================================================
        # RETURN
        # ====================================================

        return GoalState(

            model_version=GOAL_MODEL_VERSION,

            home_team=(
                str(home_team)
                if home_team is not None
                else None
            ),

            away_team=(
                str(away_team)
                if away_team is not None
                else None
            ),

            # ------------------------------------------------
            # xG
            # ------------------------------------------------

            home_xgf_rec=home_xgf,
            home_xga_rec=home_xga,

            away_xgf_rec=away_xgf,
            away_xga_rec=away_xga,

            # ------------------------------------------------
            # Lambda
            # ------------------------------------------------

            home_lambda=home_lambda,
            away_lambda=away_lambda,
            total_lambda=total_lambda,

            # ------------------------------------------------
            # Attack evidence
            # ------------------------------------------------

            home_shots_rec=home_shots,
            away_shots_rec=away_shots,

            home_sot_rec=home_sot,
            away_sot_rec=away_sot,

            home_big_chances_rec=home_big_chances,
            away_big_chances_rec=away_big_chances,

            # ------------------------------------------------
            # Defence evidence
            # ------------------------------------------------

            home_shots_against_rec=home_shots_against,
            away_shots_against_rec=away_shots_against,

            home_sot_against_rec=home_sot_against,
            away_sot_against_rec=away_sot_against,

            home_big_chances_against_rec=home_big_chances_against,
            away_big_chances_against_rec=away_big_chances_against,

            # ------------------------------------------------
            # Differentials
            # ------------------------------------------------

            home_shots_diff_rec=home_shots_diff,
            away_shots_diff_rec=away_shots_diff,

            home_sot_diff_rec=home_sot_diff,
            away_sot_diff_rec=away_sot_diff,

            home_big_chances_diff_rec=home_big_chances_diff,
            away_big_chances_diff_rec=away_big_chances_diff,

            # ------------------------------------------------
            # Ratios
            # ------------------------------------------------

            home_sot_per_shot=home_sot_per_shot,
            away_sot_per_shot=away_sot_per_shot,

            home_big_chances_per_shot=home_big_chances_per_shot,
            away_big_chances_per_shot=away_big_chances_per_shot,

            # ------------------------------------------------
            # Samples
            # ------------------------------------------------

            home_xgf_sample=home_xgf_sample,
            home_xga_sample=home_xga_sample,

            away_xgf_sample=away_xgf_sample,
            away_xga_sample=away_xga_sample,

            home_shots_sample=home_shots_sample,
            away_shots_sample=away_shots_sample,

            home_sot_sample=home_sot_sample,
            away_sot_sample=away_sot_sample,

            home_big_chances_sample=home_big_chances_sample,
            away_big_chances_sample=away_big_chances_sample,

            # ------------------------------------------------
            # Matches
            # ------------------------------------------------

            home_matches=home_matches,
            away_matches=away_matches,

            # ------------------------------------------------
            # Availability
            # ------------------------------------------------

            xg_available=xg_available,

            shots_available=shots_available,

            sot_available=sot_available,

            big_chances_available=big_chances_available,

            # ------------------------------------------------
            # Validity
            # ------------------------------------------------

            calculation_valid=calculation_valid,
        )

    # ========================================================
    # PREDICT
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

    # ========================================================
    # COMPATIBILITY
    # ========================================================

    def calculate_goal_state(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> GoalState:

        return self.calculate(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )


# ============================================================
# STANDALONE FUNCTION
# ============================================================

def calculate_goal_state(
    home_context: Any,
    away_context: Any,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    max_history: int = DEFAULT_MAX_HISTORY,
) -> Dict[str, Any]:

    model = GoalModel(
        max_history=max_history
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

        "team_xg_history": (
            1.20,
            1.50,
            1.80,
            1.40,
            2.00,
            1.70,
        ),

        "opponent_xg_history": (
            0.80,
            1.10,
            0.90,
            1.30,
            0.70,
            1.00,
        ),

        "shots_history": (
            10,
            12,
            15,
            13,
            17,
            16,
        ),

        "shots_conceded_history": (
            11,
            10,
            9,
            13,
            8,
            10,
        ),

        "shots_on_target_history": (
            4,
            5,
            6,
            5,
            7,
            6,
        ),

        "shots_on_target_against_history": (
            3,
            4,
            3,
            5,
            2,
            4,
        ),

        "big_chances_history": (
            1,
            2,
            2,
            1,
            3,
            2,
        ),

        "big_chances_against_history": (
            2,
            1,
            1,
            2,
            1,
            2,
        ),
    }

    away_context = {

        "team": "Краснодар",

        "matches_count": 6,

        "team_xg_history": (
            1.10,
            1.30,
            1.50,
            1.20,
            1.40,
            1.60,
        ),

        "opponent_xg_history": (
            1.00,
            1.20,
            1.30,
            1.10,
            1.00,
            1.20,
        ),

        "shots_history": (
            11,
            12,
            14,
            13,
            15,
            16,
        ),

        "shots_conceded_history": (
            12,
            13,
            11,
            14,
            10,
            12,
        ),

        "shots_on_target_history": (
            4,
            5,
            5,
            4,
            6,
            6,
        ),

        "shots_on_target_against_history": (
            4,
            5,
            4,
            5,
            3,
            4,
        ),

        "big_chances_history": (
            1,
            1,
            2,
            2,
            2,
            3,
        ),

        "big_chances_against_history": (
            1,
            2,
            2,
            1,
            2,
            2,
        ),
    }

    state = GoalModel().calculate(
        home_context=home_context,
        away_context=away_context,
    )

    print(
        "GOAL MODEL v1.1"
    )

    print(
        "Home λ:",
        state.home_lambda,
    )

    print(
        "Away λ:",
        state.away_lambda,
    )

    print(
        "Total λ:",
        state.total_lambda,
    )

    print(
        "Home shots:",
        state.home_shots_rec,
    )

    print(
        "Away shots:",
        state.away_shots_rec,
    )

    print(
        "Home SOT:",
        state.home_sot_rec,
    )

    print(
        "Away SOT:",
        state.away_sot_rec,
    )

    print(
        "Home big chances:",
        state.home_big_chances_rec,
    )

    print(
        "Away big chances:",
        state.away_big_chances_rec,
    )

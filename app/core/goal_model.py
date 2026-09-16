#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
GOAL MODEL v1.0
============================================================

НАЗНАЧЕНИЕ
----------

GoalModel преобразует фактическую историю xG команды
из FormContext в базовое состояние ожидаемых голов.

GoalModel НЕ является WinnerModel.
GoalModel НЕ является ProbabilityModel.
GoalModel НЕ является ScorePredictor.

Цепочка:

    FormContext
        ↓
    GoalModel
        ↓
    home_lambda
    away_lambda
        ↓
    ProbabilityModel / ScorePredictor

============================================================
MATHEMATICAL CONTRACT v1
============================================================

Для каждой команды FormContext предоставляет:

    team_xg_history
        собственный xG команды (XGF)

    opponent_xg_history
        xG соперника против команды (XGA)

Истории находятся в каноническом порядке:

    M1 → M2 → ... → M6

где:

    M1 = самый старый матч
    M6 = самый свежий матч

Temporal weights:

    M1 = 1
    M2 = 2
    M3 = 3
    M4 = 4
    M5 = 5
    M6 = 6

Weighted XGF:

    XGF_rec =
        Σ(w_i * XGF_i) / Σ(w_i)

Weighted XGA:

    XGA_rec =
        Σ(w_i * XGA_i) / Σ(w_i)

Для матча:

    λHome =
        (Home_XGF_rec + Away_XGA_rec) / 2

    λAway =
        (Away_XGF_rec + Home_XGA_rec) / 2

============================================================
IMPORTANT
============================================================

GoalModel v1.0 НЕ использует:

    - geometric mean
    - home advantage multiplier
    - league strength
    - opponent rating
    - FAJ Rating
    - Form multiplier
    - Control multiplier
    - Winner Signal
    - finishing bonus
    - arbitrary coefficients
    - confidence
    - risk
    - bookmaker odds
    - actual future result

Missing xG:

    None != 0

Если вся необходимая история отсутствует,
соответствующий показатель остаётся None.

Если для λ недостаточно одного из двух компонентов,
λ также остаётся None.

============================================================
VERSION
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence


# ============================================================
# VERSION
# ============================================================

GOAL_MODEL_VERSION = "1.0"
GOAL_MODEL_STATUS = "CONTRACT_V1"


# ============================================================
# TEMPORAL WEIGHTS
# ============================================================

DEFAULT_MAX_HISTORY = 6


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Безопасное преобразование значения в float.

    None остаётся None.

    Пустые значения:
        None

    Некорректные значения:
        None

    Никогда не заменяет отсутствие данных на 0.
    """

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
    Получение значения из:

        dict
        sqlite3.Row
        объекта с атрибутами
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
        # sqlite3.Row / mapping-like
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


def _to_sequence(
    value: Any,
) -> List[Any]:
    """
    Нормализует history в обычный список.

    None -> []

    tuple/list -> list

    одиночное значение -> [value]
    """

    if value is None:

        return []

    if isinstance(
        value,
        (list, tuple),
    ):

        return list(value)

    return [value]


# ============================================================
# WEIGHTED MEAN
# ============================================================

def weighted_mean(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Recency-weighted mean.

    Канонический порядок:

        values[0] = M1 = oldest
        values[-1] = newest

    Вес:

        M1 = 1
        M2 = 2
        ...
        Mn = n

    ВАЖНО:

    Если значение None, оно НЕ получает вес.

    Пример:

        [1.0, None, 2.0]

    веса:

        1, 2, 3

    используется:

        (1*1.0 + 3*2.0) / (1+3)

    То есть отсутствие наблюдения
    не превращается в ноль.
    """

    if not values:

        return None

    numerator = 0.0
    denominator = 0.0

    for index, raw_value in enumerate(
        values,
        start=1,
    ):

        value = _safe_float(
            raw_value
        )

        if value is None:

            continue

        weight = float(index)

        numerator += (
            weight * value
        )

        denominator += weight

    if denominator <= 0:

        return None

    return (
        numerator
        / denominator
    )


# ============================================================
# GOAL STATE
# ============================================================

@dataclass
class GoalState:
    """
    Чистое математическое состояние GoalModel.
    """

    model_version: str = GOAL_MODEL_VERSION

    # --------------------------------------------------------
    # TEAM
    # --------------------------------------------------------

    home_team: Optional[str] = None
    away_team: Optional[str] = None

    # --------------------------------------------------------
    # RECENT XG STATES
    # --------------------------------------------------------

    home_xgf_rec: Optional[float] = None
    home_xga_rec: Optional[float] = None

    away_xgf_rec: Optional[float] = None
    away_xga_rec: Optional[float] = None

    # --------------------------------------------------------
    # EXPECTED GOALS
    # --------------------------------------------------------

    home_lambda: Optional[float] = None
    away_lambda: Optional[float] = None

    total_lambda: Optional[float] = None

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    home_xgf_sample: int = 0
    home_xga_sample: int = 0

    away_xgf_sample: int = 0
    away_xga_sample: int = 0

    # --------------------------------------------------------
    # HISTORY SIZE
    # --------------------------------------------------------

    home_matches: int = 0
    away_matches: int = 0

    # --------------------------------------------------------
    # DIAGNOSTICS
    # --------------------------------------------------------

    home_lambda_available: bool = False
    away_lambda_available: bool = False

    calculation_valid: bool = False


# ============================================================
# GOAL MODEL
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v1.0.

    Единственная математическая задача:

        FACT xG history
            ↓
        recency-weighted XGF/XGA
            ↓
        structural matchup
            ↓
        λHome / λAway

    Никакой дополнительной корректировки здесь нет.
    """

    VERSION = GOAL_MODEL_VERSION

    MAX_HISTORY = DEFAULT_MAX_HISTORY

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:

        if max_history <= 0:

            max_history = DEFAULT_MAX_HISTORY

        self.max_history = int(
            max_history
        )

    # ========================================================
    # HISTORY EXTRACTION
    # ========================================================

    def _extract_history(
        self,
        context: Any,
        key: str,
    ) -> List[Optional[float]]:
        """
        Получает историю из FormContext.

        Основной контракт:

            team_xg_history
            opponent_xg_history
        """

        value = _get_value(
            context,
            key,
        )

        values = _to_sequence(
            value
        )

        # ----------------------------------------------------
        # FormContext уже гарантирует:
        #
        # oldest -> newest
        #
        # Поэтому здесь НЕ выполняется reverse().
        # ----------------------------------------------------

        values = values[
            :self.max_history
        ]

        return [
            _safe_float(value)
            for value in values
        ]

    # ========================================================
    # TEAM XGF
    # ========================================================

    def _calculate_xgf(
        self,
        context: Any,
    ) -> Optional[float]:
        """
        Recency-weighted XGF команды.
        """

        history = self._extract_history(
            context,
            "team_xg_history",
        )

        return weighted_mean(
            history
        )

    # ========================================================
    # TEAM XGA
    # ========================================================

    def _calculate_xga(
        self,
        context: Any,
    ) -> Optional[float]:
        """
        Recency-weighted XGA команды.
        """

        history = self._extract_history(
            context,
            "opponent_xg_history",
        )

        return weighted_mean(
            history
        )

    # ========================================================
    # SAMPLE
    # ========================================================

    def _count_available(
        self,
        context: Any,
        key: str,
    ) -> int:
        """
        Количество доступных xG наблюдений.
        """

        history = self._extract_history(
            context,
            key,
        )

        return sum(
            1
            for value in history
            if value is not None
        )

    # ========================================================
    # MATCH COUNT
    # ========================================================

    def _get_matches_count(
        self,
        context: Any,
    ) -> int:
        """
        Получает количество матчей
        непосредственно из FormContext.
        """

        value = _get_value(
            context,
            "matches_count",
        )

        if value is not None:

            try:

                return int(value)

            except (
                TypeError,
                ValueError,
            ):

                pass

        # Fallback только как размер
        # фактически переданной истории.

        history = self._extract_history(
            context,
            "team_xg_history",
        )

        return len(history)

    # ========================================================
    # LAMBDA
    # ========================================================

    @staticmethod
    def _calculate_lambda(
        attack_xgf: Optional[float],
        opponent_xga: Optional[float],
    ) -> Optional[float]:
        """
        Базовая формула Goal State.

        λ = (XGF команды + XGA соперника) / 2

        Если один компонент отсутствует,
        λ НЕ рассчитывается.

        Missing != 0.
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
    # MAIN CALCULATION
    # ========================================================

    def calculate(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> GoalState:
        """
        Основной расчёт Goal State.

        home_context:
            FormContext домашней команды

        away_context:
            FormContext гостевой команды

        Формулы:

            Home XGF:
                home.team_xg_history

            Home XGA:
                home.opponent_xg_history

            Away XGF:
                away.team_xg_history

            Away XGA:
                away.opponent_xg_history

            λHome:
                (Home XGF + Away XGA) / 2

            λAway:
                (Away XGF + Home XGA) / 2
        """

        # ----------------------------------------------------
        # TEAM NAMES
        # ----------------------------------------------------

        if home_team is None:

            home_team = _get_value(
                home_context,
                "team",
            )

        if away_team is None:

            away_team = _get_value(
                away_context,
                "team",
            )

        # ----------------------------------------------------
        # RECENT XGF / XGA
        # ----------------------------------------------------

        home_xgf_rec = (
            self._calculate_xgf(
                home_context
            )
        )

        home_xga_rec = (
            self._calculate_xga(
                home_context
            )
        )

        away_xgf_rec = (
            self._calculate_xgf(
                away_context
            )
        )

        away_xga_rec = (
            self._calculate_xga(
                away_context
            )
        )

        # ----------------------------------------------------
        # λ HOME
        #
        # Home attack:
        #       Home XGF
        #
        # Away defensive allowance:
        #       Away XGA
        # ----------------------------------------------------

        home_lambda = (
            self._calculate_lambda(
                attack_xgf=home_xgf_rec,
                opponent_xga=away_xga_rec,
            )
        )

        # ----------------------------------------------------
        # λ AWAY
        #
        # Away attack:
        #       Away XGF
        #
        # Home defensive allowance:
        #       Home XGA
        # ----------------------------------------------------

        away_lambda = (
            self._calculate_lambda(
                attack_xgf=away_xgf_rec,
                opponent_xga=home_xga_rec,
            )
        )

        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # SAMPLES
        # ----------------------------------------------------

        home_xgf_sample = (
            self._count_available(
                home_context,
                "team_xg_history",
            )
        )

        home_xga_sample = (
            self._count_available(
                home_context,
                "opponent_xg_history",
            )
        )

        away_xgf_sample = (
            self._count_available(
                away_context,
                "team_xg_history",
            )
        )

        away_xga_sample = (
            self._count_available(
                away_context,
                "opponent_xg_history",
            )
        )

        # ----------------------------------------------------
        # VALIDITY
        # ----------------------------------------------------

        home_lambda_available = (
            home_lambda is not None
        )

        away_lambda_available = (
            away_lambda is not None
        )

        calculation_valid = (
            home_lambda_available
            and away_lambda_available
        )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        return GoalState(

            model_version=self.VERSION,

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

            home_xgf_rec=home_xgf_rec,
            home_xga_rec=home_xga_rec,

            away_xgf_rec=away_xgf_rec,
            away_xga_rec=away_xga_rec,

            home_lambda=home_lambda,
            away_lambda=away_lambda,

            total_lambda=total_lambda,

            home_xgf_sample=home_xgf_sample,
            home_xga_sample=home_xga_sample,

            away_xgf_sample=away_xgf_sample,
            away_xga_sample=away_xga_sample,

            home_matches=self._get_matches_count(
                home_context
            ),

            away_matches=self._get_matches_count(
                away_context
            ),

            home_lambda_available=(
                home_lambda_available
            ),

            away_lambda_available=(
                away_lambda_available
            ),

            calculation_valid=(
                calculation_valid
            ),
        )

    # ========================================================
    # DICT API
    # ========================================================

    def predict(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Основной orchestration-friendly API.

        Возвращает обычный dict,
        чтобы существующие компоненты FAJ
        могли использовать результат
        без зависимости от dataclass.
        """

        state = self.calculate(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )

        return asdict(
            state
        )

    # ========================================================
    # COMPATIBILITY ALIASES
    # ========================================================

    def calculate_goal_state(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Явное имя для Brain / AnalysisEngine.
        """

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
) -> Dict[str, Any]:
    """
    Stateless helper API.
    """

    model = GoalModel()

    return model.predict(
        home_context=home_context,
        away_context=away_context,
        home_team=home_team,
        away_team=away_team,
    )


# ============================================================
# DEBUG / SELF TEST
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # FormContext-like test data.
    #
    # M1 oldest -> M6 newest
    # --------------------------------------------------------

    home_context = {

        "team": "Зенит",

        "matches_count": 6,

        "team_xg_history": (
            1.00,
            1.20,
            1.40,
            1.60,
            1.80,
            2.00,
        ),

        "opponent_xg_history": (
            1.40,
            1.30,
            1.20,
            1.10,
            1.00,
            0.90,
        ),
    }

    away_context = {

        "team": "ЦСКА",

        "matches_count": 6,

        "team_xg_history": (
            1.20,
            1.30,
            1.40,
            1.50,
            1.60,
            1.70,
        ),

        "opponent_xg_history": (
            1.60,
            1.50,
            1.40,
            1.30,
            1.20,
            1.10,
        ),
    }

    model = GoalModel()

    result = model.predict(
        home_context=home_context,
        away_context=away_context,
    )

    print(
        "GOAL MODEL v1.0"
    )

    print(
        "Home XGF:",
        result["home_xgf_rec"],
    )

    print(
        "Home XGA:",
        result["home_xga_rec"],
    )

    print(
        "Away XGF:",
        result["away_xgf_rec"],
    )

    print(
        "Away XGA:",
        result["away_xga_rec"],
    )

    print(
        "Home λ:",
        result["home_lambda"],
    )

    print(
        "Away λ:",
        result["away_lambda"],
    )

    print(
        "Total λ:",
        result["total_lambda"],
    )

    print(
        "Valid:",
        result["calculation_valid"],
    )

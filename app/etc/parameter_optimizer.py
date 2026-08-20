#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/parameter_optimizer.py
============================================================

НАЗНАЧЕНИЕ
-----------
Формирование предложений по изменению параметров FAJ
на основании накопленных сигналов обучения ETC.

ЦЕПОЧКА:

    learning_records
          ↓
    LearningAnalyzer
          ↓
    Error Patterns / Signals
          ↓
    ParameterOptimizer
          ↓
    Parameter Change Proposal
          ↓
    EvolutionEngine
          ↓
    model_parameters

ВАЖНО
------
Этот модуль НЕ изменяет параметры модели.

Он только отвечает на вопрос:

    "Есть ли достаточно оснований предложить изменение?"

МОДУЛЬ НЕ:
    - не изменяет database.py;
    - не изменяет model_parameters;
    - не изменяет team_passports;
    - не изменяет predictions;
    - не выполняет обучение;
    - не применяет изменения автоматически.

МОДУЛЬ:
    - анализирует сигналы ETC;
    - сопоставляет ошибки с параметрами;
    - рассчитывает направление изменения;
    - рассчитывает величину предлагаемого изменения;
    - формирует proposal;
    - устанавливает уровень уверенности.

============================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Parameter Optimizer"


# ============================================================
# LIMITS
# ============================================================

MIN_CONFIDENCE = 0.60
MIN_SIGNAL_STRENGTH = 0.30
MIN_PATTERN_COUNT = 3

MAX_PARAMETER_DELTA = 0.05
DEFAULT_PARAMETER_DELTA = 0.02


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class ParameterProposal:
    """
    Предложение ETC по изменению параметра.

    Это НЕ применённое изменение.
    """

    parameter_name: str

    current_value: Optional[float]

    proposed_value: Optional[float]

    delta: float

    direction: str

    reason: str

    error_type: str

    cause_type: str

    evidence_count: int

    confidence: float

    signal_strength: float

    priority: str

    status: str = "proposed"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# MAIN CLASS
# ============================================================

class ParameterOptimizer:
    """
    ETC Parameter Optimizer.

    Только формирует предложения.
    """

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE,
        min_signal_strength: float = MIN_SIGNAL_STRENGTH,
        min_pattern_count: int = MIN_PATTERN_COUNT,
        max_parameter_delta: float = MAX_PARAMETER_DELTA,
    ) -> None:

        self.min_confidence = max(
            0.0,
            min(1.0, float(min_confidence)),
        )

        self.min_signal_strength = max(
            0.0,
            min(1.0, float(min_signal_strength)),
        )

        self.min_pattern_count = max(
            1,
            int(min_pattern_count),
        )

        self.max_parameter_delta = abs(
            float(max_parameter_delta)
        )

    # ========================================================
    # PARAMETER MAPPING
    # ========================================================

    @staticmethod
    def map_signal_to_parameter(
        error_type: str,
        cause_type: str,
    ) -> Optional[str]:
        """
        Сопоставляет тип ошибки с параметром модели.

        Здесь намеренно нет агрессивного автоматического
        маппинга всех ошибок.
        """

        mapping = {

            "home_attack_overestimated":
                "attack",

            "home_attack_underestimated":
                "attack",

            "away_attack_overestimated":
                "attack",

            "away_attack_underestimated":
                "attack",

            "match_balance_misread":
                "faj_rating",

        }

        if cause_type in mapping:
            return mapping[cause_type]

        if error_type == "over25_miss":
            return "tempo"

        if error_type == "over35_miss":
            return "tempo"

        if error_type == "btts_miss":
            return "attack"

        if error_type == "winner_miss":
            return "faj_rating"

        return None

    # ========================================================
    # DIRECTION
    # ========================================================

    @staticmethod
    def determine_direction(
        cause_type: str,
    ) -> str:
        """
        Определяет направление изменения.
        """

        if cause_type in (
            "home_attack_overestimated",
            "away_attack_overestimated",
        ):
            return "decrease"

        if cause_type in (
            "home_attack_underestimated",
            "away_attack_underestimated",
        ):
            return "increase"

        return "review"

    # ========================================================
    # DELTA
    # ========================================================

    def calculate_delta(
        self,
        signal: Dict[str, Any],
    ) -> float:
        """
        Рассчитывает предлагаемую величину изменения.

        Изменение ограничивается MAX_PARAMETER_DELTA.
        """

        confidence = float(
            signal.get(
                "confidence",
                0.0,
            )
        )

        strength = float(
            signal.get(
                "signal_strength",
                0.0,
            )
        )

        count = int(
            signal.get(
                "count",
                0,
            )
        )

        if count < self.min_pattern_count:
            return 0.0

        if confidence < self.min_confidence:
            return 0.0

        if strength < self.min_signal_strength:
            return 0.0

        base = DEFAULT_PARAMETER_DELTA

        factor = (
            0.5
            + 0.5 * confidence
        )

        factor *= (
            0.5
            + 0.5 * min(
                1.0,
                count / 10.0,
            )
        )

        delta = base * factor

        return round(
            min(
                delta,
                self.max_parameter_delta,
            ),
            4,
        )

    # ========================================================
    # CURRENT VALUE
    # ========================================================

    @staticmethod
    def calculate_proposed_value(
        current_value: Optional[float],
        delta: float,
        direction: str,
    ) -> Optional[float]:
        """
        Рассчитывает новое значение.

        Если текущее значение неизвестно,
        proposal всё равно может существовать,
        но proposed_value будет None.
        """

        if current_value is None:
            return None

        current = float(current_value)

        if direction == "increase":
            return round(
                current + delta,
                6,
            )

        if direction == "decrease":
            return round(
                current - delta,
                6,
            )

        return current

    # ========================================================
    # PRIORITY
    # ========================================================

    @staticmethod
    def determine_priority(
        count: int,
        confidence: float,
        severity: float,
    ) -> str:

        if (
            count >= 5
            and confidence >= 0.80
            and severity >= 3
        ):
            return "high"

        if (
            count >= 3
            and confidence >= 0.60
        ):
            return "medium"

        return "low"

    # ========================================================
    # SINGLE PROPOSAL
    # ========================================================

    def create_proposal(
        self,
        signal: Dict[str, Any],
        current_parameters: Optional[
            Dict[str, float]
        ] = None,
    ) -> Optional[ParameterProposal]:
        """
        Создаёт предложение для одного сигнала.
        """

        error_type = (
            signal.get("error_type")
            or "unknown"
        )

        cause_type = (
            signal.get("cause_type")
            or "unknown"
        )

        parameter_name = (
            self.map_signal_to_parameter(
                error_type,
                cause_type,
            )
        )

        if not parameter_name:
            return None

        count = int(
            signal.get(
                "count",
                0,
            )
        )

        confidence = float(
            signal.get(
                "confidence",
                0.0,
            )
        )

        signal_strength = float(
            signal.get(
                "signal_strength",
                0.0,
            )
        )

        average_severity = float(
            signal.get(
                "average_severity",
                0.0,
            )
        )

        delta = self.calculate_delta(
            signal
        )

        if delta <= 0:
            return None

        direction = self.determine_direction(
            cause_type
        )

        current_value = None

        if current_parameters:

            current_value = current_parameters.get(
                parameter_name
            )

        proposed_value = (
            self.calculate_proposed_value(
                current_value,
                delta,
                direction,
            )
        )

        priority = (
            self.determine_priority(
                count,
                confidence,
                average_severity,
            )
        )

        reason = (
            f"Повторяющаяся ошибка "
            f"{error_type}; причина "
            f"{cause_type}; "
            f"наблюдений={count}; "
            f"confidence={confidence:.2f}"
        )

        return ParameterProposal(

            parameter_name=parameter_name,

            current_value=current_value,

            proposed_value=proposed_value,

            delta=delta,

            direction=direction,

            reason=reason,

            error_type=error_type,

            cause_type=cause_type,

            evidence_count=count,

            confidence=confidence,

            signal_strength=signal_strength,

            priority=priority,

        )

    # ========================================================
    # OPTIMIZE
    # ========================================================

    def optimize(
        self,
        signals: List[
            Dict[str, Any]
        ],
        current_parameters: Optional[
            Dict[str, float]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """
        Формирует список предложений.
        """

        proposals = []

        for signal in signals:

            proposal = self.create_proposal(
                signal=signal,
                current_parameters=current_parameters,
            )

            if proposal is None:
                continue

            proposals.append(
                proposal.to_dict()
            )

        return proposals

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    @staticmethod
    def deduplicate(
        proposals: List[
            Dict[str, Any]
        ],
    ) -> List[Dict[str, Any]]:
        """
        Если несколько сигналов предлагают
        изменить один параметр, оставляем
        наиболее сильный сигнал.
        """

        best: Dict[
            str,
            Dict[str, Any]
        ] = {}

        for proposal in proposals:

            parameter = proposal[
                "parameter_name"
            ]

            if parameter not in best:

                best[parameter] = proposal

                continue

            existing = best[parameter]

            existing_strength = (
                float(
                    existing.get(
                        "signal_strength",
                        0.0,
                    )
                )
                * float(
                    existing.get(
                        "confidence",
                        0.0,
                    )
                )
            )

            new_strength = (
                float(
                    proposal.get(
                        "signal_strength",
                        0.0,
                    )
                )
                * float(
                    proposal.get(
                        "confidence",
                        0.0,
                    )
                )
            )

            if new_strength > existing_strength:

                best[parameter] = proposal

        return list(best.values())

    # ========================================================
    # FULL RUN
    # ========================================================

    def run(
        self,
        signals: List[
            Dict[str, Any]
        ],
        current_parameters: Optional[
            Dict[str, float]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Полный цикл формирования proposals.
        """

        proposals = self.optimize(
            signals=signals,
            current_parameters=current_parameters,
        )

        proposals = self.deduplicate(
            proposals
        )

        return {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "signals_analyzed": len(signals),
            "proposals_created": len(
                proposals
            ),
            "proposals": proposals,
        }


# ============================================================
# MODULE-LEVEL HELPER
# ============================================================

def optimize_parameters(
    signals: List[
        Dict[str, Any]
    ],
    current_parameters: Optional[
        Dict[str, float]
    ] = None,
) -> Dict[str, Any]:
    """
    Удобная функция для ETC.
    """

    optimizer = ParameterOptimizer()

    return optimizer.run(
        signals=signals,
        current_parameters=current_parameters,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("=" * 70)
    print("FAJ ETC — Parameter Optimizer")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    signals = [

        {
            "error_type": "score_miss",
            "cause_type": "home_attack_overestimated",
            "count": 6,
            "average_severity": 3.2,
            "confidence": 0.80,
            "signal_strength": 0.70,
        },

        {
            "error_type": "winner_miss",
            "cause_type": "match_balance_misread",
            "count": 2,
            "average_severity": 3.0,
            "confidence": 0.40,
            "signal_strength": 0.25,
        },
    ]

    current_parameters = {
        "attack": 0.18,
        "faj_rating": 0.20,
        "tempo": 0.05,
    }

    result = optimize_parameters(
        signals=signals,
        current_parameters=current_parameters,
    )

    print(
        f"Signals: "
        f"{result['signals_analyzed']}"
    )

    print(
        f"Proposals: "
        f"{result['proposals_created']}"
    )

    for proposal in result["proposals"]:

        print("-" * 60)

        for key, value in proposal.items():

            print(
                f"{key}: {value}"
            )

    print("=" * 70)

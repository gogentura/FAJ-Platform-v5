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
Формирование предложений по изменению модельных параметров
FAJ на основании накопленных сигналов ETC.

АРХИТЕКТУРА:

    MATCH RESULT
          ↓
    FACTS / GOLD
          ↓
    ERROR CLASSIFIER
          ↓
    LEARNING MEMORY
          ↓
    LEARNING ANALYZER
          ↓
    ERROR PATTERNS
          ↓
    ETC SIGNALS
          ↓
    PARAMETER OPTIMIZER
          ↓
    PARAMETER PROPOSALS
          ↓
    [MANUAL / EVOLUTION ENGINE]
          ↓
    model_parameters
          ↓
    NEXT LEARNING CYCLE

ВАЖНО
------
ParameterOptimizer НЕ является Evolution Engine.

Он НЕ применяет изменения.

Он только отвечает на вопрос:

    "Есть ли достаточно накопленных доказательств,
     чтобы предложить изменение конкретного
     модельного параметра?"

============================================================
ЖЁСТКИЕ ПРИНЦИПЫ FAJ
============================================================

МОДУЛЬ НЕ:

    - не изменяет database.py;
    - не изменяет match_results;
    - не изменяет predictions;
    - не изменяет gold;
    - не изменяет learning_memory;
    - не изменяет team_passports;
    - не изменяет FAJ Club Rating;
    - не изменяет model_parameters;
    - не запускает обучение;
    - не применяет proposal автоматически;
    - не удаляет исторические данные.

МОДУЛЬ:

    - читает сигналы ETC;
    - проверяет достаточность доказательств;
    - определяет потенциальный параметр;
    - определяет направление;
    - рассчитывает малое изменение;
    - формирует proposal;
    - присваивает confidence;
    - присваивает priority;
    - объясняет причину предложения.

============================================================
ВАЖНОЕ РАЗДЕЛЕНИЕ
============================================================

FAJ CLUB RATING
    ↓
    отдельный динамический рейтинг команды.

MODEL PARAMETERS
    ↓
    параметры математической модели.

Поэтому:

    "faj_rating" НЕ является параметром,
    который должен изменяться этим модулем.

Изменение Club Rating выполняется:

    match_result
         ↓
    club_rating_updater.py
         ↓
    team_passport
         +
    team_history

А изменение model_parameters должно проходить:

    ETC signals
         ↓
    ParameterOptimizer
         ↓
    proposal
         ↓
    Evolution Engine / controlled approval
         ↓
    model_parameters

============================================================

ИСПРАВЛЕНИЯ v2.1
============================================================

1. Добавлен mapping xg_overestimated / xg_underestimated → xg_scale.

2. В calculate_delta() добавлена защита от duplicate evidence
   (одинаковые match_id в одном сигнале).

3. В run() добавлено логирование conflict detection.

============================================================
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.1"
MODULE_NAME = "ETC Parameter Optimizer"


# ============================================================
# SAFETY LIMITS
# ============================================================

# Минимальное доверие для предложения.
MIN_CONFIDENCE = 0.60

# Минимальная сила сигнала.
MIN_SIGNAL_STRENGTH = 0.30

# Минимальное количество подтверждений.
MIN_PATTERN_COUNT = 3

# Максимальное изменение параметра за один proposal.
MAX_PARAMETER_DELTA = 0.05

# Базовое изменение.
DEFAULT_PARAMETER_DELTA = 0.02


# ============================================================
# PARAMETER LIMITS
# ============================================================

"""
Безопасные границы параметров FAJ.

ВАЖНО:

Это НЕ новая архитектура весов.

Это только safety limits для proposal.

Они не применяются автоматически.
"""

PARAMETER_LIMITS: Dict[str, tuple[float, float]] = {

    # Основные FAJ model weights.
    "attack": (0.00, 1.00),
    "defense": (0.00, 1.00),
    "control": (0.00, 1.00),
    "efficiency": (0.00, 1.00),
    "mentality": (0.00, 1.00),
    "discipline": (0.00, 1.00),
    "fitness": (0.00, 1.00),
    "predictability": (0.00, 1.00),
    "opposition": (0.00, 1.00),

    # Тактические компоненты.
    "tempo": (0.00, 1.00),
    "press": (0.00, 1.00),
    "transition": (0.00, 1.00),
    "tactical": (0.00, 1.00),
    "coach": (0.00, 1.00),
    "form": (0.00, 1.00),

    # xG calibration component.
    "xg_scale": (0.10, 5.00),
}


# ============================================================
# PARAMETER MAPPING
# ============================================================

"""
Сопоставление причин ошибок с модельными параметрами.

ВАЖНО:

Club Rating здесь отсутствует намеренно.

faj_rating:
    НЕ параметр optimizer.

FAJ Rating обновляется club_rating_updater.py.

ИСПРАВЛЕНИЕ v2.1:
    Добавлен mapping xg_overestimated / xg_underestimated → xg_scale.
"""

CAUSE_PARAMETER_MAP: Dict[str, str] = {

    # --------------------------------------------------------
    # ATTACK
    # --------------------------------------------------------

    "home_attack_overestimated":
        "attack",

    "home_attack_underestimated":
        "attack",

    "away_attack_overestimated":
        "attack",

    "away_attack_underestimated":
        "attack",

    # --------------------------------------------------------
    # XG (v2.1)
    # --------------------------------------------------------

    "xg_overestimated":
        "xg_scale",

    "xg_underestimated":
        "xg_scale",

    # --------------------------------------------------------
    # TACTICAL / TEMPO
    # --------------------------------------------------------

    "tempo_overestimated":
        "tempo",

    "tempo_underestimated":
        "tempo",

    "press_overestimated":
        "press",

    "press_underestimated":
        "press",

    "transition_overestimated":
        "transition",

    "transition_underestimated":
        "transition",

    # --------------------------------------------------------
    # FORM / TEAM STATE
    # --------------------------------------------------------

    "form_overestimated":
        "form",

    "form_underestimated":
        "form",

    # --------------------------------------------------------
    # TACTICAL BALANCE
    # --------------------------------------------------------

    "tactical_misread":
        "tactical",

    "transition_misread":
        "transition",

    "press_misread":
        "press",
}


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class ParameterProposal:
    """
    Предложение ETC по изменению модельного параметра.

    Это только аналитическое предложение.

    Оно НЕ означает, что параметр уже изменён.
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

    Только аналитический слой.

    НЕ изменяет БД.
    НЕ изменяет параметры.
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
            min(
                1.0,
                float(min_confidence),
            ),
        )

        self.min_signal_strength = max(
            0.0,
            min(
                1.0,
                float(min_signal_strength),
            ),
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
        Сопоставляет сигнал ETC с модельным параметром.

        Никакого изменения здесь не происходит.
        """

        error_type = (
            str(error_type)
            if error_type is not None
            else "unknown"
        )

        cause_type = (
            str(cause_type)
            if cause_type is not None
            else "unknown"
        )

        # Сначала используем наиболее точную причину.
        parameter = CAUSE_PARAMETER_MAP.get(
            cause_type
        )

        if parameter:
            return parameter

        # ----------------------------------------------------
        # Общие fallback-сигналы
        # ----------------------------------------------------

        if error_type in (
            "over25_miss",
            "over35_miss",
        ):
            return "tempo"

        if error_type == "btts_miss":
            return "attack"

        # winner_miss намеренно НЕ маппится
        # на faj_rating.
        #
        # Ошибка winner может быть вызвана:
        #   - балансом;
        #   - home advantage;
        #   - xG;
        #   - формой;
        #   - тактикой.
        #
        # Поэтому недостаточно доказательств
        # для автоматического предложения.

        return None

    # ========================================================
    # DIRECTION
    # ========================================================

    @staticmethod
    def determine_direction(
        cause_type: str,
    ) -> str:
        """
        Определяет направление потенциального изменения.
        """

        cause_type = str(
            cause_type or ""
        )

        if cause_type.endswith(
            "_overestimated"
        ):
            return "decrease"

        if cause_type.endswith(
            "_underestimated"
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
        Рассчитывает величину proposal.

        Величина намеренно маленькая.

        ETC не должен делать резкие изменения модели
        после нескольких матчей.

        ИСПРАВЛЕНИЕ v2.1:
            Добавлена защита от duplicate evidence.
            Учитываются только уникальные match_id.
        """

        confidence = self._safe_float(
            signal.get("confidence")
        )

        strength = self._safe_float(
            signal.get("signal_strength")
        )

        # Используем уникальные match_id для подсчета
        # (защита от дублирования evidence)
        matches = signal.get("matches", [])
        if isinstance(matches, list):
            unique_matches = len(set(
                int(m) for m in matches if m is not None
            ))
        else:
            unique_matches = self._safe_int(
                signal.get("count")
            )

        count = unique_matches if unique_matches > 0 else self._safe_int(
            signal.get("count")
        )

        if count < self.min_pattern_count:
            return 0.0

        if confidence < self.min_confidence:
            return 0.0

        if strength < self.min_signal_strength:
            return 0.0

        # ----------------------------------------------------
        # Базовое изменение
        # ----------------------------------------------------

        base = DEFAULT_PARAMETER_DELTA

        # Confidence factor.
        confidence_factor = (
            0.5
            + 0.5 * confidence
        )

        # Evidence factor.
        evidence_factor = (
            0.5
            + 0.5 * min(
                1.0,
                count / 10.0,
            )
        )

        # Signal strength factor.
        strength_factor = (
            0.5
            + 0.5 * strength
        )

        delta = (
            base
            * confidence_factor
            * evidence_factor
            * strength_factor
        )

        delta = min(
            delta,
            self.max_parameter_delta,
        )

        return round(
            delta,
            6,
        )

    # ========================================================
    # CURRENT VALUE
    # ========================================================

    @staticmethod
    def _get_current_value(
        parameter_name: str,
        current_parameters: Optional[
            Dict[str, float]
        ],
    ) -> Optional[float]:

        if not current_parameters:
            return None

        value = current_parameters.get(
            parameter_name
        )

        if value is None:
            return None

        try:
            return float(value)

        except (TypeError, ValueError):
            return None

    # ========================================================
    # PROPOSED VALUE
    # ========================================================

    @staticmethod
    def calculate_proposed_value(
        current_value: Optional[float],
        delta: float,
        direction: str,
        parameter_name: Optional[str] = None,
    ) -> Optional[float]:
        """
        Рассчитывает proposed_value.

        Значение дополнительно ограничивается
        safety limits параметра.
        """

        if current_value is None:
            return None

        current = float(
            current_value
        )

        if direction == "increase":

            proposed = current + delta

        elif direction == "decrease":

            proposed = current - delta

        else:

            proposed = current

        # ----------------------------------------------------
        # SAFETY LIMITS
        # ----------------------------------------------------

        if parameter_name:

            limits = PARAMETER_LIMITS.get(
                parameter_name
            )

            if limits:

                minimum, maximum = limits

                proposed = max(
                    minimum,
                    min(
                        maximum,
                        proposed,
                    ),
                )

        return round(
            proposed,
            6,
        )

    # ========================================================
    # PRIORITY
    # ========================================================

    @staticmethod
    def determine_priority(
        count: int,
        confidence: float,
        severity: float,
        signal_strength: float,
    ) -> str:
        """
        Определяет приоритет предложения.
        """

        if (
            count >= 5
            and confidence >= 0.80
            and severity >= 3.0
            and signal_strength >= 0.60
        ):
            return "high"

        if (
            count >= 3
            and confidence >= 0.60
            and signal_strength >= 0.30
        ):
            return "medium"

        return "low"

    # ========================================================
    # REASON
    # ========================================================

    @staticmethod
    def _build_reason(
        error_type: str,
        cause_type: str,
        count: int,
        confidence: float,
        signal_strength: float,
        direction: str,
        parameter_name: str,
    ) -> str:

        return (
            f"Повторяющийся сигнал ETC: "
            f"error_type={error_type}; "
            f"cause_type={cause_type}; "
            f"parameter={parameter_name}; "
            f"direction={direction}; "
            f"наблюдений={count}; "
            f"confidence={confidence:.2f}; "
            f"signal_strength={signal_strength:.2f}. "
            f"Требуется отдельная проверка перед применением."
        )

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
        Создаёт proposal для одного сигнала.

        Если доказательств недостаточно —
        возвращает None.
        """

        if not signal:
            return None

        error_type = (
            signal.get("error_type")
            or "unknown"
        )

        cause_type = (
            signal.get("cause_type")
            or "unknown"
        )

        # ----------------------------------------------------
        # PARAMETER
        # ----------------------------------------------------

        parameter_name = (
            self.map_signal_to_parameter(
                error_type=error_type,
                cause_type=cause_type,
            )
        )

        if not parameter_name:
            logger.debug(
                "No parameter mapping for "
                "error=%s cause=%s",
                error_type,
                cause_type,
            )

            return None

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        count = self._safe_int(
            signal.get("count")
        )

        confidence = self._safe_float(
            signal.get("confidence")
        )

        signal_strength = self._safe_float(
            signal.get("signal_strength")
        )

        average_severity = self._safe_float(
            signal.get("average_severity")
        )

        # ----------------------------------------------------
        # DELTA
        # ----------------------------------------------------

        delta = self.calculate_delta(
            signal
        )

        if delta <= 0:
            return None

        # ----------------------------------------------------
        # DIRECTION
        # ----------------------------------------------------

        direction = self.determine_direction(
            cause_type
        )

        # Не предлагаем изменение,
        # если направление неизвестно.
        if direction == "review":
            return None

        # ----------------------------------------------------
        # CURRENT PARAMETER
        # ----------------------------------------------------

        current_value = (
            self._get_current_value(
                parameter_name,
                current_parameters,
            )
        )

        # ----------------------------------------------------
        # PROPOSED VALUE
        # ----------------------------------------------------

        proposed_value = (
            self.calculate_proposed_value(
                current_value=current_value,
                delta=delta,
                direction=direction,
                parameter_name=parameter_name,
            )
        )

        # ----------------------------------------------------
        # PRIORITY
        # ----------------------------------------------------

        priority = (
            self.determine_priority(
                count=count,
                confidence=confidence,
                severity=average_severity,
                signal_strength=signal_strength,
            )
        )

        # ----------------------------------------------------
        # REASON
        # ----------------------------------------------------

        reason = self._build_reason(
            error_type=error_type,
            cause_type=cause_type,
            count=count,
            confidence=confidence,
            signal_strength=signal_strength,
            direction=direction,
            parameter_name=parameter_name,
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

            status="proposed",

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
        Формирует proposals для всех сигналов.
        """

        proposals: List[
            Dict[str, Any]
        ] = []

        for signal in signals:

            try:

                proposal = self.create_proposal(
                    signal=signal,
                    current_parameters=current_parameters,
                )

                if proposal is None:
                    continue

                proposals.append(
                    proposal.to_dict()
                )

            except Exception as exc:

                logger.exception(
                    "Parameter proposal failed: %s",
                    exc,
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
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Если несколько сигналов предлагают
        изменение одного параметра, оставляет
        наиболее доказательный proposal.

        Никаких изменений БД здесь нет.
        """

        best: Dict[
            str,
            Dict[str, Any]
        ] = {}

        for proposal in proposals:

            parameter = proposal.get(
                "parameter_name"
            )

            if not parameter:
                continue

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
                * max(
                    1,
                    int(
                        existing.get(
                            "evidence_count",
                            0,
                        )
                    ),
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
                * max(
                    1,
                    int(
                        proposal.get(
                            "evidence_count",
                            0,
                        )
                    ),
                )
            )

            if new_strength > existing_strength:

                best[parameter] = proposal

        return list(
            best.values()
        )

    # ========================================================
    # CONFLICT DETECTION
    # ========================================================

    @staticmethod
    def detect_conflicts(
        proposals: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Проверяет предложения на конфликт направлений.

        Например:

            attack increase
            attack decrease

        одновременно.

        Такой конфликт нельзя автоматически применять.
        """

        directions: Dict[
            str,
            set[str]
        ] = {}

        for proposal in proposals:

            parameter = proposal.get(
                "parameter_name"
            )

            direction = proposal.get(
                "direction"
            )

            if not parameter or not direction:
                continue

            directions.setdefault(
                parameter,
                set(),
            ).add(direction)

        conflicts = []

        for parameter, values in directions.items():

            if (
                "increase" in values
                and "decrease" in values
            ):

                conflicts.append(
                    {
                        "parameter_name": parameter,
                        "directions": sorted(
                            values
                        ),
                        "status": "conflict",
                        "action": (
                            "manual_review_required"
                        ),
                    }
                )

        return conflicts

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
        Полный цикл Parameter Optimizer.

        Результат является аналитическим proposal.

        Никаких изменений модели не происходит.
        """

        signals = signals or []

        raw_proposals = self.optimize(
            signals=signals,
            current_parameters=current_parameters,
        )

        proposals = self.deduplicate(
            raw_proposals
        )

        conflicts = self.detect_conflicts(
            raw_proposals
        )

        # ----------------------------------------------------
        # Конфликт делает proposal небезопасным
        # для автоматического применения.
        # ----------------------------------------------------

        conflict_parameters = {
            item["parameter_name"]
            for item in conflicts
        }

        for proposal in proposals:

            parameter = proposal.get(
                "parameter_name"
            )

            if parameter in conflict_parameters:

                proposal["status"] = (
                    "conflict_review"
                )

        # ----------------------------------------------------
        # Логирование конфликтов (v2.1)
        # ----------------------------------------------------

        if conflicts:
            logger.info(
                "ETC Parameter Optimizer: "
                "обнаружены конфликты по параметрам: %s",
                [c["parameter_name"] for c in conflicts]
            )

        result = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,

            "signals_analyzed": len(
                signals
            ),

            "raw_proposals_created": len(
                raw_proposals
            ),

            "proposals_created": len(
                proposals
            ),

            "conflicts": conflicts,

            "conflict_count": len(
                conflicts
            ),

            "requires_review": bool(
                conflicts
            ),

            "auto_apply": False,

            "proposals": proposals,
        }

        logger.info(
            "ETC Parameter Optimizer: "
            "signals=%s proposals=%s conflicts=%s",
            len(signals),
            len(proposals),
            len(conflicts),
        )

        return result

    # ========================================================
    # SAFE HELPERS
    # ========================================================

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:

            if value is None:
                return default

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            return default

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:

        try:

            if value is None:
                return default

            return int(value)

        except (
            TypeError,
            ValueError,
        ):

            return default


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
    Удобная точка входа ETC.

    Только формирует proposals.
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
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
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
            "error_type": "over25_miss",
            "cause_type": "tempo_overestimated",
            "count": 5,
            "average_severity": 3.0,
            "confidence": 0.75,
            "signal_strength": 0.65,
        },

        {
            "error_type": "winner_miss",
            "cause_type": "match_balance_misread",
            "count": 8,
            "average_severity": 4.0,
            "confidence": 0.90,
            "signal_strength": 0.80,
        },

        {
            "error_type": "score_miss",
            "cause_type": "home_attack_underestimated",
            "count": 4,
            "average_severity": 3.0,
            "confidence": 0.70,
            "signal_strength": 0.60,
        },
    ]

    current_parameters = {

        "attack": 0.18,

        "defense": 0.18,

        "control": 0.15,

        "efficiency": 0.12,

        "mentality": 0.10,

        "discipline": 0.08,

        "fitness": 0.07,

        "predictability": 0.07,

        "opposition": 0.05,

        "tempo": 0.05,

        "press": 0.05,

        "transition": 0.05,

        "tactical": 0.05,

        "coach": 0.04,

        "form": 0.03,

        "xg_scale": 2.50,
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
        f"Raw proposals: "
        f"{result['raw_proposals_created']}"
    )

    print(
        f"Final proposals: "
        f"{result['proposals_created']}"
    )

    print(
        f"Conflicts: "
        f"{result['conflict_count']}"
    )

    print(
        f"Auto apply: "
        f"{result['auto_apply']}"
    )

    for proposal in result["proposals"]:

        print("-" * 60)

        for key, value in proposal.items():

            print(
                f"{key}: {value}"
            )

    print("=" * 70)

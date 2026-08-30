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

ИСПРАВЛЕНИЯ v2.3
============================================================

1. Поддержка canonical Signal Contract (average_confidence → confidence fallback)
2. Поддержка average_severity → severity fallback
3. Документирован канонический Signal Contract
4. Версия обновлена до 2.3

ИСПРАВЛЕНИЯ v2.2
============================================================

1. Единый источник evidence_count — _get_evidence_count()
2. Безопасная обработка match_id через _safe_match_id()
3. Защита от невалидных значений в matches
4. Разделение event_count и unique_match_count

АРХИТЕКТУРА:

    ETC SIGNALS
         ↓
    PARAMETER OPTIMIZER
         ↓
    PARAMETER PROPOSALS
         ↓
    [MANUAL / EVOLUTION ENGINE]
         ↓
    model_parameters

ВАЖНО
------
ParameterOptimizer НЕ является Evolution Engine.
Он НЕ применяет изменения.
Он только формирует proposal.

МОДУЛЬ НЕ:
    - изменяет database.py
    - изменяет match_results
    - изменяет predictions
    - изменяет gold
    - изменяет learning_memory
    - изменяет team_passports
    - изменяет FAJ Club Rating
    - изменяет model_parameters
    - запускает обучение
    - применяет proposal автоматически


============================================================
SIGNAL CONTRACT (канонический)
============================================================

LearningAnalyzer.generate_signals() возвращает:

{
    "signal_type": str,                    # "repeated_prediction_error"
    "error_type": str,                     # "score_miss", "winner_miss", etc.
    "cause_type": str,                     # "home_attack_overestimated", etc.
    "matches": List[int],                  # match_id списком
    "event_count": int,                    # всего событий в группе
    "unique_match_count": int,             # уникальных матчей (основной evidence)
    "average_severity": float,             # средняя severity (0-5)
    "average_xg_error": Optional[float],   # средняя xG ошибка
    "average_confidence": float,           # средняя confidence (0-1) ← ОСНОВНОЙ
    "average_impact": float,               # средняя impact (0-1)
    "signal_strength": float,              # сила сигнала (0-1)
    "priority": str,                       # "high" | "medium" | "low"
    "recommendations": List[str],          # рекомендации
}

ParameterOptimizer читает:
    - error_type
    - cause_type
    - unique_match_count (через _get_evidence_count)
    - average_confidence (с fallback на confidence)
    - signal_strength
    - average_severity (с fallback на severity)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.3"
MODULE_NAME = "ETC Parameter Optimizer"


# ============================================================
# SAFETY LIMITS
# ============================================================

MIN_CONFIDENCE = 0.60
MIN_SIGNAL_STRENGTH = 0.30
MIN_PATTERN_COUNT = 3
MAX_PARAMETER_DELTA = 0.05
DEFAULT_PARAMETER_DELTA = 0.02


# ============================================================
# PARAMETER LIMITS
# ============================================================

PARAMETER_LIMITS: Dict[str, tuple[float, float]] = {
    "attack": (0.00, 1.00),
    "defense": (0.00, 1.00),
    "control": (0.00, 1.00),
    "efficiency": (0.00, 1.00),
    "mentality": (0.00, 1.00),
    "discipline": (0.00, 1.00),
    "fitness": (0.00, 1.00),
    "predictability": (0.00, 1.00),
    "opposition": (0.00, 1.00),
    "tempo": (0.00, 1.00),
    "press": (0.00, 1.00),
    "transition": (0.00, 1.00),
    "tactical": (0.00, 1.00),
    "coach": (0.00, 1.00),
    "form": (0.00, 1.00),
    "xg_scale": (0.10, 5.00),
}


# ============================================================
# PARAMETER MAPPING
# ============================================================

CAUSE_PARAMETER_MAP: Dict[str, str] = {
    "home_attack_overestimated": "attack",
    "home_attack_underestimated": "attack",
    "away_attack_overestimated": "attack",
    "away_attack_underestimated": "attack",
    "xg_overestimated": "xg_scale",
    "xg_underestimated": "xg_scale",
    "tempo_overestimated": "tempo",
    "tempo_underestimated": "tempo",
    "press_overestimated": "press",
    "press_underestimated": "press",
    "transition_overestimated": "transition",
    "transition_underestimated": "transition",
    "form_overestimated": "form",
    "form_underestimated": "form",
    "tactical_misread": "tactical",
    "transition_misread": "transition",
    "press_misread": "press",
}


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class ParameterProposal:
    """Предложение ETC по изменению модельного параметра."""
    parameter_name: str
    current_value: Optional[float]
    proposed_value: Optional[float]
    delta: float
    direction: str
    reason: str
    error_type: str
    cause_type: str
    evidence_count: int
    unique_match_count: int
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
    ETC Parameter Optimizer v2.3.

    Только аналитический слой.
    НЕ изменяет БД. НЕ изменяет параметры.

    НОВОЕ v2.3:
        - Поддержка canonical Signal Contract
        - average_confidence → confidence fallback
        - average_severity → severity fallback
    """

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE,
        min_signal_strength: float = MIN_SIGNAL_STRENGTH,
        min_pattern_count: int = MIN_PATTERN_COUNT,
        max_parameter_delta: float = MAX_PARAMETER_DELTA,
    ) -> None:
        self.min_confidence = max(0.0, min(1.0, float(min_confidence)))
        self.min_signal_strength = max(0.0, min(1.0, float(min_signal_strength)))
        self.min_pattern_count = max(1, int(min_pattern_count))
        self.max_parameter_delta = abs(float(max_parameter_delta))

    # ========================================================
    # EVIDENCE COUNT — ЕДИНЫЙ ИСТОЧНИК (НОВОЕ v2.2)
    # ========================================================

    @staticmethod
    def _safe_match_id(value: Any) -> Optional[int]:
        """
        Безопасное извлечение match_id из любого источника.

        Возвращает:
            - положительный int → валидный match_id
            - None → невалидный
        """
        if value is None:
            return None

        try:
            match_id = int(value)
        except (TypeError, ValueError):
            return None

        if match_id <= 0:
            return None

        return match_id

    @staticmethod
    def _normalize_matches(matches: Any) -> List[int]:
        """
        Нормализует список match_id из signal.

        Возвращает только уникальные положительные match_id.
        """
        if not matches:
            return []

        if not isinstance(matches, (list, tuple, set)):
            matches = [matches]

        unique_ids: Set[int] = set()
        for m in matches:
            match_id = ParameterOptimizer._safe_match_id(m)
            if match_id is not None:
                unique_ids.add(match_id)

        return sorted(unique_ids)

    def _get_evidence_count(self, signal: Dict[str, Any]) -> int:
        """
        ЕДИНСТВЕННЫЙ источник evidence_count для всего optimizer.

        Приоритет:
            1. Уникальные match_id из поля "matches"
            2. Поле "unique_match_count"
            3. Поле "count" (fallback)
        """
        # 1. Нормализуем matches
        matches = signal.get("matches")
        normalized = self._normalize_matches(matches)

        if normalized:
            return len(normalized)

        # 2. unique_match_count
        unique_count = self._safe_int(signal.get("unique_match_count"), default=0)
        if unique_count > 0:
            return unique_count

        # 3. Fallback: count
        count = self._safe_int(signal.get("count"), default=0)
        if count > 0:
            return count

        return 0

    # ========================================================
    # PARAMETER MAPPING
    # ========================================================

    @staticmethod
    def map_signal_to_parameter(error_type: str, cause_type: str) -> Optional[str]:
        error_type = str(error_type) if error_type is not None else "unknown"
        cause_type = str(cause_type) if cause_type is not None else "unknown"

        parameter = CAUSE_PARAMETER_MAP.get(cause_type)
        if parameter:
            return parameter

        if error_type in ("over25_miss", "over35_miss"):
            return "tempo"
        if error_type == "btts_miss":
            return "attack"

        return None

    # ========================================================
    # DIRECTION
    # ========================================================

    @staticmethod
    def determine_direction(cause_type: str) -> str:
        cause_type = str(cause_type or "")
        if cause_type.endswith("_overestimated"):
            return "decrease"
        if cause_type.endswith("_underestimated"):
            return "increase"
        return "review"

    # ========================================================
    # DELTA (ИСПРАВЛЕНО v2.3)
    # ========================================================

    def calculate_delta(self, signal: Dict[str, Any]) -> float:
        """
        Рассчитывает величину proposal.

        ИСПРАВЛЕНИЕ v2.3:
            - Использует average_confidence с fallback на confidence
            - Использует единый _get_evidence_count()
        """
        # ✅ ИСПРАВЛЕНИЕ: поддержка canonical Signal Contract
        confidence = self._safe_float(
            signal.get("average_confidence"),
            default=self._safe_float(signal.get("confidence"), 0.0)
        )

        strength = self._safe_float(signal.get("signal_strength"))

        # ЕДИНЫЙ ИСТОЧНИК evidence_count
        count = self._get_evidence_count(signal)

        if count < self.min_pattern_count:
            return 0.0

        if confidence < self.min_confidence:
            return 0.0

        if strength < self.min_signal_strength:
            return 0.0

        base = DEFAULT_PARAMETER_DELTA

        confidence_factor = 0.5 + 0.5 * confidence
        evidence_factor = 0.5 + 0.5 * min(1.0, count / 10.0)
        strength_factor = 0.5 + 0.5 * strength

        delta = base * confidence_factor * evidence_factor * strength_factor
        delta = min(delta, self.max_parameter_delta)

        return round(delta, 6)

    # ========================================================
    # CURRENT VALUE
    # ========================================================

    @staticmethod
    def _get_current_value(parameter_name: str, current_parameters: Optional[Dict[str, float]]) -> Optional[float]:
        if not current_parameters:
            return None

        value = current_parameters.get(parameter_name)
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
        if current_value is None:
            return None

        current = float(current_value)

        if direction == "increase":
            proposed = current + delta
        elif direction == "decrease":
            proposed = current - delta
        else:
            proposed = current

        if parameter_name:
            limits = PARAMETER_LIMITS.get(parameter_name)
            if limits:
                minimum, maximum = limits
                proposed = max(minimum, min(maximum, proposed))

        return round(proposed, 6)

    # ========================================================
    # PRIORITY
    # ========================================================

    @staticmethod
    def determine_priority(count: int, confidence: float, severity: float, signal_strength: float) -> str:
        if count >= 5 and confidence >= 0.80 and severity >= 3.0 and signal_strength >= 0.60:
            return "high"
        if count >= 3 and confidence >= 0.60 and signal_strength >= 0.30:
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
            f"уникальных матчей={count}; "
            f"confidence={confidence:.2f}; "
            f"signal_strength={signal_strength:.2f}. "
            f"Требуется отдельная проверка перед применением."
        )

    # ========================================================
    # SINGLE PROPOSAL (ИСПРАВЛЕНО v2.3)
    # ========================================================

    def create_proposal(
        self,
        signal: Dict[str, Any],
        current_parameters: Optional[Dict[str, float]] = None,
    ) -> Optional[ParameterProposal]:
        if not signal:
            return None

        error_type = signal.get("error_type") or "unknown"
        cause_type = signal.get("cause_type") or "unknown"

        parameter_name = self.map_signal_to_parameter(error_type, cause_type)
        if not parameter_name:
            logger.debug("No parameter mapping for error=%s cause=%s", error_type, cause_type)
            return None

        # ЕДИНЫЙ evidence_count (НОВОЕ v2.2)
        count = self._get_evidence_count(signal)

        # Для уникальных match_id используем normalized matches
        matches = signal.get("matches")
        unique_match_ids = self._normalize_matches(matches)
        unique_match_count = len(unique_match_ids) if unique_match_ids else count

        # ✅ ИСПРАВЛЕНИЕ: поддержка canonical Signal Contract
        # Приоритет: average_confidence > confidence
        confidence = self._safe_float(
            signal.get("average_confidence"),
            default=self._safe_float(signal.get("confidence"), 0.0)
        )

        signal_strength = self._safe_float(signal.get("signal_strength"))

        # ✅ ИСПРАВЛЕНИЕ: поддержка average_severity с fallback на severity
        average_severity = self._safe_float(
            signal.get("average_severity"),
            default=self._safe_float(signal.get("severity"), 0.0)
        )

        delta = self.calculate_delta(signal)
        if delta <= 0:
            return None

        direction = self.determine_direction(cause_type)
        if direction == "review":
            return None

        current_value = self._get_current_value(parameter_name, current_parameters)

        proposed_value = self.calculate_proposed_value(
            current_value=current_value,
            delta=delta,
            direction=direction,
            parameter_name=parameter_name,
        )

        priority = self.determine_priority(
            count=unique_match_count,
            confidence=confidence,
            severity=average_severity,
            signal_strength=signal_strength,
        )

        reason = self._build_reason(
            error_type=error_type,
            cause_type=cause_type,
            count=unique_match_count,
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
            unique_match_count=unique_match_count,
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
        signals: List[Dict[str, Any]],
        current_parameters: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        proposals: List[Dict[str, Any]] = []

        for signal in signals:
            try:
                proposal = self.create_proposal(signal, current_parameters)
                if proposal is None:
                    continue
                proposals.append(proposal.to_dict())
            except Exception as exc:
                logger.exception("Parameter proposal failed: %s", exc)

        return proposals

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    @staticmethod
    def deduplicate(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        best: Dict[str, Dict[str, Any]] = {}

        for proposal in proposals:
            parameter = proposal.get("parameter_name")
            if not parameter:
                continue

            if parameter not in best:
                best[parameter] = proposal
                continue

            existing = best[parameter]
            existing_strength = (
                float(existing.get("signal_strength", 0.0))
                * float(existing.get("confidence", 0.0))
                * max(1, int(existing.get("unique_match_count", 0)))
            )

            new_strength = (
                float(proposal.get("signal_strength", 0.0))
                * float(proposal.get("confidence", 0.0))
                * max(1, int(proposal.get("unique_match_count", 0)))
            )

            if new_strength > existing_strength:
                best[parameter] = proposal

        return list(best.values())

    # ========================================================
    # CONFLICT DETECTION
    # ========================================================

    @staticmethod
    def detect_conflicts(proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        directions: Dict[str, set[str]] = {}

        for proposal in proposals:
            parameter = proposal.get("parameter_name")
            direction = proposal.get("direction")

            if not parameter or not direction:
                continue

            directions.setdefault(parameter, set()).add(direction)

        conflicts = []
        for parameter, values in directions.items():
            if "increase" in values and "decrease" in values:
                conflicts.append({
                    "parameter_name": parameter,
                    "directions": sorted(values),
                    "status": "conflict",
                    "action": "manual_review_required",
                })

        return conflicts

    # ========================================================
    # FULL RUN
    # ========================================================

    def run(
        self,
        signals: List[Dict[str, Any]],
        current_parameters: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        signals = signals or []

        raw_proposals = self.optimize(signals, current_parameters)
        proposals = self.deduplicate(raw_proposals)
        conflicts = self.detect_conflicts(raw_proposals)

        conflict_parameters = {item["parameter_name"] for item in conflicts}

        for proposal in proposals:
            parameter = proposal.get("parameter_name")
            if parameter in conflict_parameters:
                proposal["status"] = "conflict_review"

        if conflicts:
            logger.info(
                "ETC Parameter Optimizer: обнаружены конфликты по параметрам: %s",
                [c["parameter_name"] for c in conflicts]
            )

        return {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "signals_analyzed": len(signals),
            "raw_proposals_created": len(raw_proposals),
            "proposals_created": len(proposals),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "requires_review": bool(conflicts),
            "auto_apply": False,
            "proposals": proposals,
        }

    # ========================================================
    # SAFE HELPERS
    # ========================================================

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default


# ============================================================
# MODULE-LEVEL HELPER
# ============================================================

def optimize_parameters(
    signals: List[Dict[str, Any]],
    current_parameters: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    optimizer = ParameterOptimizer()
    return optimizer.run(signals, current_parameters)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print("FAJ ETC — Parameter Optimizer")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    # Тест с canonical Signal Contract
    signals = [
        {
            "error_type": "score_miss",
            "cause_type": "home_attack_overestimated",
            "matches": [101, 102, 103, 104, 105],
            "unique_match_count": 5,
            "average_severity": 3.2,
            "average_confidence": 0.80,
            "signal_strength": 0.70,
            "priority": "high",
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
        "attack": 0.18, "defense": 0.18, "control": 0.15, "efficiency": 0.12,
        "mentality": 0.10, "discipline": 0.08, "fitness": 0.07, "predictability": 0.07,
        "opposition": 0.05, "tempo": 0.05, "press": 0.05, "transition": 0.05,
        "tactical": 0.05, "coach": 0.04, "form": 0.03, "xg_scale": 2.50,
    }

    result = optimize_parameters(signals, current_parameters)

    print(f"Signals: {result['signals_analyzed']}")
    print(f"Raw proposals: {result['raw_proposals_created']}")
    print(f"Final proposals: {result['proposals_created']}")
    print(f"Conflicts: {result['conflict_count']}")
    print(f"Auto apply: {result['auto_apply']}")

    for proposal in result["proposals"]:
        print("-" * 60)
        for key, value in proposal.items():
            print(f"{key}: {value}")

    print("=" * 70)

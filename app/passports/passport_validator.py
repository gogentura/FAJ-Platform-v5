#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Passport Validator v1.0.1

РОЛЬ:
    Проверка качества и целостности паспортов команд.

ИЗМЕНЕНИЯ v1.0.1:
    - Взвешенное качество паспорта (FIELD_WEIGHTS)
    - Штраф за default-паспорта
=====================================================
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from app.passports.passport_manager import TeamPassport

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    is_valid: bool = True
    score: float = 1.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    completeness: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "quality_score": self.quality_score,
            "completeness": self.completeness,
            "confidence": self.confidence
        }


class PassportValidator:
    VERSION = "1.0.1"

    RANGES = {
        "attack": (0, 100),
        "defense": (0, 100),
        "control": (0, 100),
        "efficiency": (0, 100),
        "mentality": (0, 100),
        "tempo": (0, 100),
        "press": (0, 100),
        "transition": (0, 100),
        "coach": (0, 100),
        "squad_strength": (0, 100),
        "form": (0, 100),
        "predictability": (0, 100),
        "big_match_factor": (0, 100),
        "home_strength": (0, 100),
        "away_strength": (0, 100),
        "tournament_factor": (0, 100),
        "opposition_quality": (0, 100),
        "xg_for": (0.1, 5.0),
        "xg_against": (0.1, 5.0),
        "injury_index": (0, 1),
        "fatigue_index": (0, 1),
        "transfer_index": (0, 1)
    }

    FIELD_WEIGHTS = {
        "attack": 1.5,
        "defense": 1.5,
        "control": 1.2,
        "efficiency": 1.2,
        "mentality": 1.0,
        "tempo": 0.8,
        "press": 0.8,
        "transition": 0.8,
        "coach": 1.0,
        "squad_strength": 1.2,
        "form": 1.2,
        "xg_for": 1.5,
        "xg_against": 1.5
    }

    REQUIRED_FIELDS = list(FIELD_WEIGHTS.keys())
    VALID_STYLES = ["balanced", "attacking", "defensive", "counter", "possession", "direct"]

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"Passport Validator v{self.VERSION} initialized")

    # ============================================================
    # PUBLIC API
    # ============================================================

    def validate(self, passport: TeamPassport) -> ValidationResult:
        result = ValidationResult()

        self._check_ranges(passport, result)
        self._check_completeness(passport, result)
        self._check_style(passport, result)
        self._check_source(passport, result)
        self._check_conflicts(passport, result)
        self._calculate_scores(passport, result)

        return result

    def validate_batch(self, passports: List[TeamPassport]) -> List[ValidationResult]:
        return [self.validate(p) for p in passports]

    def get_passport_quality(self, passport: TeamPassport) -> float:
        result = self.validate(passport)
        return result.quality_score

    def get_completeness(self, passport: TeamPassport) -> float:
        result = self.validate(passport)
        return result.completeness

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _check_ranges(self, passport: TeamPassport, result: ValidationResult) -> None:
        for field, (min_val, max_val) in self.RANGES.items():
            value = getattr(passport, field, None)

            if value is None:
                result.warnings.append(f"Поле '{field}' отсутствует")
                continue

            try:
                val = float(value)
                if val < min_val or val > max_val:
                    result.errors.append(
                        f"Поле '{field}' = {val:.2f} вне диапазона [{min_val}, {max_val}]"
                    )
            except (ValueError, TypeError):
                result.errors.append(f"Поле '{field}' имеет некорректный тип: {value}")

    def _check_completeness(self, passport: TeamPassport, result: ValidationResult) -> None:
        total_weight = 0.0
        filled_weight = 0.0

        for field, weight in self.FIELD_WEIGHTS.items():
            total_weight += weight
            value = getattr(passport, field, None)
            if value is not None and value != 0:
                filled_weight += weight

        completeness = filled_weight / total_weight if total_weight > 0 else 0.0
        result.completeness = round(completeness, 2)

        if completeness < 0.5:
            result.warnings.append(
                f"Низкая заполненность: {completeness:.0%}"
            )
        elif completeness < 0.8:
            result.warnings.append(
                f"Средняя заполненность: {completeness:.0%}"
            )

    def _check_style(self, passport: TeamPassport, result: ValidationResult) -> None:
        style = passport.style_identity
        if style not in self.VALID_STYLES:
            result.warnings.append(
                f"Неизвестный стиль игры: '{style}'. "
                f"Допустимые: {', '.join(self.VALID_STYLES)}"
            )

    def _check_source(self, passport: TeamPassport, result: ValidationResult) -> None:
        source = passport.metadata.source_name
        update_type = passport.metadata.update_type

        if source == "default":
            result.warnings.append("Используются значения по умолчанию")

        if update_type == "initial" and passport.metadata.passport_version == 1:
            result.suggestions.append("Рекомендуется обновить паспорт после первых матчей")

    def _check_conflicts(self, passport: TeamPassport, result: ValidationResult) -> None:
        if passport.xg_for < 0.5 and passport.attack > 80:
            result.warnings.append(
                f"Высокая атака ({passport.attack}) при низком xG_for ({passport.xg_for})"
            )

        if passport.xg_against > 2.0 and passport.defense > 80:
            result.warnings.append(
                f"Высокая защита ({passport.defense}) при высоком xG_against ({passport.xg_against})"
            )

        if passport.injury_index > 0.3 and passport.squad_strength > 80:
            result.warnings.append(
                f"Высокая сила состава ({passport.squad_strength}) "
                f"при высоком индексе травм ({passport.injury_index})"
            )

    def _calculate_scores(self, passport: TeamPassport, result: ValidationResult) -> None:
        quality = result.completeness

        if result.errors:
            quality *= max(0, 1 - len(result.errors) * 0.1)

        if result.warnings:
            quality *= max(0.5, 1 - len(result.warnings) * 0.05)

        if passport.metadata.source_name == "default":
            quality *= 0.7

        result.quality_score = round(min(1.0, quality), 2)

        confidence = 0.3
        source = passport.metadata.source_name
        if source in ["api", "transfermarkt", "understat"]:
            confidence += 0.3
        elif source == "manual":
            confidence += 0.2
        elif source == "default":
            confidence += 0.1

        if passport.metadata.passport_version > 1:
            confidence += min(0.2, passport.metadata.passport_version * 0.02)

        confidence += passport.metadata.data_confidence * 0.2
        result.confidence = round(min(1.0, confidence), 2)

        result.score = round((result.quality_score + result.confidence) / 2, 2)
        result.is_valid = len(result.errors) == 0


# ============================================================
# SINGLETON
# ============================================================

_default_validator: Optional[PassportValidator] = None


def get_passport_validator() -> PassportValidator:
    global _default_validator
    if _default_validator is None:
        _default_validator = PassportValidator()
    return _default_validator


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ Passport Validator v1.0.1 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    validator = get_passport_validator()
    print(f"\n📊 Version: {validator.VERSION}")
    print(f"📊 Field Weights: {validator.FIELD_WEIGHTS}")

    print("\n" + "=" * 60)
    print("✅ Passport Validator v1.0.1 готов к работе.")
    print("=" * 60)

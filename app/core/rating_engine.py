#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Rating Engine v1.0

РОЛЬ:
    Расчёт FAJ Rating команды на основе паспорта.
=====================================================
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RatingEngine:
    VERSION = "1.0"

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"Rating Engine v{self.VERSION} initialized")

    def calculate(self, passport: Dict[str, Any]) -> float:
        try:
            from app.passports.passport_manager import calculate_faj_rating
            return calculate_faj_rating(passport)
        except Exception as e:
            logger.warning(f"Rating fallback: {e}")
            return self._fallback_rating(passport)

    def _fallback_rating(self, passport: Dict[str, Any]) -> float:
        params = [
            self._safe(passport.get("attack"), 70),
            self._safe(passport.get("defense"), 70),
            self._safe(passport.get("control"), 70),
            self._safe(passport.get("form"), 70),
            self._safe(passport.get("efficiency"), 70),
            self._safe(passport.get("mentality"), 70),
            self._safe(passport.get("fitness"), 70)
        ]
        return round(sum(params) / len(params), 1)

    def _safe(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

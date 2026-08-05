#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Agreement Engine v1.0

РОЛЬ:
    Расчёт согласованности между моделями.
=====================================================
"""

import logging
from typing import Dict, Any

from app.config import config

logger = logging.getLogger(__name__)


class AgreementEngine:
    VERSION = "1.0"

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"Agreement Engine v{self.VERSION} initialized")

    def calculate(
        self,
        poisson_result: Dict[str, Any],
        mc_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        p = poisson_result.get("result_probability", {})
        m = mc_result

        home_diff = abs(p.get("home", config.DEFAULT_HOME_PROB) - m.get("home_win", config.DEFAULT_HOME_PROB))
        draw_diff = abs(p.get("draw", config.DEFAULT_DRAW_PROB) - m.get("draw", config.DEFAULT_DRAW_PROB))
        away_diff = abs(p.get("away", config.DEFAULT_AWAY_PROB) - m.get("away_win", config.DEFAULT_AWAY_PROB))

        overall = (
            home_diff * config.AGREEMENT_WEIGHT_HOME +
            draw_diff * config.AGREEMENT_WEIGHT_DRAW +
            away_diff * config.AGREEMENT_WEIGHT_AWAY
        )

        return {
            "home": round(1.0 - home_diff, 4),
            "draw": round(1.0 - draw_diff, 4),
            "away": round(1.0 - away_diff, 4),
            "overall": round(1.0 - overall, 4)
        }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Raw Prediction Builder v1.0

РОЛЬ:
    Формирование сырого прогноза из результатов моделей.
=====================================================
"""

import logging
from typing import Dict, Any, Optional

from app.config import config

logger = logging.getLogger(__name__)


class RawPredictionBuilder:
    VERSION = "1.0"

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"Raw Prediction Builder v{self.VERSION} initialized")

    def build(
        self,
        home_team: str,
        away_team: str,
        league: str,
        home_rating: float,
        away_rating: float,
        home_xg: float,
        away_xg: float,
        poisson_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        probs = poisson_result.get("result_probability", {})

        return {
            "match": {
                "home": home_team,
                "away": away_team,
                "league": league
            },
            "rating": {
                "home": home_rating,
                "away": away_rating
            },
            "xg": {
                "home": home_xg,
                "away": away_xg
            },
            "probability": {
                "home": probs.get("home", config.DEFAULT_HOME_PROB),
                "draw": probs.get("draw", config.DEFAULT_DRAW_PROB),
                "away": probs.get("away", config.DEFAULT_AWAY_PROB)
            },
            "score_prediction": {
                "faj_score": poisson_result.get("most_likely_score", "0:0"),
                "probability": poisson_result.get("score_probability", 0)
            },
            "btts": poisson_result.get("btts_probability", 0),
            "over_2_5": poisson_result.get("over_2_5", 0),
            "context": context
        }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ Core Engine v7.3

РОЛЬ:
    Тонкий фасад над Prediction Pipeline.
    Единая точка входа для всей платформы.
=====================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import config
from app.core.prediction_pipeline import PredictionPipeline
from app.core.match_context import MatchContext

logger = logging.getLogger(__name__)


class FAJCore:
    VERSION = config.CORE_VERSION
    PLATFORM_VERSION = config.PLATFORM_VERSION

    def __init__(self, pipeline: Optional[PredictionPipeline] = None):
        self.version = self.VERSION
        self.platform_version = self.PLATFORM_VERSION
        self.pipeline = pipeline or PredictionPipeline()
        logger.info(f"FAJ Core v{self.VERSION} initialized")

    def predict(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        return self.predict_match(home_team, away_team, league, context)

    def predict_match(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        try:
            return self.pipeline.run(home_team, away_team, league, context)
        except Exception as e:
            logger.exception(f"Prediction failed: {e}")
            return {"status": "error", "message": str(e), "timestamp": datetime.now().isoformat()}

    def status(self) -> Dict[str, Any]:
        pipeline_status = self.pipeline.status() if hasattr(self.pipeline, "status") else {}
        return {
            "core": "FAJ Core Engine",
            "core_version": self.VERSION,
            "platform_version": self.PLATFORM_VERSION,
            "pipeline_version": pipeline_status.get("version", "unknown"),
            "status": "READY",
            "pipeline": pipeline_status
        }

    def test(self) -> Dict[str, Any]:
        return self.predict_match("Зенит", "Спартак", "RPL")


if __name__ == "__main__":
    core = FAJCore()
    print(core.status())
    print(core.test())

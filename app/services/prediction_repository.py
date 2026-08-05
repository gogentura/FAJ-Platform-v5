#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Repository v1.0

РОЛЬ:
    Сохранение прогнозов в базу данных.
=====================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PredictionRepository:
    VERSION = "1.0"

    def __init__(self, db_connection=None, save_enabled: bool = True):
        self.version = self.VERSION
        self.db = db_connection
        self.save_enabled = save_enabled
        logger.info(f"Prediction Repository v{self.VERSION} initialized")

    def save(self, prediction: Dict[str, Any]) -> bool:
        if not self.save_enabled:
            logger.debug("Save disabled")
            return True

        try:
            conn = self.db if self.db else self._get_db()
            cursor = conn.cursor()

            raw = prediction.get("raw_prediction", {})
            match = raw.get("match", {})
            xg = raw.get("xg", {})

            cursor.execute(
                """
                INSERT INTO gold_dataset
                (prediction_id, home_team, away_team, model_version,
                 xg_home_pred, xg_away_pred, faj_score, confidence, risk, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    prediction.get("prediction_id"),
                    match.get("home"),
                    match.get("away"),
                    prediction.get("metadata", {}).get("pipeline_version"),
                    xg.get("home", 0.0),
                    xg.get("away", 0.0),
                    raw.get("score_prediction", {}).get("faj_score", "0:0"),
                    prediction.get("confidence", {}).get("overall", 0.0),
                    prediction.get("risk", {}).get("score", 0),
                    datetime.now().isoformat()
                )
            )

            conn.commit()
            logger.info(f"Saved: {prediction.get('prediction_id')}")
            return True

        except Exception as e:
            logger.error(f"Save error: {e}")
            return False

    def _get_db(self):
        from app.database import get_db
        return get_db()

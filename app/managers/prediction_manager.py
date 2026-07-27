# =====================================================
# FAJ Platform v6.9.3
# app/managers/prediction_manager.py
#
# Prediction Manager
#
# Compatible:
# - tour_predictor v6.9.3
# - prediction_pipeline v6.9.3
# - faj_predictions handler
# - PostgreSQL
# =====================================================
import json
import logging
from datetime import datetime
from app.database import get_db

logger = logging.getLogger(__name__)


# =====================================================
# HELPERS
# =====================================================
def safe_json(value):
    try:
        if isinstance(value, str):
            return value
        return json.dumps(value or {}, ensure_ascii=False)
    except Exception:
        return "{}"


def safe_float(value):
    try:
        if value is None:
            return 0
        return float(value)
    except Exception:
        return 0


# =====================================================
# CLEAR OLD PREDICTIONS
# =====================================================
def clear_predictions():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM predictions")
        conn.commit()
        conn.close()
        logger.info("FAJ predictions cleared")
        return True
    except Exception as e:
        logger.error("Clear predictions error: %s", e, exc_info=True)
        return False


# =====================================================
# SAVE SINGLE PREDICTION
# =====================================================
def save_prediction(fixture, prediction):
    try:
        if not fixture or not prediction:
            logger.warning("Empty fixture or prediction")
            return False

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO predictions
            (
                fixture_id,
                home_win,
                draw,
                away_win,
                xg_home,
                xg_away,
                score_prediction,
                confidence,
                model_version,
                created
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                fixture.get("id"),
                safe_float(prediction.get("home_probability", 0)) / 100,
                safe_float(prediction.get("draw_probability", 0)) / 100,
                safe_float(prediction.get("away_probability", 0)) / 100,
                safe_float(prediction.get("xg_home")),
                safe_float(prediction.get("xg_away")),
                prediction.get("expected_score", "-"),
                safe_float(prediction.get("confidence")),
                "FAJ v6.9.3",
                datetime.now()
            )
        )
        conn.commit()
        conn.close()

        logger.info(
            "Prediction saved: %s - %s",
            fixture.get("home_team"),
            fixture.get("away_team")
        )
        return True
    except Exception as e:
        logger.error("Save prediction error: %s", e, exc_info=True)
        return False


# =====================================================
# SAVE TOUR BATCH
# =====================================================
def save_predictions_batch(fixtures, predictions):
    """
    Сохранение полного тура FAJ
    """
    saved = 0
    if not fixtures or not predictions:
        logger.warning("Empty batch data")
        return 0

    for fixture, prediction in zip(fixtures, predictions):
        try:
            if save_prediction(fixture, prediction):
                saved += 1
        except Exception as e:
            logger.error("Batch save item error: %s", e, exc_info=True)

    logger.info("FAJ predictions saved: %s/%s", saved, len(predictions))
    return saved


# =====================================================
# GET PREDICTIONS
# TELEGRAM HANDLER API
# =====================================================
def get_predictions(limit=20):
    """
    Основной API для:
    
    app/handlers/faj_predictions.py
    
    Возвращает последние прогнозы FAJ
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                fixture_id,
                home_team,
                away_team,
                league,
                season,
                winner,
                expected_score,
                xg_home,
                xg_away,
                confidence,
                model_version,
                created_at
            FROM predictions
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()

        result = []
        for row in rows:
            try:
                result.append(dict(row))
            except Exception:
                result.append(row)
        return result
    except Exception as e:
        logger.error("get_predictions error: %s", e, exc_info=True)
        return []


# =====================================================
# GET PREDICTION HISTORY
# =====================================================
def get_prediction_history(limit=100):
    """
    Learning Layer history
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM predictions
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,)
        )
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.error("Prediction history error: %s", e, exc_info=True)
        return []


# =====================================================
# GET ONE PREDICTION
# =====================================================
def get_prediction_by_id(prediction_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM predictions
            WHERE id=%s
            LIMIT 1
            """,
            (prediction_id,)
        )
        row = cur.fetchone()
        conn.close()

        if row:
            try:
                return dict(row)
            except Exception:
                return row
        return None
    except Exception as e:
        logger.error("get_prediction_by_id error: %s", e, exc_info=True)
        return None


# =====================================================
# CLEAN DUPLICATES
# =====================================================
def delete_duplicate_predictions():
    """
    Удаляет повторные генерации тура
    Оставляет последнюю запись
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM predictions p1
            USING predictions p2
            WHERE p1.id < p2.id
            AND p1.fixture_id = p2.fixture_id
            """
        )
        deleted = cur.rowcount
        conn.commit()
        conn.close()

        logger.info("Duplicates removed: %s", deleted)
        return deleted
    except Exception as e:
        logger.error("Duplicate cleanup error: %s", e, exc_info=True)
        return 0


# =====================================================
# EXPORTS
# =====================================================
__all__ = [
    'clear_predictions',
    'save_prediction',
    'save_predictions_batch',
    'get_predictions',
    'get_prediction_history',
    'get_prediction_by_id',
    'delete_duplicate_predictions'
]


# =====================================================
# END PREDICTION MANAGER
# =====================================================

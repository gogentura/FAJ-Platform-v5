# =====================================================
# FAJ Platform v6.9.3
# app/managers/prediction_manager.py
#
# Prediction Manager
#
# Compatible:
# - prediction_pipeline.py v6.9.3
# - tour_predictor.py v6.9.3
# - generate_predictions.py
# - PostgreSQL
# =====================================================
import logging
from app.database import get_db

logger = logging.getLogger(__name__)


# =====================================================
# SAFE HELPERS
# =====================================================
def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def row_to_dict(row):
    try:
        return dict(row)
    except Exception:
        return row


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
                model_version
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
                %s
            )
            """,
            (
                fixture.get("id"),
                safe_float(prediction.get("home_probability", 0)) / 100,
                safe_float(prediction.get("draw_probability", 0)) / 100,
                safe_float(prediction.get("away_probability", 0)) / 100,
                safe_float(prediction.get("xg_home", 0)),
                safe_float(prediction.get("xg_away", 0)),
                prediction.get("expected_score", "-"),
                safe_float(prediction.get("confidence", 0)),
                prediction.get("pipeline_version", "6.9.3")
            )
        )

        conn.commit()
        conn.close()

        logger.info(
            "FAJ Prediction saved %s - %s",
            fixture.get("home_team"),
            fixture.get("away_team")
        )
        return True

    except Exception as e:
        logger.error("save_prediction error: %s", e, exc_info=True)
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
# END PREDICTION MANAGER
# =====================================================

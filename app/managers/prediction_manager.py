# =====================================================
# FAJ Platform v7.0.3
# app/managers/prediction_manager.py
#
# Prediction Manager
#
# Flow:
#
# FAJ Core
#    |
#    v
# Prediction Pipeline
#    |
#    v
# save_prediction()
#    |
#    v
# PostgreSQL predictions
#    |
#    v
# Result Learning Engine
#
# =====================================================
import logging
from datetime import datetime
from app.database import get_db

logger = logging.getLogger(__name__)
MODEL_VERSION = "FAJ v7.0.3"

# =====================================================
# SAFE
# =====================================================
def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default

def safe_json(value):
    """
    PostgreSQL JSONB helper
    """
    if value is None:
        return {}
    if isinstance(
        value,
        (dict, list)
    ):
        return value
    return {}

# =====================================================
# SAVE ONE PREDICTION
# =====================================================
def save_prediction(
        fixture,
        prediction
):
    try:
        if not fixture or not prediction:
            logger.warning(
                "Empty fixture or prediction"
            )
            return False
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO predictions
            (
                fixture_id,
                league,
                season,
                round,
                home_team,
                away_team,
                winner_prediction,
                home_probability,
                draw_probability,
                away_probability,
                xg_home,
                xg_away,
                expected_score,
                top_scores,
                btts_probability,
                over25_probability,
                confidence,
                model_version,
                winner,
                home_rating,
                away_rating,
                risk,
                category,
                factors,
                season_phase,
                passport_quality,
                created_at
            )
            VALUES
            (
                %s,%s,%s,%s,
                %s,%s,
                %s,
                %s,%s,%s,
                %s,%s,
                %s,
                %s,
                %s,%s,
                %s,
                %s,
                %s,
                %s,%s,
                %s,%s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                fixture.get(
                    "id"
                ),
                fixture.get(
                    "league",
                    "RPL"
                ),
                fixture.get(
                    "season",
                    "2026/27"
                ),
                fixture.get(
                    "round",
                    ""
                ),
                fixture.get(
                    "home_team",
                    "-"
                ),
                fixture.get(
                    "away_team",
                    "-"
                ),
                prediction.get(
                    "winner",
                    prediction.get(
                        "winner_prediction",
                        "-"
                    )
                ),
                safe_float(
                    prediction.get(
                        "home_probability"
                    )
                ),
                safe_float(
                    prediction.get(
                        "draw_probability"
                    )
                ),
                safe_float(
                    prediction.get(
                        "away_probability"
                    )
                ),
                safe_float(
                    prediction.get(
                        "xg_home"
                    )
                ),
                safe_float(
                    prediction.get(
                        "xg_away"
                    )
                ),
                prediction.get(
                    "expected_score",
                    "-"
                ),
                safe_json(
                    prediction.get(
                        "top_scores"
                    )
                ),
                safe_float(
                    prediction.get(
                        "btts_probability"
                    )
                ),
                safe_float(
                    prediction.get(
                        "over25_probability"
                    )
                ),
                safe_float(
                    prediction.get(
                        "confidence"
                    )
                ),
                prediction.get(
                    "model_version",
                    MODEL_VERSION
                ),
                None,
                safe_float(
                    prediction.get(
                        "home_rating"
                    )
                ),
                safe_float(
                    prediction.get(
                        "away_rating"
                    )
                ),
                prediction.get(
                    "risk",
                    "Средний"
                ),
                prediction.get(
                    "grade",
                    "C"
                ),
                safe_json(
                    prediction.get(
                        "factors"
                    )
                ),
                prediction.get(
                    "season_phase",
                    "regular"
                ),
                prediction.get(
                    "passport_quality",
                    "standard"
                ),
                datetime.now()
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(
            "Prediction saved: %s - %s",
            fixture.get(
                "home_team"
            ),
            fixture.get(
                "away_team"
            )
        )
        return True
    except Exception as e:
        logger.exception(
            "Prediction save error: %s",
            e
        )
        return False

# =====================================================
# GET PREDICTIONS
# =====================================================
def get_predictions(
        limit=20
):
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
                winner_prediction,
                winner,
                expected_score,
                xg_home,
                xg_away,
                home_probability,
                draw_probability,
                away_probability,
                confidence,
                risk,
                category,
                model_version,
                actual_score,
                accuracy,
                created_at
            FROM predictions
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (
                limit,
            )
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for row in rows:
            try:
                result.append(
                    dict(row)
                )
            except Exception:
                result.append(
                    row
                )
        return result
    except Exception as e:
        logger.exception(
            "Get predictions error"
        )
        return []

# =====================================================
# GET HISTORY
# =====================================================
def get_prediction_history(
        limit=100
):
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
            (
                limit,
            )
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        logger.exception(
            "Prediction history error"
        )
        return []

# =====================================================
# GET BY ID
# =====================================================
def get_prediction_by_id(
        prediction_id
):
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
            (
                prediction_id,
            )
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.exception(
            "Prediction by id error"
        )
        return None

# =====================================================
# GET TEAM PREDICTIONS
# =====================================================
def get_team_predictions(
        team,
        limit=20
):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM predictions
            WHERE
            home_team=%s
            OR
            away_team=%s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (
                team,
                team,
                limit
            )
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [
            dict(row)
            for row in rows
        ]
    except Exception as e:
        logger.exception(
            "Team predictions error"
        )
        return []

# =====================================================
# CLEAR
# =====================================================
def clear_predictions():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM predictions
            """
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        logger.info(
            "Deleted predictions: %s",
            deleted
        )
        return True
    except Exception as e:
        logger.exception(
            "Clear predictions error"
        )
        return False

# =====================================================
# UPDATE RESULT AFTER MATCH
# =====================================================
def update_prediction_result(
        prediction_id,
        actual_score,
        actual_winner
):
    try:
        conn = get_db()
        cur = conn.cursor()
        # получаем прогноз
        cur.execute(
            """
            SELECT
                winner_prediction,
                expected_score
            FROM predictions
            WHERE id=%s
            LIMIT 1
            """,
            (
                prediction_id,
            )
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        try:
            data = dict(row)
        except:
            data = {
                "winner_prediction": row[0],
                "expected_score": row[1]
            }
        accuracy = calculate_accuracy(
            data.get(
                "winner_prediction"
            ),
            data.get(
                "expected_score"
            ),
            actual_winner,
            actual_score
        )
        cur.execute(
            """
            UPDATE predictions
            SET
            actual_score=%s,
            actual_winner=%s,
            winner=%s,
            accuracy=%s
            WHERE id=%s
            """,
            (
                actual_score,
                actual_winner,
                actual_winner,
                accuracy,
                prediction_id
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(
            "Prediction result updated id=%s accuracy=%s",
            prediction_id,
            accuracy
        )
        return True
    except Exception as e:
        logger.exception(
            "Update result error"
        )
        return False

# =====================================================
# ACCURACY ENGINE
# =====================================================
def calculate_accuracy(
        predicted_winner,
        predicted_score,
        actual_winner,
        actual_score
):
    score = 0
    # победитель
    if predicted_winner == actual_winner:
        score += 50
    # точный счет
    if predicted_score == actual_score:
        score += 50
    else:
        try:
            p = predicted_score.split("-")
            a = actual_score.split("-")
            if (
                len(p) == 2
                and len(a) == 2
            ):
                if (
                    int(p[0]) - int(p[1])
                ) == (
                    int(a[0]) - int(a[1])
                ):
                    score += 25
        except:
            pass
    return score

# =====================================================
# DELETE DUPLICATES
# =====================================================
def delete_duplicate_predictions():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM predictions p1
            USING predictions p2
            WHERE
            p1.id < p2.id
            AND p1.fixture_id = p2.fixture_id
            """
        )
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        logger.info(
            "Duplicates removed: %s",
            deleted
        )
        return deleted
    except Exception as e:
        logger.exception(
            "Delete duplicate error"
        )
        return 0

# =====================================================
# EXPORTS
# =====================================================
__all__ = [
    "save_prediction",
    "get_predictions",
    "get_prediction_history",
    "get_prediction_by_id",
    "get_team_predictions",
    "update_prediction_result",
    "calculate_accuracy",
    "delete_duplicate_predictions",
    "clear_predictions"
]

# =====================================================
# END
# =====================================================

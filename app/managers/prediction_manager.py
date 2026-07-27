# =====================================================
# FAJ Platform v6.9.2
# app/managers/prediction_manager.py
#
# Prediction Manager
#
# Compatible:
# FAJCore v6.8+
# prediction_pipeline v6.9.2
# PostgreSQL
# generate_tour
# debug_prediction
# =====================================================
import logging
import ast
import json
import numpy as np
from app.database import get_db
from app.services.prediction_pipeline import (
    predict_match_pipeline
)
from app.core.faj_core import FAJCore

logger = logging.getLogger(__name__)

# =====================================================
# CLEAN NUMPY
# =====================================================
def clean_value(value):
    if isinstance(value, np.generic):
        return value.item()
    return value

def clean_prediction(data):
    if data is None:
        return {}
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = clean_prediction(value)
            elif isinstance(value, list):
                result[key] = [
                    clean_prediction(v)
                    if isinstance(v, dict)
                    else clean_value(v)
                    for v in value
                ]
            else:
                result[key] = clean_value(value)
        return result
    return clean_value(data)

# =====================================================
# NORMALIZE PIPELINE RESULT
# =====================================================
def normalize_prediction(prediction):
    prediction = clean_prediction(prediction)
    if not prediction:
        return {}
    return {
        "winner": prediction.get("winner", "-"),
        "winner_name": prediction.get("winner_name", "-"),
        "home_probability": float(prediction.get("home_probability", 0)),
        "draw_probability": float(prediction.get("draw_probability", 0)),
        "away_probability": float(prediction.get("away_probability", 0)),
        "xg_home": float(prediction.get("xg_home", 0)),
        "xg_away": float(prediction.get("xg_away", 0)),
        "expected_score": prediction.get("expected_score", "-"),
        "top_scores": prediction.get("top_scores", []),
        "btts": prediction.get("btts", 0),
        "over25": prediction.get("over25", 0),
        "under25": prediction.get("under25", 0),
        "confidence": float(prediction.get("confidence", 0)),
        "risk": prediction.get("risk", "Высокий"),
        "grade": prediction.get("grade", "C"),
        "category": prediction.get("category", "C"),
        "home_rating": float(prediction.get("home_rating", 0)),
        "away_rating": float(prediction.get("away_rating", 0)),
        "factors": prediction.get("factors", []),
        "season_phase": prediction.get("season_phase", "start"),
        "passport_quality": prediction.get("passport_quality", {"home": 0, "away": 0})
    }

# =====================================================
# SAVE PREDICTION
# =====================================================
def save_prediction(fixture, prediction):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
        """
        INSERT INTO predictions
        (
            fixture_id,
            league,
            season,
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
            risk,
            grade,
            category,
            factors,
            home_rating,
            away_rating,
            season_phase,
            model_version,
            created
        )
        VALUES
        (
            %s,%s,%s,
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
            %s,
            %s,
            %s,%s,
            %s,
            %s,
            NOW()
        )
        ON CONFLICT (fixture_id)
        DO UPDATE SET
            winner_prediction = EXCLUDED.winner_prediction,
            home_probability = EXCLUDED.home_probability,
            draw_probability = EXCLUDED.draw_probability,
            away_probability = EXCLUDED.away_probability,
            xg_home = EXCLUDED.xg_home,
            xg_away = EXCLUDED.xg_away,
            expected_score = EXCLUDED.expected_score,
            confidence = EXCLUDED.confidence,
            risk = EXCLUDED.risk,
            grade = EXCLUDED.grade,
            category = EXCLUDED.category,
            factors = EXCLUDED.factors,
            home_rating = EXCLUDED.home_rating,
            away_rating = EXCLUDED.away_rating,
            model_version = EXCLUDED.model_version
        """,
        (
            fixture.get("id"),
            fixture.get("league", "RPL"),
            fixture.get("season", "2026/27"),
            fixture.get("home_team"),
            fixture.get("away_team"),
            prediction.get("winner"),
            prediction.get("home_probability", 0),
            prediction.get("draw_probability", 0),
            prediction.get("away_probability", 0),
            prediction.get("xg_home", 0),
            prediction.get("xg_away", 0),
            prediction.get("expected_score", "-"),
            json.dumps(prediction.get("top_scores", []), ensure_ascii=False),
            prediction.get("btts", 0),
            prediction.get("over25", 0),
            prediction.get("confidence", 0),
            prediction.get("risk", "Высокий"),
            prediction.get("grade", "C"),
            prediction.get("category", "C"),
            json.dumps(prediction.get("factors", []), ensure_ascii=False),
            prediction.get("home_rating", 0),
            prediction.get("away_rating", 0),
            prediction.get("season_phase", "start"),
            FAJCore.VERSION
        )
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Prediction save error: %s", e, exc_info=True)
        raise
    finally:
        conn.close()

# =====================================================
# CREATE SINGLE PREDICTION
# =====================================================
def create_prediction(fixture, core=None):
    try:
        prediction = predict_match_pipeline(
            home_team=fixture.get("home_team"),
            away_team=fixture.get("away_team"),
            league=fixture.get("league", "RPL"),
            core=core
        )
        prediction = normalize_prediction(prediction)
        save_prediction(fixture, prediction)
        return prediction
    except Exception as e:
        logger.error("Create prediction failed: %s", e, exc_info=True)
        return None

# =====================================================
# CREATE TOUR
# =====================================================
def create_tour_predictions(fixtures, core=None):
    generated = 0
    errors = []
    for fixture in fixtures:
        try:
            result = create_prediction(fixture, core)
            if result:
                generated += 1
            else:
                errors.append({
                    "match": f"{fixture.get('home_team')} - {fixture.get('away_team')}",
                    "error": "empty prediction"
                })
        except Exception as e:
            errors.append({
                "match": f"{fixture.get('home_team')} - {fixture.get('away_team')}",
                "error": str(e)
            })
    return {
        "generated": generated,
        "errors": errors
    }

# =====================================================
# GET PREDICTIONS
# =====================================================
def get_predictions(league=None, season=None):
    conn = get_db()
    try:
        cur = conn.cursor()
        query = """
        SELECT *
        FROM predictions
        WHERE 1=1
        """
        params = []
        if league:
            query += " AND league=%s"
            params.append(league)
        if season:
            query += " AND season=%s"
            params.append(season)
        query += " ORDER BY created DESC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for field in ["top_scores", "factors"]:
                try:
                    if item.get(field):
                        item[field] = json.loads(item[field])
                except Exception:
                    item[field] = []
            result.append(item)
        return result
    finally:
        conn.close()

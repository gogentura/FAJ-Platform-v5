# =====================================================
# FAJ Platform v6.9
# app/managers/prediction_manager.py
#
# Prediction Manager
# PostgreSQL version
#
# FIX:
# - unified pipeline
# - сохраняет FAJ v6.8 fields
# - совместимость debug_prediction/generate_tour
# =====================================================
import logging
import ast
import json
from datetime import datetime
import numpy as np
from app.database import get_db
from app.core.faj_core import FAJCore
from app.services.prediction_pipeline import (
    predict_match_pipeline
)

logger = logging.getLogger(__name__)

# =====================================================
# NUMPY CLEAN
# =====================================================
def clean_value(value):
    if isinstance(value, np.generic):
        return value.item()
    return value

def clean_prediction(data):
    if not data:
        return {}
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

# =====================================================
# NORMALIZE FAJ RESPONSE v6.9
# =====================================================
def normalize_prediction(raw):
    raw = clean_prediction(raw)
    decision = raw.get(
        "decision",
        {}
    )
    xg_block = raw.get(
        "xg",
        {}
    )
    predicted = xg_block.get(
        "predicted",
        xg_block
    )
    return {
        # -------------------------
        # RESULT
        # -------------------------
        "winner":
            decision.get(
                "winner"
            ),
        "winner_name":
            decision.get(
                "winner_name"
            ),
        "expected_score":
            decision.get(
                "expected_score",
                ""
            ),
        # -------------------------
        # PROBABILITIES
        # -------------------------
        "home_probability":
            float(
                decision.get(
                    "home_probability",
                    0
                )
            ),
        "draw_probability":
            float(
                decision.get(
                    "draw_probability",
                    0
                )
            ),
        "away_probability":
            float(
                decision.get(
                    "away_probability",
                    0
                )
            ),
        # -------------------------
        # xG
        # -------------------------
        "xg_home":
            float(
                predicted.get(
                    "home",
                    0
                )
            ),
        "xg_away":
            float(
                predicted.get(
                    "away",
                    0
                )
            ),
    }

# =====================================================
# SAVE MODEL PREDICTION v6.9
# =====================================================
def save_prediction(
    fixture,
    prediction
):
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
            home_rating,
            away_rating,
            risk,
            category,
            factors,
            season_phase,
            home_data_quality,
            away_data_quality,
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
            %s,%s,
            %s,%s,
            %s,
            %s,
            %s,%s,
            %s,
            NOW()
        )
        ON CONFLICT(fixture_id)
        DO UPDATE SET
            winner_prediction = EXCLUDED.winner_prediction,
            home_probability = EXCLUDED.home_probability,
            draw_probability = EXCLUDED.draw_probability,
            away_probability = EXCLUDED.away_probability,
            xg_home = EXCLUDED.xg_home,
            xg_away = EXCLUDED.xg_away,
            expected_score = EXCLUDED.expected_score,
            confidence = EXCLUDED.confidence,
            home_rating = EXCLUDED.home_rating,
            away_rating = EXCLUDED.away_rating,
            risk = EXCLUDED.risk,
            category = EXCLUDED.category,
            factors = EXCLUDED.factors,
            season_phase = EXCLUDED.season_phase,
            model_version = EXCLUDED.model_version
        """,
        (
            # --------------------
            # FIXTURE
            # --------------------
            fixture.get("id"),
            fixture.get("league", "RPL"),
            fixture.get("season", "2026/27"),
            fixture.get("home_team"),
            fixture.get("away_team"),
            # --------------------
            # RESULT
            # --------------------
            prediction.get("winner"),
            # --------------------
            # PROB
            # --------------------
            prediction.get("home_probability", 0),
            prediction.get("draw_probability", 0),
            prediction.get("away_probability", 0),
            # --------------------
            # XG
            # --------------------
            prediction.get("xg_home", 0),
            prediction.get("xg_away", 0),
            # --------------------
            # SCORE
            # --------------------
            prediction.get("expected_score", ""),
            json.dumps(
                prediction.get("top_scores", []),
                ensure_ascii=False
            ),
            # --------------------
            # MARKETS
            # --------------------
            prediction.get("btts", 0),
            prediction.get("over25", 0),
            # --------------------
            # FAJ v6.8
            # --------------------
            prediction.get("confidence", 0),
            prediction.get("home_rating", 0),
            prediction.get("away_rating", 0),
            prediction.get("risk", "Высокий"),
            prediction.get("category", "C"),
            json.dumps(
                prediction.get("factors", []),
                ensure_ascii=False
            ),
            prediction.get("season_phase", "start"),
            prediction.get("home_data_quality", 0),
            prediction.get("away_data_quality", 0),
            FAJCore.VERSION
        )
        )
        conn.commit()
        logger.info(
            "Prediction saved fixture=%s",
            fixture.get("id")
        )
    except Exception as e:
        conn.rollback()
        logger.error(
            "Prediction save failed: %s",
            e,
            exc_info=True
        )
        raise
    finally:
        conn.close()

# =====================================================
# CREATE SINGLE PREDICTION v6.9
# =====================================================
def create_prediction(
    fixture,
    core=None
):
    if core is None:
        core = FAJCore()
    home = fixture.get("home_team")
    away = fixture.get("away_team")
    league = fixture.get("league", "RPL")
    if not home or not away:
        raise Exception(
            "Нет команд для прогноза"
        )
    # =================================================
    # ЕДИНЫЙ PIPELINE
    # =================================================
    raw_prediction = predict_match_pipeline(
        home,
        away,
        league,
        core
    )
    if not raw_prediction:
        raise Exception(
            "Pipeline вернул пустой прогноз"
        )
    prediction = normalize_prediction(
        raw_prediction
    )
    # =================================================
    # ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ v6.9
    # =================================================
    prediction["home_rating"] = (
        raw_prediction
        .get("decision", {})
        .get("home_rating", 0)
    )
    prediction["away_rating"] = (
        raw_prediction
        .get("decision", {})
        .get("away_rating", 0)
    )
    prediction["risk"] = (
        raw_prediction
        .get("risk", "Высокий")
    )
    prediction["category"] = (
        raw_prediction
        .get("category", "C")
    )
    prediction["factors"] = (
        raw_prediction
        .get("factors", [])
    )
    prediction["season_phase"] = (
        raw_prediction
        .get("season_phase", "start")
    )
    prediction["home_data_quality"] = (
        raw_prediction
        .get("data_quality", {})
        .get("home", 0)
    )
    prediction["away_data_quality"] = (
        raw_prediction
        .get("data_quality", {})
        .get("away", 0)
    )
    # =================================================
    # СОХРАНЕНИЕ
    # =================================================
    save_prediction(
        fixture,
        prediction
    )
    return prediction

# =====================================================
# CREATE TOUR PREDICTIONS v6.9
# =====================================================
def create_tour_predictions(
    fixtures,
    core=None
):
    if core is None:
        core = FAJCore()
    generated = 0
    errors = []
    predictions = []
    for fixture in fixtures:
        try:
            prediction = create_prediction(
                fixture,
                core
            )
            predictions.append(
                {
                    "fixture": fixture,
                    "prediction": prediction
                }
            )
            generated += 1
        except Exception as e:
            logger.error(
                "Tour prediction error %s",
                e,
                exc_info=True
            )
            errors.append(
                {
                    "match":
                        f"{fixture.get('home_team')} - {fixture.get('away_team')}",
                    "error":
                        str(e)
                }
            )
    return {
        "generated": generated,
        "errors": errors,
        "predictions": predictions
    }

# =====================================================
# GET PREDICTIONS v6.9
# =====================================================
def get_predictions(
    league=None,
    season=None
):
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
            query += """
            AND league=%s
            """
            params.append(league)
        if season:
            query += """
            AND season=%s
            """
            params.append(season)
        query += """
        ORDER BY fixture_id ASC
        """
        cur.execute(
            query,
            tuple(params)
        )
        rows = cur.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            # -------------------------
            # JSON fields
            # -------------------------
            try:
                item["top_scores"] = json.loads(
                    item.get("top_scores", "[]")
                )
            except Exception:
                try:
                    item["top_scores"] = ast.literal_eval(
                        item.get("top_scores", "[]")
                    )
                except Exception:
                    item["top_scores"] = []
            try:
                item["factors"] = json.loads(
                    item.get("factors", "[]")
                )
            except Exception:
                item["factors"] = []
            # -------------------------
            # DEFAULTS v6.9
            # -------------------------
            item.setdefault("confidence", 0)
            item.setdefault("risk", "Высокий")
            item.setdefault("category", "C")
            item.setdefault("season_phase", "start")
            item.setdefault("home_rating", 0)
            item.setdefault("away_rating", 0)
            result.append(item)
        return result
    finally:
        conn.close()

# =====================================================
# GET SINGLE PREDICTION
# =====================================================
def get_prediction_by_fixture(
    fixture_id
):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
        """
        SELECT *
        FROM predictions
        WHERE fixture_id=%s
        LIMIT 1
        """,
        (fixture_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["top_scores"] = json.loads(
                item.get("top_scores", "[]")
            )
        except Exception:
            item["top_scores"] = []
        try:
            item["factors"] = json.loads(
                item.get("factors", "[]")
            )
        except Exception:
            item["factors"] = []
        return item
    finally:
        conn.close()

# =====================================================
# DELETE PREDICTIONS
# =====================================================
def clear_predictions():
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
        """
        DELETE FROM predictions
        """
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(
            "Clear predictions error: %s",
            e,
            exc_info=True
        )
        return False
    finally:
        conn.close()

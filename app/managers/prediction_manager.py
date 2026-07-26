# =====================================================
# FAJ Platform v6.6
# app/managers/prediction_manager.py
#
# Prediction Manager
# PostgreSQL version
# =====================================================
import logging
import ast
import numpy as np
from app.database import get_db
from app.core.faj_core import FAJCore

logger = logging.getLogger(__name__)

# =====================================================
# SAFE CLEAN
# =====================================================
def clean_value(value):
    """
    Убирает numpy типы
    """
    if isinstance(value, np.generic):
        return value.item()
    return value

def clean_prediction(data):
    """
    Рекурсивная очистка ответа модели
    """
    if data is None:
        return {}
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[key] = clean_prediction(value)
        return result
    if isinstance(data, list):
        return [
            clean_prediction(item)
            for item in data
        ]
    return clean_value(data)

# =====================================================
# NORMALIZE FAJ CORE RESPONSE v6.6
# =====================================================
def normalize_prediction(raw):
    raw = clean_prediction(raw)
    decision = raw.get(
        "decision",
        {}
    )
    simulation = raw.get(
        "simulation",
        {}
    )
    xg_block = raw.get(
        "xg",
        {}
    )
    xg = xg_block.get(
        "predicted",
        xg_block
    )
    return {
        # =========================
        # RESULT
        # =========================
        "winner":
            decision.get(
                "winner",
                "unknown"
            ),
        "winner_name":
            decision.get(
                "winner_name",
                ""
            ),
        "expected_score":
            decision.get(
                "expected_score",
                ""
            ),
        # =========================
        # PROBABILITIES
        # =========================
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
        "winner_probability":
            float(
                decision.get(
                    "winner_probability",
                    0
                )
            ),
        # =========================
        # xG
        # =========================
        "xg_home":
            float(
                xg.get(
                    "home",
                    0
                )
            ),
        "xg_away":
            float(
                xg.get(
                    "away",
                    0
                )
            ),
        # =========================
        # SCORES
        # =========================
        "top_scores":
            simulation.get(
                "top_scores",
                []
            ),
        # =========================
        # MARKETS
        # =========================
        "btts":
            float(
                raw.get(
                    "btts",
                    0
                )
            ),
        "over25":
            float(
                raw.get(
                    "over25",
                    0
                )
            ),
        "under25":
            float(
                raw.get(
                    "under25",
                    0
                )
            ),
        # =========================
        # FAJ META
        # =========================
        "confidence":
            float(
                decision.get(
                    "confidence",
                    raw.get(
                        "confidence",
                        0
                    )
                )
            ),
        "home_rating":
            float(
                raw.get(
                    "home_rating",
                    decision.get(
                        "home_rating",
                        0
                    )
                )
            ),
        "away_rating":
            float(
                raw.get(
                    "away_rating",
                    decision.get(
                        "away_rating",
                        0
                    )
                )
            ),
        "risk":
            raw.get(
                "risk",
                "Средний"
            ),
        "grade":
            raw.get(
                "grade",
                "C"
            )
    }

# =====================================================
# SAVE MODEL PREDICTION v6.6
# =====================================================
def save_prediction(
    fixture,
    prediction
):
    conn = get_db()
    try:
        cur = conn.cursor()
        top_scores = prediction.get(
            "top_scores",
            []
        )
        # PostgreSQL json-friendly
        if not isinstance(top_scores, str):
            top_scores = str(top_scores)
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
            winner_name,
            home_probability,
            draw_probability,
            away_probability,
            xg_home,
            xg_away,
            expected_score,
            top_scores,
            btts_probability,
            over25_probability,
            under25_probability,
            confidence,
            home_rating,
            away_rating,
            risk,
            grade,
            model_version,
            created
        )
        VALUES
        (
            %s,%s,%s,
            %s,%s,
            %s,%s,
            %s,%s,%s,
            %s,%s,
            %s,
            %s,
            %s,%s,%s,
            %s,
            %s,%s,
            %s,%s,
            %s,
            NOW()
        )
        ON CONFLICT(fixture_id)
        DO UPDATE SET
            winner_prediction = EXCLUDED.winner_prediction,
            winner_name = EXCLUDED.winner_name,
            home_probability = EXCLUDED.home_probability,
            draw_probability = EXCLUDED.draw_probability,
            away_probability = EXCLUDED.away_probability,
            xg_home = EXCLUDED.xg_home,
            xg_away = EXCLUDED.xg_away,
            expected_score = EXCLUDED.expected_score,
            top_scores = EXCLUDED.top_scores,
            btts_probability = EXCLUDED.btts_probability,
            over25_probability = EXCLUDED.over25_probability,
            under25_probability = EXCLUDED.under25_probability,
            confidence = EXCLUDED.confidence,
            home_rating = EXCLUDED.home_rating,
            away_rating = EXCLUDED.away_rating,
            risk = EXCLUDED.risk,
            grade = EXCLUDED.grade,
            model_version = EXCLUDED.model_version
        """,
        (
            # fixture
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
            # teams
            fixture.get(
                "home_team"
            ),
            fixture.get(
                "away_team"
            ),
            # result
            prediction.get(
                "winner",
                "unknown"
            ),
            prediction.get(
                "winner_name",
                ""
            ),
            # probabilities
            prediction.get(
                "home_probability",
                0
            ),
            prediction.get(
                "draw_probability",
                0
            ),
            prediction.get(
                "away_probability",
                0
            ),
            # xG
            prediction.get(
                "xg_home",
                0
            ),
            prediction.get(
                "xg_away",
                0
            ),
            # score
            prediction.get(
                "expected_score",
                ""
            ),
            top_scores,
            # markets
            prediction.get(
                "btts",
                0
            ),
            prediction.get(
                "over25",
                0
            ),
            prediction.get(
                "under25",
                0
            ),
            # confidence
            prediction.get(
                "confidence",
                0
            ),
            # ratings
            prediction.get(
                "home_rating",
                0
            ),
            prediction.get(
                "away_rating",
                0
            ),
            # risk
            prediction.get(
                "risk",
                "Средний"
            ),
            prediction.get(
                "grade",
                "C"
            ),
            # version
            FAJCore.VERSION
        )
        )
        conn.commit()
        logger.info(
            "Prediction saved: %s - %s",
            fixture.get(
                "home_team"
            ),
            fixture.get(
                "away_team"
            )
        )
    except Exception as e:
        conn.rollback()
        logger.error(
            "Prediction save error: %s",
            e,
            exc_info=True
        )
        raise
    finally:
        conn.close()

# =====================================================
# CREATE ONE PREDICTION v6.6
# =====================================================
def create_prediction(
    fixture,
    core=None
):
    if not fixture:
        raise ValueError(
            "Fixture пустой"
        )
    if core is None:
        core = FAJCore()
    home = fixture.get(
        "home_team"
    )
    away = fixture.get(
        "away_team"
    )
    league = fixture.get(
        "league",
        "RPL"
    )
    season = fixture.get(
        "season",
        "2026/27"
    )
    if not home or not away:
        raise ValueError(
            "Нет команд в fixture"
        )
    logger.info(
        "FAJ prediction start: %s - %s",
        home,
        away
    )
    # ==============================
    # CORE
    # ==============================
    raw_prediction = core.predict_match(
        home,
        away,
        league
    )
    if not raw_prediction:
        raise Exception(
            "FAJ Core вернул пустой результат"
        )
    # ==============================
    # NORMALIZE
    # ==============================
    prediction = normalize_prediction(
        raw_prediction
    )
    # ==============================
    # ADD META
    # ==============================
    decision = raw_prediction.get(
        "decision",
        {}
    )
    prediction["fixture_id"] = fixture.get(
        "id"
    )
    prediction["league"] = league
    prediction["season"] = season
    prediction["home_rating"] = raw_prediction.get(
        "home_rating",
        decision.get(
            "home_rating",
            0
        )
    )
    prediction["away_rating"] = raw_prediction.get(
        "away_rating",
        decision.get(
            "away_rating",
            0
        )
    )
    prediction["risk"] = (
        raw_prediction
        .get(
            "risk",
            "Средний"
        )
    )
    prediction["grade"] = (
        raw_prediction
        .get(
            "grade",
            "C"
        )
    )
    # ==============================
    # SAVE
    # ==============================
    save_prediction(
        fixture,
        prediction
    )
    logger.info(
        "FAJ prediction complete: %s - %s",
        home,
        away
    )
    return prediction

# =====================================================
# CREATE TOUR PREDICTIONS v6.6
# =====================================================
def create_tour_predictions(
    fixtures,
    core=None
):
    if not fixtures:
        return {
            "generated": 0,
            "errors": [
                "Нет fixtures"
            ]
        }
    generated = 0
    errors = []
    if core is None:
        core = FAJCore()
    logger.info(
        "FAJ tour generation started: %s matches",
        len(fixtures)
    )
    for fixture in fixtures:
        try:
            prediction = create_prediction(
                fixture,
                core
            )
            if prediction:
                generated += 1
        except Exception as e:
            match_name = (
                f"{fixture.get('home_team')}"
                " - "
                f"{fixture.get('away_team')}"
            )
            logger.error(
                "Tour prediction failed %s: %s",
                match_name,
                e,
                exc_info=True
            )
            errors.append(
                {
                    "match": match_name,
                    "error": str(e)
                }
            )
    logger.info(
        "FAJ tour finished. Generated=%s Errors=%s",
        generated,
        len(errors)
    )
    return {
        "generated": generated,
        "errors": errors
    }

# =====================================================
# GET PREDICTIONS v6.6
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
            params.append(
                league
            )
        if season:
            query += """
            AND season=%s
            """
            params.append(
                season
            )
        query += """
        ORDER BY created DESC
        """
        cur.execute(
            query,
            tuple(params)
        )
        rows = cur.fetchall()
        predictions = []
        for row in rows:
            item = dict(row)
            # =====================================
            # TOP SCORES SAFE LOAD
            # =====================================
            raw_scores = item.get(
                "top_scores",
                "[]"
            )
            if isinstance(
                raw_scores,
                list
            ):
                item["top_scores"] = raw_scores
            else:
                try:
                    item["top_scores"] = ast.literal_eval(
                        raw_scores
                    )
                except Exception:
                    item["top_scores"] = []
            # =====================================
            # COMPATIBILITY OLD RECORDS
            # =====================================
            defaults = {
                "winner_name":
                    item.get(
                        "winner_prediction",
                        "Нет данных"
                    ),
                "home_probability":
                    0,
                "draw_probability":
                    0,
                "away_probability":
                    0,
                "xg_home":
                    0,
                "xg_away":
                    0,
                "expected_score":
                    "",
                "confidence":
                    0,
                "home_rating":
                    0,
                "away_rating":
                    0,
                "risk":
                    "Средний",
                "grade":
                    "C"
            }
            for key, value in defaults.items():
                if item.get(key) is None:
                    item[key] = value
            predictions.append(
                item
            )
        logger.info(
            "FAJ predictions loaded: %s",
            len(predictions)
        )
        return predictions
    except Exception as e:
        logger.error(
            "Prediction loading error: %s",
            e,
            exc_info=True
        )
        return []
    finally:
        conn.close()

# =====================================================
# FAJ Platform v6.1
# Prediction Manager
# =====================================================
from datetime import datetime
import ast
import numpy as np
from app.database import get_db
from app.core.faj_core import FAJCore

# =====================================================
# NUMPY → PYTHON
# =====================================================
def clean_value(value):
    if isinstance(value, np.generic):
        return value.item()
    return value

def clean_prediction(prediction):
    if prediction is None:
        return {}
    cleaned = {}
    for key, value in prediction.items():
        if isinstance(value, dict):
            cleaned[key] = clean_prediction(value)
        elif isinstance(value, list):
            cleaned[key] = [
                clean_prediction(v) if isinstance(v, dict)
                else clean_value(v)
                for v in value
            ]
        else:
            cleaned[key] = clean_value(value)
    return cleaned

# =====================================================
# NORMALIZE FAJ CORE RESPONSE
# =====================================================
def normalize_prediction(raw_prediction):
    raw_prediction = clean_prediction(raw_prediction)
    decision = raw_prediction.get("decision", {})
    predicted_xg = (
        raw_prediction
        .get("xg", {})
        .get("predicted", {})
    )
    return {
        "winner":
            decision.get("winner"),
        "winner_name":
            decision.get("winner_name"),
        "home_probability":
            float(decision.get("home_prob", 0)),
        "draw_probability":
            float(decision.get("draw_prob", 0)),
        "away_probability":
            float(decision.get("away_prob", 0)),
        "winner_probability":
            float(decision.get("winner_probability", 0)),
        "xg_home":
            float(predicted_xg.get("home", 0)),
        "xg_away":
            float(predicted_xg.get("away", 0)),
        "expected_score":
            decision.get("expected_score"),
        "top_scores":
            raw_prediction.get("simulation", {}).get(
                "top_scores",
                []
            ),
        "btts":
            float(raw_prediction.get("btts", 0)),
        "over25":
            float(raw_prediction.get("over25", 0)),
        "confidence":
            float(decision.get("confidence", 0))
    }

# =====================================================
# SAVE PREDICTION
# =====================================================
def save_prediction(
    fixture,
    prediction
):
    prediction = clean_prediction(
        prediction
    )
    conn = get_db()
    try:
        conn.execute(
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
            created
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            fixture.get("id"),
            fixture.get("league"),
            fixture.get("season"),
            fixture.get("round"),
            fixture.get("home_team"),
            fixture.get("away_team"),
            prediction.get("winner"),
            prediction.get("home_probability"),
            prediction.get("draw_probability"),
            prediction.get("away_probability"),
            prediction.get("xg_home"),
            prediction.get("xg_away"),
            prediction.get("expected_score"),
            str(
                prediction.get(
                    "top_scores",
                    []
                )
            ),
            prediction.get("btts"),
            prediction.get("over25"),
            prediction.get("confidence"),
            FAJCore.VERSION,
            datetime.now().isoformat()
        )
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# =====================================================
# CREATE SINGLE PREDICTION
# =====================================================
def create_prediction(
    fixture,
    core=None
):
    if core is None:
        core = FAJCore()
    home_team = fixture.get(
        "home_team"
    )
    away_team = fixture.get(
        "away_team"
    )
    # -----------------------------------------
    # Поддержка всех версий FAJCore
    # -----------------------------------------
    if hasattr(core, "predict"):
        raw_prediction = core.predict(
            home_team,
            away_team,
            fixture.get(
                "league",
                "RPL"
            )
        )
    else:
        raw_prediction = core.predict_match(
            home_team,
            away_team,
            fixture.get(
                "league",
                "RPL"
            )
        )
    # -----------------------------------------
    if raw_prediction.get("error"):
        raise Exception(
            raw_prediction["error"]
        )
    prediction = normalize_prediction(
        raw_prediction
    )
    save_prediction(
        fixture,
        prediction
    )
    return prediction

# =====================================================
# CREATE TOUR PREDICTIONS
# =====================================================
def create_tour_predictions(
    fixtures,
    core=None
):
    if core is None:
        core = FAJCore()
    generated = 0
    errors = []
    for fixture in fixtures:
        try:
            create_prediction(
                fixture,
                core
            )
            generated += 1
        except Exception as e:
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
        "league": "RPL",
        "season": "2026/27"
    }

# =====================================================
# GET PREDICTIONS
# =====================================================
def get_predictions(
    league=None,
    season=None,
    round_number=None
):
    conn = get_db()
    try:
        query = """
        SELECT
            p.*,
            f.match_date
        FROM predictions p
        LEFT JOIN fixtures f
            ON p.fixture_id = f.id
        WHERE 1=1
        """
        params = []
        if league:
            query += """
            AND p.league = ?
            """
            params.append(
                league
            )
        if season:
            query += """
            AND p.season = ?
            """
            params.append(
                season
            )
        if round_number:
            query += """
            AND p.round = ?
            """
            params.append(
                round_number
            )
        query += """
        ORDER BY
            p.round ASC,
            f.match_date ASC,
            p.fixture_id ASC
        """
        rows = conn.execute(
            query,
            tuple(params)
        ).fetchall()
        predictions = []
        for row in rows:
            item = dict(row)
            # превращаем строку обратно в список
            try:
                if item.get("top_scores"):
                    item["top_scores"] = ast.literal_eval(
                        item["top_scores"]
                    )
            except Exception:
                item["top_scores"] = []
            predictions.append(item)
        return predictions
    finally:
        conn.close()

# =====================================================
# COUNT
# =====================================================
def count_predictions():
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM predictions
            """
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()

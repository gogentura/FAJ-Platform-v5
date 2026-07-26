# =====================================================
# FAJ Platform v6.6
# app/managers/prediction_manager.py
# PostgreSQL Edition
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

def clean_prediction(data):
    if data is None:
        return {}
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(v, dict):
                result[k] = clean_prediction(v)
            elif isinstance(v, list):
                result[k] = [
                    clean_prediction(i)
                    if isinstance(i, dict)
                    else clean_value(i)
                    for i in v
                ]
            else:
                result[k] = clean_value(v)
        return result
    return data

# =====================================================
# NORMALIZE FAJ RESPONSE
# =====================================================
def normalize_prediction(raw):
    raw = clean_prediction(raw)
    decision = raw.get("decision", {})
    predicted = (
        raw
        .get("xg", {})
        .get("predicted", {})
    )
    simulation = raw.get(
        "simulation",
        {}
    )
    return {
        "winner":
            decision.get("winner"),
        "winner_name":
            decision.get("winner_name"),
        "home_probability":
            float(
                decision.get(
                    "home_probability",
                    decision.get("home_prob", 0)
                )
            ),
        "draw_probability":
            float(
                decision.get(
                    "draw_probability",
                    decision.get("draw_prob", 0)
                )
            ),
        "away_probability":
            float(
                decision.get(
                    "away_probability",
                    decision.get("away_prob", 0)
                )
            ),
        "winner_probability":
            float(
                decision.get(
                    "winner_probability",
                    0
                )
            ),
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
        "expected_score":
            decision.get(
                "expected_score",
                ""
            ),
        "top_scores":
            simulation.get(
                "top_scores",
                []
            ),
        "btts":
            raw.get(
                "btts",
                0
            ),
        "over25":
            raw.get(
                "over25",
                0
            ),
        "under25":
            raw.get(
                "under25",
                0
            ),
        "confidence":
            float(
                decision.get(
                    "confidence",
                    0
                )
            )
    }

# =====================================================
# SAVE PREDICTION
# =====================================================
def save_prediction(fixture, prediction):
    prediction = clean_prediction(
        prediction
    )
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
            created
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
            %s,
            %s,
            %s,
            %s,
            NOW()
        )
        ON CONFLICT (fixture_id)
        DO UPDATE SET
            winner_prediction=EXCLUDED.winner_prediction,
            home_probability=EXCLUDED.home_probability,
            draw_probability=EXCLUDED.draw_probability,
            away_probability=EXCLUDED.away_probability,
            xg_home=EXCLUDED.xg_home,
            xg_away=EXCLUDED.xg_away,
            expected_score=EXCLUDED.expected_score,
            top_scores=EXCLUDED.top_scores,
            btts_probability=EXCLUDED.btts_probability,
            over25_probability=EXCLUDED.over25_probability,
            confidence=EXCLUDED.confidence,
            model_version=EXCLUDED.model_version
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
            FAJCore.VERSION
        )
    )
    conn.commit()
    cur.close()
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
    home = fixture.get("home_team")
    away = fixture.get("away_team")
    league = fixture.get("league", "RPL")

    if hasattr(core, "predict"):
        raw = core.predict(
            home,
            away,
            league
        )
    else:
        raw = core.predict_match(
            home,
            away,
            league
        )

    if raw is None:
        return None

    prediction = normalize_prediction(raw)
    save_prediction(
        fixture,
        prediction
    )
    return prediction

# =====================================================
# CREATE TOUR
# =====================================================
def create_tour_predictions(
    fixtures,
    core=None
):
    if core is None:
        core = FAJCore()
    created = 0
    errors = []
    for fixture in fixtures:
        try:
            create_prediction(
                fixture,
                core
            )
            created += 1
        except Exception as e:
            errors.append(
                {
                    "match":
                        f"{fixture.get('home_team')} — {fixture.get('away_team')}",
                    "error":
                        str(e)
                }
            )
    return {
        "generated": created,
        "errors": errors
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
    cur = conn.cursor()
    query = """
        SELECT
            p.*,
            f.match_date
        FROM predictions p
        LEFT JOIN fixtures f
            ON p.fixture_id = f.id
        WHERE TRUE
    """
    params = []
    if league:
        query += " AND p.league = %s"
        params.append(league)
    if season:
        query += " AND p.season = %s"
        params.append(season)
    if round_number:
        query += " AND p.round = %s"
        params.append(round_number)
    query += """
        ORDER BY
            f.match_date,
            p.fixture_id
    """
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    predictions = []
    for row in rows:
        item = dict(row)
        try:
            if item.get("top_scores"):
                item["top_scores"] = ast.literal_eval(
                    item["top_scores"]
                )
        except Exception:
            item["top_scores"] = []
        predictions.append(item)
    cur.close()
    conn.close()
    return predictions

# =====================================================
# GET BY FIXTURE
# =====================================================
def get_prediction_by_fixture(fixture_id):
    conn = get_db()
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
    cur.close()
    conn.close()
    if row:
        item = dict(row)
        try:
            if item.get("top_scores"):
                item["top_scores"] = ast.literal_eval(
                    item["top_scores"]
                )
        except Exception:
            item["top_scores"] = []
        return item
    return None

# =====================================================
# COUNT
# =====================================================
def count_predictions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM predictions
        """
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row["cnt"]
    return 0

# =====================================================
# DELETE ALL
# =====================================================
def clear_predictions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM predictions"
    )
    conn.commit()
    cur.close()
    conn.close()

# =====================================================
# VERSION
# =====================================================
def manager_version():
    return "PredictionManager v6.6 PostgreSQL"

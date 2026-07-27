# =====================================================
# FAJ Platform v6.9.2
# app/services/tour_predictor.py
#
# Tournament Predictor Service
#
# Pipeline:
#
# fixtures
#    ↓
# prediction_pipeline
#    ↓
# prediction_manager
#    ↓
# PostgreSQL
#
# Compatible:
# FAJCore v6.8+
# prediction_pipeline v6.9.2
# prediction_manager v6.9.2
# =====================================================
import logging
from app.database import get_db
from app.services.prediction_pipeline import (
    predict_match_pipeline
)
from app.managers.prediction_manager import (
    save_prediction
)

logger = logging.getLogger(__name__)

# =====================================================
# LOAD FIXTURES
# =====================================================
def get_tour_fixtures(
    league="RPL",
    season="2026/27"
):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
        """
        SELECT *
        FROM fixtures
        WHERE league=%s
        AND season=%s
        AND status='scheduled'
        ORDER BY match_date, match_time
        """,
        (
            league,
            season
        )
        )
        rows = cur.fetchall()
        fixtures = []
        for row in rows:
            fixtures.append(
                dict(row)
            )
        logger.info(
            "FAJ fixtures loaded: %s",
            len(fixtures)
        )
        return fixtures
    except Exception as e:
        logger.error(
            "Fixture loading error: %s",
            e,
            exc_info=True
        )
        return []
    finally:
        conn.close()

# =====================================================
# NORMALIZE TOUR OUTPUT
# =====================================================
def enrich_prediction(
    prediction,
    fixture
):
    if not prediction:
        return None
    prediction["fixture_id"] = fixture.get(
        "id"
    )
    prediction["home_team"] = fixture.get(
        "home_team"
    )
    prediction["away_team"] = fixture.get(
        "away_team"
    )
    prediction["league"] = fixture.get(
        "league",
        "RPL"
    )
    prediction["season"] = fixture.get(
        "season",
        "2026/27"
    )
    prediction["round"] = fixture.get(
        "round"
    )
    prediction["match_date"] = fixture.get(
        "match_date"
    )
    prediction["match_time"] = fixture.get(
        "match_time"
    )
    return prediction

# =====================================================
# SINGLE FIXTURE PREDICTION
# =====================================================
def predict_fixture(
    fixture,
    core=None
):
    try:
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
        if not home or not away:
            logger.warning(
                "Invalid fixture %s",
                fixture
            )
            return None
        prediction = predict_match_pipeline(
            home_team=home,
            away_team=away,
            league=league,
            core=core
        )
        if not prediction:
            logger.warning(
                "Empty prediction %s - %s",
                home,
                away
            )
            return None
        return enrich_prediction(
            prediction,
            fixture
        )
    except Exception as e:
        logger.error(
            "Prediction fixture error %s - %s : %s",
            fixture.get(
                "home_team"
            ),
            fixture.get(
                "away_team"
            ),
            e,
            exc_info=True
        )
        return None

# =====================================================
# TOUR GENERATION
# =====================================================
def predict_tour(
    league="RPL",
    season="2026/27",
    core=None
):
    fixtures = get_tour_fixtures(
        league,
        season
    )
    if not fixtures:
        logger.warning(
            "No scheduled fixtures found"
        )
        return []
    results = []
    logger.info(
        "FAJ tour prediction started: %s matches",
        len(fixtures)
    )
    for fixture in fixtures:
        try:
            prediction = predict_fixture(
                fixture,
                core
            )
            if not prediction:
                logger.warning(
                    "Skip fixture: %s - %s",
                    fixture.get(
                        "home_team"
                    ),
                    fixture.get(
                        "away_team"
                    )
                )
                continue
            try:
                save_prediction(
                    fixture,
                    prediction
                )
            except Exception as e:
                logger.error(
                    "Prediction save failed: %s",
                    e,
                    exc_info=True
                )
            results.append(
                prediction
            )
        except Exception as e:
            logger.error(
                "Tour match error: %s",
                e,
                exc_info=True
            )
    logger.info(
        "FAJ tour completed: %s predictions",
        len(results)
    )
    return results

# =====================================================
# TELEGRAM REPORT DATA
# =====================================================
def generate_tour_report(
    league="RPL",
    season="2026/27",
    core=None
):
    predictions = predict_tour(
        league,
        season,
        core
    )
    report = []
    for prediction in predictions:
        report.append(
            {
                "home_team":
                    prediction.get(
                        "home_team",
                        "-"
                    ),
                "away_team":
                    prediction.get(
                        "away_team",
                        "-"
                    ),
                "winner":
                    prediction.get(
                        "winner",
                        "-"
                    ),
                "winner_name":
                    prediction.get(
                        "winner_name",
                        "-"
                    ),
                "score":
                    prediction.get(
                        "expected_score",
                        "-"
                    ),
                "xg":
                    {
                        "home":
                            prediction.get(
                                "xg_home",
                                0
                            ),
                        "away":
                            prediction.get(
                                "xg_away",
                                0
                            )
                    },
                "rating":
                    {
                        "home":
                            prediction.get(
                                "home_rating",
                                0
                            ),
                        "away":
                            prediction.get(
                                "away_rating",
                                0
                            )
                    },
                "confidence":
                    prediction.get(
                        "confidence",
                        0
                    ),
                "risk":
                    prediction.get(
                        "risk",
                        "Высокий"
                    ),
                "grade":
                    prediction.get(
                        "grade",
                        "C"
                    ),
                "factors":
                    prediction.get(
                        "factors",
                        []
                    ),
                "season_phase":
                    prediction.get(
                        "season_phase",
                        "start"
                    ),
                "passport_quality":
                    prediction.get(
                        "passport_quality",
                        {
                            "home":0,
                            "away":0
                        }
                    )
            }
        )
    return report

# =====================================================
# COMPATIBILITY ALIAS
# =====================================================
def generate_tour_predictions(
    league="RPL",
    season="2026/27",
    core=None
):
    return predict_tour(
        league,
        season,
        core
    )

# =====================================================
# EXPORTS
# =====================================================
__all__ = [
    "get_tour_fixtures",
    "predict_fixture",
    "predict_tour",
    "generate_tour_report",
    "generate_tour_predictions"
]

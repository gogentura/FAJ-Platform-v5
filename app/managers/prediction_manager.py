# =====================================================
# SAVE SINGLE PREDICTION
# =====================================================
def save_prediction(
    fixture,
    prediction
):
    try:
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
    %s,%s,%s,%s,%s,%s,%s,%s,%s
)
""",
(
    fixture.get("id"),
    prediction.get("home_probability", 0) / 100,
    prediction.get("draw_probability", 0) / 100,
    prediction.get("away_probability", 0) / 100,
    prediction.get("xg_home", 0),
    prediction.get("xg_away", 0),
    prediction.get("expected_score", "-"),
    prediction.get("confidence", 0),
    FAJCore.VERSION
)
)

        conn.commit()
        conn.close()

        logger.info(
            "FAJ Prediction saved: %s - %s | fixture=%s",
            fixture.get("home_team"),
            fixture.get("away_team"),
            fixture.get("id")
        )
        return True

    except Exception as e:
        logger.error(
            "Prediction save error: %s",
            e,
            exc_info=True
        )
        return False

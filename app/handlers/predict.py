# =====================================================
# FAJ Platform v6.4.1
# app/handlers/predict.py
#
# Main Match Prediction Handler (использует pipeline)
# =====================================================

import traceback
import logging
from aiogram import types

from app.services.prediction_pipeline import predict_match_pipeline
from app.utils.formatter import format_prediction
from app.utils.explainer import explain_prediction
from app.handlers.keyboard import get_main_keyboard

logger = logging.getLogger(__name__)

# =====================================================
# SAFE FLOAT
# =====================================================
def safe_float(value, default=0):
    try:
        if isinstance(value, dict):
            return default
        return float(value)
    except Exception:
        return default

# =====================================================
# PARSE MATCH
# =====================================================
def parse_match(text):
    text = text.strip()
    if text.lower().startswith("прогноз"):
        text = text[8:].strip()
    parts = text.split()
    if len(parts) < 2:
        return None, None
    home = parts[0]
    away = " ".join(parts[1:])
    return home, away

# =====================================================
# HANDLE PREDICT
# =====================================================
async def handle_predict(
    message: types.Message,
    core,
    journal
):
    text = (message.text or "").strip()
    home, away = parse_match(text)
    if not home or not away:
        return

    league = "RPL"

    await message.answer(
        f"⏳ Анализирую матч\n\n⚽ {home} — {away}",
        reply_markup=get_main_keyboard()
    )

    try:
        # ----------------------------------------------
        # PIPELINE (единая точка входа)
        # ----------------------------------------------
        prediction = predict_match_pipeline(home, away, league)

        if not prediction:
            raise Exception("Prediction pipeline вернул None")

        # ----------------------------------------------
        # ИЗВЛЕКАЕМ ДАННЫЕ
        # ----------------------------------------------
        xg_home = prediction.get("xg_home", 0)
        xg_away = prediction.get("xg_away", 0)
        faj_rating = {
            home: prediction.get("home_rating", 0),
            away: prediction.get("away_rating", 0)
        }
        confidence = prediction.get("confidence", 0)
        risk_level = prediction.get("risk", "Средний")

        # Для formatter нужны паспорта (объяснение факторов)
        # Просто передадим пустые, если не используем explainer
        home_pass = {}
        away_pass = {}
        factors = explain_prediction(
            home_pass,
            away_pass,
            xg_home,
            xg_away,
            league
        )

        # ----------------------------------------------
        # ФОРМАТИРУЕМ ОТВЕТ
        # ----------------------------------------------
        answer = format_prediction(
            home,
            away,
            league,
            {"home": xg_home, "away": xg_away},
            prediction,  # prediction содержит все decision-поля
            prediction.get("top_scores", []),
            prediction.get("btts", 0),
            prediction.get("over25", 0),
            factors,
            faj_rating,
            risk_level,
            confidence
        )

        # ----------------------------------------------
        # СОХРАНЯЕМ В ЖУРНАЛ
        # ----------------------------------------------
        journal_data = {
            "home_team": home,
            "away_team": away,
            "league": league,
            "winner": prediction.get("winner", ""),
            "winner_probability": prediction.get("winner_probability", 0),
            "home_probability": prediction.get("home_probability", 0),
            "draw_probability": prediction.get("draw_probability", 0),
            "away_probability": prediction.get("away_probability", 0),
            "xg_home": xg_home,
            "xg_away": xg_away,
            "expected_score": prediction.get("expected_score", ""),
            "top_scores": prediction.get("top_scores", []),
            "btts": prediction.get("btts", 0),
            "over25": prediction.get("over25", 0),
            "home_rating": prediction.get("home_rating", 0),
            "away_rating": prediction.get("away_rating", 0),
            "confidence": confidence,
            "risk": risk_level,
            "grade": prediction.get("grade", "C"),
            "grade_name": prediction.get("grade_name", "")
        }

        journal.save(
            match=f"{home} — {away}",
            fixture_id=prediction.get("fixture_id"),
            prediction=journal_data
        )

        await message.answer(
            answer,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        logger.error(traceback.format_exc())
        await message.answer(
            f"❌ Ошибка модели\n\nТип:\n{type(e).__name__}\n\nОшибка:\n{str(e)}",
            reply_markup=get_main_keyboard()
        )

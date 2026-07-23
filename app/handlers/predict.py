import logging
import traceback

from aiogram import types

from app.utils.formatter import format_prediction
from app.utils.explainer import explain_prediction
from app.database import get_db
from app.handlers.keyboard import get_main_keyboard

logger = logging.getLogger(__name__)


def load_passport(team):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM passports WHERE team = ?",
        (team,)
    ).fetchone()
    conn.close()

    return dict(row) if row else None


async def handle_predict(message: types.Message, core, journal):

    try:

        text = (message.text or "").strip()

        # поддержка команды:
        # Прогноз Зенит Спартак
        if text.lower().startswith("прогноз "):
            text = text[9:].strip()

        parts = text.split()

        if len(parts) < 2:
            await message.answer(
                "❌ Напиши две команды.\n\n"
                "Например:\n"
                "Зенит Спартак\n\n"
                "или\n"
                "Прогноз Зенит Спартак",
                reply_markup=get_main_keyboard()
            )
            return

        home = parts[0]
        away = parts[1]

        league = "RPL"

        if len(parts) >= 3:
            if parts[2].upper() in ["RPL", "UCL", "EPL"]:
                league = parts[2].upper()

        await message.answer(
            f"⏳ Анализирую матч\n\n"
            f"{home} — {away}",
            reply_markup=get_main_keyboard()
        )

        result = core.predict_match(
            home,
            away,
            league
        )

        home_pass = load_passport(home) or {}
        away_pass = load_passport(away) or {}

        factors = explain_prediction(
            home_pass,
            away_pass,
            result["xg"]["predicted"]["home"],
            result["xg"]["predicted"]["away"],
            league
        )

        text = format_prediction(
            home,
            away,
            league,
            result["xg"]["predicted"],
            result["decision"],
            result["top_scores"],
            result["btts"],
            result["over25"],
            factors
        )

        journal.save(
            match=f"{home} — {away}",
            prediction={
                "winner": result["decision"]["winner_name"],
                "winner_probability": result["decision"]["winner_probability"],
                "xg_home": result["xg"]["predicted"]["home"],
                "xg_away": result["xg"]["predicted"]["away"],
                "expected_score": result["decision"]["expected_score"],
                "confidence": result["decision"]["confidence"]
            }
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

    except Exception:

        error = traceback.format_exc()

        logger.error(error)

        await message.answer(
            "❌ Ошибка модели FAJ\n\n"
            f"<pre>{error[:3500]}</pre>",
            parse_mode="HTML"
        )

# =====================================================
# FAJ Platform v6.3
# app/debug_prediction.py
#
# Prediction Debug Handler
# =====================================================

import traceback
import logging

from aiogram import types

from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


logger = logging.getLogger(__name__)


# =====================================================
# TEAM PASSPORT DEBUG
# =====================================================

def debug_passport(team):

    real_team = get_team_by_alias(team)

    if real_team:
        team = real_team


    passport = load_passport(team)


    if not passport:
        return {
            "team": team,
            "status": "NOT FOUND"
        }


    return {
        "team": passport.get("team"),
        "league": passport.get("league"),
        "season": passport.get("season"),

        "attack": passport.get("attack"),
        "defense": passport.get("defense"),
        "control": passport.get("control"),

        "form": passport.get(
            "form",
            passport.get(
                "form_index",
                0
            )
        ),

        "xg_for": passport.get(
            "xg_for",
            passport.get(
                "historical_xg_value",
                0
            )
        ),

        "xg_against": passport.get(
            "xg_against",
            0
        )
    }



# =====================================================
# DEBUG COMMAND
# =====================================================

async def cmd_debug_prediction(
    message: types.Message,
    core
):

    try:

        text = (
            message.text
            .replace(
                "/debug_prediction",
                ""
            )
            .strip()
        )


        parts = text.split()


        if len(parts) < 2:

            await message.answer(
                """
🧪 Debug Prediction

Пример:

/debug_prediction Акрон Зенит
"""
            )

            return



        home = parts[0]

        away = " ".join(parts[1:])



        await message.answer(
            f"""
🧪 FAJ Debug

Матч:

⚽ {home} — {away}

Проверяю:
• паспорта
• FAJ Core
• xG
• decision
• simulation
"""
        )



        # ==============================
        # PASSPORTS
        # ==============================


        home_pass = debug_passport(
            home
        )

        away_pass = debug_passport(
            away
        )



        # ==============================
        # CORE
        # ==============================


        result = core.predict_match(

            home,

            away,

            "RPL"

        )



        if not result:

            await message.answer(
                "❌ FAJ Core вернул пустой результат"
            )

            return



        # ==============================
        # OUTPUT
        # ==============================


        answer = f"""
✅ DEBUG OK


🏠 {home_pass}

🚩 {away_pass}


🧠 CORE:

Ключи результата:

{list(result.keys())}


📊 xG:

{result.get('xg')}


📈 Decision:

{result.get('decision')}


🎯 Simulation:

{result.get('simulation')}
"""


        await message.answer(
            answer
        )



    except Exception as e:


        logger.error(
            traceback.format_exc()
        )


        await message.answer(

            "❌ DEBUG ERROR\n\n"

            f"{type(e).__name__}\n\n"

            f"{str(e)}"

        )

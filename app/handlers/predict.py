# =====================================================
# FAJ Platform v6.3
# app/handlers/predict.py
#
# Prediction Handler
# =====================================================


import traceback
import logging

from aiogram import types

from app.database import get_db
from app.passport_manager import get_team_by_alias

from app.utils.formatter import format_prediction
from app.utils.explainer import explain_prediction

from app.handlers.keyboard import get_main_keyboard


logger = logging.getLogger(__name__)


# =====================================================
# LOAD PASSPORT
# =====================================================


def load_passport(team):

    real_team = get_team_by_alias(team)


    conn = get_db()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT *
        FROM team_passports
        WHERE team=%s
        LIMIT 1
        """,
        (
            real_team,
        )
    )


    row = cur.fetchone()


    conn.close()


    if row:

        return dict(row)


    return None



# =====================================================
# MENU IGNORE
# =====================================================


IGNORE_BUTTONS = [

    "📈 Прогноз",

    "📋 Последние прогнозы",

    "⚽ Статус",

    "📁 Паспорта",

    "🔄 Загрузить паспорта",

    "Загрузить паспорта",

    "Загрузить",

    "паспорта",

    "🔄 Синхронизировать календарь",

    "📅 Матчи",

    "⚙️ Админ",

    "/start"

]



# =====================================================
# HANDLER
# =====================================================


async def handle_predict(

    message: types.Message,

    core,

    journal

):


    text = (
        message.text or ""
    ).strip()



    # -----------------------------------------
    # IGNORE BUTTONS
    # -----------------------------------------

    if text in IGNORE_BUTTONS:

        return



    lower = text.lower()



    if lower in [

        "загрузить",

        "паспорта",

        "календарь",

        "статус",

        "админ"

    ]:

        return



    # -----------------------------------------
    # PREFIX
    # -----------------------------------------

    if lower.startswith(
        "прогноз "
    ):

        text = text[9:].strip()



    parts = text.split()



    if len(parts) < 2:

        return



    home_team = parts[0]

    away_team = parts[1]


    league = "RPL"



    if len(parts) >= 3:

        possible_league = parts[2].upper()

        if possible_league in [

            "RPL",

            "EPL",

            "UCL",

            "LALIGA",

            "SERIEA",

            "BUNDESLIGA",

            "LIGUE1"

        ]:

            league = possible_league



    await message.answer(

        f"""
⏳ FAJ анализирует матч

⚽ {home_team} — {away_team}

🧠 Модель v6.3
""",

        reply_markup=get_main_keyboard()

    )



    try:



        # -------------------------------------
        # CORE
        # -------------------------------------


        result = core.predict_match(

            home_team,

            away_team,

            league

        )



        if not result:

            raise Exception(
                "FAJ Core вернул пустой ответ"
            )



        if "xg" not in result:

            raise Exception(
                "FAJ Core не вернул xG"
            )



        # -------------------------------------
        # XG
        # -------------------------------------


        predicted_xg = result["xg"].get(

            "predicted",

            {}

        )


        xg_home = float(

            predicted_xg.get(

                "home",

                0

            )

        )


        xg_away = float(

            predicted_xg.get(

                "away",

                0

            )

        )



        # -------------------------------------
        # PASSPORTS
        # -------------------------------------


        home_pass = load_passport(
            home_team
        ) or {}


        away_pass = load_passport(
            away_team
        ) or {}



        factors = explain_prediction(

            home_pass,

            away_pass,

            xg_home,

            xg_away,

            league

        )



        # -------------------------------------
        # FORMAT
        # -------------------------------------


        decision = result.get(

            "decision",

            {}

        )


        answer = format_prediction(

            home_team,

            away_team,

            league,

            {

                "home": xg_home,

                "away": xg_away

            },

            decision,

            result.get(

                "top_scores",

                []

            ),

            result.get(

                "btts",

                decision.get(
                    "btts",
                    0
                )

            ),

            result.get(

                "over25",

                decision.get(
                    "over25",
                    0
                )

            ),

            factors

        )



        # -------------------------------------
        # JOURNAL
        # -------------------------------------


        if journal:


            journal.save(

                match=f"{home_team} — {away_team}",


                prediction={

                    "winner":

                        decision.get(
                            "winner_name",
                            ""
                        ),


                    "winner_probability":

                        float(

                            decision.get(
                                "winner_probability",
                                0
                            )

                        ),


                    "xg_home":

                        xg_home,


                    "xg_away":

                        xg_away,


                    "expected_score":

                        decision.get(
                            "expected_score",
                            ""
                        ),


                    "confidence":

                        float(

                            decision.get(
                                "confidence",
                                0
                            )

                        )

                }

            )



        await message.answer(

            answer,

            parse_mode="Markdown",

            reply_markup=get_main_keyboard()

        )



    except Exception as e:


        logger.error(
            traceback.format_exc()
        )


        await message.answer(

            f"""
❌ Ошибка модели


Тип:

{type(e).__name__}


Ошибка:

{str(e)}
""",

            reply_markup=get_main_keyboard()

        )

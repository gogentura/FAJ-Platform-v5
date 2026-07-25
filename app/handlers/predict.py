# =====================================================
# FAJ Platform v6.3
# app/handlers/predict.py
#
# Prediction Handler
# PostgreSQL + FAJ Core v6.3
# =====================================================


import traceback

from aiogram import types


from app.utils.formatter import format_prediction
from app.utils.explainer import explain_prediction

from app.passport_manager import load_passport

from app.handlers.keyboard import get_main_keyboard



# =====================================================
# LOAD PASSPORT
# =====================================================

def get_passport(team):

    try:

        passport = load_passport(team)

        return passport or {}

    except Exception:

        return {}



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



    # =================================================
    # IGNORE BUTTONS
    # =================================================

    ignore_buttons = [

        "📈 Прогноз",

        "📋 Последние прогнозы",

        "⚽ Статус",

        "📁 Паспорта",

        "🔄 Загрузить паспорта",

        "/start"

    ]


    if text in ignore_buttons:

        return



    # =================================================
    # PREFIX
    # =================================================

    if text.lower().startswith(
        "прогноз "
    ):

        text = text[8:].strip()



    parts = text.split()



    if len(parts) < 2:

        return



    home = parts[0]

    away = parts[1]


    league = "RPL"



    if len(parts) >= 3:

        possible_league = (
            parts[2]
            .upper()
        )


        allowed = [

            "RPL",

            "EPL",

            "UCL",

            "LALIGA",

            "SERIEA",

            "BUNDESLIGA",

            "LIGUE1"

        ]


        if possible_league in allowed:

            league = possible_league



    await message.answer(

        f"⏳ Анализирую матч\n\n"
        f"⚽ {home} — {away}",

        reply_markup=get_main_keyboard()

    )



    try:



        # =================================================
        # CORE
        # =================================================


        result = core.predict_match(

            home,

            away,

            league

        )



        if not result:

            raise Exception(

                "FAJ Core вернул пустой ответ"

            )



        if "error" in result:

            raise Exception(

                result["error"]

            )



        # =================================================
        # XG
        # =================================================


        predicted_xg = (

            result

            .get(
                "xg",
                {}
            )

            .get(
                "predicted",
                {}
            )

        )



        if not predicted_xg:

            raise Exception(

                "FAJ Core не вернул xG"

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



        # =================================================
        # SIMULATION
        # =================================================


        simulation = result.get(

            "simulation",

            {}

        )



        top_scores = simulation.get(

            "top_scores",

            []

        )



        # =================================================
        # DECISION
        # =================================================


        decision = result.get(

            "decision",

            {}

        )



        btts = decision.get(

            "btts",

            0

        )



        over25 = decision.get(

            "over25",

            0

        )



        # =================================================
        # PASSPORTS
        # =================================================


        home_passport = get_passport(

            home

        )


        away_passport = get_passport(

            away

        )



        factors = explain_prediction(

            home_passport,

            away_passport,

            xg_home,

            xg_away,

            league

        )



        # =================================================
        # FORMAT
        # =================================================


        answer = format_prediction(

            home,

            away,

            league,


            {

                "home":

                    xg_home,


                "away":

                    xg_away

            },


            decision,


            top_scores,


            btts,


            over25,


            factors

        )



        # =================================================
        # JOURNAL
        # =================================================


        journal_prediction = {


            **decision,


            "xg_home":

                xg_home,


            "xg_away":

                xg_away,


            "top_scores":

                top_scores

        }



        journal.save(

            match=f"{home} — {away}",

            prediction=journal_prediction

        )



        # =================================================
        # SEND RESULT
        # =================================================


        await message.answer(

            answer,

            parse_mode="Markdown",

            reply_markup=get_main_keyboard()

        )



    except Exception as e:


        print(

            traceback.format_exc()

        )



        await message.answer(

            "❌ Ошибка модели\n\n"

            f"Тип:\n"

            f"{type(e).__name__}\n\n"

            f"Ошибка:\n"

            f"{str(e)}",

            reply_markup=get_main_keyboard()

        )

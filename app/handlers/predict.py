# =====================================================
# FAJ Platform v6.3.2
# app/handlers/predict.py
#
# Main Match Prediction Handler
# =====================================================


import traceback
import logging


from aiogram import types


from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


from app.core.risk_engine import (
    risk_engine
)


from app.utils.formatter import (
    format_prediction
)


from app.utils.explainer import (
    explain_prediction
)


from app.handlers.keyboard import (
    get_main_keyboard
)



logger = logging.getLogger(__name__)



# =====================================================
# PASSPORT LOADER
# =====================================================


def load_team_passport(team):


    real_team = get_team_by_alias(team)


    if real_team:

        team = real_team



    passport = load_passport(team)


    return passport or {}



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
# PREDICT
# =====================================================


async def handle_predict(

    message: types.Message,

    core,

    journal

):


    text = (

        message.text or ""

    ).strip()



    home, away = parse_match(text)



    if not home or not away:

        return



    league = "RPL"



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

                "FAJ Core пустой ответ"

            )



        # =================================================
        # FIXTURE ID
        # =================================================


        fixture_id = result.get(

            "fixture_id"

        )



        # =================================================
        # XG
        # =================================================


        predicted = (

            result.get(

                "xg",

                {}

            )

            .get(

                "predicted",

                {}

            )

        )



        xg_home = safe_float(

            predicted.get(

                "home",

                0

            )

        )


        xg_away = safe_float(

            predicted.get(

                "away",

                0

            )

        )



        # =================================================
        # PASSPORTS
        # =================================================


        home_pass = load_team_passport(

            home

        )


        away_pass = load_team_passport(

            away

        )



        home_rating = safe_float(

            home_pass.get(

                "faj_rating",

                home_pass.get(

                    "rating",

                    0

                )

            )

        )



        away_rating = safe_float(

            away_pass.get(

                "faj_rating",

                away_pass.get(

                    "rating",

                    0

                )

            )

        )



        # =================================================
        # DECISION
        # =================================================


        decision = result.get(

            "decision",

            {}

        )



        winner_probability = safe_float(

            decision.get(

                "winner_probability",

                0

            )

        )



        confidence = safe_float(

            decision.get(

                "confidence",

                0

            )

        )



        # =================================================
        # RISK ENGINE
        # =================================================


        risk = risk_engine.analyze(

            confidence,

            home_rating,

            away_rating,

            winner_probability,

            xg_home,

            xg_away

        )



        decision.update(

            {

                "risk":

                    risk.get(

                        "risk",

                        "Средний"

                    ),


                "grade":

                    risk.get(

                        "grade",

                        "C"

                    ),


                "grade_name":

                    risk.get(

                        "grade_name",

                        "Высокий риск"

                    )

            }

        )



        # =================================================
        # FACTORS
        # =================================================


        factors = explain_prediction(

            home_pass,

            away_pass,

            xg_home,

            xg_away,

            league

        )



        # =================================================
        # RATING OBJECT
        # =================================================


        faj_rating = {


            home:

                home_rating,


            away:

                away_rating

        }



        # =================================================
        # TOP SCORES
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


            decision.get(

                "btts",

                result.get(

                    "btts",

                    0

                )

            ),


            decision.get(

                "over25",

                result.get(

                    "over25",

                    0

                )

            ),


            factors,


            faj_rating,


            risk.get(

                "risk",

                "Средний"

            ),


            confidence

        )



        # =================================================
        # JOURNAL DATA
        # =================================================


        journal_prediction = {


            "home_team":

                home,


            "away_team":

                away,


            "league":

                league,


            "winner":

                decision.get(

                    "winner",

                    ""

                ),



            "winner_probability":

                winner_probability,



            "home_probability":

                decision.get(

                    "home_probability",

                    0

                ),



            "draw_probability":

                decision.get(

                    "draw_probability",

                    0

                ),



            "away_probability":

                decision.get(

                    "away_probability",

                    0

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



            "top_scores":

                top_scores,



            "btts":

                decision.get(

                    "btts",

                    0

                ),



            "over25":

                decision.get(

                    "over25",

                    0

                ),



            "home_rating":

                home_rating,



            "away_rating":

                away_rating,



            "confidence":

                confidence,



            "risk":

                risk.get(

                    "risk",

                    "Средний"

                ),



            "grade":

                risk.get(

                    "grade",

                    "C"

                ),



            "grade_name":

                risk.get(

                    "grade_name",

                    ""

                )

        }



        journal.save(

            match=f"{home} — {away}",

            fixture_id=fixture_id,

            prediction=journal_prediction

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

            "❌ Ошибка модели\n\n"

            f"Тип:\n"
            f"{type(e).__name__}\n\n"

            f"Ошибка:\n"
            f"{str(e)}",

            reply_markup=get_main_keyboard()

        )

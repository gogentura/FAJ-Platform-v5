# =====================================================
# FAJ Platform v6.3
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

    alias = get_team_by_alias(team)


    if alias:

        team = alias


    passport = load_passport(team)


    if isinstance(passport, dict):

        return passport


    return {}



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



    return (
        parts[0],
        " ".join(parts[1:])
    )



# =====================================================
# HANDLE PREDICT
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

        f"⏳ Анализ FAJ\n\n"
        f"⚽ {home} — {away}",

        reply_markup=get_main_keyboard()

    )



    try:


        # =============================================
        # CORE
        # =============================================


        result = core.predict_match(

            home,

            away,

            league

        )


        if not result:

            raise Exception(
                "FAJ Core вернул пустой результат"
            )



        # =============================================
        # XG
        # =============================================


        xg_data = (
            result
            .get("xg", {})
            .get("predicted", {})
        )


        xg_home = float(
            xg_data.get(
                "home",
                0
            )
        )


        xg_away = float(
            xg_data.get(
                "away",
                0
            )
        )



        # =============================================
        # PASSPORTS
        # =============================================


        home_pass = load_team_passport(
            home
        )


        away_pass = load_team_passport(
            away
        )



        home_rating = float(
            home_pass.get(
                "faj_rating",
                0
            )
        )


        away_rating = float(
            away_pass.get(
                "faj_rating",
                0
            )
        )



        # =============================================
        # DECISION
        # =============================================


        decision = result.get(
            "decision",
            {}
        )


        if not isinstance(decision, dict):

            decision = {}



        confidence = float(

            decision.get(
                "confidence",
                0
            )

        )



        winner_probability = float(

            decision.get(
                "winner_probability",
                0
            )

        )



        # =============================================
        # RISK ENGINE
        # =============================================


        risk = risk_engine.analyze(

            confidence,

            home_rating,

            away_rating,

            winner_probability,

            xg_home,

            xg_away

        )



        # =============================================
        # FACTORS
        # =============================================


        factors = explain_prediction(

            home_pass,

            away_pass,

            xg_home,

            xg_away,

            league

        )



        # =============================================
        # RATINGS DICT
        # =============================================


        faj_rating = {

            home:
                home_rating,


            away:
                away_rating

        }



        # =============================================
        # FORMAT
        # =============================================


        simulation = result.get(
            "simulation",
            {}
        )


        top_scores = simulation.get(
            "top_scores",
            []
        )



        answer = format_prediction(

            home,

            away,

            league,


            {
                "home": xg_home,
                "away": xg_away
            },


            decision,


            top_scores,


            decision.get(
                "btts",
                0
            ),


            decision.get(
                "over25",
                0
            ),


            factors,


            faj_rating,


            risk.get(
                "risk",
                "Средний"
            ),


            risk.get(
                "confidence",
                confidence
            )

        )



        # =============================================
        # JOURNAL SAVE
        # =============================================


        journal.save(

            match=f"{home} — {away}",


            prediction={


                "winner":
                    decision.get(
                        "winner",
                        ""
                    ),


                "winner_name":
                    decision.get(
                        "winner_name",
                        ""
                    ),


                "winner_probability":
                    winner_probability,


                "home_probability":
                    decision.get(
                        "home_probability",
                        decision.get(
                            "home_prob",
                            0
                        )
                    ),


                "draw_probability":
                    decision.get(
                        "draw_probability",
                        decision.get(
                            "draw_prob",
                            0
                        )
                    ),


                "away_probability":
                    decision.get(
                        "away_probability",
                        decision.get(
                            "away_prob",
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


                "confidence":
                    confidence,


                "risk":
                    risk.get(
                        "risk",
                        ""
                    ),


                "faj_rating":
                    faj_rating

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

            "❌ Ошибка модели\n\n"

            f"Тип:\n"
            f"{type(e).__name__}\n\n"

            f"Ошибка:\n"
            f"{str(e)}",

            reply_markup=get_main_keyboard()

        )

# =====================================================
# FAJ Platform v6.3.1
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
# LOAD PASSPORT
# =====================================================

def load_team_passport(team):

    real_team = get_team_by_alias(team)

    if real_team:
        team = real_team


    passport = load_passport(team)


    return passport or {}



# =====================================================
# FAJ RATING
# =====================================================

def calculate_faj_rating(passport):

    if not passport:

        return 0



    rating = (

        float(passport.get("attack", 70)) * 0.18

        +

        float(passport.get("defense", 70)) * 0.18

        +

        float(passport.get("control", 70)) * 0.15

        +

        float(passport.get("efficiency", 70)) * 0.12

        +

        float(passport.get("mentality", 70)) * 0.10

        +

        float(passport.get("discipline", 70)) * 0.08

        +

        float(passport.get("fitness", 70)) * 0.07

        +

        float(passport.get("predictability", 70)) * 0.07

    )


    return round(
        rating,
        1
    )



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
                "FAJ Core пустой ответ"
            )



        # =============================================
        # XG
        # =============================================


        xg_block = result.get(
            "xg",
            {}
        )


        predicted = xg_block.get(
            "predicted",
            {}
        )


        xg_home = float(
            predicted.get(
                "home",
                0
            )
        )


        xg_away = float(
            predicted.get(
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



        # =============================================
        # FAJ RATING
        # =============================================


        home_rating = calculate_faj_rating(
            home_pass
        )


        away_rating = calculate_faj_rating(
            away_pass
        )



        # =============================================
        # DECISION
        # =============================================


        decision = result.get(
            "decision",
            {}
        )


        winner_probability = float(

            decision.get(
                "winner_probability",
                0
            )

        )


        confidence = float(

            decision.get(
                "confidence",
                0
            )

        )



        # =============================================
        # RISK
        # =============================================


        risk = risk_engine.analyze(

            confidence,

            home_rating,

            away_rating,

            winner_probability,

            xg_home,

            xg_away

        )



        decision.update({

            "risk":
                risk.get(
                    "risk",
                    "Средний"
                ),

            "grade":
                risk.get(
                    "grade",
                    "B"
                ),

            "grade_name":
                risk.get(
                    "grade_name",
                    ""
                )

        })



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
        # FORMAT
        # =============================================


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


            result.get(
                "simulation",
                {}
            ).get(
                "top_scores",
                []
            ),


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


            {
                home:
                    home_rating,

                away:
                    away_rating

            },


            risk.get(
                "risk",
                "Средний"
            ),


            confidence

        )



        # =============================================
        # JOURNAL
        # =============================================


        journal.save(

            match=f"{home} — {away}",


            prediction={

                **decision,


                "winner_name":
                    decision.get(
                        "winner_name",
                        ""
                    ),


                "xg_home":
                    xg_home,


                "xg_away":
                    xg_away,


                "top_scores":
                    result.get(
                        "simulation",
                        {}
                    ).get(
                        "top_scores",
                        []
                    ),


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


                "home_rating":
                    home_rating,


                "away_rating":
                    away_rating

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

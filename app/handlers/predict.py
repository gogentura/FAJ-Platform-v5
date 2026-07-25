# =====================================================
# FAJ Platform v6.3
# app/handlers/predict.py
#
# Main Match Prediction Handler
# SAFE VERSION
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
# PASSPORT
# =====================================================

def load_team_passport(team):

    real_team = get_team_by_alias(team)

    if real_team:
        team = real_team


    passport = load_passport(team)


    if not isinstance(passport, dict):
        return {}


    return passport



# =====================================================
# FAJ RATING
# =====================================================

def calculate_faj_rating(passport):

    if not isinstance(passport, dict):
        return 0


    value = passport.get(
        "faj_rating"
    )


    if isinstance(
        value,
        (int,float)
    ):
        return round(
            float(value),
            1
        )


    attack = float(
        passport.get(
            "attack",
            70
        )
    )


    defense = float(
        passport.get(
            "defense",
            70
        )
    )


    control = float(
        passport.get(
            "control",
            70
        )
    )


    form = float(
        passport.get(
            "form",
            passport.get(
                "form_index",
                70
            )
        )
    )


    rating = (

        attack * 0.30 +

        defense * 0.30 +

        control * 0.20 +

        form * 0.20

    )


    return round(
        rating,
        1
    )



# =====================================================
# PARSE
# =====================================================

def parse_match(text):

    text = text.strip()


    if text.lower().startswith(
        "прогноз"
    ):
        text = text[8:].strip()


    parts = text.split()


    if len(parts) < 2:
        return None,None


    home = parts[0]


    away = " ".join(
        parts[1:]
    )


    return home,away



# =====================================================
# XG SAFE
# =====================================================

def extract_xg(result):

    home = 0
    away = 0


    if not isinstance(
        result,
        dict
    ):
        return home,away



    xg = result.get(
        "xg",
        {}
    )


    if isinstance(
        xg,
        dict
    ):


        if isinstance(
            xg.get("predicted"),
            dict
        ):

            home = xg["predicted"].get(
                "home",
                0
            )

            away = xg["predicted"].get(
                "away",
                0
            )

        else:

            home = xg.get(
                "home",
                0
            )

            away = xg.get(
                "away",
                0
            )


    home = result.get(
        "xg_home",
        home
    )


    away = result.get(
        "xg_away",
        away
    )


    try:

        return (
            round(float(home),2),
            round(float(away),2)
        )

    except:

        return 0,0



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



    home,away = parse_match(
        text
    )


    if not home or not away:
        return



    league = "RPL"



    await message.answer(

        f"⏳ Анализирую матч\n\n"
        f"⚽ {home} — {away}",

        reply_markup=get_main_keyboard()

    )



    try:


        result = core.predict_match(

            home,

            away,

            league

        )


        if not isinstance(
            result,
            dict
        ):
            raise Exception(
                "FAJ Core вернул не dict"
            )



        xg_home,xg_away = extract_xg(
            result
        )



        home_pass = load_team_passport(
            home
        )


        away_pass = load_team_passport(
            away
        )



        home_rating = calculate_faj_rating(
            home_pass
        )


        away_rating = calculate_faj_rating(
            away_pass
        )



        decision = result.get(
            "decision",
            {}
        )


        if not isinstance(
            decision,
            dict
        ):

            decision = {}



        winner_probability = float(
            decision.get(
                "winner_probability",
                0
            )
        )


        confidence = float(
            decision.get(
                "confidence",
                winner_probability
            )
        )



        risk = risk_engine.analyze(

            confidence,

            home_rating,

            away_rating,

            winner_probability,

            xg_home,

            xg_away

        )


        if not isinstance(
            risk,
            dict
        ):

            risk = {

                "risk":"Средний",

                "grade":"B",

                "grade_name":
                    "Рабочий прогноз"

            }



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
                    "Рабочий прогноз"
                )

        })



        factors = explain_prediction(

            home_pass,

            away_pass,

            xg_home,

            xg_away,

            league

        )



        simulation = result.get(
            "simulation",
            {}
        )


        if not isinstance(
            simulation,
            dict
        ):
            simulation = {}



        answer = format_prediction(

            home,

            away,

            league,


            {
                "home":xg_home,
                "away":xg_away
            },


            decision,


            simulation.get(
                "top_scores",
                []
            ),


            decision.get(
                "btts",
                0
            ),


            decision.get(
                "over25",
                0
            ),


            factors,


            home_rating,

            away_rating,

            risk

        )



        journal.save(

            match=f"{home} — {away}",

            prediction={

                **decision,

                "xg_home":
                    xg_home,

                "xg_away":
                    xg_away,

                "winner_probability":
                    winner_probability,

                "confidence":
                    confidence,

                "top_scores":
                    simulation.get(
                        "top_scores",
                        []
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

            "❌ Ошибка модели\n\n"

            f"Тип:\n{type(e).__name__}\n\n"

            f"Ошибка:\n{str(e)}",

            reply_markup=get_main_keyboard()

        )

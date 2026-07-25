# =====================================================
# FAJ Platform v6.3
# app/handlers/predict.py
#
# Main Match Prediction Handler
# PostgreSQL
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

    return passport or {}



# =====================================================
# FAJ RATING
# =====================================================

def calculate_faj_rating(passport):

    if not passport:
        return 0


    # если уже есть готовый рейтинг
    existing = passport.get(
        "faj_rating"
    )


    if isinstance(
        existing,
        (int, float)
    ):
        return round(
            float(existing),
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
# PARSE MATCH
# =====================================================

def parse_match(text):

    text = text.strip()


    if text.lower().startswith(
        "прогноз"
    ):

        text = text[8:].strip()



    parts = text.split()


    if len(parts) < 2:

        return None, None



    home = parts[0]


    away = " ".join(
        parts[1:]
    )


    return home, away



# =====================================================
# XG EXTRACTOR
# =====================================================

def extract_xg(result):

    xg_home = 0
    xg_away = 0


    try:

        xg = result.get(
            "xg",
            {}
        )


        # вариант FAJ v6
        if isinstance(xg, dict):

            if "predicted" in xg:

                predicted = xg["predicted"]

                xg_home = predicted.get(
                    "home",
                    0
                )

                xg_away = predicted.get(
                    "away",
                    0
                )

            else:

                xg_home = xg.get(
                    "home",
                    0
                )

                xg_away = xg.get(
                    "away",
                    0
                )


        # прямые поля
        if not xg_home:

            xg_home = result.get(
                "xg_home",
                0
            )


        if not xg_away:

            xg_away = result.get(
                "xg_away",
                0
            )


    except Exception:

        pass



    return (

        round(
            float(xg_home),
            2
        ),

        round(
            float(xg_away),
            2
        )

    )



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



    home, away = parse_match(
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

        xg_home, xg_away = extract_xg(
            result
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
                winner_probability
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
                    "Рабочий прогноз"
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
                "home": xg_home,
                "away": xg_away
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



        # =============================================
        # JOURNAL
        # =============================================

        journal.save(

            match=f"{home} — {away}",

            prediction={

                **decision,


                "winner_probability":
                    winner_probability,


                "xg_home":
                    xg_home,


                "xg_away":
                    xg_away,


                "confidence":
                    confidence,


                "top_scores":
                    result.get(
                        "simulation",
                        {}
                    ).get(
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

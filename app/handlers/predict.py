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
# LOAD PASSPORT
# =====================================================

def load_team_passport(team):

    real_team = get_team_by_alias(team)

    if real_team:

        team = real_team


    passport = load_passport(team)


    return passport or {}



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
# PREDICT HANDLER
# =====================================================

async def handle_predict(

    message: types.Message,

    core,

    journal

):


    text = (
        message.text or ""
    ).strip()



    # -------------------------
    # IGNORE BUTTONS
    # -------------------------

    ignore = [

        "📈 Прогноз",

        "📋 Последние прогнозы",

        "⚽ Статус",

        "📁 Паспорта",

        "🔄 Загрузить паспорта",

        "📅 Матчи",

        "🤖 FAJ прогнозы",

        "🧠 Мои прогнозы",

        "🏆 Турниры",

        "📋 Журнал",

        "⚙️ Админ",

        "❤️ Проверка",

        "/start"

    ]


    if text in ignore:

        return



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



        if "xg" not in result:

            raise Exception(

                "FAJ Core не вернул xG"

            )



        # =================================================
        # XG
        # =================================================


        predicted_xg = result["xg"]["predicted"]


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
        # PASSPORTS
        # =================================================


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



        # =================================================
        # DECISION
        # =================================================


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



        decision.update({


            "risk":

                risk["risk"],


            "grade":

                risk["grade"],


            "grade_name":

                risk["grade_name"]


        })



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



        # =================================================
        # JOURNAL
        # =================================================


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

                    confidence

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

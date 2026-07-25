# =====================================================
# FAJ Platform v6.3
# app/handlers/predict.py
#
# Prediction Handler
# PostgreSQL compatible
# =====================================================

import traceback
import logging


from aiogram import types


from app.database import get_db


from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


from app.utils.formatter import format_prediction


from app.utils.explainer import explain_prediction


from app.handlers.keyboard import get_main_keyboard



logger = logging.getLogger(__name__)



# =====================================================
# FIXTURE ID
# =====================================================

def get_fixture_id(
    home,
    away,
    league="RPL"
):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT id
            FROM fixtures
            WHERE home_team=%s
            AND away_team=%s
            AND league=%s
            LIMIT 1
            """,
            (
                home,
                away,
                league
            )
        ).fetchone()


        if row:

            return row["id"]


    except Exception:

        pass


    finally:

        conn.close()



    return None



# =====================================================
# FAJ RATING
# =====================================================

def calculate_faj_rating(passport):

    if not passport:

        return 0



    rating = (

        float(passport.get("attack",70)) * 0.18 +

        float(passport.get("defense",70)) * 0.18 +

        float(passport.get("control",70)) * 0.15 +

        float(passport.get("efficiency",70)) * 0.12 +

        float(passport.get("mentality",70)) * 0.10 +

        float(passport.get("fitness",70)) * 0.10 +

        float(passport.get("form",70)) * 0.17

    )



    return round(
        rating,
        1
    )



# =====================================================
# RISK
# =====================================================

def calculate_risk(decision):


    probability = max(

        decision.get(
            "home_probability",
            decision.get(
                "home_prob",
                0
            )
        ),

        decision.get(
            "draw_probability",
            decision.get(
                "draw_prob",
                0
            )
        ),

        decision.get(
            "away_probability",
            decision.get(
                "away_prob",
                0
            )
        )

    )



    if probability >= 70:

        return "Низкий"



    elif probability >=55:

        return "Средний"



    else:

        return "Высокий"





# =====================================================
# CONFIDENCE
# =====================================================

def calculate_confidence(

    decision,

    xg_home,

    xg_away

):


    main_probability = max(

        decision.get(
            "home_probability",
            0
        ),

        decision.get(
            "draw_probability",
            0
        ),

        decision.get(
            "away_probability",
            0
        )

    )



    score = 50



    score += (

        main_probability - 50

    )



    score += abs(

        xg_home-xg_away

    ) * 10



    return round(

        min(
            score,
            95
        ),

        1

    )





# =====================================================
# LOAD PASSPORT SAFE
# =====================================================

def load_team_passport(team):


    real = get_team_by_alias(team)



    if real:

        team = real



    return load_passport(team)






# =====================================================
# MAIN HANDLER
# =====================================================

async def handle_predict(

    message: types.Message,

    core,

    journal

):


    text = (

        message.text or ""

    ).strip()



    ignore = [

        "📈 Прогноз",

        "📋 Последние прогнозы",

        "⚽ Статус",

        "📁 Паспорта",

        "🔄 Загрузить паспорта",

        "/start"

    ]



    if text in ignore:

        return




    if text.lower().startswith(
        "прогноз "
    ):

        text = text[9:].strip()




    parts = text.split()



    if len(parts)<2:

        return



    home = parts[0]

    away = parts[1]


    league="RPL"



    if len(parts)>=3:

        if parts[2].upper() in [

            "RPL",

            "EPL",

            "UCL",

            "LALIGA",

            "SERIEA",

            "BUNDESLIGA",

            "LIGUE1"

        ]:

            league = parts[2].upper()





    await message.answer(

        f"⏳ Анализирую матч\n\n"
        f"⚽ {home} — {away}",

        reply_markup=get_main_keyboard()

    )




    try:


        # =============================
        # CORE
        # =============================


        result = core.predict_match(

            home,

            away,

            league

        )




        if "error" in result:

            raise Exception(

                result["error"]

            )



        xg_data = result.get(
            "xg",
            {}
        ).get(
            "predicted",
            {}
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



        if xg_home == 0 and xg_away ==0:

            raise Exception(
                "FAJ Core не вернул xG"
            )





        # =============================
        # PASSPORTS
        # =============================


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




        decision = result["decision"]




        risk = calculate_risk(
            decision
        )



        confidence = calculate_confidence(

            decision,

            xg_home,

            xg_away

        )




        factors = explain_prediction(

            home_pass or {},

            away_pass or {},

            xg_home,

            xg_away,

            league

        )




        # =============================
        # FORMAT
        # =============================


        answer = format_prediction(

            home,

            away,

            league,


            {

                "home":xg_home,

                "away":xg_away

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


            factors

        )



        answer += (

            "\n\n━━━━━━━━━━━━━━\n"

            "🧠 *FAJ Rating*\n"

            f"{home}: {home_rating}\n"

            f"{away}: {away_rating}\n\n"

            f"⚠️ Риск: {risk}\n"

            f"🎯 Уверенность FAJ: {confidence}%"

        )





        # =============================
        # JOURNAL
        # =============================


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
                    decision.get(
                        "winner_probability",
                        0
                    ),


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
                    confidence,


                "fixture_id":
                    get_fixture_id(
                        home,
                        away,
                        league
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

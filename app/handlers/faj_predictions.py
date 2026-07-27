# =====================================================
# FAJ Platform v6.9.2
# app/handlers/faj_predictions.py
#
# FAJ Predictions Viewer
#
# Reads:
# prediction_manager
#
# Compatible:
# - prediction_pipeline v6.9.2
# - tour_predictor v6.9.2
# - PostgreSQL
# =====================================================


import json
import logging


from aiogram.types import Message


from app.managers.prediction_manager import (
    get_predictions
)


from app.keyboards.main import (
    main_keyboard
)


logger = logging.getLogger(__name__)





# =====================================================
# SAFE HELPERS
# =====================================================


def safe_value(
    value,
    default="-"
):

    if value is None:
        return default

    return value






def safe_json_load(
    value,
    default=None
):

    if value is None:
        return default or []


    if isinstance(
        value,
        (list, dict)
    ):
        return value


    try:

        return json.loads(
            value
        )

    except:

        return default or []






# =====================================================
# CONFIDENCE BADGE
# =====================================================


def confidence_badge(
    value
):

    try:

        value=float(value)


        if value <= 1:

            value *= 100



        if value >=65:

            icon="🟢"

        elif value >=50:

            icon="🟡"

        elif value >=35:

            icon="🟠"

        else:

            icon="🔴"



        return (
            f"{icon} {value:.1f}%"
        )


    except:

        return "⚪ Нет данных"








# =====================================================
# QUALITY FORMAT
# =====================================================


def quality_format(
    value
):

    try:

        value=float(value)


        if value <=1:

            value*=100



        if value>=80:

            return f"🟢 {value:.0f}%"

        elif value>=50:

            return f"🟡 {value:.0f}%"

        else:

            return f"🔴 {value:.0f}%"



    except:

        return "🔴 0%"








# =====================================================
# MAIN HANDLER
# =====================================================


async def cmd_faj_predictions(

    message: Message

):


    try:


        predictions = get_predictions(
            limit=20
        )



        # защита от None
        if not predictions:

            await message.answer(

"""
⚠️ FAJ прогнозов пока нет.

Создайте прогнозы:

🚀 Создать прогнозы тура

или

/generate_tour
"""

            )

            return




        # удаляем битые записи
        predictions = [
            p for p in predictions
            if isinstance(
                p,
                dict
            )
        ]



        if not predictions:

            await message.answer(

"""
⚠️ В базе нет корректных прогнозов FAJ.

Создайте новый тур:

/generate_tour
"""

            )

            return





        text="""

🤖 *FAJ ПРОГНОЗЫ*

🧠 FAJ Engine v6.9.2

━━━━━━━━━━━━━━

"""





        for p in predictions:



            home=p.get(
                "home_team",
                "?"
            )


            away=p.get(
                "away_team",
                "?"
            )



            winner=p.get(
                "winner",
                "-"
            )



            score=p.get(
                "expected_score",
                p.get(
                    "score_prediction",
                    "-"
                )
            )



            xg_home=p.get(
                "xg_home",
                0
            )


            xg_away=p.get(
                "xg_away",
                0
            )



            rating_home=p.get(
                "home_rating",
                0
            )


            rating_away=p.get(
                "away_rating",
                0
            )



            confidence=p.get(
                "confidence",
                0
            )



            risk=p.get(
                "risk",
                "Средний"
            )



            category=p.get(
                "category",
                p.get(
                    "grade",
                    "C"
                )
            )



            factors=safe_json_load(
                p.get(
                    "factors"
                ),
                []
            )



            quality=safe_json_load(
                p.get(
                    "passport_quality"
                ),
                {}
            )



            if not isinstance(
                quality,
                dict
            ):
                quality={}




            text+=f"""

⚽ *{home} — {away}*


🏆 Победа:

{winner}


🎯 Счёт:

{score}


📊 xG:

{xg_home} — {xg_away}


🧠 FAJ Rating:

{rating_home} — {rating_away}


🔥 Уверенность:

{confidence_badge(
    confidence
)}


⚠️ Риск:

{risk}


🏷 Категория:

{category}


📁 Паспорт:

🏠 {quality_format(
quality.get(
    "home",
    0
)
)}

🚩 {quality_format(
quality.get(
    "away",
    0
)
)}

"""



            if factors:


                text+="\n🧠 Факторы:\n"


                for factor in factors:

                    text+=(
                        f"\n• {factor}"
                    )



            text+="\n\n──────────────\n"





        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )





    except Exception as e:


        logger.exception(
            "FAJ predictions handler error"
        )


        await message.answer(

f"""
❌ FAJ ПРОГНОЗ ERROR


{type(e).__name__}


{str(e)}

"""

        )

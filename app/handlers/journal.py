# =====================================================
# FAJ Platform v6.3.1
# app/handlers/journal.py
#
# Journal Viewer Handler
# =====================================================

import logging

from aiogram import types

from app.database import get_connection
from app.handlers.keyboard import get_main_keyboard


logger = logging.getLogger(__name__)


# =====================================================
# HELPERS
# =====================================================

def safe(value, default="Нет данных"):

    if value is None:
        return default

    return value



def winner_label(
    winner,
    home_team=None,
    away_team=None
):

    if winner == "home":

        if home_team:
            return home_team

        return "Хозяева"


    if winner == "away":

        if away_team:
            return away_team

        return "Гости"


    if winner in [
        "draw",
        "ничья"
    ]:

        return "Ничья"


    return safe(winner)



def confidence_grade(
    grade,
    grade_name
):

    if grade:

        if grade_name:

            return (
                f"{grade} — "
                f"{grade_name}"
            )

        return grade


    return "Нет данных"



# =====================================================
# JOURNAL COMMAND
# =====================================================

async def cmd_journal(
    message: types.Message
):

    try:

        conn = get_connection()

        cur = conn.cursor()


        cur.execute(
            """
            SELECT *
            FROM journal
            ORDER BY id DESC
            LIMIT 5
            """
        )


        rows = cur.fetchall()


        conn.close()



        if not rows:

            await message.answer(

                "📋 Журнал FAJ пуст",

                reply_markup=get_main_keyboard()

            )

            return



        text = "📋 *Последние прогнозы FAJ:*\n\n"



        for row in rows:


            # -----------------------------
            # MATCH
            # -----------------------------

            home = row.get(
                "home_team"
            )

            away = row.get(
                "away_team"
            )


            if home and away:

                match = (
                    f"{home} — {away}"
                )

            else:

                match = (
                    row.get(
                        "match",
                        "Неизвестный матч"
                    )
                )



            # -----------------------------
            # WINNER
            # -----------------------------

            winner = winner_label(

                row.get(
                    "winner"
                ),

                home,

                away

            )



            # -----------------------------
            # XG
            # -----------------------------

            xg_home = row.get(
                "xg_home"
            )

            xg_away = row.get(
                "xg_away"
            )


            if (
                xg_home is not None
                and
                xg_away is not None
            ):

                xg = (
                    f"{float(xg_home):.2f}"
                    " — "
                    f"{float(xg_away):.2f}"
                )

            else:

                xg = "Нет данных"



            # -----------------------------
            # SCORE
            # -----------------------------

            score = safe(

                row.get(
                    "expected_score"
                ),

                "Нет данных"

            )



            # -----------------------------
            # PROBABILITY
            # -----------------------------

            probability = row.get(
                "winner_probability"
            )


            if probability is not None:

                probability = (
                    f"{float(probability):.1f}%"
                )

            else:

                probability = (
                    "Нет данных"
                )



            # -----------------------------
            # RATING
            # -----------------------------

            home_rating = row.get(
                "home_rating"
            )

            away_rating = row.get(
                "away_rating"
            )


            if (
                home_rating is not None
                and
                away_rating is not None
            ):

                rating = (

                    f"{float(home_rating):.1f}"
                    " — "
                    f"{float(away_rating):.1f}"

                )

            else:

                rating = (
                    "Нет данных"
                )



            # -----------------------------
            # CONFIDENCE
            # -----------------------------

            confidence = row.get(
                "confidence"
            )


            if confidence is not None:

                confidence = (
                    f"{float(confidence):.1f}%"
                )

            else:

                confidence = (
                    "Нет данных"
                )



            category = confidence_grade(

                row.get(
                    "grade"
                ),

                row.get(
                    "grade_name"
                )

            )



            risk = safe(

                row.get(
                    "risk"
                ),

                "Нет данных"

            )



            # -----------------------------
            # FACT
            # -----------------------------

            actual = row.get(
                "actual_score"
            )


            if actual:

                fact = actual

            else:

                fact = "нет"



            text += (

                f"⚽ *{match}*\n"

                f"🏆 Победа: {winner}\n"

                f"📊 xG: {xg}\n"

                f"🎯 Счёт: {score}\n"

                f"📈 Вероятность: {probability}\n\n"

                f"🧠 FAJ Rating: {rating}\n"

                f"🎯 Уверенность: {confidence}\n"

                f"🏷 Категория: {category}\n"

                f"⚠️ Риск: {risk}\n\n"

                f"✅ Факт: {fact}\n"

                "──────────────\n"

            )



        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=get_main_keyboard()

        )



    except Exception as e:


        logger.error(

            "Journal error: %s",

            e,

            exc_info=True

        )


        await message.answer(

            "❌ Ошибка журнала FAJ",

            reply_markup=get_main_keyboard()

        )

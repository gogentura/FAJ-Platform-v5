from aiogram import types

from app.database import get_db
from app.accuracy_engine import AccuracyEngine
from app.handlers.keyboard import get_main_keyboard

from datetime import datetime



accuracy_engine = AccuracyEngine()



# =====================================================
# SAVE RESULT
# =====================================================

async def cmd_result(
    message: types.Message
):


    text = (
        message.text
        or ""
    ).strip()



    if text.lower().startswith(
        "результат"
    ):

        text = text[9:].strip()



    parts = text.split()



    if len(parts) < 3:


        await message.answer(

            """
⚽ Введите результат:

Пример:

Зенит Спартак 2:1

или

Результат Зенит Спартак 2:1
            """,

            reply_markup=get_main_keyboard()

        )

        return



    home = parts[0]

    away = parts[1]

    score = parts[2]



    if ":" not in score:


        await message.answer(

            "❌ Формат счёта должен быть 2:1",

            reply_markup=get_main_keyboard()

        )

        return



    try:


        home_goals, away_goals = map(
            int,
            score.split(":")
        )


    except:


        await message.answer(

            "❌ Ошибка формата счёта",

            reply_markup=get_main_keyboard()

        )

        return




    match = (
        f"{home} — {away}"
    )



    if home_goals > away_goals:

        winner = home


    elif away_goals > home_goals:

        winner = away


    else:

        winner = "Ничья"




    conn = get_db()



    conn.execute(
    """
    INSERT INTO match_results

    (
        match,
        date,
        home_goals,
        away_goals,
        score,
        winner,
        created
    )

    VALUES

    (
        ?,
        ?,
        ?,
        ?,
        ?,
        ?,
        ?
    )

    """,

    (

        match,

        datetime.now().isoformat(),

        home_goals,

        away_goals,

        score,

        winner,

        datetime.now().isoformat()

    )

    )



    conn.commit()

    conn.close()




    # Проверяем прогноз

    result = accuracy_engine.evaluate_match(
        match
    )



    if "error" in result:


        await message.answer(

            f"""
✅ Результат сохранён

⚽ {match}
🎯 Факт: {score}

ℹ️ Проверка прогноза:
{result['error']}
            """,

            reply_markup=get_main_keyboard()

        )

        return





    await message.answer(

        f"""
✅ Результат обработан

⚽ {match}

🎯 Факт:
{score}

🏆 Победитель:
{winner}


📊 Проверка FAJ:

Исход:
{"✅" if result["outcome_hit"] else "❌"}

Точный счёт:
{"✅" if result["score_hit"] else "❌"}


FAJ:
{result["accuracy"]}
        """,

        reply_markup=get_main_keyboard()

    )

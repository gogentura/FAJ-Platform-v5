from aiogram.types import Message
from app.core.faj_core import FAJCore


async def handle_predict(message: Message):

    if not message.text:
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer(
            "Формат:\nКоманда1 Команда2\n\nПример:\nЗенит Спартак"
        )
        return


    home_team = parts[0]
    away_team = parts[1]


    await message.answer(
        f"⏳ FAJ считает матч:\n"
        f"{home_team} — {away_team}"
    )


    try:

        core = FAJCore()

        result = core.predict_match(
            home_team,
            away_team
        )


        if result.get("error"):

            await message.answer(
                f"❌ {result['error']}"
            )
            return


        await message.answer(
            f"""
⚽ FAJ Prediction v5.1

{home_team} — {away_team}

📊 xG:
{result.get('xg')}

🎯 Решение:
{result.get('decision')}

🏆 Топ счета:
{result.get('top_scores')}

🧠 Версия:
{result.get('version')}
"""
        )


    except Exception as e:

        await message.answer(
            f"❌ Ошибка прогноза:\n{type(e).__name__}: {e}"
        )

from aiogram.types import Message
from app.core.faj_core import FAJCore


async def handle_predict(message: Message):

    text = message.text.split()

    if len(text) < 2:
        await message.answer(
            "Формат:\nКоманда1 Команда2\n\nПример:\nЗенит Спартак"
        )
        return


    home_team = text[0]
    away_team = text[1]


    await message.answer(
        f"⚽ FAJ анализирует:\n"
        f"{home_team} — {away_team}\n\n"
        f"⏳ Расчёт..."
    )


    try:

        core = FAJCore()

        result = core.predict_match(
            home_team,
            away_team
        )


        if "error" in result:

            await message.answer(
                f"❌ Ошибка:\n{result['error']}"
            )
            return


        xg = result.get("xg", {}).get(
            "predicted",
            {}
        )


        decision = result.get(
            "decision",
            {}
        )


        await message.answer(
            f"""
🏆 FAJ Prediction v5.1

⚽ {home_team} — {away_team}

📊 xG:
{home_team}: {xg.get('home', '-')}
{away_team}: {xg.get('away', '-')}

🎯 Решение:
{decision}

📌 Топ счета:
{result.get('top_scores', [])}

🧠 Версия:
{result.get('version')}
"""
        )


    except Exception as e:

        await message.answer(
            f"❌ Ошибка прогноза:\n"
            f"{type(e).__name__}: {e}"
        )

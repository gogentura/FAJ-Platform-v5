from aiogram import types

from app.journal import Journal
from app.handlers.keyboard import get_main_keyboard


journal = Journal()



async def cmd_journal(
    message: types.Message
):


    entries = journal.get_all(
        limit=5
    )


    if not entries:

        await message.answer(
            "📭 Журнал пуст",
            reply_markup=get_main_keyboard()
        )

        return



    text = "📋 *Последние прогнозы:*\n\n"



    for e in entries:


        match = e.get(
            "match",
            "Неизвестный матч"
        )


        winner = e.get(
            "winner",
            ""
        )


        winner_prob = e.get(
            "winner_prob",
            0
        )


        xg_home = e.get(
            "xg_home",
            0
        )


        xg_away = e.get(
            "xg_away",
            0
        )


        score = e.get(
            "expected_score",
            ""
        )


        actual = e.get(
            "actual_score",
            ""
        )



        text += (
            f"⚽ *{match}*\n"
            f"🏆 Победа: {winner}\n"
            f"📊 xG: {xg_home} — {xg_away}\n"
            f"🎯 Счёт: {score}\n"
            f"📈 Вероятность: {winner_prob}%\n"
            f"✅ Факт: {actual if actual else 'нет'}\n"
            f"──────────────\n"
        )



    await message.answer(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

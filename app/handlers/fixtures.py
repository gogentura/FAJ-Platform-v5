# =====================================================
# FAJ Platform v5.2
# Fixtures Handler
# =====================================================


from aiogram import types

from app.loaders.fixtures_loader import get_upcoming_fixtures

from app.handlers.keyboard import get_main_keyboard



# =====================================================
# SHOW UPCOMING FIXTURES
# =====================================================


async def cmd_fixtures(
    message: types.Message
):


    fixtures = get_upcoming_fixtures(
        league="RPL",
        limit=10
    )



    if not fixtures:

        await message.answer(
            "📅 Календарь пуст\n\n"
            "Матчи ещё не загружены.",
            reply_markup=get_main_keyboard()
        )

        return



    text = (
        "📅 *Ближайшие матчи РПЛ*\n"
        "──────────────\n\n"
    )



    for i, match in enumerate(
        fixtures,
        start=1
    ):


        text += (

            f"{i}️⃣ "
            f"{match['home_team']} — "
            f"{match['away_team']}\n"

            f"📆 {match['match_date']}\n"

            f"🏆 Тур {match.get('round', '?')}\n"

            f"──────────────\n"

        )



    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )



# =====================================================
# SHOW ROUND
# =====================================================


async def cmd_round(
    message: types.Message,
    round_number: int = 1
):


    from app.loaders.fixtures_loader import get_fixtures



    fixtures = get_fixtures(
        league="RPL",
        season="2026/27"
    )



    round_games = [

        f for f in fixtures

        if f.get("round") == round_number

    ]



    if not round_games:


        await message.answer(
            f"❌ Тур {round_number} не найден",
            reply_markup=get_main_keyboard()
        )

        return



    text = (
        f"🏆 *РПЛ 2026/27*\n"
        f"Тур {round_number}\n"
        "──────────────\n\n"
    )



    for game in round_games:


        text += (

            f"⚽ "
            f"{game['home_team']} — "
            f"{game['away_team']}\n"

            f"📆 {game['match_date']}\n\n"

        )



    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

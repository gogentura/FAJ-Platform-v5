# =====================================================
# FAJ Platform v6.0
# Fixtures Handler
# =====================================================


from aiogram import types


from app.loaders.fixtures_loader import (
    get_upcoming_fixtures,
    count_fixtures
)


from app.keyboards.fixtures import (
    fixtures_keyboard
)


from app.keyboards.main import (
    main_keyboard
)



# =====================================================
# SHOW FIXTURES
# =====================================================


async def cmd_fixtures(
    message: types.Message
):


    total = count_fixtures(
        league="RPL"
    )


    if total == 0:


        await message.answer(

            """
📅 Календарь пуст


Матчи ещё не загружены.


Сначала загрузите календарь РПЛ:

⚙️ Админ
↓
📥 Загрузить календарь
""",

            reply_markup=main_keyboard()

        )


        return



    fixtures = get_upcoming_fixtures(

        league="RPL",

        limit=10

    )



    if not fixtures:


        await message.answer(

            """
📅 Ближайших матчей нет.


Календарь загружен,
но все матчи уже прошли.
""",

            reply_markup=fixtures_keyboard()

        )


        return



    text = """

📅 *Ближайшие матчи РПЛ*

"""



    for match in fixtures:


        text += (

            f"⚽ {match.get('home_team')} "
            f"— "
            f"{match.get('away_team')}\n"

            f"📅 {match.get('match_date')}\n"

            f"🔹 Тур: {match.get('round')}\n"

        )


        if match.get(
            "prediction_created"
        ):


            text += (
                "📈 Прогноз создан\n"
            )


        else:

            text += (
                "⏳ Ожидает прогноз\n"
            )



        text += (

            "──────────────\n"

        )



    await message.answer(

        text,

        parse_mode="Markdown",

        reply_markup=fixtures_keyboard()

    )



# =====================================================
# BUTTONS
# =====================================================


async def fixtures_rpl_button(
    message: types.Message
):

    await cmd_fixtures(message)



async def fixtures_all_button(
    message: types.Message
):


    await message.answer(

        """
🌍 Все турниры


Модуль подключается.


Доступные лиги:

🇷🇺 РПЛ
🏴 АПЛ
🇪🇸 Ла Лига
🇩🇪 Бундеслига
🇮🇹 Серия А
🇫🇷 Лига 1
🏆 Лига чемпионов
""",

        reply_markup=fixtures_keyboard()

    )



async def fixtures_next_button(
    message: types.Message
):


    await cmd_fixtures(message)



async def fixture_predict_button(
    message: types.Message
):


    await message.answer(

        """
📈 Прогноз матча


Выберите матч из календаря.


Автоматический запуск прогноза
будет подключён следующим этапом.
""",

        reply_markup=fixtures_keyboard()

    )

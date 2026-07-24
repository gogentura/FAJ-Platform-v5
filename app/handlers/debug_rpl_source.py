# =====================================================
# FAJ Platform v6.1
# app/handlers/debug_rpl_source.py
#
# Проверка доступности источников РПЛ
# =====================================================

from aiogram.types import Message
import requests


SOURCES = {
    "PremierLiga":
        "https://premierliga.ru/matches/?tournament=724&stage=2962&month=0&club=0&match=all",

    "Soccer365":
        "https://soccer365.ru/competitions/13/",

    "Sport-Express":
        "https://www.sport-express.ru/football/L/russia/premier/2026-2027/calendar/tours/",

    "Flashscore":
        "https://www.flashscore.com.ua/football/russia/premier-league/",

    "NB-Bet":
        "https://nb-bet.com/Tournaments/1-Rossiya-Premer-Liga-statistika-turnira",
}


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
}


async def cmd_debug_rpl_source(message: Message):

    text = "🔍 Проверка источников РПЛ\n\n"

    for name, url in SOURCES.items():

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=20,
                allow_redirects=True
            )

            html_size = len(response.text)

            text += (
                f"🌐 {name}\n"
                f"HTTP: {response.status_code}\n"
                f"HTML: {html_size} символов\n"
                f"URL: {response.url}\n\n"
            )

        except Exception as e:

            text += (
                f"❌ {name}\n"
                f"{type(e).__name__}\n"
                f"{e}\n\n"
            )

    await message.answer(text)

import aiohttp
import asyncio
from app.config import Config


async def test():

    url = "https://v3.football.api-sports.io/teams"

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    params = {
        "search": "Real Madrid"
    }

    async with aiohttp.ClientSession() as session:

        async with session.get(
            url,
            headers=headers,
            params=params
        ) as response:

            print("STATUS:", response.status)

            data = await response.json()

            print(data)


asyncio.run(test())

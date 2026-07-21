import aiohttp
from datetime import datetime, timedelta
from app.config import Config
from app.rating_cache import get_rating

class Notifier:
    def __init__(self, bot):
        self.bot = bot
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {"X-Auth-Token": Config.FOOTBALL_DATA_KEY}

    async def send_top_matches(self, chat_id: str):
        matches = await self._get_upcoming_matches()
        if not matches:
            await self.bot.send_message(chat_id, "Нет ближайших матчей в топ-лигах.")
            return
        scored = []
        for m in matches:
            home = m["home"]
            away = m["away"]
            home_rating = get_rating(home, 100)
            away_rating = get_rating(away, 100)
            scored.append({
                "home": home,
                "away": away,
                "league": m["league"],
                "date": m["date"],
                "total_rating": home_rating + away_rating
            })
        top5 = sorted(scored, key=lambda x: x["total_rating"], reverse=True)[:5]
        if not top5:
            await self.bot.send_message(chat_id, "Нет матчей с высоким рейтингом.")
            return
        text = "🏆 *Топ-5 матчей по силе команд:*\n"
        for i, m in enumerate(top5, 1):
            text += f"{i}. *{m['home']} — {m['away']}* ({m['league']})\n"
            text += f"   📅 {m['date']}\n"
        await self.bot.send_message(chat_id, text, parse_mode="Markdown")

    async def _get_upcoming_matches(self):
        today = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        leagues = {
            "EPL": "PL",
            "LaLiga": "PD",
            "Bundesliga": "BL1",
            "SerieA": "SA",
            "Ligue1": "FL1",
            "UCL": "CL",
            "RPL": "RPL"
        }
        matches = []
        for league, comp_id in leagues.items():
            url = f"{self.base_url}/competitions/{comp_id}/matches"
            params = {"dateFrom": today, "dateTo": end}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for match in data.get("matches", []):
                            matches.append({
                                "home": match["homeTeam"]["name"],
                                "away": match["awayTeam"]["name"],
                                "league": league,
                                "date": match["utcDate"][:10]
                            })
        return matches

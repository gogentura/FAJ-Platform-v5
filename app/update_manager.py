import asyncio
from app.api_client import APIClient
from app.passport_manager import save_passport, is_updated_today
from app.api_tracker import increment_usage

class UpdateManager:
    def __init__(self):
        self.api = APIClient()

    async def update_team(self, team_name: str):
        stats = await self.api.get_team_stats(team_name)
        if not stats:
            return {"status": "error", "message": f"Команда {team_name} не найдена"}
        passport = self._build_passport(stats)
        version = save_passport(team_name, passport)
        increment_usage()
        return {"status": "ok", "team": team_name, "version": version}

    async def update_rpl(self):
        teams = ["Зенит", "Спартак", "ЦСКА", "Динамо М", "Локомотив", "Краснодар",
                 "Ростов", "Ахмат", "Рубин", "Крылья Советов", "Факел", "Оренбург",
                 "Балтика", "Акрон", "Динамо Мх", "Родина"]
        results = []
        for team in teams:
            if is_updated_today(team):
                results.append({"team": team, "status": "skipped", "reason": "уже обновлён сегодня"})
                continue
            result = await self.update_team(team)
            results.append(result)
            await asyncio.sleep(0.2)
        return {"status": "done", "results": results}

    def _build_passport(self, stats):
        return {
            "avg_goals": stats["avg_goals"],
            "avg_goals_conceded": stats["avg_goals_conceded"],
            "avg_possession": stats["avg_possession"],
            "avg_xg": stats["avg_xg"],
            "attack": min(100, 70 + stats["avg_goals"] * 10),
            "defense": min(100, 70 - stats["avg_goals_conceded"] * 8),
            "control": min(100, 70 + (stats["avg_possession"] - 50) * 0.4),
            "form_index": min(100, 70 + (stats["avg_goals"] - 1.2) * 20)
        }

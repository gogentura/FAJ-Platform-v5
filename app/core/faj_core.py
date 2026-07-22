import time
import numpy as np
from app.passport_manager import load_passport

class FAJCore:
    def __init__(self):
        self.version = "5.1"

    def predict_match(self, home_team, away_team, league="RPL"):
        start = time.time()

        home_pass = load_passport(home_team)
        away_pass = load_passport(away_team)

        if not home_pass or not away_pass:
            return {"error": "Паспорт не найден. Обновите: /update_team"}

        # Извлекаем исторический xG (если есть)
        hist_xg_home = home_pass.get("historical_xg_value") or 1.3
        hist_xg_away = away_pass.get("historical_xg_value") or 1.3

        # Рассчитываем предсказанный xG на основе паспортов и соперника
        home_attack = home_pass["attack"]
        home_defense = home_pass["defense"]
        home_form = home_pass["form_index"]
        away_attack = away_pass["attack"]
        away_defense = away_pass["defense"]
        away_form = away_pass["form_index"]

        home_xg = hist_xg_home * (1 + (home_attack - 70) / 200) * (1 + (home_form - 70) / 300)
        away_xg = hist_xg_away * (1 + (away_attack - 70) / 200) * (1 + (away_form - 70) / 300)

        # Домашнее преимущество
        home_adv = 1.12 if league == "RPL" else 1.15
        home_xg *= home_adv
        away_xg /= home_adv

        home_xg = max(0.2, min(4.0, home_xg))
        away_xg = max(0.2, min(4.0, away_xg))

        # Симуляция и всё остальное
        simulation = self._simulate(home_xg, away_xg)
        btts = self._btts_prob(home_xg, away_xg)
        over25 = self._over25_prob(home_xg, away_xg)
        decision = self._decide(simulation, home_xg, away_xg)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "xg": {
                "historical": {"home": hist_xg_home, "away": hist_xg_away},
                "predicted": {"home": home_xg, "away": away_xg}
            },
            "simulation": simulation,
            "decision": decision,
            "btts": btts,
            "over25": over25,
            "top_scores": simulation["top_scores"],
            "processing_time": round(time.time() - start, 2),
            "version": self.version
        }

    # ... остальные методы (_simulate, _btts_prob, _over25_prob, _decide) — без изменений

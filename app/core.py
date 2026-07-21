import time
import asyncio
import numpy as np
from app.api_client import APIClient
from app.tactical_engine import TacticalEngine

class FAJCore:
    def __init__(self):
        self.version = "5.0.0"
        self.api_client = APIClient()
        self.tactical_engine = TacticalEngine()

    def predict_match(self, home_team, away_team, league="RPL"):
        start = time.time()
        
        # Получаем данные через API
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            home_stats = loop.run_until_complete(self.api_client.get_team_stats(home_team))
            away_stats = loop.run_until_complete(self.api_client.get_team_stats(away_team))
            loop.close()
        except Exception as e:
            print(f"API error: {e}")
            home_stats = None
            away_stats = None

        # Фолбэк
        if not home_stats:
            home_stats = {"avg_goals": 1.8, "avg_goals_conceded": 0.9, "avg_possession": 58, "avg_xg": 1.6}
        if not away_stats:
            away_stats = {"avg_goals": 1.4, "avg_goals_conceded": 1.2, "avg_possession": 52, "avg_xg": 1.3}

        # Паспорта
        home_passport = self._build_passport(home_stats)
        away_passport = self._build_passport(away_stats)

        # xG с учётом лиги
        home_xg, away_xg = self._calculate_xg(home_passport, away_passport, league)

        # Симуляции
        simulation = self._simulate(home_xg, away_xg)

        # BTTS и Тотал
        btts_prob = self._btts_prob(home_xg, away_xg)
        over25_prob = self._over25_prob(home_xg, away_xg)

        # Тактический анализ
        tactical = self.tactical_engine.analyze(home_passport, away_passport, home_stats, away_stats)

        # Решение
        decision = self._decide(simulation, home_xg, away_xg)

        # Рекомендация
        recommendation = self._recommend(decision, btts_prob, over25_prob)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "xg": {"home": home_xg, "away": away_xg},
            "simulation": simulation,
            "decision": decision,
            "btts": btts_prob,
            "over25": over25_prob,
            "recommendation": recommendation,
            "tactical": tactical,
            "top_scores": simulation["top_scores"],
            "processing_time": round(time.time() - start, 2),
            "version": self.version
        }

    def _build_passport(self, stats):
        attack = min(100, 70 + stats["avg_goals"] * 10)
        defense = min(100, 70 - stats["avg_goals_conceded"] * 8)
        control = min(100, 70 + (stats["avg_possession"] - 50) * 0.4)
        form = min(100, 70 + (stats["avg_goals"] - 1.2) * 20)
        return {"attack": attack, "defense": defense, "control": control, "form_index": form}

    def _calculate_xg(self, home, away, league):
        league_avg = {
            "EPL": 1.42, "LaLiga": 1.35, "Bundesliga": 1.40,
            "SerieA": 1.32, "Ligue1": 1.30, "UCL": 1.38, "RPL": 1.25
        }.get(league, 1.30)
        home_adv = {
            "EPL": 1.18, "LaLiga": 1.16, "Bundesliga": 1.20,
            "SerieA": 1.15, "Ligue1": 1.14, "UCL": 1.10, "RPL": 1.12
        }.get(league, 1.15)
        home_xg = league_avg * (home["attack"]/100) * (2 - away["defense"]/100) * home_adv * (home["form_index"]/100)
        away_xg = league_avg * (away["attack"]/100) * (2 - home["defense"]/100) * (1/home_adv) * (away["form_index"]/100)
        return round(max(0.2, min(4.0, home_xg)), 2), round(max(0.2, min(4.0, away_xg)), 2)

    def _simulate(self, home_xg, away_xg, n=10000):
        np.random.seed(42)
        home_goals = np.random.poisson(home_xg, n)
        away_goals = np.random.poisson(away_xg, n)

        home_wins = np.sum(home_goals > away_goals)
        draws = np.sum(home_goals == away_goals)
        away_wins = np.sum(home_goals < away_goals)

        score_counts = {}
        for h, a in zip(home_goals, away_goals):
            key = (h, a)
            score_counts[key] = score_counts.get(key, 0) + 1
        top_scores = sorted(score_counts.items(), key=lambda x: -x[1])[:5]
        top_scores_formatted = [(f"{s[0]}-{s[1]}", round(c/n, 3)) for s, c in top_scores]

        stability = 1 - np.std([home_wins/n, draws/n, away_wins/n])

        return {
            "home_win_prob": home_wins / n,
            "draw_prob": draws / n,
            "away_win_prob": away_wins / n,
            "top_scores": top_scores_formatted,
            "stability": round(stability, 3)
        }

    def _btts_prob(self, home_xg, away_xg):
        # Упрощённая оценка: 1 - P(0-0) - P(1-0) - P(0-1)
        from math import exp
        p00 = exp(-(home_xg + away_xg))
        p10 = exp(-home_xg) * (1 - exp(-away_xg))
        p01 = exp(-away_xg) * (1 - exp(-home_xg))
        return round(1 - p00 - p10 - p01, 3)

    def _over25_prob(self, home_xg, away_xg):
        # Упрощённая оценка через Пуассон
        from math import exp
        prob = 0
        for h in range(4):
            for a in range(4):
                if h+a > 2:
                    prob += (exp(-home_xg) * home_xg**h) / (h+1) * (exp(-away_xg) * away_xg**a) / (a+1)
        return round(min(1.0, prob), 3)

    def _decide(self, sim, home_xg, away_xg):
        home = sim["home_win_prob"]
        draw = sim["draw_prob"]
        away = sim["away_win_prob"]

        if home >= draw and home >= away:
            winner = "home"
            winner_name = "Хозяева"
        elif away >= home and away >= draw:
            winner = "away"
            winner_name = "Гости"
        else:
            winner = "draw"
            winner_name = "Ничья"

        max_prob = max(home, draw, away)
        confidence = int(50 + max_prob * 40 + sim["stability"] * 20)
        expected_score = f"{round(home_xg)}-{round(away_xg)}"

        return {
            "winner": winner,
            "winner_name": winner_name,
            "winner_probability": round(max_prob * 100, 1),
            "expected_score": expected_score,
            "home_prob": round(home * 100, 1),
            "draw_prob": round(draw * 100, 1),
            "away_prob": round(away * 100, 1),
            "confidence": confidence,
            "top_scores": sim["top_scores"]
        }

    def _recommend(self, decision, btts, over25):
        # Простая логика: если вероятность победы > 55% и уверенность > 65% → ставим на победу
        if decision["winner_probability"] > 55 and decision["confidence"] > 65:
            if decision["winner"] == "home":
                return f"Победа {decision['winner_name']} (кф ~1.8)"
            elif decision["winner"] == "away":
                return f"Победа {decision['winner_name']} (кф ~2.1)"
        if btts > 0.55:
            return "Обе забьют (кф ~1.7)"
        if over25 > 0.55:
            return "Тотал больше 2.5 (кф ~1.9)"
        if decision["confidence"] < 50:
            return "Матч нестабилен — ставку не рекомендую"
        return "Нет явной рекомендации"

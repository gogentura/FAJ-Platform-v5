import time
import asyncio
import numpy as np
from app.api_client import APIClient
from app.rating_cache import update_rating
from app.standings_engine import StandingsEngine

class FAJCore:
    def __init__(self):
        self.version = "5.0.0"
        self.api_client = APIClient()
        self.standings = StandingsEngine()

    def predict_match(self, home_team, away_team, league="RPL"):
        start = time.time()
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

        if not home_stats:
            home_stats = {"avg_goals": 1.8, "avg_goals_conceded": 0.9, "avg_possession": 58, "avg_xg": 1.6}
        if not away_stats:
            away_stats = {"avg_goals": 1.4, "avg_goals_conceded": 1.2, "avg_possession": 52, "avg_xg": 1.3}

        home_passport = self._build_passport(home_stats)
        away_passport = self._build_passport(away_stats)
        
        # Обновляем кеш рейтингов
        home_rating = home_passport["attack"] + home_passport["defense"]
        away_rating = away_passport["attack"] + away_passport["defense"]
        update_rating(home_team, home_rating)
        update_rating(away_team, away_rating)

        home_xg, away_xg = self._calculate_xg(home_passport, away_passport, league)
        simulation = self._simulate(home_xg, away_xg)
        btts_prob = self._btts_prob(home_xg, away_xg)
        over25_prob = self._over25_prob(home_xg, away_xg)
        tactical = self._tactical_analysis(home_stats, away_stats, home_passport, away_passport)
        decision = self._decide(simulation, home_xg, away_xg)
        recommendation = self._recommend(decision, btts_prob, over25_prob)

        result = {
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

        # Получаем место в таблице (если есть данные и лига подходит)
        try:
            if league in ["EPL", "LaLiga", "Bundesliga", "SerieA", "Ligue1", "RPL", "UCL"]:
                # Синхронно получаем таблицу (можно добавить асинхронность позже)
                loop2 = asyncio.new_event_loop()
                asyncio.set_event_loop(loop2)
                home_standing = loop2.run_until_complete(self.standings.get_team_standing(home_team, league))
                away_standing = loop2.run_until_complete(self.standings.get_team_standing(away_team, league))
                loop2.close()
                if home_standing:
                    result["home_standing"] = home_standing
                if away_standing:
                    result["away_standing"] = away_standing
        except Exception as e:
            print(f"Ошибка получения таблицы: {e}")

        return result

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
        from math import exp
        p00 = exp(-(home_xg + away_xg))
        p10 = exp(-home_xg) * (1 - exp(-away_xg))
        p01 = exp(-away_xg) * (1 - exp(-home_xg))
        return round(1 - p00 - p10 - p01, 3)

    def _over25_prob(self, home_xg, away_xg):
        from math import exp
        prob = 0
        for h in range(4):
            for a in range(4):
                if h+a > 2:
                    prob += (exp(-home_xg) * home_xg**h) / (h+1) * (exp(-away_xg) * away_xg**a) / (a+1)
        return round(min(1.0, prob), 3)

    def _tactical_analysis(self, home_stats, away_stats, home_passport, away_passport):
        home_style = self._style_description(home_passport, home_stats)
        away_style = self._style_description(away_passport, away_stats)
        compatibility = 70 + abs(home_passport["attack"] - away_passport["defense"]) * 0.3
        compatibility = min(100, round(compatibility, 1))
        summary_parts = []
        summary_parts.append(f"Домашний стиль: {home_style}")
        summary_parts.append(f"Гостевой стиль: {away_style}")
        if compatibility > 75:
            summary_parts.append("Стили хорошо совместимы, ожидается открытая игра с моментами.")
        elif compatibility > 60:
            summary_parts.append("Стили умеренно совместимы, матч может быть тактическим.")
        else:
            summary_parts.append("Стили плохо совместимы, вероятна закрытая игра с малым количеством голов.")
        if home_stats.get("avg_goals", 0) > 1.5 and away_stats.get("avg_goals_conceded", 0) > 1.2:
            summary_parts.append("Ожидаем много голов, так как домашняя атака сильнее гостевой защиты.")
        elif home_stats.get("avg_goals", 0) < 1.0 and away_stats.get("avg_goals", 0) < 1.0:
            summary_parts.append("Обе команды мало забивают, вероятен низовой матч.")
        return {"summary": ". ".join(summary_parts)}

    def _style_description(self, passport, stats):
        attack = passport["attack"]
        defense = passport["defense"]
        control = passport["control"]
        if attack > 80 and control > 70:
            return "Атакующий контроль"
        elif attack > 80 and defense < 60:
            return "Атакующий без баланса"
        elif defense > 80 and attack < 65:
            return "Обороняющийся"
        elif control > 75 and defense > 70:
            return "Контроль с балансом"
        elif stats.get("avg_possession", 50) > 55 and stats.get("avg_goals", 0) > 1.5:
            return "Владение с атакой"
        else:
            return "Сбалансированный"

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
        return "Нет явной рекомендации. Матч может быть равным или неопределённым."

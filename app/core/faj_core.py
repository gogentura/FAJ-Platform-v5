import time
import numpy as np
from app.database import get_db

class FAJCore:
    def __init__(self):
        self.version = "5.1"

    def predict_match(self, home_team, away_team, league="RPL"):
        start = time.time()

        home_pass = self._load_passport(home_team)
        away_pass = self._load_passport(away_team)

        if not home_pass or not away_pass:
            home_xg = 1.3
            away_xg = 1.3
        else:
            hist_xg_home = home_pass.get("historical_xg_value") or 1.3
            hist_xg_away = away_pass.get("historical_xg_value") or 1.3
            home_attack = home_pass.get("attack", 70)
            home_defense = home_pass.get("defense", 70)
            home_form = home_pass.get("form_index", 70)
            away_attack = away_pass.get("attack", 70)
            away_defense = away_pass.get("defense", 70)
            away_form = away_pass.get("form_index", 70)

            home_xg = hist_xg_home * (1 + (home_attack - 70) / 200) * (1 + (home_form - 70) / 300)
            away_xg = hist_xg_away * (1 + (away_attack - 70) / 200) * (1 + (away_form - 70) / 300)

        home_adv = 1.12 if league == "RPL" else 1.15
        home_xg *= home_adv
        away_xg /= home_adv

        home_xg = max(0.2, min(4.0, home_xg))
        away_xg = max(0.2, min(4.0, away_xg))

        simulation = self._simulate(home_xg, away_xg)
        btts = self._btts_prob(home_xg, away_xg)
        over25 = self._over25_prob(home_xg, away_xg)
        decision = self._decide(simulation, home_xg, away_xg)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "league": league,
            "xg": {
                "historical": {"home": home_pass.get("historical_xg_value") if home_pass else None,
                               "away": away_pass.get("historical_xg_value") if away_pass else None},
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

    def _load_passport(self, team):
        conn = get_db()
        row = conn.execute("SELECT * FROM passports WHERE team = ?", (team,)).fetchone()
        conn.close()
        return dict(row) if row else None

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

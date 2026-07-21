import time
import numpy as np

class FAJCore:
    def __init__(self):
        self.version = "5.0.0"
    
    def predict_match(self, home_team, away_team, tournament="RPL"):
        start = time.time()
        xg_home = 1.3 + (len(home_team) % 5) * 0.1
        xg_away = 1.0 + (len(away_team) % 5) * 0.1
        home_prob = xg_home / (xg_home + xg_away + 0.3)
        away_prob = xg_away / (xg_home + xg_away + 0.3)
        draw_prob = 0.25
        total = home_prob + draw_prob + away_prob
        home_prob /= total
        draw_prob /= total
        away_prob /= total
        if home_prob > draw_prob and home_prob > away_prob:
            winner = "home"
            winner_name = home_team
        elif away_prob > home_prob and away_prob > draw_prob:
            winner = "away"
            winner_name = away_team
        else:
            winner = "draw"
            winner_name = "Ничья"
        expected_home = round(xg_home)
        expected_away = round(xg_away)
        max_prob = max(home_prob, draw_prob, away_prob)
        confidence = int(50 + max_prob * 40)
        result = {
            "home_team": home_team,
            "away_team": away_team,
            "tournament": tournament,
            "xg": {"home": round(xg_home, 2), "away": round(xg_away, 2)},
            "probabilities": {
                "home": round(home_prob * 100, 1),
                "draw": round(draw_prob * 100, 1),
                "away": round(away_prob * 100, 1)
            },
            "prediction": {
                "winner": winner,
                "winner_name": winner_name,
                "winner_probability": round(max_prob * 100, 1),
                "expected_score": f"{expected_home}-{expected_away}"
            },
            "confidence": confidence,
            "processing_time": round(time.time() - start, 2),
            "version": self.version
        }
        return result

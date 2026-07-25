# =====================================================
# FAJ Platform v6.4
# app/core/faj_core.py
#
# FAJ Core Engine
# =====================================================

import time
import numpy as np
from math import exp, factorial
from datetime import datetime

from app.passport_manager import (
    load_passport,
    get_team_by_alias,
    calculate_faj_rating   # новый импорт
)
from app.database import get_db


class FAJCore:

    VERSION = "6.4"

    LEAGUE_MEAN = 1.35
    HOME_ADVANTAGE = 1.08
    MAX_GOALS = 8
    SIMULATIONS = 10000

    def __init__(self):
        self.version = self.VERSION

    # ==================================================
    # UNIVERSAL API
    # ==================================================
    def predict(self, home_team, away_team, league="RPL"):
        return self.predict_match(home_team, away_team, league)

    # ==================================================
    # MAIN PREDICT (с поддержкой fixture_id)
    # ==================================================
    def predict_match(self, home_team, away_team, league="RPL"):
        started = time.time()

        # ---- Загружаем паспорта ----
        home = self.load_team(home_team)
        away = self.load_team(away_team)

        if home is None:
            raise Exception(f"Паспорт не найден: {home_team}")
        if away is None:
            raise Exception(f"Паспорт не найден: {away_team}")

        # ---- Ищем fixture_id (если есть) ----
        fixture_id = self.find_fixture(home_team, away_team, league)

        # ---- Вычисляем xG ----
        home_xg = self.calculate_xg(home, away, True)
        away_xg = self.calculate_xg(away, home, False)

        # ---- Симуляция ----
        simulation = self.simulate(home_xg, away_xg)
        decision = self.make_decision(simulation, home_xg, away_xg)

        # ---- Рейтинги ----
        home_rating = calculate_faj_rating(home)
        away_rating = calculate_faj_rating(away)

        # ---- Улучшенный confidence ----
        confidence = self.calculate_confidence(
            home_rating,
            away_rating,
            home_xg,
            away_xg,
            decision["winner_probability"]
        )

        # ---- Добавляем confidence и рейтинги в decision ----
        decision["confidence"] = confidence
        decision["home_rating"] = home_rating
        decision["away_rating"] = away_rating

        # ---- Формируем результат ----
        return {
            "version": self.version,
            "league": league,
            "home_team": home_team,
            "away_team": away_team,
            "fixture_id": fixture_id,                     # ✅ добавлено
            "home_rating": home_rating,                   # ✅ добавлено
            "away_rating": away_rating,                   # ✅ добавлено
            "xg": {
                "predicted": {
                    "home": round(home_xg, 2),
                    "away": round(away_xg, 2)
                }
            },
            "simulation": simulation,
            "decision": decision,
            "btts": self.btts_probability(home_xg, away_xg),
            "over25": self.over25_probability(home_xg, away_xg),
            "under25": self.under25_probability(home_xg, away_xg),
            "processing_time": round(time.time() - started, 3)
        }

    # ==================================================
    # FIND FIXTURE (поиск fixture_id)
    # ==================================================
    def find_fixture(self, home_team, away_team, league="RPL"):
        """Пытается найти id матча в таблице fixtures по командам и сегодняшней дате."""
        try:
            conn = get_db()
            cur = conn.cursor()
            today = datetime.now().date().isoformat()
            cur.execute(
                """
                SELECT id
                FROM fixtures
                WHERE LOWER(home_team) = LOWER(%s)
                  AND LOWER(away_team) = LOWER(%s)
                  AND league = %s
                  AND match_date >= %s
                  AND status = 'scheduled'
                ORDER BY match_date ASC
                LIMIT 1
                """,
                (home_team, away_team, league, today)
            )
            row = cur.fetchone()
            conn.close()
            return row["id"] if row else None
        except Exception:
            return None

    # ==================================================
    # LOAD TEAM (исправлено под team_passports)
    # ==================================================
    def load_team(self, team):
        real_team = get_team_by_alias(team)
        if not real_team:
            real_team = team

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM team_passports
            WHERE LOWER(team) = LOWER(%s)
            LIMIT 1
            """,
            (real_team,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    # ==================================================
    # УЛУЧШЕННЫЙ CONFIDENCE
    # ==================================================
    def calculate_confidence(self, home_rating, away_rating, home_xg, away_xg, win_prob):
        """
        Уверенность модели (0–100) с учётом:
        - вероятности победы (win_prob)
        - разницы рейтингов (rating_diff)
        - разницы xG (xg_diff)
        """
        rating_diff = home_rating - away_rating
        xg_diff = home_xg - away_xg

        # базовый уровень от вероятности
        base = win_prob

        # бонус за разницу рейтингов (макс. +10%)
        rating_bonus = min(10, max(-10, rating_diff / 2))

        # бонус за разницу xG (макс. +10%)
        xg_bonus = min(10, max(-10, xg_diff * 5))

        confidence = base + rating_bonus + xg_bonus

        # ограничиваем 0–100
        return round(max(0, min(100, confidence)), 1)

    # ==================================================
    # ОСТАЛЬНЫЕ МЕТОДЫ (calculate_xg, simulate, poisson, btts, over25, etc.)
    # ОНИ НЕ МЕНЯЮТСЯ
    # ==================================================
    def calculate_xg(self, team, opponent, home=True):
        # ... (без изменений)
        base_attack = float(team.get("xg_for") or self.LEAGUE_MEAN)
        base_defense = float(opponent.get("xg_against") or self.LEAGUE_MEAN)
        xg = base_attack * 0.55 + base_defense * 0.45

        attack = float(team.get("attack") or 70)
        xg *= (1 + (attack - 70) / 200)

        defence = float(opponent.get("defense") or 70)
        xg *= (1 + (70 - defence) / 250)

        form = float(team.get("form") or 70)
        xg *= (1 + (form - 70) / 300)

        control = float(team.get("control") or 70)
        xg *= (1 + (control - 70) / 500)

        efficiency = float(team.get("efficiency") or 70)
        xg *= (1 + (efficiency - 70) / 450)

        mentality = float(team.get("mentality") or 70)
        xg *= (1 + (mentality - 70) / 600)

        fitness = float(team.get("fitness") or 70)
        xg *= (1 + (fitness - 70) / 500)

        if home:
            xg *= self.HOME_ADVANTAGE

        injuries = float(team.get("injury_index") or 0)
        xg *= (1 - injuries / 500)

        fatigue = float(team.get("fatigue_index") or 0)
        xg *= (1 - fatigue / 500)

        transfer = float(team.get("transfer_index") or 0)
        xg *= (1 + transfer / 1000)

        return max(0.10, min(4.00, xg))

    def poisson(self, goals, xg):
        return exp(-xg) * (xg ** goals) / factorial(goals)

    def simulate(self, home_xg, away_xg):
        # Убираем фиксированный seed — теперь случайный
        np.random.seed(None)
        home_goals = np.random.poisson(home_xg, self.SIMULATIONS)
        away_goals = np.random.poisson(away_xg, self.SIMULATIONS)

        home_win = int(np.sum(home_goals > away_goals))
        draw = int(np.sum(home_goals == away_goals))
        away_win = int(np.sum(home_goals < away_goals))

        scores = {}
        for h, a in zip(home_goals, away_goals):
            h = min(int(h), self.MAX_GOALS)
            a = min(int(a), self.MAX_GOALS)
            key = (h, a)
            scores[key] = scores.get(key, 0) + 1

        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        top_scores = [
            {
                "score": f"{score[0]}-{score[1]}",
                "probability": round(count / self.SIMULATIONS * 100, 2)
            }
            for score, count in top
        ]

        return {
            "home_win_prob": round(home_win / self.SIMULATIONS, 3),
            "draw_prob": round(draw / self.SIMULATIONS, 3),
            "away_win_prob": round(away_win / self.SIMULATIONS, 3),
            "top_scores": top_scores
        }

    def btts_probability(self, home_xg, away_xg):
        p_home_zero = exp(-home_xg)
        p_away_zero = exp(-away_xg)
        return round(1 - p_home_zero - p_away_zero + p_home_zero * p_away_zero, 3)

    def over25_probability(self, home_xg, away_xg):
        prob = 0
        for h in range(self.MAX_GOALS + 1):
            for a in range(self.MAX_GOALS + 1):
                if h + a > 2:
                    prob += self.poisson(h, home_xg) * self.poisson(a, away_xg)
        return round(prob, 3)

    def under25_probability(self, home_xg, away_xg):
        return round(1 - self.over25_probability(home_xg, away_xg), 3)

    def over15_probability(self, home_xg, away_xg):
        prob = 0
        for h in range(self.MAX_GOALS + 1):
            for a in range(self.MAX_GOALS + 1):
                if h + a > 1:
                    prob += self.poisson(h, home_xg) * self.poisson(a, away_xg)
        return round(prob, 3)

    def over35_probability(self, home_xg, away_xg):
        prob = 0
        for h in range(self.MAX_GOALS + 1):
            for a in range(self.MAX_GOALS + 1):
                if h + a > 3:
                    prob += self.poisson(h, home_xg) * self.poisson(a, away_xg)
        return round(prob, 3)

    def make_decision(self, simulation, home_xg, away_xg):
        home = simulation["home_win_prob"]
        draw = simulation["draw_prob"]
        away = simulation["away_win_prob"]

        if home >= draw and home >= away:
            winner = "home"
            winner_name = "Хозяева"
        elif away >= draw and away >= home:
            winner = "away"
            winner_name = "Гости"
        else:
            winner = "draw"
            winner_name = "Ничья"

        win_prob = max(home, draw, away) * 100
        top_score = simulation["top_scores"][0]["score"] if simulation["top_scores"] else f"{round(home_xg)}-{round(away_xg)}"

        # confidence будет пересчитан позже в predict_match, но оставим на всякий случай
        return {
            "winner": winner,
            "winner_name": winner_name,
            "winner_probability": round(win_prob, 1),
            "home_probability": round(home * 100, 1),
            "draw_probability": round(draw * 100, 1),
            "away_probability": round(away * 100, 1),
            "expected_score": top_score,
            "btts": self.btts_probability(home_xg, away_xg),
            "over15": self.over15_probability(home_xg, away_xg),
            "over25": self.over25_probability(home_xg, away_xg),
            "under25": self.under25_probability(home_xg, away_xg),
            "over35": self.over35_probability(home_xg, away_xg)
        }

    # ==================================================
    # INFO
    # ==================================================
    def info(self):
        return {
            "engine": "FAJ Engine",
            "version": self.version,
            "simulations": self.SIMULATIONS,
            "league_mean": self.LEAGUE_MEAN,
            "home_advantage": self.HOME_ADVANTAGE
        }

# =====================================================
# FAJ Platform v6.3
# FAJ Core
# =====================================================

import time
import numpy as np

from math import exp
from math import factorial

from app.passport_manager import load_passport


class FAJCore:

    VERSION = "6.3"

    LEAGUE_MEAN = 1.35

    HOME_ADVANTAGE = 1.08

    MAX_GOALS = 8

    SIMULATIONS = 10000

    # ==============================================

    def __init__(self):

        self.version = self.VERSION

    # ==============================================
    # UNIVERSAL API
    # ==============================================

    def predict(

        self,

        home_team,

        away_team,

        league="RPL"

    ):

        return self.predict_match(

            home_team,

            away_team,

            league

        )

    # ==============================================
    # MAIN
    # ==============================================

    def predict_match(

        self,

        home_team,

        away_team,

        league="RPL"

    ):

        started = time.time()

        home = load_passport(home_team)

        away = load_passport(away_team)

        if home is None:

            raise Exception(

                f"Паспорт не найден: {home_team}"

            )

        if away is None:

            raise Exception(

                f"Паспорт не найден: {away_team}"

            )

        home_xg = self.calculate_xg(

            home,

            away,

            True

        )

        away_xg = self.calculate_xg(

            away,

            home,

            False

        )

        simulation = self.simulate(

            home_xg,

            away_xg

        )

        decision = self.make_decision(

            simulation,

            home_xg,

            away_xg

        )

        return {

            "version": self.version,

            "league": league,

            "home_team": home_team,

            "away_team": away_team,

            "home_xg": round(home_xg, 2),

            "away_xg": round(away_xg, 2),

            "simulation": simulation,

            "decision": decision,

            "processing_time":

                round(

                    time.time() - started,

                    3

                )

        }

    # ==============================================
    # XG MODEL
    # FAJ Platform v6.3
    # ==============================================

    def calculate_xg(

        self,

        team,

        opponent,

        home=True

    ):

        # -------------------------
        # Базовый xG
        # -------------------------

        base_attack = (

            float(team.get("xg_for") or self.LEAGUE_MEAN)

        )

        base_defense = (

            float(opponent.get("xg_against") or self.LEAGUE_MEAN)

        )

        xg = (

            base_attack * 0.55 +

            base_defense * 0.45

        )

        # -------------------------
        # ATTACK
        # -------------------------

        attack = float(team.get("attack") or 70)

        xg *= (

            1 +

            (attack - 70) / 200

        )

        # -------------------------
        # OPPONENT DEFENCE
        # -------------------------

        defence = float(opponent.get("defense") or 70)

        xg *= (

            1 +

            (70 - defence) / 250

        )

        # -------------------------
        # FORM
        # -------------------------

        form = float(team.get("form") or 70)

        xg *= (

            1 +

            (form - 70) / 300

        )

        # -------------------------
        # CONTROL
        # -------------------------

        control = float(team.get("control") or 70)

        xg *= (

            1 +

            (control - 70) / 500

        )

        # -------------------------
        # EFFICIENCY
        # -------------------------

        efficiency = float(

            team.get("efficiency") or 70

        )

        xg *= (

            1 +

            (efficiency - 70) / 450

        )

        # -------------------------
        # MENTALITY
        # -------------------------

        mentality = float(

            team.get("mentality") or 70

        )

        xg *= (

            1 +

            (mentality - 70) / 600

        )

        # -------------------------
        # FITNESS
        # -------------------------

        fitness = float(

            team.get("fitness") or 70

        )

        xg *= (

            1 +

            (fitness - 70) / 500

        )

        # -------------------------
        # HOME BONUS
        # -------------------------

        if home:

            xg *= self.HOME_ADVANTAGE

        # -------------------------
        # INJURIES
        # -------------------------

        injuries = float(

            team.get("injury_index") or 0

        )

        xg *= (

            1 -

            injuries / 500

        )

        # -------------------------
        # FATIGUE
        # -------------------------

        fatigue = float(

            team.get("fatigue_index") or 0

        )

        xg *= (

            1 -

            fatigue / 500

        )

        # -------------------------
        # TRANSFERS
        # -------------------------

        transfer = float(

            team.get("transfer_index") or 0

        )

        xg *= (

            1 +

            transfer / 1000

        )

        # -------------------------
        # LIMITS
        # -------------------------

        xg = max(

            0.10,

            min(

                4.00,

                xg

            )

        )

        return xg

    # ==============================================
    # POISSON
    # ==============================================

    def poisson(self, goals, xg):
        return (
            exp(-xg)
            *
            (xg ** goals)
            /
            factorial(goals)
        )

    # ==============================================
    # MONTE CARLO
    # ==============================================

    def simulate(
        self,
        home_xg,
        away_xg
    ):
        np.random.seed(42)
        home_goals = np.random.poisson(
            home_xg,
            self.SIMULATIONS
        )
        away_goals = np.random.poisson(
            away_xg,
            self.SIMULATIONS
        )
        home_win = int(
            np.sum(
                home_goals > away_goals
            )
        )
        draw = int(
            np.sum(
                home_goals == away_goals
            )
        )
        away_win = int(
            np.sum(
                home_goals < away_goals
            )
        )
        scores = {}
        for h, a in zip(
            home_goals,
            away_goals
        ):
            h = min(
                int(h),
                self.MAX_GOALS
            )
            a = min(
                int(a),
                self.MAX_GOALS
            )
            key = (h, a)
            scores[key] = (
                scores.get(key, 0)
                + 1
            )
        top = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        top_scores = []
        for score, count in top:
            top_scores.append(
                {
                    "score":
                        f"{score[0]}-{score[1]}",
                    "probability":
                        round(
                            count
                            /
                            self.SIMULATIONS
                            *
                            100,
                            2
                        )
                }
            )
        return {
            "home_win_prob":
                round(
                    home_win
                    /
                    self.SIMULATIONS,
                    3
                ),
            "draw_prob":
                round(
                    draw
                    /
                    self.SIMULATIONS,
                    3
                ),
            "away_win_prob":
                round(
                    away_win
                    /
                    self.SIMULATIONS,
                    3
                ),
            "top_scores":
                top_scores
        }

    # ==============================================
    # BOTH TEAMS TO SCORE
    # ==============================================

    def btts_probability(
        self,
        home_xg,
        away_xg
    ):
        p_home_zero = exp(-home_xg)
        p_away_zero = exp(-away_xg)
        probability = (
            1
            - p_home_zero
            - p_away_zero
            + p_home_zero * p_away_zero
        )
        return round(probability, 3)

    # ==============================================
    # OVER 2.5
    # ==============================================

    def over25_probability(
        self,
        home_xg,
        away_xg
    ):
        probability = 0
        for h in range(
            self.MAX_GOALS + 1
        ):
            for a in range(
                self.MAX_GOALS + 1
            ):
                if h + a > 2:
                    probability += (
                        self.poisson(
                            h,
                            home_xg
                        )
                        *
                        self.poisson(
                            a,
                            away_xg
                        )
                    )
        return round(probability, 3)

    # ==============================================
    # UNDER 2.5
    # ==============================================

    def under25_probability(
        self,
        home_xg,
        away_xg
    ):
        return round(
            1 -
            self.over25_probability(
                home_xg,
                away_xg
            ),
            3
        )

    # ==============================================
    # OVER 1.5
    # ==============================================

    def over15_probability(
        self,
        home_xg,
        away_xg
    ):
        probability = 0
        for h in range(
            self.MAX_GOALS + 1
        ):
            for a in range(
                self.MAX_GOALS + 1
            ):
                if h + a > 1:
                    probability += (
                        self.poisson(h, home_xg)
                        *
                        self.poisson(a, away_xg)
                    )
        return round(probability, 3)

    # ==============================================
    # OVER 3.5
    # ==============================================

    def over35_probability(
        self,
        home_xg,
        away_xg
    ):
        probability = 0
        for h in range(
            self.MAX_GOALS + 1
        ):
            for a in range(
                self.MAX_GOALS + 1
            ):
                if h + a > 3:
                    probability += (
                        self.poisson(h, home_xg)
                        *
                        self.poisson(a, away_xg)
                    )
        return round(probability, 3)

    # ==============================================
    # FINAL DECISION
    # ==============================================

    def make_decision(

        self,

        simulation,

        home_xg,

        away_xg

    ):

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

        confidence = int(
            50 + max(home, draw, away) * 40
        )

        top_score = "1-1"

        if simulation["top_scores"]:

            top_score = simulation["top_scores"][0]["score"]

        return {

            "winner": winner,

            "winner_name": winner_name,

            "winner_probability":

                round(

                    max(home, draw, away) * 100,

                    1

                ),

            "home_probability":

                round(home * 100, 1),

            "draw_probability":

                round(draw * 100, 1),

            "away_probability":

                round(away * 100, 1),

            "expected_score": top_score,

            "confidence": confidence,

            "btts":

                self.btts_probability(

                    home_xg,

                    away_xg

                ),

            "over15":

                self.over15_probability(

                    home_xg,

                    away_xg

                ),

            "over25":

                self.over25_probability(

                    home_xg,

                    away_xg

                ),

            "under25":

                self.under25_probability(

                    home_xg,

                    away_xg

                ),

            "over35":

                self.over35_probability(

                    home_xg,

                    away_xg

                )

        }


    # ==============================================
    # VERSION
    # ==============================================

    def info(self):

        return {

            "engine": "FAJ Engine",

            "version": self.version,

            "simulations": self.SIMULATIONS,

            "league_mean": self.LEAGUE_MEAN,

            "home_advantage": self.HOME_ADVANTAGE

        }

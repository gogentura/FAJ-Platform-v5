#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0

Prediction Engine

Отвечает за математический прогноз:

Passport
   ↓
FAJ Rating
   ↓
xG Model
   ↓
Poisson
   ↓
Monte Carlo
   ↓
Probabilities
   ↓
Scores
=====================================================
"""


import hashlib
import numpy as np

from math import exp, factorial


from app.passports.loader import load_passport
from app.passports.passport_schema import calculate_faj_rating


from app.models.xg_model import XGModel
from app.models.poisson_model import PoissonModel



class PredictionEngine:


    VERSION = "12.0"


    LEAGUE_MEAN = 1.35

    HOME_ADVANTAGE = 1.08

    MAX_GOALS = 8

    SIMULATIONS = 10000



    def __init__(self):

        self.xg_model = XGModel()

        self.poisson = PoissonModel()



    # ================================================
    # SAFE VALUE
    # ================================================

    def safe(
        self,
        value,
        default=70
    ):

        try:

            if value is None:
                return default

            return float(value)

        except:

            return default



    # ================================================
    # LOAD TEAM PASSPORT
    # ================================================

    def load_team(
        self,
        team
    ):


        passport = load_passport(team)


        if passport:

            return passport



        raise Exception(
            f"Паспорт команды не найден: {team}"
        )



    # ================================================
    # RANDOM SEED
    # ================================================

    def build_seed(
        self,
        home,
        away,
        league
    ):


        key = (
            f"{home}|{away}|{league}"
        )


        value = hashlib.md5(
            key.encode()
        ).hexdigest()


        return int(
            value[:8],
            16
        )



    # ================================================
    # XG CALCULATION
    # ================================================

    def calculate_xg(
        self,
        team,
        opponent,
        home=True
    ):


        xg = self.xg_model.calculate(

            team,

            opponent

        )


        if home:

            xg *= self.HOME_ADVANTAGE



        return round(

            max(
                0.10,
                min(
                    4.0,
                    xg
                )
            ),

            3

        )



    # ================================================
    # MONTE CARLO SIMULATION
    # ================================================

    def simulate(

        self,

        home,

        away,

        league,

        home_xg,

        away_xg

    ):



        rng = np.random.default_rng(

            self.build_seed(
                home,
                away,
                league
            )

        )


        home_goals = rng.poisson(

            home_xg,

            self.SIMULATIONS

        )


        away_goals = rng.poisson(

            away_xg,

            self.SIMULATIONS

        )



        scores = {}


        home_win = 0

        draw = 0

        away_win = 0



        for h,a in zip(
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


            scores[(h,a)] = scores.get(
                (h,a),
                0
            ) + 1



            if h>a:

                home_win +=1


            elif h==a:

                draw +=1


            else:

                away_win +=1




        top_scores = sorted(

            scores.items(),

            key=lambda x:x[1],

            reverse=True

        )



        return {


            "home_probability":
                round(
                    home_win/self.SIMULATIONS*100,
                    2
                ),


            "draw_probability":
                round(
                    draw/self.SIMULATIONS*100,
                    2
                ),


            "away_probability":
                round(
                    away_win/self.SIMULATIONS*100,
                    2
                ),



            "top_scores":

                [

                    {

                    "score":
                        f"{s[0]}-{s[1]}",

                    "probability":
                        round(
                            c/self.SIMULATIONS*100,
                            2
                        )

                    }

                    for s,c in top_scores[:10]

                ]

        }



    # ================================================
    # MAIN PREDICT
    # ================================================

    def predict(

        self,

        home_team,

        away_team,

        league="RPL"

    ):


        home = self.load_team(
            home_team
        )


        away = self.load_team(
            away_team
        )



        home_rating = calculate_faj_rating(
            home
        )


        away_rating = calculate_faj_rating(
            away
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

            home_team,

            away_team,

            league,

            home_xg,

            away_xg

        )



        return {


            "version":
                self.VERSION,


            "home_team":
                home_team,


            "away_team":
                away_team,


            "ratings":

            {

                "home":
                    round(home_rating,1),

                "away":
                    round(away_rating,1)

            },


            "xg":

            {

                "home":
                    home_xg,

                "away":
                    away_xg

            },


            "simulation":
                simulation


        }

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Match Engine
"""

import math
import random
from collections import Counter


class FAJMatchEngine:


    def __init__(self):

        self.league_mean_xg = 1.35
        self.home_advantage = 1.12
        self.simulation_count = 10000



    def calculate_team_power(self, passport):

        weights = {

            "attack":0.18,
            "defense":0.18,
            "control":0.15,
            "efficiency":0.12,
            "mentality":0.10,
            "tempo":0.05,
            "press":0.05,
            "transition":0.05,
            "flexibility":0.05,
            "coach":0.04,
            "form":0.03

        }


        power = 0


        for key, weight in weights.items():

            try:

                power += float(
                    passport.get(key,50)
                ) * weight

            except:

                power += 50 * weight


        return round(power,2)



    def calculate_xg(
        self,
        home,
        away
    ):


        home_attack = float(
            home.get("attack",50)
        ) / 100


        away_attack = float(
            away.get("attack",50)
        ) / 100


        home_def = float(
            home.get("defense",50)
        ) / 100


        away_def = float(
            away.get("defense",50)
        ) / 100



        xg_home = (
            self.league_mean_xg *
            (home_attack / max(away_def,0.1)) *
            self.home_advantage
        )


        xg_away = (
            self.league_mean_xg *
            (away_attack / max(home_def,0.1))
        )


        return (
            round(min(max(xg_home,0.1),4),2),
            round(min(max(xg_away,0.1),4),2)
        )



    def poisson(self, x):

        L = math.exp(-x)

        k = 0
        p = 1


        while p > L:

            k += 1
            p *= random.random()


        return k-1



    def simulate(
        self,
        xg_home,
        xg_away
    ):


        scores=[]


        for _ in range(self.simulation_count):

            scores.append(
                (
                    self.poisson(xg_home),
                    self.poisson(xg_away)
                )
            )


        home=sum(
            1 for h,a in scores if h>a
        )

        draw=sum(
            1 for h,a in scores if h==a
        )

        away=sum(
            1 for h,a in scores if h<a
        )


        counter=Counter(scores)


        top=[]

        for score,count in counter.most_common(5):

            top.append({

                "score":
                    f"{score[0]}:{score[1]}",

                "prob":
                    round(
                        count/self.simulation_count*100,
                        1
                    )

            })


        return {

            "P1":
                round(home/self.simulation_count*100,1),

            "PX":
                round(draw/self.simulation_count*100,1),

            "P2":
                round(away/self.simulation_count*100,1),

            "top_scores":
                top

        }



    def predict_match(
        self,
        home_passport,
        away_passport
    ):


        home_power = self.calculate_team_power(
            home_passport
        )


        away_power = self.calculate_team_power(
            away_passport
        )


        xg_home,xg_away = self.calculate_xg(
            home_passport,
            away_passport
        )


        simulation = self.simulate(
            xg_home,
            xg_away
        )



        return {


            "home_power":
                home_power,


            "away_power":
                away_power,


            "xg_home":
                xg_home,


            "xg_away":
                xg_away,


            "home_win":
                simulation["P1"],


            "draw":
                simulation["PX"],


            "away_win":
                simulation["P2"],


            "top_scores":
                simulation["top_scores"],


            "confidence":
                round(
                    max(
                        simulation["P1"],
                        simulation["PX"],
                        simulation["P2"]
                    ),
                    1
                ),


            "risk":
                "Средний"


        }

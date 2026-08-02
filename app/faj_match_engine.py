#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0

Match Prediction Engine + Brain Integration

"""

import math
import random

from typing import Dict, Tuple
from collections import Counter

from app.brain.brain_manager import FAJBrainManager



class FAJMatchEngine:


    def __init__(self):

        self.league_mean_xg = 1.35

        self.home_advantage = 1.12

        self.simulation_count = 10000


        self.weights = {

            "attack": 0.18,
            "defense": 0.18,
            "control": 0.15,
            "efficiency": 0.12,
            "mentality": 0.10,
            "tempo": 0.05,
            "press": 0.05,
            "transition": 0.05,
            "flexibility": 0.05,
            "coach": 0.04,
            "form": 0.03

        }


        # подключаем мозг

        self.brain = FAJBrainManager()



    # =====================================================
    # СИЛА КОМАНДЫ
    # =====================================================

    def calculate_team_power(
        self,
        passport: Dict
    ) -> float:


        power = 0


        for key, weight in self.weights.items():

            value = passport.get(
                key,
                50
            )

            try:

                power += float(value) * weight

            except:

                power += 50 * weight


        return round(
            power,
            2
        )



    # =====================================================
    # xG
    # =====================================================

    def calculate_xg(
        self,
        home_passport,
        away_passport
    ) -> Tuple[float,float]:


        home_attack = float(
            home_passport.get(
                "attack",
                50
            )
        ) / 100


        away_defense = float(
            away_passport.get(
                "defense",
                50
            )
        ) / 100


        away_attack = float(
            away_passport.get(
                "attack",
                50
            )
        ) / 100


        home_defense = float(
            home_passport.get(
                "defense",
                50
            )
        ) / 100



        home_form = float(
            home_passport.get(
                "form",
                50
            )
        ) / 100


        away_form = float(
            away_passport.get(
                "form",
                50
            )
        ) / 100



        xg_home = (
            self.league_mean_xg *
            (home_attack / max(away_defense,0.01)) *
            (0.5+0.5*home_form) *
            self.home_advantage
        )


        xg_away = (
            self.league_mean_xg *
            (away_attack / max(home_defense,0.01)) *
            (0.5+0.5*away_form)
        )


        xg_home=max(
            0.10,
            min(
                4,
                xg_home
            )
        )


        xg_away=max(
            0.10,
            min(
                4,
                xg_away
            )
        )


        return (
            round(xg_home,2),
            round(xg_away,2)
        )



    # =====================================================
    # POISSON
    # =====================================================

    def poisson_sample(
        self,
        xg
    ):

        L=math.exp(-xg)

        k=0

        p=1


        while p>L:

            k+=1

            p*=random.random()


        return k-1



    # =====================================================
    # MONTE CARLO
    # =====================================================

    def monte_carlo_simulation(
        self,
        xg_home,
        xg_away
    ):


        results=[]


        for _ in range(
            self.simulation_count
        ):

            results.append(
                (
                    self.poisson_sample(xg_home),
                    self.poisson_sample(xg_away)
                )
            )



        home=sum(
            1 for h,a in results
            if h>a
        )


        draw=sum(
            1 for h,a in results
            if h==a
        )


        away=sum(
            1 for h,a in results
            if h<a
        )


        scores=Counter(results)


        return {

            "P1":
                home/self.simulation_count,

            "PX":
                draw/self.simulation_count,

            "P2":
                away/self.simulation_count,


            "top_scores":[

                {
                    "score":f"{h}:{a}",

                    "prob":round(
                        c/self.simulation_count*100,
                        1
                    )
                }

                for (h,a),c
                in scores.most_common(5)

            ]

        }



    # =====================================================
    # ГЛАВНЫЙ ПРОГНОЗ
    # =====================================================

    def predict_match(
        self,
        home_passport,
        away_passport,
        match_name=None
    ):


        xg_home,xg_away = self.calculate_xg(
            home_passport,
            away_passport
        )


        simulation=self.monte_carlo_simulation(
            xg_home,
            xg_away
        )



        result={

            "xg_home":
                xg_home,

            "xg_away":
                xg_away,


            "home_win":
                round(simulation["P1"]*100,1),


            "draw":
                round(simulation["PX"]*100,1),


            "away_win":
                round(simulation["P2"]*100,1),


            "top_scores":
                simulation["top_scores"]

        }



        # =========================================
        # запись в память FAJ
        # =========================================

        if match_name:


            self.brain.save_prediction(

                match_name,

                result

            )


        return result

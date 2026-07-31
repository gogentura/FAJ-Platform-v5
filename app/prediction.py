#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0

Prediction Engine

Football Analytics Journal

Pipeline:

Passport
   ↓
Strength Model
   ↓
xG Engine
   ↓
Poisson
   ↓
Expert Layer
   ↓
Prediction

"""


import math
from itertools import product



class FAJPrediction:



    def __init__(
        self,
        passport_manager
    ):


        self.version = "10.0"

        self.passport = passport_manager



    # =====================================
    # TEAM DATA
    # =====================================


    def get_team(
        self,
        name
    ):


        if not self.passport:

            return None



        for team in self.passport.passports:


            if team.get(
                "team"
            ) == name:

                return team



        return None



    # =====================================
    # xG ENGINE
    # =====================================


    def calculate_xg(
        self,
        home,
        away
    ):


        home_attack = float(
            home.get(
                "attack",
                70
            )
        )


        away_attack = float(
            away.get(
                "attack",
                70
            )
        )



        home_def = float(
            home.get(
                "defense",
                70
            )
        )


        away_def = float(
            away.get(
                "defense",
                70
            )
        )



        home_form = float(
            home.get(
                "form",
                70
            )
        )


        away_form = float(
            away.get(
                "form",
                70
            )
        )



        home_advantage = 1.12



        xg_home = (

            1.35

            *

            (1 + (home_attack - 70) / 200)

            *

            (1 + (70 - away_def) / 200)

            *

            (1 + (home_form - 70) / 300)

            *

            home_advantage

        )



        xg_away = (

            1.15

            *

            (1 + (away_attack - 70) / 200)

            *

            (1 + (70 - home_def) / 200)

            *

            (1 + (away_form - 70) / 300)

        )



        return {


            "home_xg":

            round(
                xg_home,
                2
            ),


            "away_xg":

            round(
                xg_away,
                2
            )


        }




    # =====================================
    # POISSON
    # =====================================


    def poisson(
        self,
        value,
        goals
    ):


        return (

            math.pow(
                value,
                goals
            )

            *

            math.exp(
                -value
            )

            /

            math.factorial(
                goals
            )

        )



    # =====================================
    # SCORE MATRIX
    # =====================================


    def score_matrix(
        self,
        home_xg,
        away_xg
    ):


        results = []



        for h,a in product(

            range(0,6),

            range(0,6)

        ):


            probability = (

                self.poisson(
                    home_xg,
                    h
                )

                *

                self.poisson(
                    away_xg,
                    a
                )

            )


            results.append({

                "score":

                f"{h}:{a}",


                "probability":

                round(
                    probability*100,
                    2
                )

            })



        results.sort(

            key=lambda x:
            x["probability"],

            reverse=True

        )



        return results[:5]



    # =====================================
    # FINAL P1 X P2
    # =====================================


    def outcome_probability(
        self,
        matrix
    ):


        p1 = 0

        x = 0

        p2 = 0



        for item in matrix:


            score = item["score"]


            h,a = map(

                int,

                score.split(":")

            )



            if h>a:

                p1 += item["probability"]



            elif h==a:

                x += item["probability"]



            else:

                p2 += item["probability"]



        return {


            "P1":

            round(p1,1),


            "X":

            round(x,1),


            "P2":

            round(p2,1)

        }



    # =====================================
    # MAIN
    # =====================================


    def predict(
        self,
        home_name,
        away_name
    ):


        home = self.get_team(
            home_name
        )


        away = self.get_team(
            away_name
        )



        if not home or not away:


            return {

                "error":

                "Команда не найдена"

            }




        xg = self.calculate_xg(

            home,

            away

        )



        scores = self.score_matrix(

            xg["home_xg"],

            xg["away_xg"]

        )



        outcome = self.outcome_probability(

            scores

        )



        confidence = max(

            outcome.values()

        )



        return {


            "home":

            home_name,


            "away":

            away_name,


            "xg":

            xg,


            "scores":

            scores,


            "probability":

            outcome,


            "confidence":

            round(

                confidence,

                1

            ),


            "version":

            self.version

        }

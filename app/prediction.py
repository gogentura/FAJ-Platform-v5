#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0.1

Prediction Engine

Passport
    ↓
xG Engine
    ↓
Poisson Matrix
    ↓
Outcome Probability
    ↓
Final Prediction

"""


import math
from itertools import product



class FAJPrediction:


    def __init__(self, passport_manager):

        self.version = "10.0.1"

        self.passport = passport_manager



    # =====================================
    # FIND TEAM
    # =====================================


    def get_team(self, name):


        if not self.passport:

            return None



        for team in self.passport.passports:


            if team.get("team") == name:

                return team



        return None



    # =====================================
    # xG ENGINE
    # =====================================


    def calculate_xg(self, home, away):


        home_attack = float(
            home.get("attack", 70)
        )

        away_attack = float(
            away.get("attack", 70)
        )


        home_def = float(
            home.get("defense", 70)
        )

        away_def = float(
            away.get("defense", 70)
        )


        home_form = float(
            home.get("form", 70)
        )

        away_form = float(
            away.get("form", 70)
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
                min(xg_home,4),
                2
            ),


            "away_xg":
            round(
                min(xg_away,4),
                2
            )

        }




    # =====================================
    # POISSON
    # =====================================


    def poisson(self, xg, goals):


        return (

            math.pow(xg, goals)

            *

            math.exp(-xg)

            /

            math.factorial(goals)

        )



    # =====================================
    # FULL SCORE MATRIX
    # =====================================


    def score_matrix(self, home_xg, away_xg):


        matrix = []



        for home_goals, away_goals in product(

            range(0,8),

            range(0,8)

        ):


            probability = (

                self.poisson(
                    home_xg,
                    home_goals
                )

                *

                self.poisson(
                    away_xg,
                    away_goals
                )

            )



            matrix.append({

                "score":
                f"{home_goals}:{away_goals}",


                "probability":
                probability

            })



        matrix.sort(

            key=lambda x:
            x["probability"],

            reverse=True

        )



        return matrix



    # =====================================
    # P1 X P2
    # =====================================


    def outcome_probability(self, matrix):


        p1 = 0

        draw = 0

        p2 = 0



        for item in matrix:


            home, away = map(

                int,

                item["score"].split(":")

            )


            value = item["probability"]



            if home > away:


                p1 += value



            elif home == away:


                draw += value



            else:


                p2 += value



        total = (

            p1 +

            draw +

            p2

        )



        return {


            "P1":

            round(
                p1 / total * 100,
                1
            ),


            "X":

            round(
                draw / total * 100,
                1
            ),


            "P2":

            round(
                p2 / total * 100,
                1
            )


        }




    # =====================================
    # MAIN PREDICTION
    # =====================================


    def predict(self, home_name, away_name):


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



        matrix = self.score_matrix(

            xg["home_xg"],

            xg["away_xg"]

        )



        probabilities = self.outcome_probability(

            matrix

        )



        top_scores = []



        for item in matrix[:5]:


            top_scores.append({

                "score":

                item["score"],


                "probability":

                round(
                    item["probability"]*100,
                    2
                )

            })



        confidence = max(

            probabilities.values()

        )



        return {


            "home":

            home_name,


            "away":

            away_name,


            "xg":

            xg,


            "scores":

            top_scores,


            "probability":

            probabilities,


            "confidence":

            round(
                confidence,
                1
            ),


            "version":

            self.version

        }

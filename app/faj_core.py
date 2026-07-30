#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.5

FAJ Core

Главный аналитический модуль.

Цикл:

Team Passport
        ↓
Strength Calculation
        ↓
xG Engine
        ↓
Probability Engine
        ↓
Prediction
        ↓
Memory Learning

"""


from datetime import datetime
import math


from app.passport_updater import PassportUpdater
from app.memory_engine import MemoryEngine



class FAJCore:


    def __init__(self):

        self.version = "9.5"

        self.passport = PassportUpdater()

        self.memory = MemoryEngine()


        # базовые параметры FAJ

        self.LEAGUE_XG = 1.35

        self.HOME_ADVANTAGE = 1.12



    # =================================================
    # SEARCH TEAM
    # =================================================


    def get_team(
        self,
        name
    ):

        return self.passport.find_team(
            name
        )



    # =================================================
    # MAIN PREDICTION
    # =================================================


    def predict_match(
        self,
        home,
        away
    ):


        home_team = self.get_team(
            home
        )

        away_team = self.get_team(
            away
        )


        if not home_team or not away_team:


            return {

                "error":
                "Команда не найдена"

            }



        # -----------------------------
        # Passport values
        # -----------------------------


        attack_home = self.num(
            home_team.get(
                "attack"
            )
        )


        defense_home = self.num(
            home_team.get(
                "defense"
            )
        )


        form_home = self.num(
            home_team.get(
                "form"
            )
        )



        attack_away = self.num(
            away_team.get(
                "attack"
            )
        )


        defense_away = self.num(
            away_team.get(
                "defense"
            )
        )


        form_away = self.num(
            away_team.get(
                "form"
            )
        )



        # -----------------------------
        # xG ENGINE v9.5
        # -----------------------------


        home_attack_factor = (
            1 +
            (attack_home - 75)
            /
            200
        )


        away_attack_factor = (
            1 +
            (attack_away - 75)
            /
            200
        )


        home_def_factor = (
            1 -
            (defense_away - 75)
            /
            250
        )


        away_def_factor = (
            1 -
            (defense_home - 75)
            /
            250
        )


        home_form_factor = (
            1 +
            (form_home - 75)
            /
            300
        )


        away_form_factor = (
            1 +
            (form_away - 75)
            /
            300
        )



        xg_home = (

            self.LEAGUE_XG *

            home_attack_factor *

            home_def_factor *

            home_form_factor *

            self.HOME_ADVANTAGE

        )



        xg_away = (

            self.LEAGUE_XG *

            away_attack_factor *

            away_def_factor *

            away_form_factor

        )



        # ограничение

        xg_home = round(
            max(
                0.1,
                min(
                    xg_home,
                    4.0
                )
            ),
            2
        )


        xg_away = round(
            max(
                0.1,
                min(
                    xg_away,
                    4.0
                )
            ),
            2
        )



        # -----------------------------
        # Probability Engine
        # -----------------------------


        strength_home = (

            attack_home +

            defense_home +

            form_home

        )


        strength_away = (

            attack_away +

            defense_away +

            form_away

        )



        total = (

            strength_home +

            strength_away

        )



        p1 = round(
            strength_home / total * 100,
            1
        )


        p2 = round(
            strength_away / total * 100,
            1
        )


        draw = round(
            100 - p1 - p2,
            1
        )



        # -----------------------------
        # SCORE MODEL
        # -----------------------------


        score = self.predict_score(
            xg_home,
            xg_away
        )



        return {


            "FAJ Version":
            self.version,


            "match":

            f"{home} - {away}",



            "xG":

            {

                "home":
                xg_home,

                "away":
                xg_away

            },



            "probability":

            {

                "P1":
                p1,

                "X":
                draw,

                "P2":
                p2

            },



            "prediction":

            score,


            "confidence":

            round(
                max(
                    p1,
                    draw,
                    p2
                )
                /
                100,
                2
            )

        }



    # =================================================
    # SCORE
    # =================================================


    def predict_score(
        self,
        home_xg,
        away_xg
    ):


        home_goals = round(
            home_xg
        )


        away_goals = round(
            away_xg
        )


        return (

            f"{home_goals}:"
            f"{away_goals}"

        )



    # =================================================
    # NUMBER
    # =================================================


    def num(
        self,
        value
    ):

        try:

            return float(
                value
            )

        except:

            return 70



    # =================================================
    # STATUS
    # =================================================


    def status(self):


        print(
            "======================"
        )

        print(
            "FAJ CORE",
            self.version
        )


        print(
            "Teams:",
            len(
                self.passport.passports
            )
        )


        print(
            "Memory:",
            len(
                self.memory.memory
            )
        )


        print(
            "======================"
        )




if __name__ == "__main__":


    faj = FAJCore()


    faj.status()



    result = faj.predict_match(

        "Динамо М",

        "Крылья Советов"

    )


    print(result)

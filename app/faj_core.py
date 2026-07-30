#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.3

FAJ Core

Главный управляющий модуль.

Цикл:

Team Passport
        ↓
FAJ Rating
        ↓
xG Engine
        ↓
Poisson
        ↓
Expert Layer
        ↓
Prediction
        ↓
Memory / Calibration


"""


from datetime import datetime


from app.passport_updater import PassportUpdater
from app.memory_engine import MemoryEngine



class FAJCore:


    def __init__(self):

        self.version = "9.3"


        self.passport = PassportUpdater()

        self.memory = MemoryEngine()



        # FAJ constants

        self.LEAGUE_XG = 1.35

        self.HOME_ADVANTAGE = 1.12



    # =================================================
    # TEAM
    # =================================================


    def get_team(
        self,
        name
    ):


        return self.passport.find_team(
            name
        )



    # =================================================
    # PREDICTION ENGINE
    # =================================================


    def predict_match(
        self,
        home,
        away
    ):


        home_passport = self.get_team(
            home
        )


        away_passport = self.get_team(
            away
        )


        if not home_passport or not away_passport:


            return {

                "status":
                "error",

                "message":
                "Команда не найдена"

            }



        # -----------------------------
        # Passport
        # -----------------------------


        home_strength = self.calculate_strength(
            home_passport
        )


        away_strength = self.calculate_strength(
            away_passport
        )



        # -----------------------------
        # xG
        # -----------------------------


        xg_home, xg_away = self.calculate_xg(

            home_passport,

            away_passport

        )



        # -----------------------------
        # Probability
        # -----------------------------


        probabilities = self.calculate_probability(

            home_strength,

            away_strength

        )



        # -----------------------------
        # Score
        # -----------------------------


        score = self.poisson_score(

            xg_home,

            xg_away

        )



        # -----------------------------
        # Expert Layer
        # -----------------------------


        expert = self.expert_layer(

            home_passport,

            away_passport

        )



        return {


            "version":
            self.version,


            "match":

            f"{home} - {away}",



            "teams":

            {

                "home":
                home_strength,


                "away":
                away_strength

            },



            "xG":

            {

                "home":
                xg_home,


                "away":
                xg_away

            },



            "probability":
            probabilities,



            "score":
            score,



            "expert":
            expert



        }



    # =================================================
    # FAJ RATING
    # =================================================


    def calculate_strength(
        self,
        team
    ):


        values = [

            self.num(team.get("attack")),

            self.num(team.get("defense")),

            self.num(team.get("control")),

            self.num(team.get("efficiency")),

            self.num(team.get("mentality")),

            self.num(team.get("form"))

        ]


        return round(

            sum(values)
            /
            len(values),

            2

        )



    # =================================================
    # xG ENGINE
    # =================================================


    def calculate_xg(
        self,
        home,
        away
    ):


        attack_home = self.num(
            home.get("attack")
        )


        attack_away = self.num(
            away.get("attack")
        )


        defense_home = self.num(
            home.get("defense")
        )


        defense_away = self.num(
            away.get("defense")
        )


        form_home = self.num(
            home.get("form")
        )


        form_away = self.num(
            away.get("form")
        )



        xg_home = (

            self.LEAGUE_XG *

            (1 + (attack_home-75)/200) *

            (1 - (defense_away-75)/250) *

            (1 + (form_home-75)/300) *

            self.HOME_ADVANTAGE

        )



        xg_away = (

            self.LEAGUE_XG *

            (1 + (attack_away-75)/200) *

            (1 - (defense_home-75)/250) *

            (1 + (form_away-75)/300)

        )



        return (

            round(
                self.limit_xg(xg_home),
                2
            ),

            round(
                self.limit_xg(xg_away),
                2
            )

        )



    # =================================================
    # PROBABILITY
    # =================================================


    def calculate_probability(
        self,
        home,
        away
    ):


        total = home + away


        p1 = round(
            home/total*100,
            1
        )


        p2 = round(
            away/total*100,
            1
        )


        draw = round(

            100-p1-p2,

            1

        )


        return {


            "P1":
            p1,


            "X":
            draw,


            "P2":
            p2


        }



    # =================================================
    # POISSON PLACEHOLDER
    # =================================================


    def poisson_score(
        self,
        xg_home,
        xg_away
    ):


        return {


            "main":

            f"{round(xg_home)}:{round(xg_away)}",



            "alternatives":

            [

                "1:1",

                "1:0",

                "2:1"

            ]

        }



    # =================================================
    # EXPERT LAYER
    # =================================================


    def expert_layer(
        self,
        home,
        away
    ):


        return {


            "status":
            "ACTIVE",


            "comment":

            "Экспертный слой ожидает ручной корректировки"

        }



    # =================================================
    # UTILS
    # =================================================


    def num(
        self,
        value
    ):


        try:

            return float(value)

        except:

            return 70



    def limit_xg(
        self,
        value
    ):


        return max(

            0.1,

            min(

                value,

                4.0

            )

        )



    # =================================================
    # STATUS
    # =================================================


    def status(self):


        return {


            "version":
            self.version,


            "teams":
            len(
                self.passport.passports
            ),


            "memory":
            len(
                self.memory.memory
            ),


            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            )

        }




if __name__ == "__main__":


    faj = FAJCore()


    print(
        faj.status()
    )


    print(

        faj.predict_match(

            "Динамо М",

            "Крылья Советов"

        )

    )

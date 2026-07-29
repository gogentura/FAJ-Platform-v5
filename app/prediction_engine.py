# -*- coding: utf-8 -*-

"""
FAJ Football Analytics Journal Platform

Prediction Engine 9.0

Модуль прогнозирования матчей.

Версия:
FAJ_9.0
"""


import math


class PredictionEngine:


    def __init__(self, faj_engine):

        self.engine = faj_engine

        self.version = "FAJ_9.0"



    def calculate_xg(
        self,
        home_team,
        away_team
    ):


        comparison = self.engine.compare_teams(
            home_team,
            away_team
        )


        if not comparison:
            return None



        difference = comparison["difference"]



        league_xg = self.engine.get_parameter(
            "league_mean_xg"
        )


        if not league_xg:

            league_xg = 1.35



        home_advantage = self.engine.get_parameter(
            "home_advantage"
        )


        if not home_advantage:

            home_advantage = 1.08



        home_xg = (

            league_xg

            *

            home_advantage

            *

            (
                1
                +
                difference / 100
            )

        )


        away_xg = (

            league_xg

            *

            (
                1
                -
                difference / 120
            )

        )


        home_xg = max(
            0.1,
            min(home_xg,4.0)
        )


        away_xg = max(
            0.1,
            min(away_xg,4.0)
        )


        return {

            "home_xg":
                round(home_xg,2),

            "away_xg":
                round(away_xg,2)

        }



    def predict_result(
        self,
        home_team,
        away_team
    ):


        xg = self.calculate_xg(
            home_team,
            away_team
        )


        if not xg:
            return None



        home = xg["home_xg"]

        away = xg["away_xg"]



        if home > away + 0.35:

            result = "P1"

        elif away > home + 0.35:

            result = "P2"

        else:

            result = "X"



        score = (

            round(home),

            round(away)

        )


        return {


            "home_team":
                home_team,


            "away_team":
                away_team,


            "xg_home":
                home,


            "xg_away":
                away,


            "result":
                result,


            "score_prediction":
                f"{score[0]}:{score[1]}",


            "model":
                self.version

        }



if __name__ == "__main__":


    from database import FAJDatabase
    from faj_engine import FAJEngine



    db = FAJDatabase()

    db.load_all()


    engine = FAJEngine(db)


    predictor = PredictionEngine(
        engine
    )


    prediction = predictor.predict_result(
        "Акрон",
        "Зенит"
    )


    print(prediction)

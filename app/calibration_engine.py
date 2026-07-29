# -*- coding: utf-8 -*-

"""
FAJ Football Analytics Journal Platform

Calibration Engine 9.0

Модуль анализа ошибок и корректировок.

Версия:
FAJ_9.0
"""


from datetime import date


class CalibrationEngine:


    def __init__(self, database):

        self.db = database

        self.version = "FAJ_9.0"



    def check_result(
        self,
        prediction,
        fact
    ):


        predicted = prediction["result"]

        actual = fact["fact_result"]


        if predicted == actual:

            return {

                "status":
                    "SUCCESS",

                "error":
                    None

            }



        return {

            "status":
                "FAIL",

            "error":
                self.detect_error(
                    predicted,
                    actual
                )

        }



    def detect_error(
        self,
        predicted,
        actual
    ):


        if predicted == "X" and actual != "X":

            return "DRAW_OVERESTIMATION"



        if predicted == "P1" and actual == "P2":

            return "HOME_TEAM_UNDERESTIMATION"



        if predicted == "P2" and actual == "P1":

            return "AWAY_TEAM_UNDERESTIMATION"



        return "RESULT_MISMATCH"



    def create_calibration_note(
        self,
        match,
        analysis
    ):


        return {

            "date":
                str(date.today()),

            "version":
                self.version,

            "match":
                match,

            "problem":
                analysis["error"],

            "action":
                self.recommend_action(
                    analysis["error"]
                )

        }



    def recommend_action(
        self,
        error
    ):


        corrections = {


            "DRAW_OVERESTIMATION":
                "Reduce draw probability weight",


            "HOME_TEAM_UNDERESTIMATION":
                "Increase home attacking confidence",


            "AWAY_TEAM_UNDERESTIMATION":
                "Increase away team strength evaluation",


            "RESULT_MISMATCH":
                "Review match factors"

        }


        return corrections.get(
            error,
            "Manual analysis required"
        )



if __name__ == "__main__":


    from database import FAJDatabase


    db = FAJDatabase()

    db.load_all()


    calibration = CalibrationEngine(
        db
    )


    test_prediction = {

        "result":
            "X"

    }


    test_fact = {

        "fact_result":
            "P1"

    }


    analysis = calibration.check_result(
        test_prediction,
        test_fact
    )


    print(analysis)

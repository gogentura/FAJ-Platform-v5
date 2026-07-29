# -*- coding: utf-8 -*-

"""
FAJ Football Analytics Journal Platform

FAJ 9.0 Test Interface

Первый запуск аналитического ядра.

Версия:
FAJ_9.0
"""


from database import FAJDatabase
from faj_engine import FAJEngine
from prediction_engine import PredictionEngine
from calibration_engine import CalibrationEngine



def show_prediction(result):

    print("\n==========================")
    print(" FAJ 9.0 PREDICTION")
    print("==========================")

    print(
        "Матч:",
        result["home_team"],
        "-",
        result["away_team"]
    )

    print(
        "xG:",
        result["xg_home"],
        ":",
        result["xg_away"]
    )

    print(
        "Исход:",
        result["result"]
    )

    print(
        "Счёт:",
        result["score_prediction"]
    )

    print(
        "Model:",
        result["model"]
    )



def main():


    print(
        """
==============================
 FAJ PLATFORM 9.0 ONLINE
 Football Analytics Journal
==============================
        """
    )


    print(
        "Loading database..."
    )


    db = FAJDatabase()

    db.load_all()



    engine = FAJEngine(
        db
    )


    predictor = PredictionEngine(
        engine
    )


    calibration = CalibrationEngine(
        db
    )



    print(
        "\nВведите команды"
    )


    home = input(
        "Домашняя команда: "
    )


    away = input(
        "Гостевая команда: "
    )



    prediction = predictor.predict_result(
        home,
        away
    )


    if prediction:


        show_prediction(
            prediction
        )


    else:

        print(
            "Команды не найдены"
        )



    print(
        "\nFAJ готов к анализу"
    )



if __name__ == "__main__":

    main()

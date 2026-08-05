#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ Core Engine

Главный управляющий слой платформы

Pipeline:

Match
 ↓
Passport Loader
 ↓
Prediction Engine
 ↓
xG Model
 ↓
Poisson Model
 ↓
Confidence
 ↓
Calibration
 ↓
Risk
 ↓
Final Prediction
 ↓
Journal / Learning

=====================================================
"""


from datetime import datetime


from app.core.prediction_engine import PredictionEngine
from app.core.final_prediction import FinalPrediction
from app.core.confidence_engine import ConfidenceEngine
from app.core.calibration_engine import CalibrationEngine
from app.core.risk_engine import RiskEngine


from app.storage.journal import Journal


class FAJCore:


    VERSION = "12.0"


    def __init__(self):

        self.version = self.VERSION


        self.prediction_engine = PredictionEngine()

        self.final_prediction = FinalPrediction()

        self.confidence_engine = ConfidenceEngine()

        self.calibration_engine = CalibrationEngine()

        self.risk_engine = RiskEngine()

        self.journal = Journal()



    # =================================================
    # MAIN API
    # =================================================


    def predict_match(
        self,
        home_team,
        away_team,
        league="RPL"
    ):


        try:


            # 1. Основной расчёт

            prediction = self.prediction_engine.predict(
                home_team,
                away_team,
                league
            )



            # 2. Confidence

            confidence = self.confidence_engine.calculate(
                prediction
            )


            prediction["confidence"] = confidence



            # 3. Calibration

            prediction = self.calibration_engine.adjust(
                prediction
            )



            # 4. Risk

            risk = self.risk_engine.calculate(
                prediction
            )


            prediction["risk"] = risk



            # 5. Финальный формат

            result = self.final_prediction.build(
                prediction
            )



            # 6. Время

            result["timestamp"] = (
                datetime.now()
                .strftime("%Y-%m-%d %H:%M:%S")
            )


            result["version"] = self.VERSION



            # 7. Журнал

            self.journal.save_prediction(
                result
            )


            return {

                "status":
                    "success",

                "data":
                    result

            }



        except Exception as e:


            return {

                "status":
                    "error",

                "message":
                    str(e)

            }




    # =================================================
    # STATUS
    # =================================================


    def status(self):


        return {


            "platform":
                "FAJ Platform",


            "version":
                self.VERSION,


            "engine":
                "Prediction Engine v12",


            "status":
                "READY"



        }



    # =================================================
    # TEST
    # =================================================


    def test(self):


        return self.predict_match(

            "Зенит",

            "Спартак",

            "RPL"

        )




if __name__ == "__main__":


    core = FAJCore()


    print(
        core.status()
    )


    print(
        core.test()
    )

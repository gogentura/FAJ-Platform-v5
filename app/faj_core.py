#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0

FAJ Core

Главный управляющий модуль платформы.

Pipeline:

Match
 ↓
Passport Engine
 ↓
Prediction Engine
 ↓
xG Engine
 ↓
Poisson
 ↓
Expert Layer
 ↓
Memory
 ↓
Journal

"""


from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater
from app.prediction import FAJPrediction



class FAJCore:



    def __init__(self):


        self.version = "10.0"


        self.memory = MemoryEngine()


        self.passport = PassportUpdater()


        self.prediction = FAJPrediction(

            self.passport

        )



    # =====================================
    # MATCH PREDICTION API
    # =====================================


    def predict_match(

        self,

        home,

        away

    ):


        result = self.prediction.predict(

            home,

            away

        )



        if "error" in result:


            return {


                "status":
                "error",


                "message":
                result["error"]

            }



        explanation = self.generate_explanation(

            result

        )



        result["explanation"] = explanation


        result["timestamp"] = datetime.now().strftime(

            "%Y-%m-%d %H:%M"

        )


        return {


            "status":

            "success",


            "data":

            result

        }



    # =====================================
    # EXPLANATION LAYER
    # =====================================


    def generate_explanation(

        self,

        result

    ):


        reasons = []



        xg = result.get(

            "xg",

            {}

        )


        probability = result.get(

            "probability",

            {}

        )



        if xg.get(

            "home_xg",

            0

        ) > xg.get(

            "away_xg",

            0

        ):


            reasons.append(

                "Преимущество атаки хозяев"

            )


        else:


            reasons.append(

                "Гостевая атака выглядит сильнее"

            )



        if probability.get(

            "P1",

            0

        ) > probability.get(

            "P2",

            0

        ):


            reasons.append(

                "FAJ склоняется к победе хозяев"

            )


        elif probability.get(

            "P2",

            0

        ) > probability.get(

            "P1",

            0

        ):


            reasons.append(

                "FAJ склоняется к победе гостей"

            )


        else:


            reasons.append(

                "Матч имеет высокий риск ничьей"

            )



        return reasons



    # =====================================
    # ROUND PROCESSING
    # =====================================


    def process_round(

        self,

        round_number,

        results

    ):


        errors = 0



        for match in results:



            prediction = match.get(

                "prediction"

            )


            fact = match.get(

                "fact_result"

            )



            if prediction != fact:


                errors += 1



                self.memory.add_memory(


                    version=self.version,


                    object_type="MODEL",


                    object_name="FAJ",


                    category="Prediction Error",


                    observation=(

                        f"{match.get('home')} - "

                        f"{match.get('away')} | "

                        f"FAJ {prediction} | "

                        f"Факт {fact}"

                    ),


                    conclusion=

                    "Необходимо проверить параметры модели",


                    action=

                    "Калибровка весов",


                    confidence=0.8


                )



            self.passport.update_after_match(

                match

            )



        self.passport.save_history(

            self.version,

            f"Round {round_number}"

        )



        return {


            "round":

            round_number,


            "errors":

            errors

        }



    # =====================================
    # STATUS API
    # =====================================


    def status(self):


        memory_count = 0



        if hasattr(

            self.memory,

            "memory"

        ):


            memory_count = len(

                self.memory.memory

            )



        teams = 0



        if hasattr(

            self.passport,

            "passports"

        ):


            teams = len(

                self.passport.passports

            )



        return {


            "version":

            self.version,


            "teams":

            teams,


            "passports":

            teams,


            "memory":

            memory_count,


            "model_events":

            0,


            "team_events":

            0,


            "system_events":

            1


        }



    # =====================================
    # TERMINAL
    # =====================================


    def print_status(self):


        data = self.status()



        print()

        print(
            "========== FAJ CORE v10 =========="
        )


        for k,v in data.items():

            print(

                f"{k}: {v}"

            )


        print(
            "================================="
        )





if __name__ == "__main__":


    core = FAJCore()


    core.print_status()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.3

FAJ Core

Главное ядро адаптивной системы.

Цикл:

Match Results
      ↓
Round Analyzer
      ↓
Memory Engine
      ↓
Passport Updater
      ↓
Learning Cycle
      ↓
New FAJ Version

"""


from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater



class FAJCore:


    def __init__(self):


        self.version = "9.3"


        self.memory = MemoryEngine()


        self.passport = PassportUpdater()



        self.learning_cycle = 0



    # =================================================


    def process_round(
        self,
        round_number,
        results
    ):


        print()

        print("==============================")

        print(
            " FAJ CORE v9.3 ROUND "
        )

        print("==============================")

        print()



        print(
            f"Тур: {round_number}"
        )


        print(
            f"Матчей: {len(results)}"
        )



        errors = 0



        for match in results:


            result = self.process_match(
                match
            )


            if result == "ERROR":

                errors += 1



            self.passport.update_after_match(
                match
            )



        self.learning_cycle += 1



        version = self.create_version(
            round_number
        )



        self.passport.save_history(

            version,

            f"После тура {round_number}"

        )



        print()


        print(
            "Ошибок модели:",
            errors
        )


        print(
            "Learning Cycle:",
            self.learning_cycle
        )


        print(
            "FAJ Version:",
            version
        )


        print()



        return version



    # =================================================


    def process_match(
        self,
        match
    ):


        prediction = match.get(
            "prediction"
        )


        fact = match.get(
            "fact_result"
        )



        if fact is None:

            fact = match.get(
                "result"
            )



        if prediction != fact:


            self.memory.add_memory(


                version=self.version,


                object_type="MODEL",


                object_name="FAJ",


                category="Prediction Error",



                observation=(

                    f"{match.get('home')} - "

                    f"{match.get('away')} | "

                    f"FAJ: {prediction} | "

                    f"Факт: {fact} | "

                    f"Счёт: "

                    f"{match.get('fact_score')}"

                ),



                conclusion=(

                    match.get(
                        "notes"
                    )

                    or

                    "Требуется анализ"

                ),



                action=(

                    "Передать ошибку "
                    "в Calibration Engine"

                ),



                confidence=0.85

            )



            return "ERROR"



        else:



            self.memory.add_memory(


                version=self.version,


                object_type="MODEL",


                object_name="FAJ",


                category="Prediction Success",



                observation=(

                    f"{match.get('home')} - "

                    f"{match.get('away')} | "

                    f"FAJ: {prediction} | "

                    f"Факт: {fact}"

                ),



                conclusion=

                "Прогноз подтверждён",



                action=

                "Сохранить параметры",



                confidence=0.9


            )



            return "SUCCESS"



    # =================================================


    def create_version(
        self,
        round_number
    ):


        date = datetime.now().strftime(

            "%Y%m%d"

        )


        return (

            f"9.{round_number}-"

            f"{date}"

        )



    # =================================================


    def status(self):


        stats = self.memory.statistics()



        print()

        print(
            "========== FAJ CORE =========="
        )


        print(
            "Version:",
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
            stats["total"]
        )


        print(
            "Model Events:",
            stats["model"]
        )


        print(
            "Team Events:",
            stats["team"]
        )


        print(
            "System Events:",
            stats["system"]
        )


        print(
            "Learning Cycle:",
            self.learning_cycle
        )


        print(
            "=============================="
        )

        print()



# =================================================


if __name__ == "__main__":


    faj = FAJCore()


    faj.status()


    test = [


        {

            "home":
            "ЦСКА",


            "away":
            "Балтика",


            "prediction":
            "X",


            "fact_result":
            "P1",


            "fact_score":
            "2:1"


        }

    ]



    faj.process_round(

        1,

        test

    )

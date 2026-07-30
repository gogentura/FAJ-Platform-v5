#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.0

FAJ Core v9.1

Главный управляющий модуль платформы.

Цикл:

Матч
 ↓
Сравнение прогноза и факта
 ↓
Memory Engine
 ↓
Calibration
 ↓
Passport History

"""


from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater



class FAJCore:


    def __init__(self):

        self.version = "9.1"

        self.memory = MemoryEngine()

        self.passport = PassportUpdater()



    # =====================================


    def process_round(
        self,
        round_number,
        results
    ):


        print()
        print("==============================")
        print(" FAJ ROUND PROCESSING ")
        print("==============================")
        print()


        print(
            f"Обработка тура: {round_number}"
        )


        print(
            f"Матчей получено: {len(results)}"
        )


        self.analyze_results(
            results
        )


        new_version = self.create_version(
            round_number
        )


        self.passport.save_history(
            new_version,
            f"После обработки тура {round_number}"
        )


        print()

        print(
            f"FAJ обновлён до версии {new_version}"
        )

        print()



    # =====================================


    def analyze_results(
        self,
        results
    ):


        errors = 0


        for match in results:


            prediction = match.get(
                "prediction"
            )


            # новый формат FAJ 9.0

            fact = match.get(
                "fact_result"
            )


            if fact is None:


                fact = match.get(
                    "result"
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
                        "Необходимо анализировать ошибку"

                    ),



                    action=(

                        "Проверить веса модели "
                        "и параметры матча"

                    ),



                    confidence=0.8

                )



        print(
            f"Ошибок прогноза: {errors}"
        )



    # =====================================


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



    # =====================================


    def status(self):


        print()

        print(
            "========== FAJ CORE =========="
        )


        print(
            f"Версия: {self.version}"
        )


        print(
            "Память:",
            len(
                self.memory.memory
            )
        )


        print(
            "Команды:",
            len(
                self.passport.passports
            )
        )


        print(
            "=============================="
        )


        print()



if __name__ == "__main__":


    faj = FAJCore()


    faj.status()



    test_results = [

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
            "2:1",

            "notes":
            "ЦСКА победил"

        }

    ]



    faj.process_round(
        1,
        test_results
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.0

FAJ Core v9.2

Главный управляющий модуль.

Цикл:

Матч
 ↓
RoundLoader
 ↓
RoundAnalyzer
 ↓
Memory Engine
 ↓
Passport History
 ↓
Калибровка FAJ


"""


from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater
from app.round_analyzer import RoundAnalyzer



class FAJCore:


    def __init__(self):

        self.version = "9.2"


        self.memory = MemoryEngine()


        self.passport = PassportUpdater()


        self.round_analyzer = RoundAnalyzer()



    # ==================================================

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


        # 1. Анализ тура

        report = self.round_analyzer.analyze_round(
            round_number,
            results
        )


        print()


        print(
            "FAJ ROUND REPORT"
        )


        print(
            f"Правильные исходы: "
            f"{report['correct_results']}"
        )


        print(
            f"Ошибки: "
            f"{report['wrong_results']}"
        )


        print(
            f"Ошибки счёта: "
            f"{report['score_errors']}"
        )


        print()



        # 2. Запись памяти

        self.save_round_memory(
            report
        )



        # 3. Новая версия


        new_version = self.create_version(
            round_number
        )



        # 4. История паспортов


        self.passport.save_history(

            new_version,

            f"После обработки тура {round_number}"

        )



        print()

        print(
            f"FAJ обновлён до версии {new_version}"
        )

        print()



        return report



    # ==================================================

    def save_round_memory(
        self,
        report
    ):


        for match in report["matches"]:


            self.memory.add_memory(


                version=self.version,


                object_type="MATCH",


                object_name=(

                    f"{match['home']} - "
                    f"{match['away']}"

                ),


                category=match["error_type"],



                observation=(

                    f"FAJ: {match['prediction']} | "

                    f"Факт: {match['fact']} | "

                    f"Счёт FAJ: "
                    f"{match['predicted_score']} | "

                    f"Факт: "
                    f"{match['fact_score']}"

                ),



                conclusion=match["conclusion"],



                action=(

                    "Использовать данные "
                    "для будущей калибровки"

                ),



                confidence=0.8

            )



    # ==================================================

    def create_version(
        self,
        round_number
    ):


        date = datetime.now().strftime(
            "%Y%m%d"
        )


        return (

            f"FAJ_9.{round_number}_"
            f"{date}"

        )



    # ==================================================

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
            "Команд:",
            len(
                self.passport.passports
            )
        )


        print(
            "=============================="
        )

        print()



# ==================================================


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

            "result":
            "P1",

            "predicted_score":
            "1:1",

            "home_score":
            2,

            "away_score":
            1

        }

    ]



    faj.process_round(
        1,
        test_results
    )

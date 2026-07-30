#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

FAJ Core

Главный управляющий модуль.

Цикл:

Match
 ↓
Round Analyzer
 ↓
FAJ Core
 ↓
Memory Engine
 ↓
Passport History

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


        self.analyzer = RoundAnalyzer()



    # =====================================


    def process_round(
        self,
        round_number,
        results
    ):


        print()

        print("==============================")

        print(
            " FAJ ROUND PROCESSING v9.2 "
        )

        print("==============================")


        print()


        print(
            f"Тур: {round_number}"
        )


        print(
            f"Матчей: {len(results)}"
        )



        # 1. Анализ тура


        analysis = self.analyzer.analyze_round(
            results
        )



        stats = analysis[
            "round_stats"
        ]



        print()

        print(
            "Точность:",
            stats["accuracy"]
        )



        # 2. Записываем системные выводы


        self.save_model_memory(
            analysis
        )



        # 3. Командные наблюдения


        self.save_team_memory(
            analysis
        )



        # 4. История паспортов


        version = self.create_version(
            round_number
        )


        self.passport.save_history(
            version,
            f"После тура {round_number}"
        )



        print()

        print(
            f"FAJ обновлён: {version}"
        )


        print()



    # =====================================


    def save_model_memory(
        self,
        analysis
    ):


        for item in analysis[
            "model_errors"
        ]:



            self.memory.add_memory(

                version=self.version,

                object_type="MODEL",

                object_name="FAJ",

                category=item[
                    "category"
                ],


                observation=item[
                    "observation"
                ],


                conclusion=item[
                    "conclusion"
                ],


                action=item[
                    "action"
                ],


                confidence=0.9

            )



    # =====================================


    def save_team_memory(
        self,
        analysis
    ):


        for item in analysis[
            "team_observations"
        ]:


            self.memory.add_memory(

                version=self.version,

                object_type="TEAM",

                object_name=item[
                    "team"
                ],


                category="Round Analysis",


                observation=item[
                    "observation"
                ],


                conclusion="Командный фактор обновляется",


                action=item[
                    "action"
                ],


                confidence=0.85

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

            f"9.{round_number}."
            f"{date}"

        )



    # =====================================


    def status(self):


        print()

        print(
            "========== FAJ CORE =========="
        )


        print(
            "Версия:",
            self.version
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



# =====================================


if __name__ == "__main__":


    faj = FAJCore()


    faj.status()

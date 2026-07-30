#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

FAJ Core

Главный управляющий модуль.

Цикл:

Матч
 ↓
Round Analyzer
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
from app.round_analyzer import RoundAnalyzer



class FAJCore:


    def __init__(self):

        self.version = "9.2"

        self.memory = MemoryEngine()

        self.passport = PassportUpdater()

        self.analyzer = RoundAnalyzer()

        self.processed_rounds = []



    # ======================================


    def process_round(
        self,
        round_number,
        results
    ):


        print()

        print("==============================")

        print(" FAJ ROUND PROCESSING ")

        print("==============================")



        print(
            f"Тур: {round_number}"
        )


        print(
            f"Матчей: {len(results)}"
        )



        # защита от дублей


        if round_number in self.processed_rounds:


            print(
                "Тур уже обработан"
            )


            return



        # ================================

        # Анализ тура


        analysis = self.analyzer.analyze_round(
            results
        )



        self.save_analysis(
            round_number,
            analysis
        )



        # ================================

        # История паспортов


        new_version = self.create_version(
            round_number
        )


        self.passport.save_history(

            new_version,

            f"После тура {round_number}"

        )



        self.processed_rounds.append(
            round_number
        )



        print()

        print(
            f"FAJ обновлён {new_version}"
        )

        print()



    # ======================================


    def save_analysis(
        self,
        round_number,
        analysis
    ):


        stats = analysis[
            "round_stats"
        ]



        # --------------------------

        # MODEL MEMORY


        self.memory.add_memory(

            version=self.version,

            object_type="MODEL",

            object_name="FAJ",

            category="Round Analysis",

            observation=(

                f"Тур {round_number}: "

                f"{stats['correct']} из "

                f"{stats['matches']}"

            ),

            conclusion=(

                f"Точность модели "
                f"{stats['accuracy']}"

            ),

            action=(

                "Запустить калибровку"

            ),

            confidence=0.95

        )



        # --------------------------

        # Ошибки модели


        for error in analysis[
            "model_errors"
        ]:


            self.memory.add_memory(

                version=self.version,

                object_type="MODEL",

                object_name="FAJ",

                category=error[
                    "category"
                ],

                observation=error[
                    "observation"
                ],

                conclusion=error[
                    "conclusion"
                ],

                action=error[
                    "action"
                ],

                confidence=0.8

            )



        # --------------------------

        # Командные наблюдения


        for team in analysis[
            "team_observations"
        ]:


            self.memory.add_memory(

                version=self.version,

                object_type="TEAM",

                object_name=team[
                    "team"
                ],

                category="Round Performance",

                observation=team[
                    "observation"
                ],

                conclusion=(

                    "Командный показатель "
                    "требует проверки"

                ),

                action=team[
                    "action"
                ],

                confidence=0.85

            )



        # --------------------------

        # SYSTEM


        self.memory.add_memory(

            version=self.version,

            object_type="SYSTEM",

            object_name="Learning",

            category="Cycle",

            observation=(

                f"Тур {round_number} "
                "завершён"

            ),

            conclusion=(

                "FAJ накопил новые данные"

            ),

            action=(

                "Перейти к следующему циклу"

            ),

            confidence=1.0

        )



    # ======================================


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



    # ======================================


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
            "Паспорта:",
            len(
                self.passport.passports
            )
        )


        print(
            "=============================="
        )



# ======================================


if __name__ == "__main__":


    faj = FAJCore()


    faj.status()

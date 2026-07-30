#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.3

FAJ Core

Главный управляющий модуль обучения.

Цикл:

Матч
 ↓
RoundLoader
 ↓
RoundAnalyzer
 ↓
Memory Engine
 ↓
Passport Update
 ↓
History

"""

from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater
from app.round_analyzer import RoundAnalyzer



class FAJCore:


    def __init__(self):

        self.version = "9.3"


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

        print(" FAJ CORE ROUND PROCESSING ")

        print("==============================")

        print()


        print(
            f"Тур: {round_number}"
        )


        print(
            f"Матчей: {len(results)}"
        )



        # 1.
        # Анализ тура


        analysis = self.analyzer.analyze_round(
            results
        )



        print(
            f"Создано записей памяти: {len(analysis)}"
        )



        # 2.
        # Запись памяти


        self.save_memory(
            analysis
        )



        # 3.
        # История паспортов


        version = self.create_version(
            round_number
        )


        self.passport.save_history(

            version,

            f"После анализа тура {round_number}"

        )



        print()


        print(
            f"FAJ обновлен: {version}"
        )


        print()



    # =====================================


    def save_memory(
        self,
        records
    ):


        for item in records:


            self.memory.add_memory(

                version=self.version,

                object_type=item["type"],

                object_name=item["object"],

                category=item["category"],

                observation=item["observation"],

                conclusion=item["conclusion"],

                action=item["action"],

                confidence=0.9

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

            f"FAJ_{round_number}.{date}"

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
            "Memory:",
            len(self.memory.memory)
        )


        print(
            "Teams:",
            len(self.passport.passports)
        )


        print(
            "=============================="
        )

        print()



# =====================================


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
            "2:1",

            "notes":
            "ЦСКА победил"

        }

    ]



    faj.process_round(
        1,
        test
    )

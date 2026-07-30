#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.0

FAJ Core

Главный управляющий модуль платформы.

Цикл:
Матч -> Анализ -> Память -> Калибровка -> Паспорт -> Журнал

"""

from datetime import datetime

from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater


class FAJCore:

    def __init__(self):

        self.version = "9.0"

        self.memory = MemoryEngine()

        self.passport = PassportUpdater()


    # ------------------------------------------------

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


        # 1. Анализ ошибок

        self.analyze_results(
            results
        )


        # 2. Обновление версии

        new_version = self.create_version(
            round_number
        )


        # 3. Сохранение истории паспортов

        self.passport.save_history(
            new_version,
            f"После обработки тура {round_number}"
        )


        print()

        print(
            f"FAJ обновлён до версии {new_version}"
        )

        print()


    # ------------------------------------------------

    def analyze_results(
        self,
        results
    ):


        for match in results:


            prediction = match.get(
                "prediction"
            )

            fact = match.get(
                "result"
            )


            if prediction != fact:


                self.memory.add_memory(

                    version=self.version,

                    object_type="MODEL",

                    object_name="FAJ",

                    category="Prediction Error",

                    observation=
                    f"{match['home']} - {match['away']} "
                    f"прогноз {prediction}, факт {fact}",

                    conclusion=
                    "Необходимо анализировать ошибку",

                    action=
                    "Проверить веса модели",

                    confidence=0.8
                )


    # ------------------------------------------------

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


    # ------------------------------------------------

    def status(self):

        print()

        print("========== FAJ CORE ==========")

        print(
            f"Версия: {self.version}"
        )

        print(
            "Память:",
            len(self.memory.memory)
        )

        print(
            "Команды:",
            len(self.passport.passports)
        )

        print("==============================")

        print()



if __name__ == "__main__":


    faj = FAJCore()

    faj.status()


    test_results = [

        {
            "home": "ЦСКА",
            "away": "Балтика",
            "prediction": "X",
            "result": "1"
        },

        {
            "home": "Акрон",
            "away": "Зенит",
            "prediction": "2",
            "result": "2"
        }

    ]


    faj.process_round(
        1,
        test_results
    )

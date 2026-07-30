#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.3.1

FAJ Core

Главный управляющий модуль.

Цикл:

Матч
 ↓
Prediction
 ↓
Fact Result
 ↓
Memory Engine
 ↓
Calibration
 ↓
Passport Update
 ↓
History

"""


from datetime import datetime


from app.memory_engine import MemoryEngine
from app.passport_updater import PassportUpdater



class FAJCore:


    def __init__(self):

        self.version = "9.3.1"


        self.memory = MemoryEngine()


        self.passport = PassportUpdater()



    # =====================================
    # ОБРАБОТКА ТУРА
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

                        f"FAJ: {prediction} | "

                        f"Факт: {fact} | "

                        f"Счёт: {match.get('fact_score')}"

                    ),


                    conclusion=(

                        "Проверить параметры "
                        "модели"

                    ),


                    action=(

                        "Калибровка FAJ"

                    ),


                    confidence=0.8

                )



            self.passport.update_after_match(
                match
            )



        version = self.create_version(
            round_number
        )


        self.passport.save_history(

            version,

            f"Тур {round_number}"

        )


        return {


            "round":

            round_number,


            "errors":

            errors,


            "version":

            version

        }



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
    # STATUS ДЛЯ STREAMLIT
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



        model_events = 0

        team_events = 0

        system_events = 0



        if hasattr(
            self.memory,
            "memory"
        ):


            for item in self.memory.memory:


                obj = item.get(
                    "object_type",
                    ""
                )


                if obj == "MODEL":

                    model_events += 1


                elif obj == "TEAM":

                    team_events += 1


                elif obj == "SYSTEM":

                    system_events += 1



        return {


            "version":

            self.version,


            "teams":

            teams,


            "memory":

            memory_count,


            "passports":

            teams,


            "model_events":

            model_events,


            "team_events":

            team_events,


            "system_events":

            system_events


        }



if __name__ == "__main__":


    faj = FAJCore()


    print(
        faj.status()
    )

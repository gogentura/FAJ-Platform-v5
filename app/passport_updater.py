# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

Passport Updater

Назначение:

Адаптация паспортов команд после тура.

Цикл:

Match Result
↓
Team Performance
↓
Passport Adjustment
↓
Passport History


"""


import csv
import os
from datetime import datetime



BASE_PATH = "data"



class PassportUpdater:



    def __init__(self):

        self.version = "9.2"

        self.passports = []

        self.history = []

        self.load_passports()



    # =====================================


    def load_passports(self):


        path = os.path.join(
            BASE_PATH,
            "team_passports_v40.csv"
        )


        if not os.path.exists(path):

            print(
                "[PASSPORT] File not found"
            )

            return



        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:


            reader = csv.DictReader(file)


            self.passports = list(reader)



        print(
            "[PASSPORT] Loaded:",
            len(self.passports)
        )



    # =====================================


    def find_team(
        self,
        name
    ):


        for team in self.passports:


            if team.get(
                "team"
            ) == name:


                return team



        return None



    # =====================================


    def update_after_match(
        self,
        match
    ):


        home = match.get(
            "home"
        )


        away = match.get(
            "away"
        )


        result = match.get(
            "fact_result"
        )



        if result == "P1":


            self.improve_team(
                home,
                "win"
            )


            self.reduce_team(
                away,
                "loss"
            )



        elif result == "P2":


            self.improve_team(
                away,
                "win"
            )


            self.reduce_team(
                home,
                "loss"
            )



        else:


            self.balance_team(
                home
            )


            self.balance_team(
                away
            )



    # =====================================


    def improve_team(
        self,
        team_name,
        reason
    ):


        team = self.find_team(
            team_name
        )


        if not team:

            return



        old_form = float(
            team.get(
                "form",
                70
            )
        )


        new_form = min(
            old_form + 1.5,
            100
        )


        team["form"] = str(
            round(
                new_form,
                2
            )
        )



        self.history.append({

            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),


            "version":
            self.version,


            "team":
            team_name,


            "change":
            "+FORM",


            "reason":
            reason,


            "value":
            new_form

        })



    # =====================================


    def reduce_team(
        self,
        team_name,
        reason
    ):


        team = self.find_team(
            team_name
        )


        if not team:

            return



        old_form = float(
            team.get(
                "form",
                70
            )
        )


        new_form = max(
            old_form - 1.0,
            40
        )



        team["form"] = str(
            round(
                new_form,
                2
            )
        )



        self.history.append({

            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),


            "version":
            self.version,


            "team":
            team_name,


            "change":
            "-FORM",


            "reason":
            reason,


            "value":
            new_form

        })



    # =====================================


    def balance_team(
        self,
        team_name
    ):


        self.history.append({

            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),


            "version":
            self.version,


            "team":
            team_name,


            "change":
            "DRAW",


            "reason":
            "Стабильный результат",


            "value":
            0

        })



    # =====================================


    def save_history(
        self,
        version,
        note
    ):


        path = os.path.join(
            BASE_PATH,
            "passport_history_v9.csv"
        )


        exists = os.path.exists(
            path
        )



        with open(
            path,
            "a",
            encoding="utf-8",
            newline=""
        ) as file:


            writer = csv.DictWriter(

                file,

                fieldnames=[

                    "date",
                    "version",
                    "team",
                    "change",
                    "reason",
                    "value"

                ]

            )


            if not exists:

                writer.writeheader()



            for row in self.history:

                writer.writerow(
                    row
                )



        print(
            "[PASSPORT] History saved"
        )



    # =====================================


    def status(self):


        print()

        print(
            "===== PASSPORT UPDATER ====="
        )


        print(
            "Version:",
            self.version
        )


        print(
            "Teams:",
            len(
                self.passports
            )
        )


        print(
            "History:",
            len(
                self.history
            )
        )


        print(
            "============================"
        )



if __name__ == "__main__":


    updater = PassportUpdater()

    updater.status()

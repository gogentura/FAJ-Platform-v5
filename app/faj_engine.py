# -*- coding: utf-8 -*-

"""
FAJ Football Analytics Journal Platform
FAJ Engine 9.0

Главный аналитический модуль.

Задача:
Соединяет:
- Team Passport
- Team Form
- Model Config
- Expert Layer

Версия:
FAJ_9.0
"""


class FAJEngine:


    def __init__(self, database):

        self.db = database

        self.version = "FAJ_9.0"


    def get_team_passport(self, team):

        for item in self.db.passports:

            if item["team"] == team:
                return item

        return None



    def get_team_form(self, team):

        for item in self.db.form:

            if item["team"] == team:
                return item

        return None



    def get_parameter(self, parameter):

        for item in self.db.config:

            if item["parameter"] == parameter:
                return float(item["value"])

        return None



    def calculate_team_power(self, team):

        passport = self.get_team_passport(team)

        form = self.get_team_form(team)


        if not passport:
            return None



        attack = float(
            passport["attack"]
        )

        defense = float(
            passport["defense"]
        )

        control = float(
            passport["control"]
        )

        mentality = float(
            passport["mentality"]
        )


        base_power = (

            attack * 0.18

            +

            defense * 0.18

            +

            control * 0.15

            +

            mentality * 0.10

        )


        form_bonus = 0


        if form:

            current_form = float(
                form["new_form"]
            )

            form_bonus = (
                current_form - 70
            ) * 0.05



        total_power = (
            base_power
            +
            form_bonus
        )


        return round(
            total_power,
            2
        )



    def compare_teams(
        self,
        home_team,
        away_team
    ):


        home_power = self.calculate_team_power(
            home_team
        )


        away_power = self.calculate_team_power(
            away_team
        )


        if home_power is None:
            return None


        if away_power is None:
            return None



        difference = (
            home_power
            -
            away_power
        )


        return {

            "home_team":
                home_team,

            "away_team":
                away_team,

            "home_power":
                home_power,

            "away_power":
                away_power,

            "difference":
                round(
                    difference,
                    2
                )

        }



if __name__ == "__main__":

    from database import FAJDatabase


    db = FAJDatabase()

    db.load_all()


    engine = FAJEngine(db)


    result = engine.compare_teams(
        "Акрон",
        "Зенит"
    )


    print(
        result
    )

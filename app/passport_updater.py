#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.0

Passport Updater

Обновляет паспорта команд
после каждого сыгранного тура.

Автор:
FAJ Platform
"""

from pathlib import Path
import pandas as pd


class PassportUpdater:

    def __init__(self):

        self.passports_file = Path(
            "data/team_passports_v40.csv"
        )

        self.history_file = Path(
            "data/team_passports_history.csv"
        )

        self.passports = pd.read_csv(
            self.passports_file
        )

        self.history = pd.read_csv(
            self.history_file
        )

    # ------------------------------------------------

    def get_team(self, team):

        row = self.passports[
            self.passports["Команда"] == team
        ]

        if len(row) == 0:
            return None

        return row.iloc[0]

    # ------------------------------------------------

    def update_form(
        self,
        team,
        delta
    ):

        index = self.passports[
            self.passports["Команда"] == team
        ].index

        if len(index) == 0:
            return

        idx = index[0]

        current = self.passports.loc[idx, "Форм"]

        new_value = max(
            50,
            min(
                99,
                current + delta
            )
        )

        self.passports.loc[idx, "Форм"] = new_value

    # ------------------------------------------------

    def update_attack(
        self,
        team,
        delta
    ):

        idx = self.passports[
            self.passports["Команда"] == team
        ].index[0]

        value = self.passports.loc[idx, "Атк"]

        self.passports.loc[idx, "Атк"] = max(
            50,
            min(
                99,
                value + delta
            )
        )

    # ------------------------------------------------

    def update_defense(
        self,
        team,
        delta
    ):

        idx = self.passports[
            self.passports["Команда"] == team
        ].index[0]

        value = self.passports.loc[idx, "Защ"]

        self.passports.loc[idx, "Защ"] = max(
            50,
            min(
                99,
                value + delta
            )
        )

    # ------------------------------------------------

    def reduce_uncertainty(
        self,
        team,
        delta=2
    ):

        idx = self.passports[
            self.passports["Команда"] == team
        ].index[0]

        value = self.passports.loc[idx, "Неопр"]

        self.passports.loc[idx, "Неопр"] = max(
            0,
            value - delta
        )

    # ------------------------------------------------

    def save(self):

        self.passports.to_csv(
            self.passports_file,
            index=False,
            encoding="utf-8-sig"
        )

    # ------------------------------------------------

    def save_history(
        self,
        version,
        reason
    ):

        today = pd.Timestamp.today().strftime(
            "%Y-%m-%d"
        )

        rows = []

        for _, row in self.passports.iterrows():

            rows.append({

                "date": today,

                "version": version,

                "team": row["Команда"],

                "attack": row["Атк"],

                "defense": row["Защ"],

                "control": row["Конт"],

                "efficiency": row["Эфф"],

                "mentality": row["Мент"],

                "tempo": row["Тмп"],

                "press": row["Прс"],

                "transition": row["Пдп"],

                "tactical": row["Гиб"],

                "home_strength": row["Дом"],

                "tournament_dna": row["Трн"],

                "form": row["Форм"],

                "uncertainty": row["Неопр"],

                "coach_rating": row["Coach"],

                "transfer_rating": row["Transfer"],

                "squad_depth": row["Depth"],

                "reason": reason

            })

        history = pd.concat(
            [
                self.history,
                pd.DataFrame(rows)
            ],
            ignore_index=True
        )

        history.to_csv(
            self.history_file,
            index=False,
            encoding="utf-8-sig"
        )


if __name__ == "__main__":

    updater = PassportUpdater()

    updater.update_form(
        "Зенит",
        2
    )

    updater.reduce_uncertainty(
        "Зенит"
    )

    updater.save()

    updater.save_history(
        "9.1",
        "После первого тура"
    )

    print("Паспорта обновлены.")

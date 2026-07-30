#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.1

Passport Updater

Работает с:
team_passports_v40.csv

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
            self.passports_file,
            encoding="utf-8-sig"
        )


        if self.history_file.exists():

            self.history = pd.read_csv(
                self.history_file,
                encoding="utf-8-sig"
            )

        else:

            self.history = pd.DataFrame()



    # ---------------------------------

    def get_team(
        self,
        team
    ):


        row = self.passports[

            self.passports["team"]
            ==
            team

        ]


        if len(row) == 0:

            return None


        return row.iloc[0]



    # ---------------------------------

    def update_form(
        self,
        team,
        delta
    ):


        index = self.passports[

            self.passports["team"]
            ==
            team

        ].index


        if len(index) == 0:

            return


        idx = index[0]


        current = self.passports.loc[
            idx,
            "form"
        ]


        self.passports.loc[
            idx,
            "form"
        ] = max(
            50,
            min(
                99,
                current + delta
            )
        )



    # ---------------------------------

    def update_attack(
        self,
        team,
        delta
    ):


        idx = self.passports[

            self.passports["team"]
            ==
            team

        ].index


        if len(idx) == 0:

            return


        idx = idx[0]


        self.passports.loc[
            idx,
            "attack"
        ] = max(

            50,

            min(
                99,
                self.passports.loc[
                    idx,
                    "attack"
                ]
                +
                delta
            )

        )



    # ---------------------------------

    def update_defense(
        self,
        team,
        delta
    ):


        idx = self.passports[

            self.passports["team"]
            ==
            team

        ].index


        if len(idx) == 0:

            return


        idx = idx[0]


        self.passports.loc[
            idx,
            "defense"
        ] = max(

            50,

            min(
                99,
                self.passports.loc[
                    idx,
                    "defense"
                ]
                +
                delta
            )

        )



    # ---------------------------------

    def reduce_uncertainty(
        self,
        team,
        delta=2
    ):


        idx = self.passports[

            self.passports["team"]
            ==
            team

        ].index


        if len(idx) == 0:

            return


        idx = idx[0]


        self.passports.loc[
            idx,
            "uncertainty"
        ] = max(

            0,

            self.passports.loc[
                idx,
                "uncertainty"
            ]
            -
            delta

        )



    # ---------------------------------

    def save(self):


        self.passports.to_csv(

            self.passports_file,

            index=False,

            encoding="utf-8-sig"

        )



    # ---------------------------------

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

                "team": row["team"],

                "attack": row["attack"],

                "defense": row["defense"],

                "control": row["control"],

                "efficiency": row["efficiency"],

                "mentality": row["mentality"],

                "tempo": row["tempo"],

                "press": row["press"],

                "predictability": row["predictability"],

                "flexibility": row["flexibility"],

                "home_power": row["home_power"],

                "coach": row["coach"],

                "form": row["form"],

                "uncertainty": row["uncertainty"],

                "transfer_index": row["transfer_index"],

                "depth": row["depth"],

                "reason": reason

            })


        new_history = pd.concat(

            [

                self.history,

                pd.DataFrame(rows)

            ],

            ignore_index=True

        )


        new_history.to_csv(

            self.history_file,

            index=False,

            encoding="utf-8-sig"

        )

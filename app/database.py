# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0
Database Loader

Назначение:
Загрузка памяти FAJ из CSV файлов.

Версия:
FAJ_9.0
"""

import csv
import os


BASE_PATH = "data"


class FAJDatabase:

    def __init__(self):
        self.passports = []
        self.form = []
        self.predictions = []
        self.results = []
        self.stats = []
        self.config = []
        self.expert = []
        self.journal = []
        self.calibration = []


    def load_csv(self, filename):

        path = os.path.join(BASE_PATH, filename)

        if not os.path.exists(path):
            print(f"[FAJ DATABASE] File not found: {path}")
            return []

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            return list(reader)


    def load_all(self):

        print("=== FAJ DATABASE 9.0 LOADING ===")


        self.passports = self.load_csv(
            "team_passports_v40.csv"
        )


        self.form = self.load_csv(
            "team_form_rpl_v9.csv"
        )


        self.predictions = self.load_csv(
            "rpl_round1_predictions.csv"
        )


        self.results = self.load_csv(
            "rpl_round1_results.csv"
        )


        self.stats = self.load_csv(
            "rpl_round1_match_stats.csv"
        )


        self.config = self.load_csv(
            "faj_model_config_v9.csv"
        )


        self.expert = self.load_csv(
            "faj_expert_layer_v9.csv"
        )


        self.calibration = self.load_csv(
            "faj_calibration_v9.csv"
        )


        self.journal = self.load_csv(
            "faj_journal_v9.csv"
        )


        print(
            "Passports:",
            len(self.passports)
        )

        print(
            "Predictions:",
            len(self.predictions)
        )

        print(
            "Results:",
            len(self.results)
        )

        print(
            "Journal:",
            len(self.journal)
        )


        print(
            "=== FAJ DATABASE READY ==="
        )


        return self



if __name__ == "__main__":

    db = FAJDatabase()

    db.load_all()

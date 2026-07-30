# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0

Smart Round Loader

Адаптивный загрузчик туров.
"""

from pathlib import Path
import pandas as pd


class RoundLoader:


    def __init__(self):

        self.data_path = Path(
            "data"
        )


    # ---------------------------------

    def load_csv(self, filename):

        file = self.data_path / filename


        if not file.exists():

            raise FileNotFoundError(
                f"Нет файла: {file}"
            )


        return pd.read_csv(
            file,
            encoding="utf-8-sig"
        )


    # ---------------------------------

    def find_column(
        self,
        df,
        variants
    ):

        for col in variants:

            if col in df.columns:

                return col


        return None


    # ---------------------------------

    def normalize_team(
        self,
        name
    ):

        if pd.isna(name):

            return None


        name = str(name).strip()


        replacements = {

            "ПФК ЦСКА":
                "ЦСКА",

            "ЦСКА Москва":
                "ЦСКА",

            "Зенит Санкт-Петербург":
                "Зенит",

            "ФК Краснодар":
                "Краснодар",

            "Краснодар ФК":
                "Краснодар",

            "Динамо Москва":
                "Динамо М",

            "Ахмат Грозный":
                "Ахмат",

            "Крылья Советов Самара":
                "Крылья Советов",

        }


        return replacements.get(
            name,
            name
        )


    # ---------------------------------

    def load_round(
        self,
        round_number=1
    ):


        results = self.load_csv(
            f"rpl_round{round_number}_results.csv"
        )


        predictions = self.load_csv(
            f"rpl_round{round_number}_predictions.csv"
        )


        try:

            stats = self.load_csv(
                f"rpl_round{round_number}_match_stats.csv"
            )

        except:


            stats = pd.DataFrame()



        # ищем колонки


        home_col = self.find_column(
            results,
            [
                "home_team",
                "home",
                "Хозяева",
                "Домашняя команда"
            ]
        )


        away_col = self.find_column(
            results,
            [
                "away_team",
                "away",
                "Гости",
                "Гостевая команда"
            ]
        )


        result_col = self.find_column(
            results,
            [
                "result",
                "winner",
                "Исход"
            ]
        )


        home_score_col = self.find_column(
            results,
            [
                "home_score",
                "score_home",
                "Хозяева голы"
            ]
        )


        away_score_col = self.find_column(
            results,
            [
                "away_score",
                "score_away",
                "Гости голы"
            ]
        )


        if not home_col or not away_col:

            raise Exception(
                f"Не найдены команды. Колонки: {list(results.columns)}"
            )


        matches = []


        for _, row in results.iterrows():


            home = self.normalize_team(
                row[home_col]
            )


            away = self.normalize_team(
                row[away_col]
            )


            matches.append(

                {

                    "home": home,

                    "away": away,

                    "result":
                        row[result_col]
                        if result_col
                        else None,


                    "home_score":
                        row[home_score_col]
                        if home_score_col
                        else None,


                    "away_score":
                        row[away_score_col]
                        if away_score_col
                        else None,


                    "prediction":
                        None,


                    "predicted_score":
                        None,


                    "stats":
                        {}

                }

            )


        return matches



if __name__ == "__main__":


    loader = RoundLoader()


    matches = loader.load_round(1)


    print(
        "Матчей:",
        len(matches)
    )


    for m in matches:

        print(
            m["home"],
            "-",
            m["away"]
        )

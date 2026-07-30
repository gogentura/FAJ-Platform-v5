# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0

Round Loader v9.1

Загрузчик туров.

Объединяет:
- прогноз FAJ
- фактический результат
- статистику матча
- данные для обучения модели

"""


from pathlib import Path
import pandas as pd



class RoundLoader:


    def __init__(self):

        self.data_path = Path(
            "data"
        )



    # =====================================

    def load_csv(
        self,
        filename
    ):


        file = self.data_path / filename


        if not file.exists():

            raise FileNotFoundError(
                f"Файл не найден: {file}"
            )


        return pd.read_csv(
            file,
            encoding="utf-8-sig"
        )



    # =====================================

    def normalize_team(
        self,
        team
    ):


        if pd.isna(team):

            return None


        team = str(team).strip()



        aliases = {


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


            "Динамо Махачкала":
                "Динамо Мх",


            "Ахмат Грозный":
                "Ахмат",


            "Крылья Советов Самара":
                "Крылья Советов"


        }


        return aliases.get(
            team,
            team
        )



    # =====================================

    def load_predictions(
        self,
        round_number
    ):


        file = (
            f"rpl_round{round_number}_predictions.csv"
        )


        try:

            return self.load_csv(
                file
            )

        except FileNotFoundError:


            return pd.DataFrame()



    # =====================================

    def find_prediction(
        self,
        predictions,
        home,
        away
    ):


        if predictions.empty:

            return None



        if (
            "home_team" not in predictions.columns
            or
            "away_team" not in predictions.columns
        ):

            return None



        row = predictions[

            (
                predictions["home_team"]
                == home
            )

            &

            (
                predictions["away_team"]
                == away
            )

        ]



        if len(row) == 0:

            return None



        return row.iloc[0]



    # =====================================

    def load_round(
        self,
        round_number=1
    ):



        results_file = (

            f"rpl_round{round_number}_results.csv"

        )


        results = self.load_csv(
            results_file
        )


        predictions = self.load_predictions(
            round_number
        )



        matches = []



        for _, row in results.iterrows():



            home = self.normalize_team(

                row["home_team"]

            )



            away = self.normalize_team(

                row["away_team"]

            )



            prediction = self.find_prediction(

                predictions,

                home,

                away

            )



            match = {


                "match_id":
                    row.get(
                        "match_id"
                    ),



                "round":
                    row.get(
                        "round"
                    ),



                "home":
                    home,



                "away":
                    away,



                # факт

                "fact_score":
                    row.get(
                        "fact_score"
                    ),



                "fact_result":
                    row.get(
                        "fact_result"
                    ),



                "red_cards":
                    row.get(
                        "red_cards"
                    ),



                "notes":
                    row.get(
                        "notes"
                    ),



                "date":
                    row.get(
                        "date"
                    ),



                "version":
                    row.get(
                        "version"
                    ),



                # прогноз FAJ


                "prediction":

                    prediction.get(
                        "prediction"
                    )
                    if prediction is not None
                    else None,



                "predicted_score":

                    prediction.get(
                        "score_prediction"
                    )
                    if prediction is not None
                    else None,



                "stats": {}

            }



            matches.append(
                match
            )



        return matches




# =====================================

if __name__ == "__main__":


    loader = RoundLoader()


    matches = loader.load_round(
        1
    )



    print(
        "Загружено матчей:",
        len(matches)
    )



    for match in matches:


        print(

            match["home"],

            "-",

            match["away"],

            "|",

            match["fact_score"]

        )

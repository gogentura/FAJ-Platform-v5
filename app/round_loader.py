# -*- coding: utf-8 -*-

"""
FAJ Platform 9.0

Round Loader

Загрузчик данных тура.

Объединяет:
- прогнозы FAJ
- реальные результаты
- статистику матчей

"""

from pathlib import Path
import pandas as pd


class RoundLoader:

    def __init__(self):

        self.data_path = Path(
            "data"
        )


    # -------------------------------------

    def load_csv(self, filename):

        file = self.data_path / filename

        if not file.exists():

            raise FileNotFoundError(
                f"Файл не найден: {file}"
            )

        return pd.read_csv(
            file
        )


    # -------------------------------------

    def load_round(
        self,
        round_number=1
    ):

        results_file = (
            f"rpl_round{round_number}_results.csv"
        )

        predictions_file = (
            f"rpl_round{round_number}_predictions.csv"
        )

        stats_file = (
            f"rpl_round{round_number}_match_stats.csv"
        )


        results = self.load_csv(
            results_file
        )


        predictions = self.load_csv(
            predictions_file
        )


        try:

            stats = self.load_csv(
                stats_file
            )

        except FileNotFoundError:

            stats = pd.DataFrame()



        matches = []


        for _, result in results.iterrows():


            home = result.get(
                "home_team"
            )

            away = result.get(
                "away_team"
            )


            prediction_row = predictions[

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


            prediction = None


            if len(prediction_row) > 0:

                prediction = prediction_row.iloc[0]


            match_stats = None


            if not stats.empty:


                stats_row = stats[

                    (
                        stats["home_team"]
                        == home
                    )
                    &
                    (
                        stats["away_team"]
                        == away
                    )

                ]


                if len(stats_row) > 0:

                    match_stats = (
                        stats_row.iloc[0]
                    )



            matches.append(

                {

                    "home": home,

                    "away": away,

                    "result": result.get(
                        "result"
                    ),

                    "home_score": result.get(
                        "home_score"
                    ),

                    "away_score": result.get(
                        "away_score"
                    ),

                    "prediction": (
                        prediction.get(
                            "prediction"
                        )
                        if prediction is not None
                        else None
                    ),

                    "predicted_score": (
                        prediction.get(
                            "score_prediction"
                        )
                        if prediction is not None
                        else None
                    ),

                    "stats": (
                        match_stats.to_dict()
                        if match_stats is not None
                        else {}
                    )

                }

            )


        return matches



# -------------------------------------

if __name__ == "__main__":


    loader = RoundLoader()


    data = loader.load_round(
        1
    )


    print(
        f"Загружено матчей: {len(data)}"
    )


    for match in data:

        print(
            match["home"],
            "-",
            match["away"],
            match["result"]
        )

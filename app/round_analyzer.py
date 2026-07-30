#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.1

Round Analyzer

Анализирует сыгранный тур.

Цикл:

Results CSV
      |
      ↓
Round Analyzer
      |
      ↓
FAJ Core
      |
      ↓
Memory Engine
      |
      ↓
Passport Update

"""


from collections import Counter



class RoundAnalyzer:


    def __init__(self):

        self.version = "9.1"



    # =====================================

    def analyze_round(
        self,
        results
    ):


        analysis = {


            "round_stats": {},


            "model_errors": [],


            "team_observations": [],


            "match_errors": []


        }



        total = len(results)

        correct = 0

        errors = 0



        result_counter = Counter()

        fact_counter = Counter()



        for match in results:



            prediction = (

                match.get(
                    "prediction"
                )

                or

                match.get(
                    "faj_prediction"
                )

            )



            fact = (

                match.get(
                    "fact_result"
                )

                or

                match.get(
                    "result"
                )

            )



            fact_score = match.get(
                "fact_score",
                ""
            )


            home = match.get(
                "home_team"
            ) or match.get(
                "home"
            )


            away = match.get(
                "away_team"
            ) or match.get(
                "away"
            )



            result_counter[prediction] += 1

            fact_counter[fact] += 1



            if prediction == fact:


                correct += 1



            else:


                errors += 1



                analysis[
                    "match_errors"
                ].append(


                    {


                    "type":
                    "MATCH_ERROR",


                    "home":
                    home,


                    "away":
                    away,


                    "prediction":
                    prediction,


                    "fact":
                    fact,


                    "score":
                    fact_score,


                    "note":
                    match.get(
                        "notes",
                        ""
                    )


                    }

                )



        accuracy = 0


        if total > 0:

            accuracy = round(
                correct / total,
                3
            )



        analysis[
            "round_stats"
        ] = {


            "matches":
            total,


            "correct":
            correct,


            "errors":
            errors,


            "accuracy":
            accuracy,


            "predicted_results":
            dict(result_counter),


            "actual_results":
            dict(fact_counter)


        }



        self.build_model_analysis(
            analysis
        )


        self.build_team_analysis(
            results,
            analysis
        )


        return analysis



    # =====================================


    def build_model_analysis(
        self,
        analysis
    ):


        stats = analysis[
            "round_stats"
        ]



        if stats["accuracy"] < 0.5:


            analysis[
                "model_errors"
            ].append(


                {


                "category":
                "Accuracy",


                "observation":
                f"Точность тура {stats['accuracy']}",


                "conclusion":
                "Необходимо проверить веса модели",


                "action":
                "Запустить калибровку"


                }

            )



        predicted_draws = stats[
            "predicted_results"
        ].get(
            "X",
            0
        )


        actual_draws = stats[
            "actual_results"
        ].get(
            "X",
            0
        )



        if predicted_draws > actual_draws:


            analysis[
                "model_errors"
            ].append(


                {


                "category":
                "Draw Bias",


                "observation":
                (
                    f"FAJ прогнозировал "
                    f"{predicted_draws} ничьих"
                ),


                "conclusion":
                "Модель переоценила ничейный сценарий",


                "action":
                "Снизить вес X"


                }

            )



    # =====================================


    def build_team_analysis(
        self,
        results,
        analysis
    ):


        teams = {}



        for match in results:



            score = match.get(
                "fact_score",
                ""
            )


            note = match.get(
                "notes",
                ""
            )


            home = match.get(
                "home_team"
            ) or match.get(
                "home"
            )


            away = match.get(
                "away_team"
            ) or match.get(
                "away"
            )



            if home not in teams:

                teams[home] = []

            if away not in teams:

                teams[away] = []



            teams[home].append(
                score
            )

            teams[away].append(
                score
            )



            if "удал" in note.lower():


                analysis[
                    "model_errors"
                ].append(


                    {


                    "category":
                    "Red Cards",


                    "observation":
                    note,


                    "conclusion":
                    "Удаление изменило сценарий",


                    "action":
                    "Добавить фактор карточек в xG"


                    }

                )



        for team in teams:


            analysis[
                "team_observations"
            ].append(


                {


                "team":
                team,


                "observation":
                "Команда обработана после тура",


                "action":
                "Обновить паспорт"


                }

            )



    # =====================================


    def print_report(
        self,
        analysis
    ):


        print()

        print(
            "===== FAJ ROUND REPORT ====="
        )


        print(
            analysis["round_stats"]
        )


        print()

        print(
            "MODEL:"
        )


        for item in analysis["model_errors"]:

            print(
                item
            )


        print()

        print(
            "MATCH ERRORS:"
        )


        for item in analysis["match_errors"]:

            print(
                item
            )


        print(
            "============================"
        )



if __name__ == "__main__":


    analyzer = RoundAnalyzer()


    test = [

        {
            "home_team":
            "ЦСКА",

            "away_team":
            "Балтика",

            "prediction":
            "X",

            "fact_result":
            "P1",

            "fact_score":
            "2:1",

            "notes":
            "ЦСКА победил"
        }

    ]


    result = analyzer.analyze_round(
        test
    )


    analyzer.print_report(
        result
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.0

Round Analyzer

Анализ сыгранного тура.

Цикл:

RoundLoader
      |
      ↓
RoundAnalyzer
      |
      ├── анализ прогнозов
      ├── анализ ошибок
      ├── анализ команд
      └── выводы FAJ


Версия:
FAJ_9.0
"""


from datetime import datetime



class RoundAnalyzer:


    def __init__(self):

        self.version = "FAJ_9.0"



    # --------------------------------------

    def analyze_round(
        self,
        round_number,
        matches
    ):


        report = {


            "round":
                round_number,


            "date":
                datetime.now().strftime(
                    "%Y-%m-%d"
                ),


            "total_matches":
                len(matches),


            "correct_results":
                0,


            "wrong_results":
                0,


            "score_errors":
                0,


            "matches":
                [],


            "team_analysis":
                []

        }



        for match in matches:


            result = self.analyze_match(
                match
            )


            report["matches"].append(
                result
            )


            if result["result_correct"]:

                report["correct_results"] += 1

            else:

                report["wrong_results"] += 1



            if not result["score_correct"]:

                report["score_errors"] += 1



        return report



    # --------------------------------------

    def analyze_match(
        self,
        match
    ):


        fact = match.get(
            "result"
        )


        prediction = match.get(
            "prediction"
        )


        fact_score = (

            str(
                match.get(
                    "home_score"
                )
            )
            +
            ":"
            +
            str(
                match.get(
                    "away_score"
                )
            )

        )


        predicted_score = match.get(
            "predicted_score"
        )



        result_correct = (

            prediction == fact

        )



        score_correct = (

            predicted_score == fact_score

        )



        error_type = None

        conclusion = None



        if not result_correct:


            error_type = (
                "RESULT_ERROR"
            )


            conclusion = (
                self.create_conclusion(
                    match
                )
            )



        elif not score_correct:


            error_type = (
                "SCORE_ERROR"
            )


            conclusion = (
                "Исход угадан, "
                "но счёт требует калибровки"
            )



        else:


            error_type = (
                "SUCCESS"
            )


            conclusion = (
                "Модель корректно оценила матч"
            )



        return {


            "home":
                match.get(
                    "home"
                ),


            "away":
                match.get(
                    "away"
                ),


            "prediction":
                prediction,


            "fact":
                fact,


            "predicted_score":
                predicted_score,


            "fact_score":
                fact_score,


            "result_correct":
                result_correct,


            "score_correct":
                score_correct,


            "error_type":
                error_type,


            "conclusion":
                conclusion

        }



    # --------------------------------------

    def create_conclusion(
        self,
        match
    ):


        home = match.get(
            "home"
        )


        away = match.get(
            "away"
        )


        return (

            f"FAJ ошибся в матче "
            f"{home} - {away}. "
            f"Требуется анализ факторов."
            
        )



    # --------------------------------------

    def summary_text(
        self,
        report
    ):


        return f"""

========== FAJ ROUND REPORT ==========

Тур: {report['round']}

Матчей:
{report['total_matches']}


Правильные исходы:
{report['correct_results']}


Ошибки:
{report['wrong_results']}


Ошибки счёта:
{report['score_errors']}


=======================================

"""



# --------------------------------------

if __name__ == "__main__":


    analyzer = RoundAnalyzer()


    test_matches = [

        {

            "home":
                "ЦСКА",

            "away":
                "Балтика",

            "prediction":
                "X",

            "result":
                "P1",

            "predicted_score":
                "1:1",

            "home_score":
                2,

            "away_score":
                1

        }

    ]


    report = analyzer.analyze_round(
        1,
        test_matches
    )


    print(
        analyzer.summary_text(
            report
        )
    )

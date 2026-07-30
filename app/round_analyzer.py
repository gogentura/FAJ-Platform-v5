#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.1

Round Analyzer

Назначение:

Анализ одного тура.

Задачи:

- сравнение прогноза и факта
- поиск ошибок модели
- поиск сильных/слабых сторон команд
- подготовка структурированной памяти FAJ

Цикл:

Round Result
      |
      v
Round Analyzer
      |
      +--> Model Errors
      |
      +--> Team Observations
      |
      v
FAJ Core

"""


class RoundAnalyzer:


    def __init__(self):

        self.version = "9.1"



    # =====================================


    def analyze_round(
        self,
        results
    ):


        model_errors = []

        team_observations = []


        correct = 0

        total = len(results)



        for match in results:


            prediction = match.get(
                "prediction"
            )


            fact = match.get(
                "fact_result"
            )


            if fact is None:

                fact = match.get(
                    "result"
                )



            home = match.get(
                "home",
                "Unknown"
            )


            away = match.get(
                "away",
                "Unknown"
            )


            score = match.get(
                "fact_score",
                ""
            )



            # -----------------------------

            # Проверка исхода


            if prediction == fact:


                correct += 1


            else:


                model_errors.append({

                    "category":
                    "Prediction Error",


                    "observation":

                    (
                        f"{home} - {away} | "
                        f"FAJ: {prediction} | "
                        f"Факт: {fact} | "
                        f"Счёт: {score}"
                    ),


                    "conclusion":

                    self.error_reason(
                        match
                    ),


                    "action":

                    "Проверить параметры модели"

                })



            # -----------------------------

            # Анализ команд


            if fact in [
                "P1",
                "1"
            ]:


                team_observations.append({

                    "team": home,


                    "observation":

                    (
                        f"Победа над {away} "
                        f"со счётом {score}"
                    ),


                    "action":

                    "Проверить форму и атаку"

                })



            elif fact in [
                "P2",
                "2"
            ]:


                team_observations.append({

                    "team": away,


                    "observation":

                    (
                        f"Победа над {home} "
                        f"со счётом {score}"
                    ),


                    "action":

                    "Проверить силу команды"

                })



        accuracy = 0


        if total > 0:

            accuracy = round(
                correct / total,
                2
            )



        return {


            "round_stats":

            {

                "matches":

                total,


                "correct":

                correct,


                "errors":

                total - correct,


                "accuracy":

                accuracy

            },


            "model_errors":

            model_errors,


            "team_observations":

            team_observations

        }



    # =====================================


    def error_reason(
        self,
        match
    ):


        notes = match.get(
            "notes"
        )


        if notes:

            return notes



        prediction = match.get(
            "prediction"
        )


        fact = match.get(
            "fact_result"
        )


        if prediction == "X":

            return (
                "FAJ переоценил вероятность ничьей"
            )


        if prediction != fact:

            return (
                "Необходимо проверить "
                "веса атаки, защиты и формы"
            )


        return (
            "Ошибка не определена"
        )



# =====================================


if __name__ == "__main__":


    analyzer = RoundAnalyzer()



    test = [

        {

            "home":
            "ЦСКА",


            "away":
            "Балтика",


            "prediction":
            "X",


            "fact_result":
            "P1",


            "fact_score":
            "2:1"

        }

    ]



    result = analyzer.analyze_round(
        test
    )


    print(result)

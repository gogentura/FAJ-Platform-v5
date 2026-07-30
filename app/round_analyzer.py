#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.1

Round Analyzer

Анализ сыгранного тура.

Создает структурированную память:

MATCH
TEAM
MODEL
SYSTEM

"""


class RoundAnalyzer:


    def __init__(self):

        self.version = "9.1"



    # =====================================


    def analyze_round(
        self,
        matches
    ):


        memory = []


        correct = 0
        total = len(matches)


        for match in matches:


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


            score = match.get(
                "fact_score"
            )


            home = match.get(
                "home"
            )

            away = match.get(
                "away"
            )


            # -------------------------
            # MATCH MEMORY
            # -------------------------


            if prediction == fact:

                correct += 1


                memory.append({

                    "type":
                    "MATCH",

                    "object":
                    f"{home}-{away}",

                    "category":
                    "Prediction Success",

                    "observation":
                    f"FAJ {prediction}, факт {fact}, счёт {score}",

                    "conclusion":
                    "Модель правильно оценила исход",

                    "action":
                    "Сохранить параметры"

                })


            else:


                memory.append({

                    "type":
                    "MATCH",

                    "object":
                    f"{home}-{away}",

                    "category":
                    "Prediction Error",

                    "observation":
                    (
                        f"FAJ {prediction}, "
                        f"факт {fact}, "
                        f"счёт {score}"
                    ),

                    "conclusion":
                    match.get(
                        "notes"
                    )
                    or
                    "Требуется анализ ошибки",

                    "action":
                    "Проверить параметры модели"

                })



        # -------------------------
        # MODEL MEMORY
        # -------------------------


        accuracy = round(
            correct / total * 100,
            2
        )


        memory.append({

            "type":
            "MODEL",

            "object":
            "FAJ",

            "category":
            "Round Accuracy",

            "observation":
            (
                f"Точность тура "
                f"{correct}/{total}"
            ),

            "conclusion":
            (
                "Требуется калибровка"
                if accuracy < 50
                else
                "Модель стабильна"
            ),

            "action":
            "Проверить веса"

        })



        # -------------------------
        # SYSTEM MEMORY
        # -------------------------


        memory.append({

            "type":
            "SYSTEM",

            "object":
            "Learning",

            "category":
            "Cycle",

            "observation":
            "Первый цикл анализа завершён",

            "conclusion":
            "FAJ получил новый опыт",

            "action":
            "Обновить версию модели"

        })



        return memory



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


    print(
        analyzer.analyze_round(test)
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.1

Round Analyzer

Анализ сыгранного тура.

Функции:

- сравнение FAJ прогноз / факт
- анализ ошибок модели
- анализ команд
- выявление факторов
- подготовка памяти FAJ


Цикл:

RoundLoader
      |
      ↓
RoundAnalyzer
      |
      ├── MODEL MEMORY
      ├── TEAM MEMORY
      └── SYSTEM MEMORY

"""


from datetime import datetime



class RoundAnalyzer:


    def __init__(self):

        self.version = "9.1"



    # =================================================

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


            "version":
                self.version,


            "total_matches":
                len(matches),


            "correct":
                0,


            "errors":
                0,


            "model_memory":
                [],


            "team_memory":
                [],


            "system_memory":
                []

        }



        for match in matches:


            analysis = self.analyze_match(
                match
            )


            # =========================
            # MODEL
            # =========================


            if analysis["result_correct"]:


                report["correct"] += 1


            else:


                report["errors"] += 1


                report["model_memory"].append(

                    self.create_model_memory(
                        analysis
                    )

                )



            # =========================
            # TEAM
            # =========================


            report["team_memory"].extend(

                self.create_team_memory(
                    analysis
                )

            )



        # =========================
        # SYSTEM EVENT
        # =========================


        report["system_memory"].append(

            {

                "object_type":
                    "SYSTEM",

                "object_name":
                    "Learning",

                "category":
                    "Cycle",

                "observation":
                    (
                        f"Тур {round_number} "
                        f"проанализирован"
                    ),

                "conclusion":
                    (
                        "FAJ обновляет "
                        "опыт после матча"
                    ),

                "action":
                    (
                        "Использовать "
                        "данные для калибровки"
                    ),

                "confidence":
                    1.0

            }

        )


        return report



    # =================================================


    def analyze_match(
        self,
        match
    ):


        prediction = match.get(
            "prediction"
        )


        fact = match.get(
            "result"
        )


        score = (

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


            "score":
                score,


            "predicted_score":
                predicted_score,


            "notes":
                match.get(
                    "notes"
                ),


            "result_correct":
                prediction == fact

        }



    # =================================================

    def create_model_memory(
        self,
        match
    ):


        return {


            "object_type":
                "MODEL",


            "object_name":
                "FAJ",


            "category":
                "Prediction Error",


            "observation":
                (

                    f"{match['home']} - "
                    f"{match['away']} | "

                    f"FAJ: {match['prediction']} | "

                    f"Факт: {match['fact']} | "

                    f"Счёт: {match['score']}"

                ),


            "conclusion":
                (

                    match["notes"]
                    or
                    "Требуется анализ факторов"

                ),


            "action":
                (
                    "Проверить "
                    "веса модели"
                ),


            "confidence":
                0.85

        }



    # =================================================

    def create_team_memory(
        self,
        match
    ):


        memories = []



        # победитель


        if match["fact"] == "P1":


            memories.append(

                {

                    "object_type":
                        "TEAM",

                    "object_name":
                        match["home"],

                    "category":
                        "Strength",

                    "observation":
                        (
                            "Домашняя команда "
                            "одержала победу"
                        ),

                    "conclusion":
                        (
                            "Проверить "
                            "рост формы"
                        ),

                    "action":
                        (
                            "Обновить паспорт"
                        ),

                    "confidence":
                        0.75

                }

            )



        elif match["fact"] == "P2":


            memories.append(

                {

                    "object_type":
                        "TEAM",

                    "object_name":
                        match["away"],

                    "category":
                        "Strength",

                    "observation":
                        (
                            "Гостевая команда "
                            "превысила ожидания"
                        ),

                    "conclusion":
                        (
                            "Рассмотреть "
                            "рост рейтинга"
                        ),

                    "action":
                        (
                            "Обновить паспорт"
                        ),

                    "confidence":
                        0.75

                }

            )



        return memories



    # =================================================


    def summary(
        self,
        report
    ):


        print()

        print(
            "====== FAJ ROUND ANALYSIS ======"
        )


        print(
            f"Матчей: {report['total_matches']}"
        )


        print(
            f"Правильно: {report['correct']}"
        )


        print(
            f"Ошибки: {report['errors']}"
        )


        print(
            f"Ошибки модели: "
            f"{len(report['model_memory'])}"
        )


        print(
            f"Командных записей: "
            f"{len(report['team_memory'])}"
        )


        print(
            "==============================="
        )



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

            "result":
                "P1",

            "home_score":
                2,

            "away_score":
                1,

            "notes":
                "ЦСКА победил"

        }

    ]


    report = analyzer.analyze_round(
        1,
        test
    )


    analyzer.summary(
        report
    )

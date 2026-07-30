#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

Round Analyzer

Анализ футбольного тура.

Задачи:

- сравнение прогноза и факта
- расчёт точности
- поиск ошибок модели
- подготовка Learning Memory
- подготовка Passport Update


"""


from datetime import datetime



class RoundAnalyzer:



    def __init__(self):

        self.version = "9.2"


        self.round_data = {}


    # =================================================


    def analyze_round(

        self,

        round_number,

        matches

    ):


        print()

        print("==============================")

        print(
            " FAJ ROUND ANALYZER v9.2 "
        )

        print("==============================")

        print()



        correct = 0

        errors = 0


        error_list = []

        success_list = []

        team_events = []



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



            if prediction == fact:


                correct += 1


                success_list.append({

                    "match":

                    f"{match.get('home')} - {match.get('away')}",


                    "prediction":

                    prediction,


                    "fact":

                    fact


                })



            else:


                errors += 1



                error_list.append({

                    "match":

                    f"{match.get('home')} - {match.get('away')}",


                    "prediction":

                    prediction,


                    "fact":

                    fact,


                    "score":

                    match.get(
                        "fact_score"
                    ),


                    "lesson":

                    self.detect_lesson(
                        match
                    )


                })



            team_events.extend(

                self.detect_team_event(
                    match
                )

            )



        total = len(matches)



        accuracy = 0


        if total > 0:

            accuracy = round(

                correct / total * 100,

                2

            )



        self.round_data = {


            "round":

            round_number,


            "date":

            datetime.now()
            .strftime(
                "%Y-%m-%d"
            ),


            "version":

            self.version,


            "total_matches":

            total,


            "correct":

            correct,


            "errors":

            errors,


            "accuracy":

            accuracy,


            "success":

            success_list,


            "errors_list":

            error_list,


            "team_events":

            team_events


        }



        print(
            f"Точность FAJ: {correct}/{total} ({accuracy}%)"
        )


        print(
            f"Ошибок: {errors}"
        )


        return self.round_data



    # =================================================


    def detect_lesson(

        self,

        match

    ):


        notes = (

            match.get("notes")

            or ""

        ).lower()



        if "удал" in notes:


            return (

                "Добавить влияние "
                "красной карточки"

            )



        if "нич" in notes:


            return (

                "Проверить склонность "
                "FAJ к ничьим"

            )



        return (

            "Проверить веса модели "
            "и параметры команды"

        )



    # =================================================


    def detect_team_event(

        self,

        match

    ):


        events = []



        fact = match.get(
            "fact_result"
        )



        if fact == "P1":


            events.append({

                "team":

                match.get(
                    "home"
                ),


                "impact":

                "POSITIVE",


                "reason":

                "Победа дома"

            })



        elif fact == "P2":


            events.append({

                "team":

                match.get(
                    "away"
                ),


                "impact":

                "POSITIVE",


                "reason":

                "Победа в гостях"

            })



        return events



    # =================================================


    def summary(self):


        return {


            "version":

            self.version,


            "round":

            self.round_data.get(
                "round"
            ),


            "accuracy":

            self.round_data.get(
                "accuracy"
            ),


            "errors":

            self.round_data.get(
                "errors"
            )


        }



# =================================================


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
            "2:1",


            "notes":
            "ЦСКА победил"

        }

    ]



    result = analyzer.analyze_round(

        1,

        test

    )


    print(result)

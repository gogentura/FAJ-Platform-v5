#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Learning Brain

Модуль обучения на истории матчей
"""

from typing import Dict, List
from app.brain.memory_brain import FAJMemoryBrain


class FAJLearningBrain:


    def __init__(self):

        self.memory = FAJMemoryBrain()


    # =========================================
    # АНАЛИЗ ВСЕЙ ИСТОРИИ
    # =========================================

    def analyze_history(self) -> Dict:

        records = self.memory.get_memory()


        total = len(records)

        finished = 0

        correct = 0

        mistakes = []


        for item in records:


            if item.get("status") != "finished":
                continue


            finished += 1


            analysis = item.get(
                "analysis"
            )


            if not analysis:
                continue


            if analysis.get("correct"):

                correct += 1

            else:

                mistakes.append({

                    "match":
                        item.get("match"),

                    "prediction":
                        analysis.get(
                            "predicted_score"
                        ),

                    "actual":
                        analysis.get(
                            "actual_score"
                        )

                })


        accuracy = 0

        if finished:

            accuracy = round(
                correct / finished * 100,
                1
            )


        return {

            "total_predictions": total,

            "finished": finished,

            "correct": correct,

            "accuracy": accuracy,

            "mistakes": mistakes

        }



    # =========================================
    # ПОИСК СЛАБЫХ МЕСТ
    # =========================================

    def find_patterns(self) -> List:


        analysis = self.analyze_history()


        patterns = []


        mistakes = analysis.get(
            "mistakes",
            []
        )


        if len(mistakes) >= 5:


            patterns.append({

                "type":
                    "score_prediction",

                "message":
                    "FAJ часто ошибается в точном счёте"

            })


        if analysis.get(
            "accuracy",
            0
        ) < 50 and analysis.get(
            "finished",
            0
        ) >= 10:


            patterns.append({

                "type":
                    "model_quality",

                "message":
                    "Требуется корректировка весов модели"

            })


        return patterns



    # =========================================
    # РЕКОМЕНДАЦИИ ДЛЯ FAJ ENGINE
    # =========================================

    def generate_recommendations(self) -> Dict:


        patterns = self.find_patterns()


        recommendations = []


        for p in patterns:


            if p["type"] == "score_prediction":

                recommendations.append(

                    "Увеличить влияние xG"

                )


            if p["type"] == "model_quality":

                recommendations.append(

                    "Пересмотреть веса паспорта"

                )


        return {


            "patterns": patterns,

            "recommendations":
                recommendations

        }



    # =========================================
    # СТАТУС
    # =========================================

    def get_status(self):


        result = self.analyze_history()


        return {

            "learning_ready":

                result["finished"] > 0,


            "accuracy":

                result["accuracy"],


            "samples":

                result["finished"]

        }



if __name__ == "__main__":


    brain = FAJLearningBrain()


    print(
        brain.get_status()
    )

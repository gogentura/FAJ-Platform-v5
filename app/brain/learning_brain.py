#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.1

Learning Brain

Анализирует ошибки прогнозов,
учится на результатах матчей
и формирует рекомендации для модели.
"""

from datetime import datetime
from typing import Dict, List
import json
import os


class FAJLearningBrain:


    def __init__(self):

        self.learning_rate = 0.01

        self.model_version = "10.1"

        self.memory_file = "data/learning_memory.json"


        # Базовые веса FAJ Engine

        self.weights = {

            "attack": 0.18,
            "defense": 0.18,
            "control": 0.15,
            "efficiency": 0.12,
            "mentality": 0.10,
            "tempo": 0.05,
            "press": 0.05,
            "transition": 0.05,
            "flexibility": 0.05,
            "coach": 0.04,
            "form": 0.03

        }


        self.memory = self.load_memory()



    # =====================================================
    # ПАМЯТЬ ОБУЧЕНИЯ
    # =====================================================


    def load_memory(self) -> List:

        if os.path.exists(self.memory_file):

            try:

                with open(
                    self.memory_file,
                    "r",
                    encoding="utf-8"
                ) as f:

                    return json.load(f)

            except:

                return []

        return []



    def save_memory(self):

        os.makedirs(
            "data",
            exist_ok=True
        )

        with open(
            self.memory_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.memory,
                f,
                ensure_ascii=False,
                indent=2
            )



    # =====================================================
    # АНАЛИЗ МАТЧА
    # =====================================================


    def analyze_prediction(
            self,
            prediction: Dict,
            actual: Dict
    ) -> Dict:


        analysis = {

            "date":
                datetime.now().isoformat(),

            "errors": [],

            "corrections": []

        }



        # -------------------------------
        # Проверяем точный счёт
        # -------------------------------


        predicted_scores = prediction.get(
            "top_scores",
            []
        )


        actual_score = (

            str(actual.get("home_goals"))
            +
            ":"
            +
            str(actual.get("away_goals"))

        )


        if predicted_scores:

            best_score = predicted_scores[0].get(
                "score"
            )


            if best_score != actual_score:

                analysis["errors"].append(
                    "wrong_score"
                )



        # -------------------------------
        # Проверяем исход
        # -------------------------------


        home = actual.get(
            "home_goals",
            0
        )

        away = actual.get(
            "away_goals",
            0
        )


        if home > away:

            real_result = "home"

        elif away > home:

            real_result = "away"

        else:

            real_result = "draw"



        prediction_result = self.get_prediction_result(
            prediction
        )


        if real_result != prediction_result:

            analysis["errors"].append(
                "wrong_result"
            )



        # -------------------------------
        # Анализируем причины
        # -------------------------------


        if "wrong_result" in analysis["errors"]:


            if real_result == "home":

                analysis["corrections"].append(
                    "increase_home_attack_weight"
                )


            elif real_result == "away":

                analysis["corrections"].append(
                    "increase_away_strength_weight"
                )


            else:

                analysis["corrections"].append(
                    "increase_draw_factor"
                )



        return analysis



    # =====================================================
    # ОПРЕДЕЛЕНИЕ ПРОГНОЗА
    # =====================================================


    def get_prediction_result(
            self,
            prediction: Dict
    ) -> str:


        home = prediction.get(
            "home_win",
            0
        )

        draw = prediction.get(
            "draw",
            0
        )

        away = prediction.get(
            "away_win",
            0
        )


        maximum = max(
            home,
            draw,
            away
        )


        if maximum == home:

            return "home"

        elif maximum == away:

            return "away"

        else:

            return "draw"



    # =====================================================
    # ОБУЧЕНИЕ ВЕСОВ
    # =====================================================


    def learn(
            self,
            analysis: Dict
    ) -> Dict:


        changes = {}


        for correction in analysis.get(
            "corrections",
            []
        ):


            if correction == "increase_home_attack_weight":

                self.weights["attack"] += self.learning_rate

                changes["attack"] = "+0.01"



            elif correction == "increase_away_strength_weight":

                self.weights["defense"] += self.learning_rate

                changes["defense"] = "+0.01"



            elif correction == "increase_draw_factor":

                self.weights["mentality"] += self.learning_rate

                changes["mentality"] = "+0.01"



        return changes



    # =====================================================
    # ПОЛНЫЙ ЦИКЛ ОБУЧЕНИЯ
    # =====================================================


    def process_match(
            self,
            prediction: Dict,
            actual: Dict
    ) -> Dict:


        analysis = self.analyze_prediction(
            prediction,
            actual
        )


        changes = self.learn(
            analysis
        )


        record = {

            "timestamp":
                datetime.now().isoformat(),

            "analysis":
                analysis,

            "changes":
                changes

        }


        self.memory.append(
            record
        )


        self.save_memory()


        return record



    # =====================================================
    # СТАТУС МОЗГА
    # =====================================================


    def get_status(self):

        return {

            "version":
                self.model_version,

            "memory_size":
                len(self.memory),

            "weights":
                self.weights

        }



if __name__ == "__main__":


    brain = FAJLearningBrain()


    print("="*50)
    print("FAJ Learning Brain v10.1")
    print("="*50)


    print(
        brain.get_status()
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.1
Learning Brain

Анализ ошибок прогнозов и обучение модели
"""

from datetime import datetime
from typing import Dict


class FAJLearningBrain:


    def __init__(self):

        # базовые веса FAJ
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


        self.learning_rate = 0.01



    # =====================================================
    # АНАЛИЗ ПРОГНОЗА
    # =====================================================

    def analyze_match(
            self,
            prediction: Dict,
            actual: Dict
    ) -> Dict:


        result = {

            "timestamp":
                datetime.now().isoformat(),

            "error_type": [],

            "score_error": None,

            "learning": {}

        }


        predicted_score = prediction.get(
            "top_scores",
            []
        )


        actual_score = (
            f"{actual.get('home_goals')}:"
            f"{actual.get('away_goals')}"
        )


        # ---------------------------------
        # Проверяем счёт
        # ---------------------------------

        if predicted_score:

            best_score = (
                predicted_score[0]
                .get("score")
            )

            if best_score != actual_score:

                result["error_type"].append(
                    "wrong_score"
                )


        # ---------------------------------
        # Проверяем исход
        # ---------------------------------

        predicted_home = prediction.get(
            "home_win",
            0
        )

        predicted_away = prediction.get(
            "away_win",
            0
        )


        if actual.get("home_goals") > actual.get("away_goals"):

            actual_result = "home"

        elif actual.get("home_goals") < actual.get("away_goals"):

            actual_result = "away"

        else:

            actual_result = "draw"



        if actual_result == "home":

            if predicted_home < 50:
                result["error_type"].append(
                    "underestimated_home"
                )


        elif actual_result == "away":

            if predicted_away < 50:
                result["error_type"].append(
                    "underestimated_away"
                )



        else:

            if prediction.get("draw",0)<30:

                result["error_type"].append(
                    "missed_draw"
                )


        return result



    # =====================================================
    # ОБУЧЕНИЕ ВЕСОВ
    # =====================================================


    def update_weights(
            self,
            errors:list
    ) -> Dict:


        changes = {}


        for error in errors:


            if error == "underestimated_home":

                self.weights["attack"] += self.learning_rate

                changes["attack"] = "+0.01"



            elif error == "underestimated_away":

                self.weights["defense"] += self.learning_rate

                changes["defense"] = "+0.01"



            elif error == "missed_draw":

                self.weights["mentality"] += self.learning_rate

                changes["mentality"] = "+0.01"



            elif error == "wrong_score":

                self.weights["efficiency"] += self.learning_rate

                changes["efficiency"] = "+0.01"



        return changes



    # =====================================================
    # ПОЛУЧИТЬ ТЕКУЩУЮ МОДЕЛЬ
    # =====================================================


    def get_model_state(self):

        return {

            "weights": self.weights,

            "learning_rate":
                self.learning_rate,

            "version":
                "10.1"

        }

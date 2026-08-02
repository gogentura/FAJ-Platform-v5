#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Correction Brain

Модуль корректировки модели:
- анализирует ошибки FAJ
- предлагает изменения весов
- сохраняет рекомендации
"""

import os
import json
from datetime import datetime
from typing import Dict, List

from app.brain.learning_brain import FAJLearningBrain


class FAJCorrectionBrain:


    def __init__(self, data_dir="data"):

        self.data_dir = data_dir

        self.correction_file = os.path.join(
            self.data_dir,
            "faj_corrections.json"
        )

        self.learning = FAJLearningBrain()

        self.corrections = self._load()



    # =====================================================
    # ЗАГРУЗКА КОРРЕКТИРОВОК
    # =====================================================

    def _load(self):

        if os.path.exists(self.correction_file):

            try:
                with open(
                    self.correction_file,
                    "r",
                    encoding="utf-8"
                ) as f:
                    return json.load(f)

            except:
                return []

        return []



    # =====================================================
    # СОХРАНЕНИЕ
    # =====================================================

    def _save(self):

        os.makedirs(
            self.data_dir,
            exist_ok=True
        )

        with open(
            self.correction_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.corrections,
                f,
                ensure_ascii=False,
                indent=2
            )



    # =====================================================
    # АНАЛИЗ ОШИБОК
    # =====================================================

    def analyze_errors(self) -> Dict:


        analysis = self.learning.analyze_history()


        mistakes = analysis.get(
            "mistakes",
            []
        )


        result = {

            "date":
                datetime.now().isoformat(),

            "accuracy":
                analysis.get(
                    "accuracy",
                    0
                ),

            "mistakes_count":
                len(mistakes),

            "recommendations": []

        }



        # Если мало угаданных счетов

        if len(mistakes) >= 5:

            result["recommendations"].append({

                "parameter":
                    "score_accuracy",

                "action":
                    "increase_xg_weight",

                "reason":
                    "Много ошибок точного счета"

            })



        # Если точность низкая

        if analysis.get(
            "accuracy",
            0
        ) < 50 and analysis.get(
            "finished",
            0
        ) >= 10:


            result["recommendations"].append({

                "parameter":
                    "passport_weights",

                "action":
                    "review_weights",

                "reason":
                    "Низкая общая точность"

            })



        return result



    # =====================================================
    # СОЗДАНИЕ КОРРЕКТИРОВКИ
    # =====================================================

    def create_correction(self) -> Dict:


        correction = self.analyze_errors()


        self.corrections.append(
            correction
        )


        self._save()


        return correction



    # =====================================================
    # ПОЛУЧИТЬ ИСТОРИЮ
    # =====================================================

    def get_history(self) -> List:

        return self.corrections



    # =====================================================
    # СТАТУС
    # =====================================================

    def get_status(self):


        last = None

        if self.corrections:

            last = self.corrections[-1]


        return {

            "corrections_count":
                len(self.corrections),

            "last_correction":
                last

        }



if __name__ == "__main__":


    brain = FAJCorrectionBrain()


    print("=" * 50)
    print("FAJ Correction Brain v10.0")
    print("=" * 50)


    print(
        brain.get_status()
    )

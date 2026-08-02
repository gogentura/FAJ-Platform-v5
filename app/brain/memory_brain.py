#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Memory Brain

Память FAJ:
- сохраняет прогнозы
- сохраняет реальные результаты
- анализирует ошибки
- формирует историю обучения
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional


class FAJMemoryBrain:

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        
        self.memory_file = os.path.join(
            self.data_dir,
            "faj_memory.json"
        )

        self.memory = self._load_memory()


    # =====================================================
    # ЗАГРУЗКА ПАМЯТИ
    # =====================================================

    def _load_memory(self) -> List:

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


    # =====================================================
    # СОХРАНЕНИЕ
    # =====================================================

    def _save_memory(self):

        os.makedirs(
            self.data_dir,
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
    # ЗАПИСЬ ПРОГНОЗА
    # =====================================================

    def save_prediction(
        self,
        match: str,
        prediction: Dict
    ) -> Dict:

        record = {

            "id": len(self.memory) + 1,

            "date": datetime.now().isoformat(),

            "match": match,

            "prediction": prediction,

            "actual_result": None,

            "analysis": None,

            "status": "waiting"
        }


        self.memory.append(record)

        self._save_memory()


        return record



    # =====================================================
    # ДОБАВЛЕНИЕ РЕЗУЛЬТАТА
    # =====================================================

    def add_result(
        self,
        match: str,
        actual_score: str
    ) -> Dict:


        for item in reversed(self.memory):

            if item["match"] == match:

                item["actual_result"] = actual_score

                item["status"] = "finished"

                self._save_memory()

                return item


        return {
            "error": "Матч не найден"
        }



    # =====================================================
    # АНАЛИЗ ОШИБКИ
    # =====================================================

    def analyze_prediction(
        self,
        match: str
    ) -> Dict:


        for item in reversed(self.memory):

            if item["match"] == match:

                prediction = item.get(
                    "prediction",
                    {}
                )

                actual = item.get(
                    "actual_result"
                )


                if not actual:

                    return {
                        "status": "Нет результата"
                    }


                faj_score = None


                if "top_scores" in prediction:

                    faj_score = (
                        prediction["top_scores"][0]
                        .get("score")
                    )


                analysis = {

                    "match": match,

                    "predicted_score":
                        faj_score,

                    "actual_score":
                        actual,

                    "correct":
                        faj_score == actual,

                    "date":
                        datetime.now().isoformat()
                }


                item["analysis"] = analysis


                self._save_memory()


                return analysis


        return {
            "error": "Прогноз не найден"
        }



    # =====================================================
    # СТАТИСТИКА ПАМЯТИ
    # =====================================================

    def get_statistics(self) -> Dict:


        total = len(self.memory)

        finished = 0

        correct = 0


        for item in self.memory:

            if item.get("status") == "finished":

                finished += 1


            analysis = item.get(
                "analysis"
            )


            if analysis:

                if analysis.get(
                    "correct"
                ):
                    correct += 1



        accuracy = 0


        if finished > 0:

            accuracy = round(
                correct / finished * 100,
                1
            )


        return {

            "total_predictions": total,

            "finished_matches": finished,

            "correct_predictions": correct,

            "accuracy": accuracy

        }



    # =====================================================
    # ПОЛУЧИТЬ ВСЮ ПАМЯТЬ
    # =====================================================

    def get_memory(self) -> List:

        return self.memory



    # =====================================================
    # ОЧИСТКА
    # =====================================================

    def clear_memory(self):

        self.memory = []

        self._save_memory()



# =====================================================
# ТЕСТ
# =====================================================

if __name__ == "__main__":

    brain = FAJMemoryBrain()


    print("=" * 50)
    print("FAJ Memory Brain v10.0")
    print("=" * 50)


    print(
        brain.get_statistics()
    )

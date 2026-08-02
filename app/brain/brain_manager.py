#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0

Brain Manager

Главный управляющий модуль FAJ Brain:

Memory Brain
      |
Learning Brain
      |
Correction Brain
      |
Data Brain

"""

from datetime import datetime
from typing import Dict, List

from app.brain.memory_brain import FAJMemoryBrain
from app.brain.learning_brain import FAJLearningBrain
from app.brain.correction_brain import FAJCorrectionBrain


class FAJBrainManager:


    def __init__(self):

        self.memory = FAJMemoryBrain()

        self.learning = FAJLearningBrain()

        self.correction = FAJCorrectionBrain()



    # =====================================================
    # СОХРАНИТЬ ПРОГНОЗ
    # =====================================================

    def save_prediction(
        self,
        match: str,
        prediction: Dict
    ) -> Dict:

        return self.memory.save_prediction(
            match,
            prediction
        )



    # =====================================================
    # ДОБАВИТЬ РЕЗУЛЬТАТ
    # =====================================================

    def add_result(
        self,
        match: str,
        score: str
    ) -> Dict:


        result = self.memory.add_result(
            match,
            score
        )


        if "error" not in result:

            self.memory.analyze_prediction(
                match
            )


        return result



    # =====================================================
    # АНАЛИЗ МОДЕЛИ
    # =====================================================

    def analyze_model(self) -> Dict:


        learning_result = (
            self.learning.analyze_history()
        )


        patterns = (
            self.learning.find_patterns()
        )


        return {

            "learning":

                learning_result,


            "patterns":

                patterns,


            "time":

                datetime.now().isoformat()

        }



    # =====================================================
    # ЗАПУСК КОРРЕКТИРОВКИ
    # =====================================================

    def run_correction(self) -> Dict:


        return self.correction.create_correction()



    # =====================================================
    # ПОЛНЫЙ СТАТУС МОЗГА
    # =====================================================

    def get_status(self) -> Dict:


        return {

            "memory":

                self.memory.get_statistics(),


            "learning":

                self.learning.get_status(),


            "correction":

                self.correction.get_status()

        }



    # =====================================================
    # ИСТОРИЯ
    # =====================================================

    def get_memory(self) -> List:

        return self.memory.get_memory()



# =====================================================
# ТЕСТ
# =====================================================

if __name__ == "__main__":


    print("=" * 50)
    print("FAJ Brain Manager v10.0")
    print("=" * 50)


    brain = FAJBrainManager()


    status = brain.get_status()


    print(status)

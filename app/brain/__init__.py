#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain System

Главный загрузчик мозга FAJ
"""

from .memory_brain import FAJMemoryBrain
from .learning_brain import FAJLearningBrain
from .correction_brain import FAJCorrectionBrain


__all__ = [
    "FAJMemoryBrain",
    "FAJLearningBrain",
    "FAJCorrectionBrain"
]


def get_brain_status():

    memory = FAJMemoryBrain()
    learning = FAJLearningBrain()
    correction = FAJCorrectionBrain()

    return {

        "memory":
            memory.get_statistics(),

        "learning":
            learning.get_status(),

        "correction":
            correction.get_status()

    }

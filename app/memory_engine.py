#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.0
Memory Engine

Главная задача:
- читать память FAJ
- сохранять новые наблюдения
- искать повторяющиеся ошибки
- готовить выводы для самообучения

Автор: FAJ Platform
"""

from pathlib import Path
import pandas as pd
from datetime import datetime


class MemoryEngine:

    def __init__(self):

        self.memory_file = Path("data/faj_memory.csv")

        if self.memory_file.exists():

            self.memory = pd.read_csv(self.memory_file)

        else:

            self.memory = pd.DataFrame(columns=[
                "date",
                "version",
                "object_type",
                "object_name",
                "category",
                "observation",
                "conclusion",
                "action",
                "status",
                "confidence"
            ])

    # -----------------------------------

    def save(self):

        self.memory.to_csv(
            self.memory_file,
            index=False,
            encoding="utf-8-sig"
        )

    # -----------------------------------

    def add_memory(
        self,
        version,
        object_type,
        object_name,
        category,
        observation,
        conclusion,
        action,
        confidence=1.0
    ):

        row = {

            "date": datetime.now().strftime("%Y-%m-%d"),

            "version": version,

            "object_type": object_type,

            "object_name": object_name,

            "category": category,

            "observation": observation,

            "conclusion": conclusion,

            "action": action,

            "status": "OPEN",

            "confidence": confidence

        }

        self.memory = pd.concat(
            [
                self.memory,
                pd.DataFrame([row])
            ],
            ignore_index=True
        )

        self.save()

    # -----------------------------------

    def get_open_memories(self):

        return self.memory[
            self.memory["status"] == "OPEN"
        ]

    # -----------------------------------

    def get_team_memory(self, team):

        return self.memory[
            self.memory["object_name"] == team
        ]

    # -----------------------------------

    def get_model_memory(self):

        return self.memory[
            self.memory["object_type"] == "MODEL"
        ]

    # -----------------------------------

    def apply_memory(self, index):

        self.memory.loc[index, "status"] = "APPLIED"

        self.save()

    # -----------------------------------

    def summary(self):

        print()

        print("========== FAJ MEMORY ==========")

        print()

        print(f"Всего записей: {len(self.memory)}")

        print()

        print(
            f"Открытых задач: "
            f"{len(self.get_open_memories())}"
        )

        print()

        print("===============================")

        print()


if __name__ == "__main__":

    memory = MemoryEngine()

    memory.summary()

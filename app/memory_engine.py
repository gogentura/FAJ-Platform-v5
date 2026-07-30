#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

Memory Engine

Adaptive Learning Core

Функции:

- хранение опыта FAJ
- защита от дублей
- группировка ошибок
- анализ повторяемости
- подготовка данных для Calibration Engine

"""


from pathlib import Path
from datetime import datetime
import pandas as pd



class MemoryEngine:


    def __init__(self):


        self.memory_file = Path(
            "data/faj_memory.csv"
        )


        self.columns = [

            "id",
            "date",
            "version",
            "cycle",
            "object_type",
            "object_name",
            "category",
            "observation",
            "conclusion",
            "action",
            "status",
            "confidence"

        ]


        if self.memory_file.exists():

            self.memory = pd.read_csv(
                self.memory_file,
                encoding="utf-8-sig"
            )


        else:


            self.memory = pd.DataFrame(
                columns=self.columns
            )



    # =================================


    def save(self):


        self.memory.to_csv(

            self.memory_file,

            index=False,

            encoding="utf-8-sig"

        )



    # =================================


    def exists(
        self,
        observation
    ):


        if len(self.memory)==0:

            return False


        result = self.memory[

            self.memory["observation"]
            ==
            observation

        ]


        return len(result) > 0



    # =================================


    def add_memory(

        self,

        version,

        object_type,

        object_name,

        category,

        observation,

        conclusion,

        action,

        confidence=0.8,

        cycle="LEARNING"

    ):


        # защита от дублей


        if self.exists(
            observation
        ):

            return False



        new_id = (

            len(self.memory)

        )



        row = {


            "id":
            new_id,


            "date":
            datetime.now().strftime(
                "%Y-%m-%d"
            ),


            "version":
            version,


            "cycle":
            cycle,


            "object_type":
            object_type,


            "object_name":
            object_name,


            "category":
            category,


            "observation":
            observation,


            "conclusion":
            conclusion,


            "action":
            action,


            "status":
            "OPEN",


            "confidence":
            confidence

        }



        self.memory = pd.concat(

            [

                self.memory,

                pd.DataFrame(
                    [row]
                )

            ],

            ignore_index=True

        )


        self.save()


        return True



    # =================================


    def get_open_memories(self):


        return self.memory[

            self.memory["status"]
            ==
            "OPEN"

        ]



    # =================================


    def get_model_errors(self):


        return self.memory[

            self.memory["category"]
            .astype(str)
            .str.contains(
                "Error"
            )

        ]



    # =================================


    def get_team_memory(
        self,
        team
    ):


        return self.memory[

            self.memory["object_name"]
            ==
            team

        ]



    # =================================


    def get_learning_summary(self):


        if len(self.memory)==0:

            return {}



        summary = {


            "total":

            len(
                self.memory
            ),


            "open":

            len(
                self.get_open_memories()
            ),


            "model_errors":

            len(
                self.get_model_errors()
            )

        }


        return summary



    # =================================


    def apply_memory(
        self,
        index
    ):


        self.memory.loc[

            index,

            "status"

        ] = "APPLIED"



        self.save()



    # =================================


    def clear_old_duplicates(self):


        if len(self.memory)==0:

            return



        self.memory = self.memory.drop_duplicates(

            subset=[

                "observation"

            ]

        )



        self.save()



    # =================================


    def summary(self):


        data = self.get_learning_summary()


        print()

        print(
            "========== FAJ MEMORY v9.2 =========="
        )


        print(
            "Всего:",
            data.get(
                "total"
            )
        )


        print(
            "Открытых:",
            data.get(
                "open"
            )
        )


        print(
            "Ошибок модели:",
            data.get(
                "model_errors"
            )
        )


        print(
            "====================================="
        )

        print()



if __name__ == "__main__":


    memory = MemoryEngine()

    memory.summary()

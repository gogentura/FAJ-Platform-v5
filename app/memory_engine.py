#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

Memory Engine

Назначение:

- хранение опыта FAJ
- защита от дублей
- поиск повторяющихся ошибок
- подготовка Learning Cycle


"""


from pathlib import Path
import pandas as pd
from datetime import datetime
import hashlib



class MemoryEngine:


    def __init__(self):


        self.memory_file = Path(
            "data/faj_memory.csv"
        )


        self.columns = [

            "id",

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

        ]



        if self.memory_file.exists():


            self.memory = pd.read_csv(

                self.memory_file,

                encoding="utf-8-sig"

            )


            # восстановление старых файлов


            for col in self.columns:


                if col not in self.memory.columns:

                    self.memory[col] = ""



        else:


            self.memory = pd.DataFrame(

                columns=self.columns

            )



        self.memory = self.cleanup_duplicates()



    # =====================================


    def generate_id(
        self,
        row
    ):


        text = (

            str(row["object_type"])

            +

            str(row["object_name"])

            +

            str(row["category"])

            +

            str(row["observation"])

        )


        return hashlib.md5(

            text.encode("utf-8")

        ).hexdigest()



    # =====================================


    def save(self):


        self.memory.to_csv(

            self.memory_file,

            index=False,

            encoding="utf-8-sig"

        )



    # =====================================


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


            "date":

                datetime.now().strftime(
                    "%Y-%m-%d"
                ),


            "version":

                version,


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



        row["id"] = self.generate_id(
            row
        )



        # ===========================
        # антидубликат


        exists = self.memory[

            self.memory["id"]

            ==

            row["id"]

        ]



        if len(exists) > 0:


            print(

                "FAJ MEMORY: duplicate skipped"

            )


            return False



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



    # =====================================


    def cleanup_duplicates(self):


        if len(self.memory) == 0:


            return self.memory



        before = len(
            self.memory
        )



        if "id" not in self.memory.columns:


            self.memory["id"] = ""



        self.memory["id"] = self.memory.apply(

            self.generate_id,

            axis=1

        )



        self.memory = self.memory.drop_duplicates(

            subset=["id"],

            keep="first"

        )



        after = len(
            self.memory
        )



        if before != after:


            print(

                f"FAJ MEMORY CLEANUP: "
                f"{before-after} duplicates removed"

            )


            self.save()



        return self.memory



    # =====================================


    def get_open_memories(self):


        return self.memory[

            self.memory["status"]

            ==

            "OPEN"

        ]



    # =====================================


    def get_team_memory(
        self,
        team
    ):


        return self.memory[

            self.memory["object_name"]

            ==

            team

        ]



    # =====================================


    def get_model_memory(self):


        return self.memory[

            self.memory["object_type"]

            ==

            "MODEL"

        ]



    # =====================================


    def get_system_memory(self):


        return self.memory[

            self.memory["object_type"]

            ==

            "SYSTEM"

        ]



    # =====================================


    def apply_memory(
        self,
        index
    ):


        self.memory.loc[

            index,

            "status"

        ] = "APPLIED"



        self.save()



    # =====================================


    def summary(self):


        print()

        print(
            "========== FAJ MEMORY =========="
        )


        print(
            "Всего записей:",
            len(self.memory)
        )


        print(
            "MODEL:",
            len(
                self.get_model_memory()
            )
        )


        print(
            "TEAM:",
            len(

                self.memory[

                    self.memory["object_type"]

                    ==

                    "TEAM"

                ]

            )
        )


        print(
            "SYSTEM:",
            len(
                self.get_system_memory()
            )
        )


        print(
            "OPEN:",
            len(
                self.get_open_memories()
            )
        )


        print(
            "==============================="
        )


        print()



if __name__ == "__main__":


    memory = MemoryEngine()


    memory.summary()

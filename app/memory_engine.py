#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.2

Memory Engine

Назначение:

Центральная память FAJ.

Функции:

- хранение опыта
- защита от дублей
- анализ ошибок
- обучение модели
- подготовка Calibration Engine

"""


from datetime import datetime
import hashlib



class MemoryEngine:


    def __init__(self):

        self.version = "9.2"

        self.memory = []



    # ==================================================

    def generate_id(
        self,
        object_name,
        category,
        observation
    ):

        raw = (

            object_name +
            category +
            observation

        )

        return hashlib.md5(
            raw.encode("utf-8")
        ).hexdigest()[:10]



    # ==================================================

    def exists(
        self,
        memory_id
    ):


        for item in self.memory:

            if item.get("id") == memory_id:

                return True


        return False



    # ==================================================

    def add_memory(

        self,

        version,

        object_type,

        object_name,

        category,

        observation,

        conclusion,

        action,

        confidence=0.8

    ):


        memory_id = self.generate_id(

            object_name,

            category,

            observation

        )



        # защита от повторов

        if self.exists(memory_id):

            print(

                "[FAJ MEMORY] Duplicate skipped:",

                observation[:50]

            )

            return False



        record = {


            "id":

                memory_id,


            "date":

                datetime.now()
                .strftime(
                    "%Y-%m-%d"
                ),


            "version":

                version,


            "object_type":

                object_type,


            "object":

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



        self.memory.append(
            record
        )


        print(

            "[FAJ MEMORY] Added:",

            category

        )


        return True



    # ==================================================

    def search(

        self,

        keyword

    ):


        result = []


        for item in self.memory:


            text = (

                item["observation"]
                +
                item["category"]

            ).lower()



            if keyword.lower() in text:


                result.append(item)



        return result



    # ==================================================

    def get_open_memory(self):


        return [

            x for x in self.memory

            if x["status"] == "OPEN"

        ]



    # ==================================================

    def mark_learned(

        self,

        memory_id

    ):


        for item in self.memory:


            if item["id"] == memory_id:


                item["status"] = "LEARNED"

                return True



        return False



    # ==================================================

    def statistics(self):


        model_errors = 0
        team_events = 0
        system_events = 0



        for item in self.memory:


            if item["object_type"] == "MODEL":

                model_errors += 1


            elif item["object_type"] == "TEAM":

                team_events += 1


            elif item["object_type"] == "SYSTEM":

                system_events += 1



        return {


            "total":

                len(self.memory),


            "model":

                model_errors,


            "team":

                team_events,


            "system":

                system_events


        }



    # ==================================================

    def export(self):


        return self.memory




# ==================================================


if __name__ == "__main__":


    memory = MemoryEngine()



    memory.add_memory(

        version="9.2",

        object_type="MODEL",

        object_name="FAJ",

        category="Prediction Error",

        observation=

        "ЦСКА - Балтика | FAJ X | Fact P1",

        conclusion=

        "Переоценена вероятность ничьей",

        action=

        "Снизить draw weight",

        confidence=0.9

    )



    # повтор специально

    memory.add_memory(

        version="9.2",

        object_type="MODEL",

        object_name="FAJ",

        category="Prediction Error",

        observation=

        "ЦСКА - Балтика | FAJ X | Fact P1",

        conclusion=

        "Переоценена вероятность ничьей",

        action=

        "Снизить draw weight",

        confidence=0.9

    )



    print()

    print(
        memory.statistics()
    )

"""
FAJ RPL Database
FAJ Platform v5.1
Snapshot: 21.07.2026
"""

import os
import json


PASSPORT_DIR = "data/passports"


RPL_TEAMS = [

    {
        "name": "Зенит",
        "attack": 88,
        "defense": 79,
        "form": 84,
        "home": 93,
        "away": 87,
        "uncertainty": 16,
        "rating": 91.8
    },

    {
        "name": "Локомотив",
        "attack": 81,
        "defense": 78,
        "form": 87,
        "home": 87,
        "away": 80,
        "uncertainty": 20,
        "rating": 90.2
    },

    {
        "name": "Краснодар",
        "attack": 80,
        "defense": 77,
        "form": 79,
        "home": 86,
        "away": 79,
        "uncertainty": 22,
        "rating": 89.9
    },

    {
        "name": "Динамо",
        "attack": 80,
        "defense": 78,
        "form": 81,
        "home": 88,
        "away": 79,
        "uncertainty": 24,
        "rating": 88.9
    },

    {
        "name": "Ахмат",
        "attack": 76,
        "defense": 75,
        "form": 78,
        "home": 80,
        "away": 72,
        "uncertainty": 28,
        "rating": 87.1
    },

    {
        "name": "ЦСКА",
        "attack": 78,
        "defense": 80,
        "form": 79,
        "home": 85,
        "away": 76,
        "uncertainty": 26,
        "rating": 86.9
    },

    {
        "name": "Спартак",
        "attack": 80,
        "defense": 76,
        "form": 76,
        "home": 84,
        "away": 74,
        "uncertainty": 32,
        "rating": 86.8
    },

    {
        "name": "Рубин",
        "attack": 75,
        "defense": 76,
        "form": 71,
        "home": 81,
        "away": 73,
        "uncertainty": 30,
        "rating": 85.2
    },

    {
        "name": "Ростов",
        "attack": 74,
        "defense": 74,
        "form": 74,
        "home": 79,
        "away": 70,
        "uncertainty": 28,
        "rating": 84.5
    },

    {
        "name": "Балтика",
        "attack": 71,
        "defense": 72,
        "form": 76,
        "home": 78,
        "away": 67,
        "uncertainty": 26,
        "rating": 83.5
    },

    {
        "name": "Акрон",
        "attack": 70,
        "defense": 71,
        "form": 75,
        "home": 76,
        "away": 66,
        "uncertainty": 30,
        "rating": 82.8
    },

    {
        "name": "Оренбург",
        "attack": 72,
        "defense": 73,
        "form": 70,
        "home": 77,
        "away": 68,
        "uncertainty": 32,
        "rating": 82.5
    },

    {
        "name": "Факел",
        "attack": 70,
        "defense": 72,
        "form": 68,
        "home": 76,
        "away": 65,
        "uncertainty": 34,
        "rating": 81.5
    },

    {
        "name": "Крылья Советов",
        "attack": 69,
        "defense": 71,
        "form": 67,
        "home": 74,
        "away": 64,
        "uncertainty": 36,
        "rating": 80.8
    },

    {
        "name": "Динамо Мх",
        "attack": 68,
        "defense": 70,
        "form": 70,
        "home": 72,
        "away": 63,
        "uncertainty": 32,
        "rating": 80.5
    },

    {
        "name": "Родина",
        "attack": 67,
        "defense": 69,
        "form": 68,
        "home": 70,
        "away": 61,
        "uncertainty": 38,
        "rating": 79.5
    }

]


def create_rpl_database():

    os.makedirs(
        PASSPORT_DIR,
        exist_ok=True
    )


    for team in RPL_TEAMS:

        filename = (
            team["name"]
            .lower()
            .replace(" ", "_")
            + ".json"
        )


        passport = {

            "version": "FAJ v3.4",

            "league": "РПЛ",

            "season": "2026/27",

            "snapshot": "21.07.2026",

            "source": "FAJ Database",

            **team,

            "xg": 1.4,

            "form_index": team["form"]

        }


        path = os.path.join(
            PASSPORT_DIR,
            filename
        )


        with open(
            path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                passport,
                file,
                ensure_ascii=False,
                indent=4
            )


    return True


if __name__ == "__main__":

    create_rpl_database()

    print(
        "FAJ RPL Database created"
    )

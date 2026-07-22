"""
FAJ Passport Manager v5.1
Работа с Team Passport Database
"""

import json
import os
from datetime import datetime


PASSPORT_DIR = "data/passports"


def ensure_dir():

    os.makedirs(
        PASSPORT_DIR,
        exist_ok=True
    )



def normalize(name):

    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
    )



def passport_file(team):

    return os.path.join(
        PASSPORT_DIR,
        normalize(team) + ".json"
    )



def save_passport(team, passport):

    ensure_dir()

    passport["last_updated"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with open(
        passport_file(team),
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            passport,
            f,
            ensure_ascii=False,
            indent=4
        )


    return True



def load_passport(team):

    file = passport_file(team)

    if not os.path.exists(file):

        return None


    with open(
        file,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



def passport_exists(team):

    return load_passport(team) is not None



def get_all():

    ensure_dir()

    result = []


    for file in os.listdir(PASSPORT_DIR):

        if file.endswith(".json"):

            with open(
                os.path.join(
                    PASSPORT_DIR,
                    file
                ),
                encoding="utf-8"
            ) as f:

                result.append(
                    json.load(f)
                )


    return result

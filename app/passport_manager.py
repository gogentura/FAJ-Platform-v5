"""
FAJ Passport Manager
FAJ Platform v5.1
"""

import json
import os
from datetime import datetime


PASSPORT_DIR = "data/passports"


def _ensure_dir():
    os.makedirs(PASSPORT_DIR, exist_ok=True)



def _prepare_passport(passport: dict):

    # совместимость FAJ v3.x / v5.1

    if "xg" not in passport:

        passport["xg"] = {
            "value": 1.4,
            "source": "faj"
        }


    if "avg_goals" not in passport:

        passport["avg_goals"] = {
            "value": 1.5,
            "source": "faj"
        }


    if "avg_goals_conceded" not in passport:

        passport["avg_goals_conceded"] = {
            "value": 1.0,
            "source": "faj"
        }


    if "avg_possession" not in passport:

        passport["avg_possession"] = {
            "value": 50,
            "source": "faj"
        }


    return passport



def save_passport(team_name: str, passport: dict):

    _ensure_dir()

    passport = _prepare_passport(passport)


    passport["updated_at"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    filename = os.path.join(
        PASSPORT_DIR,
        f"{team_name.lower().replace(' ', '_')}.json"
    )


    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            passport,
            file,
            ensure_ascii=False,
            indent=4
        )


    return filename



def load_passport(team_name: str):

    filename = os.path.join(
        PASSPORT_DIR,
        f"{team_name.lower().replace(' ', '_')}.json"
    )


    if not os.path.exists(filename):
        return None


    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)



def is_updated_today(team_name: str):

    return load_passport(team_name) is not None

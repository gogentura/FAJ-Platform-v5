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



def _filename(team_name: str):

    return os.path.join(
        PASSPORT_DIR,
        f"{team_name.lower().replace(' ', '_')}.json"
    )



def _prepare_passport(passport: dict):

    # Версия FAJ
    if "version" not in passport:
        passport["version"] = "5.1.0"


    # Команда
    if "team" not in passport:
        passport["team"] = "Unknown"


    # Лига
    if "league" not in passport:
        passport["league"] = "Unknown"


    # Источник
    if "source" not in passport:
        passport["source"] = "faj"


    # xG совместимость FAJ v3.x / v5.1
    if "xg" not in passport:

        passport["xg"] = {
            "value": 1.4,
            "source": "faj"
        }


    # Голы
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


    # Владение
    if "avg_possession" not in passport:

        passport["avg_possession"] = {
            "value": 50,
            "source": "faj"
        }


    # Форма
    if "form" not in passport:

        passport["form"] = {
            "value": 0.5,
            "source": "faj"
        }


    # Время обновления
    passport["updated_at"] = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    return passport



def save_passport(team_name: str, passport: dict):

    _ensure_dir()

    passport = _prepare_passport(passport)


    filename = _filename(team_name)


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

    filename = _filename(team_name)


    if not os.path.exists(filename):

        return None


    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:

        passport = json.load(file)


    return _prepare_passport(passport)



def is_updated_today(team_name: str):

    passport = load_passport(team_name)

    if passport is None:

        return False


    return True



def get_all_passports():

    _ensure_dir()

    result = []


    for file_name in os.listdir(PASSPORT_DIR):

        if file_name.endswith(".json"):

            with open(
                os.path.join(PASSPORT_DIR, file_name),
                "r",
                encoding="utf-8"
            ) as file:

                result.append(
                    json.load(file)
                )


    return result

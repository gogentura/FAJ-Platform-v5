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
    passport.setdefault(
        "version",
        "5.1.0"
    )


    # Основные поля
    passport.setdefault(
        "team",
        "Unknown"
    )

    passport.setdefault(
        "league",
        "Unknown"
    )

    passport.setdefault(
        "source",
        "faj"
    )


    # Совместимость xG
    passport.setdefault(
        "xg",
        {
            "value": 1.4,
            "source": "faj"
        }
    )


    # Голы
    passport.setdefault(
        "avg_goals",
        {
            "value": 1.5,
            "source": "faj"
        }
    )


    passport.setdefault(
        "avg_goals_conceded",
        {
            "value": 1.0,
            "source": "faj"
        }
    )


    # Владение
    passport.setdefault(
        "avg_possession",
        {
            "value": 50,
            "source": "faj"
        }
    )


    # Форма
    passport.setdefault(
        "form",
        {
            "value": 0.5,
            "source": "faj"
        }
    )


    # Дата обновления
    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    passport["updated_at"] = now

    # Старое имя поля для старых модулей FAJ
    passport["last_updated"] = now


    return passport



def save_passport(team_name: str, passport: dict):

    _ensure_dir()


    passport = _prepare_passport(
        passport
    )


    filename = _filename(
        team_name
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

    filename = _filename(
        team_name
    )


    if not os.path.exists(filename):

        return None


    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:

        passport = json.load(file)


    return _prepare_passport(
        passport
    )



def is_updated_today(team_name: str):

    passport = load_passport(
        team_name
    )

    return passport is not None



def get_all_passports():

    _ensure_dir()

    passports = []


    for filename in os.listdir(
        PASSPORT_DIR
    ):

        if filename.endswith(".json"):

            with open(
                os.path.join(
                    PASSPORT_DIR,
                    filename
                ),
                "r",
                encoding="utf-8"
            ) as file:

                passports.append(
                    json.load(file)
                )


    return passports

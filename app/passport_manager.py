"""
FAJ Passport Manager
FAJ Platform v5.1
Compatible with FAJ Engine v3.x
"""

import json
import os
from datetime import datetime


PASSPORT_DIR = "data/passports"



def _ensure_dir():
    os.makedirs(PASSPORT_DIR, exist_ok=True)



def _filename(team_name):

    return os.path.join(
        PASSPORT_DIR,
        f"{team_name.lower().replace(' ', '_')}.json"
    )



def _metric(value=70, source="faj"):

    return {
        "value": value,
        "source": source
    }



def _prepare_passport(passport: dict):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    passport.setdefault(
        "version",
        "5.1.0"
    )


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
        "api-football"
    )


    passport.setdefault(
        "last_updated",
        now
    )


    passport.setdefault(
        "updated_at",
        now
    )


    # Основные статистические поля

    passport.setdefault(
        "xg",
        {
            "value": 1.4,
            "source": "faj"
        }
    )


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


    passport.setdefault(
        "avg_possession",
        {
            "value": 50,
            "source": "faj"
        }
    )


    passport.setdefault(
        "form",
        {
            "value": 0.5,
            "source": "faj"
        }
    )


    # FAJ Team Passport

    passport.setdefault(
        "attack",
        _metric(70)
    )


    passport.setdefault(
        "defense",
        _metric(70)
    )


    passport.setdefault(
        "control",
        _metric(70)
    )


    passport.setdefault(
        "efficiency",
        _metric(70)
    )


    passport.setdefault(
        "mentality",
        _metric(70)
    )


    passport.setdefault(
        "discipline",
        _metric(70)
    )


    passport.setdefault(
        "fitness",
        _metric(70)
    )


    passport.setdefault(
        "predictability",
        _metric(70)
    )


    passport.setdefault(
        "opposition_strength",
        _metric(70)
    )


    passport.setdefault(
        "transfer_index",
        _metric(70)
    )


    passport.setdefault(
        "injury_index",
        _metric(0)
    )


    passport.setdefault(
        "fatigue_index",
        _metric(0)
    )


    return passport



def save_passport(team_name, passport):

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
    ) as f:

        json.dump(
            passport,
            f,
            ensure_ascii=False,
            indent=4
        )


    return filename



def load_passport(team_name):

    filename = _filename(
        team_name
    )


    if not os.path.exists(filename):

        return None


    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as f:

        passport = json.load(f)


    return _prepare_passport(
        passport
    )



def is_updated_today(team_name):

    return load_passport(team_name) is not None



def get_all_passports():

    _ensure_dir()

    passports = []


    for file in os.listdir(PASSPORT_DIR):

        if file.endswith(".json"):

            with open(
                os.path.join(
                    PASSPORT_DIR,
                    file
                ),
                "r",
                encoding="utf-8"
            ) as f:

                passports.append(
                    json.load(f)
                )


    return passports

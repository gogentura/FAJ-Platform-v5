import os
import json
from datetime import datetime


PASSPORT_DIR = "data/passports"


def _path(team_name: str):

    name = (
        team_name
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    return os.path.join(
        PASSPORT_DIR,
        name + ".json"
    )


def save_passport(team_name: str, passport: dict):

    os.makedirs(
        PASSPORT_DIR,
        exist_ok=True
    )

    passport.setdefault("team", team_name)
    passport.setdefault("league", "РПЛ")
    passport.setdefault("version", "5.1")

    passport.setdefault("attack", 70)
    passport.setdefault("defense", 70)
    passport.setdefault("control", 70)
    passport.setdefault("form_index", 70)

    passport.setdefault(
        "historical_xg_value",
        1.35
    )

    passport.setdefault(
        "last_updated",
        datetime.now().strftime("%Y-%m-%d")
    )


    with open(
        _path(team_name),
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            passport,
            f,
            ensure_ascii=False,
            indent=4
        )


    return passport



def load_passport(team_name: str):

    path = _path(team_name)

    print("DEBUG PASSPORT PATH:", path)


    if not os.path.exists(path):

        print("DEBUG PASSPORT NOT FOUND")

        return None


    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            passport = json.load(f)


        print(
            "DEBUG PASSPORT DATA:",
            passport
        )


        return passport


    except Exception as e:

        print(
            "DEBUG PASSPORT ERROR:",
            e
        )

        return None



def is_updated_today(team_name: str):

    passport = load_passport(team_name)

    if not passport:
        return False


    updated = passport.get(
        "last_updated"
    )


    if not updated:

        updated = passport.get(
            "updated"
        )


    return (
        updated ==
        datetime.now().strftime("%Y-%m-%d")
    )



def delete_passport(team_name: str):

    path = _path(team_name)


    if os.path.exists(path):

        os.remove(path)

        return True


    return False

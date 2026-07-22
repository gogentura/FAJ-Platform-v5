import os
import json
from datetime import datetime


PASSPORT_DIR = "data/passports"


def _path(team_name):
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


def save_passport(team_name, passport):

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



def load_passport(team_name):

    path = _path(team_name)


    if not os.path.exists(path):
        return None


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



def is_updated_today(team_name):

    passport = load_passport(team_name)

    return passport is not None



def delete_passport(team_name):

    path = _path(team_name)

    if os.path.exists(path):
        os.remove(path)

        return True

    return False

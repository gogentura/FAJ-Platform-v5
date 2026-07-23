import os
import json
from datetime import datetime


PASSPORT_DIR = "data/passports"
ALIASES_FILE = "data/aliases/teams.json"


def _load_aliases():

    if not os.path.exists(ALIASES_FILE):
        return {}

    with open(
        ALIASES_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def _normalize_team_name(team_name: str):

    aliases = _load_aliases()

    key = team_name.lower().strip()

    return aliases.get(
        key,
        key.replace(" ", "_")
    )


def _path(team_name: str):

    filename = _normalize_team_name(team_name)

    return os.path.join(
        PASSPORT_DIR,
        filename + ".json"
    )


def save_passport(team_name: str, passport: dict):

    os.makedirs(
        PASSPORT_DIR,
        exist_ok=True
    )

    passport.setdefault("team", team_name)
    passport.setdefault("league", "РПЛ")
    passport.setdefault("version", "5.2")

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

    if not os.path.exists(path):
        return None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        passport = json.load(f)

    return passport


def is_updated_today(team_name: str):

    passport = load_passport(team_name)

    if not passport:
        return False

    return passport.get(
        "last_updated"
    ) == datetime.now().strftime("%Y-%m-%d")


def delete_passport(team_name: str):

    path = _path(team_name)

    if os.path.exists(path):

        os.remove(path)

        return True

    return False

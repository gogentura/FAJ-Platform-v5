import os
import json
from datetime import datetime


PASSPORT_DIR = "app/data/passports"


def _passport_path(team_name):
    filename = (
        team_name
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        + ".json"
    )

    return os.path.join(
        PASSPORT_DIR,
        filename
    )


def ensure_directory():
    os.makedirs(
        PASSPORT_DIR,
        exist_ok=True
    )


def save_passport(team_name, passport):
    """
    Сохранение паспорта команды
    FAJ Platform v5.1
    """

    ensure_directory()

    passport.setdefault(
        "team",
        team_name
    )

    passport.setdefault(
        "version",
        "5.1"
    )

    passport.setdefault(
        "last_updated",
        datetime.now().strftime("%Y-%m-%d")
    )

    passport.setdefault(
        "attack",
        70
    )

    passport.setdefault(
        "defense",
        70
    )

    passport.setdefault(
        "form_index",
        70
    )

    passport.setdefault(
        "historical_xg_value",
        1.35
    )


    path = _passport_path(team_name)

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



def load_passport(team_name):
    """
    Загрузка паспорта команды
    """

    ensure_directory()

    path = _passport_path(team_name)


    if not os.path.exists(path):
        return None


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        passport = json.load(file)


    return passport



def is_updated_today(team_name):
    """
    Проверка наличия паспорта
    """

    passport = load_passport(team_name)

    if passport is None:
        return False


    return True



def delete_passport(team_name):
    """
    Удаление паспорта
    """

    path = _passport_path(team_name)

    if os.path.exists(path):
        os.remove(path)

        return True


    return False



def list_passports():
    """
    Список доступных паспортов
    """

    ensure_directory()

    return os.listdir(
        PASSPORT_DIR
    )

import json
from datetime import datetime

from app.config import Config


def _load_aliases():

    if not Config.ALIASES_FILE.exists():
        return {}

    with open(
        Config.ALIASES_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def normalize_team_name(team_name: str):

    aliases = _load_aliases()

    key = team_name.lower().strip()

    return aliases.get(
        key,
        key.replace(" ", "_")
    )


def passport_path(team_name: str):

    filename = normalize_team_name(team_name)

    return Config.PASSPORT_DIR / f"{filename}.json"


def save_passport(team_name: str, passport: dict):

    Config.PASSPORT_DIR.mkdir(
        parents=True,
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

    path = passport_path(team_name)

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            passport,
            f,
            ensure_ascii=False,
            indent=4
        )

    print(f"FAJ SAVE PASSPORT -> {path}")

    return passport


def load_passport(team_name: str):

    path = passport_path(team_name)

    print("=" * 60)
    print("FAJ PASSPORT")
    print("TEAM:", team_name)
    print("PATH:", path)

    if not path.exists():

        print("FILE NOT FOUND")
        print("=" * 60)

        return None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        passport = json.load(f)

    print(
        "ATTACK:",
        passport.get("attack")
    )

    print(
        "DEFENSE:",
        passport.get("defense")
    )

    print(
        "CONTROL:",
        passport.get("control")
    )

    print(
        "XG:",
        passport.get("historical_xg_value")
    )

    print("=" * 60)

    return passport


def delete_passport(team_name: str):

    path = passport_path(team_name)

    if path.exists():

        path.unlink()

        return True

    return False


def is_updated_today(team_name: str):

    passport = load_passport(team_name)

    if passport is None:
        return False

    return passport.get(
        "last_updated"
    ) == datetime.now().strftime("%Y-%m-%d")

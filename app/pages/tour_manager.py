#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Tour Manager v5.0

Главная задача:
    соревнование -> сезон -> паспорта клубов -> тур -> матчи.

КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ v5.0
--------------------------
Tour Manager теперь НЕ просто создаёт команды.

При выборе соревнования автоматически гарантируется полный
контур сезона:

    FAJ Club Rating
          │
          ▼
       команды
          │
          ▼
      сезон 2026/27
          │
          ▼
   team_passports
          │
          └── faj_rating = текущий рейтинг клуба

То есть каждый клуб получает отдельный паспорт именно для
выбранного сезона.

ВАЖНО:
    - Tour Manager НЕ рассчитывает рейтинг.
    - Tour Manager НЕ меняет рейтинг после матчей.
    - Tour Manager НЕ содержит прямого SQL.
    - Рейтинг берётся из FAJ Club Rating.
    - Паспорт создаётся только для пары team_id + season_id.
    - Существующий паспорт не перезаписывается.
    - ЛЧ имеет отдельный tournament context.
    - РПЛ / АПЛ / Ла Лига / ЛЧ не смешивают паспорта.

После этого рабочий поток:

    Tour Manager
        ↓
    team_passports.faj_rating
        ↓
    Prediction
        ↓
    Fact
        ↓
    ClubRatingUpdater
        ↓
    process_match_with_rating()
        ↓
    новый рейтинг + team_history

Tour Manager рейтинг не рассчитывает.
"""


from __future__ import annotations

import inspect
from typing import Any, Optional

import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.faj_club_ratings import (
    get_league_ratings,
    get_all_tournaments,
)


# ============================================================
# CONFIG
# ============================================================

COMPETITION_CONFIG = {
    "РПЛ": {
        "type": "domestic",
        "max_rounds": 30,
    },
    "АПЛ": {
        "type": "domestic",
        "max_rounds": 38,
    },
    "Ла Лига": {
        "type": "domestic",
        "max_rounds": 38,
    },
    "Лига чемпионов": {
        "type": "ucl",
        "max_rounds": 17,
    },
}


ROUND_LABELS = {
    "Лига чемпионов": {
        1: "Общий этап — Тур 1",
        2: "Общий этап — Тур 2",
        3: "Общий этап — Тур 3",
        4: "Общий этап — Тур 4",
        5: "Общий этап — Тур 5",
        6: "Общий этап — Тур 6",
        7: "Общий этап — Тур 7",
        8: "Общий этап — Тур 8",
        9: "Стыковые матчи — 1-й матч",
        10: "Стыковые матчи — 2-й матч",
        11: "1/8 финала — 1-й матч",
        12: "1/8 финала — 2-й матч",
        13: "Четвертьфинал — 1-й матч",
        14: "Четвертьфинал — 2-й матч",
        15: "Полуфинал — 1-й матч",
        16: "Полуфинал — 2-й матч",
        17: "Финал",
    }
}


SEASON_NAME = "2026/27"


# ============================================================
# GENERIC ROW HELPERS
# ============================================================

def row_value(
    row: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Безопасное чтение sqlite3.Row / dict / похожего объекта.
    """
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def team_id(team: Any) -> Any:
    if isinstance(team, dict):
        return team.get("id")

    try:
        return team["id"]
    except Exception:
        return getattr(team, "id", None)


def team_name(team: Any) -> str:
    if isinstance(team, dict):
        return str(
            team.get(
                "name",
                team.get("team_name", ""),
            )
        )

    try:
        return str(team["name"])
    except Exception:
        return str(getattr(team, "name", ""))


def season_id(season: Any) -> Any:
    if isinstance(season, dict):
        return season.get("id")

    try:
        return season["id"]
    except Exception:
        return getattr(season, "id", None)


def season_name(season: Any) -> str:
    if isinstance(season, dict):
        return str(
            season.get(
                "name",
                season.get("season_name", ""),
            )
        )

    try:
        return str(season["name"])
    except Exception:
        return str(getattr(season, "name", ""))


# ============================================================
# SEASON HELPERS
# ============================================================

def is_target_season(season: Any) -> bool:
    """
    Распознаёт:

        2026/27
        2026-27
        2026-2027

    как один целевой сезон.
    """
    value = (
        season_name(season)
        .strip()
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace(" ", "")
    )

    return value in {
        "2026/27",
        "2026-27",
        "2026-2027",
    } or (
        "2026/27" in value
        or "2026-27" in value
        or "2026-2027" in value
    )


def get_round_label(
    competition: str,
    number: int,
) -> str:
    return ROUND_LABELS.get(
        competition,
        {},
    ).get(
        int(number),
        f"Тур {number}",
    )


def match_is_locked(
    db: FAJDatabase,
    match_id: int,
) -> bool:
    try:
        return bool(
            db.is_result_locked(match_id)
        )
    except Exception:
        return False


# ============================================================
# PUBLIC DATABASE API COMPATIBILITY
# ============================================================

def _call_public_method(
    method,
    values: dict[str, Any],
):
    """
    Вызывает публичный метод без прямого SQL.

    Адаптирует разные варианты названий аргументов.
    """

    signature = inspect.signature(method)
    params = signature.parameters

    aliases = {
        "id": [
            "id",
            "passport_id",
            "team_passport_id",
        ],

        "team_id": [
            "team_id",
            "club_id",
        ],

        "season_id": [
            "season_id",
        ],

        "name": [
            "name",
            "season_name",
            "team_name",
        ],

        "team_name": [
            "team_name",
            "name",
        ],

        "league": [
            "league",
            "competition",
            "tournament",
        ],

        "competition": [
            "competition",
            "league",
            "tournament",
        ],

        "competition_type": [
            "competition_type",
            "tournament_type",
            "type",
        ],

        "year": [
            "year",
            "season_year",
        ],

        "status": [
            "status",
        ],

        "rating": [
            "rating",
            "faj_rating",
            "initial_rating",
            "starting_rating",
            "base_rating",
        ],

        "initial_rating": [
            "initial_rating",
            "starting_rating",
            "rating",
            "faj_rating",
        ],

        "faj_rating": [
            "faj_rating",
            "rating",
            "initial_rating",
            "starting_rating",
        ],
    }

    kwargs: dict[str, Any] = {}

    for logical_name, value in values.items():

        if value is None:
            continue

        candidates = aliases.get(
            logical_name,
            [logical_name],
        )

        for candidate in candidates:
            parameter = params.get(candidate)

            if parameter is not None:
                kwargs[candidate] = value
                break

    accepts_kwargs = any(
        parameter.kind
        == inspect.Parameter.VAR_KEYWORD
        for parameter in params.values()
    )

    if accepts_kwargs:
        for key, value in values.items():
            if value is not None:
                kwargs.setdefault(
                    key,
                    value,
                )

    return method(**kwargs)


# ============================================================
# CLUB RATING NORMALIZATION
# ============================================================

def _extract_rating_from_item(
    item: Any,
) -> Optional[float]:
    """
    Извлекает рейтинг из элемента FAJ Club Rating.

    Поддерживаются варианты:

        {"name": "...", "rating": 74.2}
        {"team_name": "...", "faj_rating": 74.2}
        {"name": "...", "initial_rating": 74.2}

    Если рейтинг отсутствует — возвращается None.
    """

    if isinstance(item, dict):

        candidates = (
            "faj_rating",
            "rating",
            "club_rating",
            "initial_rating",
            "starting_rating",
            "score",
        )

        for key in candidates:

            value = item.get(key)

            if value is None:
                continue

            try:
                return float(value)
            except (
                TypeError,
                ValueError,
            ):
                continue

    return None


def _extract_name_from_rating_item(
    item: Any,
) -> str:
    """
    Извлекает название клуба из записи Club Rating.
    """

    if isinstance(item, dict):

        for key in (
            "name",
            "team_name",
            "club_name",
            "team",
            "club",
        ):
            value = item.get(key)

            if value is not None:
                return str(value)

        return ""

    return str(item)


def _get_club_rating_catalog(
    competition: str,
) -> list[dict[str, Any]]:
    """
    Приводит результат get_league_ratings() к единому виду:

        [
            {
                "name": "...",
                "rating": 74.2,
            },
            ...
        ]

    ВАЖНО:

    если FAJ Club Rating возвращает только названия без рейтинга,
    пытаемся получить рейтинг через публичные атрибуты/функции
    модуля.

    Tour Manager никогда не подставляет искусственный рейтинг.
    """

    raw = get_league_ratings(
        competition
    )

    if raw is None:
        return []

    result: list[dict[str, Any]] = []

    # --------------------------------------------------------
    # dict:
    #
    # {
    #     "Команда": 74.2,
    #     ...
    # }
    # --------------------------------------------------------

    if isinstance(raw, dict):

        for name, value in raw.items():

            rating = None

            if isinstance(value, dict):
                rating = _extract_rating_from_item(
                    value
                )
                extracted_name = (
                    _extract_name_from_rating_item(
                        value
                    )
                    or str(name)
                )
            else:
                extracted_name = str(name)

                try:
                    rating = float(value)
                except (
                    TypeError,
                    ValueError,
                ):
                    rating = None

            result.append(
                {
                    "name": extracted_name,
                    "rating": rating,
                }
            )

        return result

    # --------------------------------------------------------
    # list / tuple
    # --------------------------------------------------------

    for item in raw:

        name = _extract_name_from_rating_item(
            item
        )

        rating = _extract_rating_from_item(
            item
        )

        result.append(
            {
                "name": name,
                "rating": rating,
            }
        )

    return result


# ============================================================
# FIND RATING IN FAJ CLUB RATING MODULE
# ============================================================

def _get_rating_from_module(
    competition: str,
    club_name: str,
) -> Optional[float]:
    """
    Если get_league_ratings() вернул только названия клубов,
    пробуем найти публичную функцию рейтинга.

    Никакого SQL.
    Никаких значений-заглушек.
    """

    try:
        import app.faj_club_ratings as rating_module
    except Exception:
        return None

    candidate_methods = (
        "get_club_rating",
        "get_team_rating",
        "get_rating",
        "get_faj_rating",
    )

    for method_name in candidate_methods:

        method = getattr(
            rating_module,
            method_name,
            None,
        )

        if not callable(method):
            continue

        candidates = [
            {
                "competition": competition,
                "team_name": club_name,
            },
            {
                "league": competition,
                "team_name": club_name,
            },
            {
                "competition": competition,
                "club_name": club_name,
            },
            {
                "team_name": club_name,
            },
            {
                "name": club_name,
            },
        ]

        for values in candidates:

            try:
                value = _call_public_method(
                    method,
                    values,
                )

                if value is None:
                    continue

                if isinstance(value, dict):
                    rating = _extract_rating_from_item(
                        value
                    )
                else:
                    rating = float(value)

                if rating is not None:
                    return float(rating)

            except Exception:
                continue

    return None


# ============================================================
# ENSURE SEASON
# ============================================================

def _ensure_season(
    db: FAJDatabase,
    competition: str,
):
    """
    Гарантирует наличие сезона 2026/27 именно для выбранного
    соревнования.
    """

    seasons = db.get_seasons()

    for season in seasons:

        if (
            str(
                row_value(
                    season,
                    "league",
                    "",
                )
            )
            == competition
            and is_target_season(season)
        ):
            return season

    candidates = (
        "create_season",
        "add_season",
        "insert_season",
    )

    for method_name in candidates:

        method = getattr(
            db,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            created = _call_public_method(
                method,
                {
                    "name": SEASON_NAME,
                    "league": competition,
                    "year": 2026,
                    "competition_type": (
                        "ucl"
                        if competition
                        == "Лига чемпионов"
                        else "league"
                    ),
                    "status": "active",
                },
            )

        except TypeError:
            continue

        seasons = db.get_seasons()

        for season in seasons:

            if (
                str(
                    row_value(
                        season,
                        "league",
                        "",
                    )
                )
                == competition
                and is_target_season(season)
            ):
                return season

        if created:

            for season in seasons:

                if season_id(season) == created:
                    return season

    raise RuntimeError(
        "Не удалось создать сезон "
        f"{SEASON_NAME} для «{competition}».\n"
        "database.py должен предоставлять "
        "публичный create_season/add_season."
    )


# ============================================================
# ENSURE TEAMS
# ============================================================

def _ensure_teams(
    db: FAJDatabase,
    competition: str,
):
    """
    Гарантирует наличие команд соревнования.

    Источник состава:
        FAJ Club Rating.

    Сам рейтинг здесь не рассчитывается.
    """

    catalog = _get_club_rating_catalog(
        competition
    )

    if not catalog:
        raise RuntimeError(
            f"FAJ Club Rating не вернул клубы "
            f"для «{competition}»."
        )

    existing = db.get_teams(
        league=competition
    )

    existing_by_name = {
        team_name(team): team
        for team in existing
    }

    missing = [
        item
        for item in catalog
        if item["name"]
        and item["name"]
        not in existing_by_name
    ]

    if missing:

        candidates = (
            "create_team",
            "add_team",
            "insert_team",
        )

        create_method = None

        for method_name in candidates:

            method = getattr(
                db,
                method_name,
                None,
            )

            if callable(method):

                create_method = method
                break

        if create_method is None:
            raise RuntimeError(
                f"database.py не предоставляет "
                f"публичный метод создания команд "
                f"для «{competition}»."
            )

        for item in missing:

            name = item["name"]

            _call_public_method(
                create_method,
                {
                    "name": name,
                    "team_name": name,
                    "league": competition,
                    "competition": competition,
                },
            )

    return db.get_teams(
        league=competition
    )


# ============================================================
# PASSPORT API
# ============================================================

def _get_passport_manager():
    """
    Возвращает PassportManager, если модуль существует.

    PassportManager является предпочтительным владельцем логики
    формирования паспорта.

    Tour Manager при этом не содержит SQL.
    """

    try:
        from app.passport_manager import PassportManager

        return PassportManager

    except ImportError:
        return None


def _get_passport_methods(
    manager: Any,
) -> list[Any]:
    """
    Получает возможные публичные методы PassportManager.
    """

    method_names = (
        "ensure_passport",
        "ensure_team_passport",
        "create_passport",
        "create_team_passport",
        "initialize_passport",
        "initialize_team_passport",
        "get_or_create_passport",
        "get_or_create_team_passport",
    )

    methods = []

    for name in method_names:

        method = getattr(
            manager,
            name,
            None,
        )

        if callable(method):
            methods.append(method)

    return methods


def _call_passport_method(
    method,
    team_id_value: int,
    season_id_value: int,
    rating: float,
    competition: str,
    team_name_value: str,
):
    """
    Универсальный вызов публичного API паспорта.

    Стартовый рейтинг передаётся явно.

    Никаких:
        50.0
        1000.0
        случайных значений.

    Только рейтинг FAJ Club Rating.
    """

    values = {
        "team_id": team_id_value,
        "season_id": season_id_value,
        "rating": rating,
        "initial_rating": rating,
        "faj_rating": rating,
        "team_name": team_name_value,
        "name": team_name_value,
        "competition": competition,
        "league": competition,
        "status": "active",
    }

    return _call_public_method(
        method,
        values,
    )


def _find_existing_passport(
    db: FAJDatabase,
    team_id_value: int,
    season_id_value: int,
):
    """
    Пытается получить существующий паспорт через публичные
    методы database.py.

    Никакого SQL.
    """

    candidate_methods = (
        "get_team_passport",
        "get_passport",
        "get_team_season_passport",
        "find_team_passport",
    )

    for method_name in candidate_methods:

        method = getattr(
            db,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            result = _call_public_method(
                method,
                {
                    "team_id": team_id_value,
                    "season_id": season_id_value,
                },
            )

            if result:
                return result

        except Exception:
            continue

    return None


def _ensure_team_passport(
    db: FAJDatabase,
    team: Any,
    season: Any,
    rating: float,
    competition: str,
) -> Any:
    """
    Гарантирует паспорт клуба для конкретного сезона.

    ИНВАРИАНТ:

        team_id + season_id

    определяют паспорт.

    Если паспорт уже существует — он НЕ перезаписывается.

    Если отсутствует — создаётся с рейтингом FAJ Club Rating.
    """

    tid = team_id(team)
    sid = season_id(season)
    tname = team_name(team)

    if tid is None:
        raise RuntimeError(
            f"У команды «{tname}» отсутствует ID."
        )

    if sid is None:
        raise RuntimeError(
            f"У сезона «{season_name(season)}» отсутствует ID."
        )

    tid = int(tid)
    sid = int(sid)

    # --------------------------------------------------------
    # 1. Сначала проверяем существующий паспорт.
    # --------------------------------------------------------

    existing = _find_existing_passport(
        db,
        tid,
        sid,
    )

    if existing:
        return existing

    # --------------------------------------------------------
    # 2. PassportManager — основной путь.
    # --------------------------------------------------------

    PassportManager = _get_passport_manager()

    if PassportManager is not None:

        manager = None

        # Поддерживаем как PassportManager(db),
        # так и PassportManager().

        for constructor_args in (
            (db,),
            (),
        ):

            try:
                manager = PassportManager(
                    *constructor_args
                )
                break
            except TypeError:
                continue

        if manager is not None:

            methods = _get_passport_methods(
                manager
            )

            for method in methods:

                try:

                    result = _call_passport_method(
                        method,
                        tid,
                        sid,
                        float(rating),
                        competition,
                        tname,
                    )

                    if result is not None:
                        return result

                    # Некоторые ensure_* методы могут
                    # ничего не возвращать. Повторно читаем
                    # через публичный API.
                    existing = _find_existing_passport(
                        db,
                        tid,
                        sid,
                    )

                    if existing:
                        return existing

                except TypeError:
                    continue

                except Exception as exc:

                    # Ошибки реального метода не скрываем,
                    # если это уже был подходящий метод.
                    raise RuntimeError(
                        "Ошибка создания паспорта "
                        f"для «{tname}», "
                        f"season_id={sid}: {exc}"
                    ) from exc

    # --------------------------------------------------------
    # 3. Прямой публичный API FAJDatabase.
    # --------------------------------------------------------

    candidates = (
        "ensure_team_passport",
        "ensure_passport",
        "create_team_passport",
        "create_passport",
        "initialize_team_passport",
        "initialize_passport",
        "get_or_create_team_passport",
        "get_or_create_passport",
    )

    for method_name in candidates:

        method = getattr(
            db,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            result = _call_passport_method(
                method,
                tid,
                sid,
                float(rating),
                competition,
                tname,
            )

            if result is not None:
                return result

            existing = _find_existing_passport(
                db,
                tid,
                sid,
            )

            if existing:
                return existing

        except TypeError:
            continue

        except Exception as exc:

            raise RuntimeError(
                "Ошибка создания паспорта "
                f"для «{tname}», "
                f"season_id={sid}: {exc}"
            ) from exc

    raise RuntimeError(
        "Не найден публичный API формирования "
        "team_passport.\n\n"
        "Ожидался PassportManager или один из "
        "публичных методов FAJDatabase:\n"
        "ensure_team_passport / ensure_passport /\n"
        "create_team_passport / create_passport."
    )


# ============================================================
# ENSURE PASSPORTS FOR COMPETITION
# ============================================================

def _ensure_passports(
    db: FAJDatabase,
    competition: str,
    season: Any,
    teams: list[Any],
) -> dict[int, dict[str, Any]]:
    """
    Формирует паспорта всех клубов выбранного соревнования
    на выбранный сезон.

    Источник стартового рейтинга:
        FAJ Club Rating.

    Результат:

        {
            team_id: {
                "team": ...,
                "rating": ...,
                "passport": ...
            }
        }

    КРИТИЧЕСКОЕ ПРАВИЛО:

        отсутствующий рейтинг = ОШИБКА.

    Мы не создаём паспорт с искусственным рейтингом.
    """

    sid = int(
        season_id(season)
    )

    catalog = _get_club_rating_catalog(
        competition
    )

    rating_by_name: dict[str, Optional[float]] = {}

    for item in catalog:

        name = str(
            item["name"]
        ).strip()

        rating = item.get(
            "rating"
        )

        if rating is None:

            rating = _get_rating_from_module(
                competition,
                name,
            )

        if rating is not None:

            try:
                rating = float(rating)
            except (
                TypeError,
                ValueError,
            ):
                rating = None

        rating_by_name[name] = rating

    passports: dict[
        int,
        dict[str, Any]
    ] = {}

    for team in teams:

        tid = team_id(team)
        tname = team_name(team).strip()

        if tid is None:
            raise RuntimeError(
                f"Команда «{tname}» не имеет ID."
            )

        # ----------------------------------------------------
        # Ищем рейтинг строго по имени клуба.
        # ----------------------------------------------------

        rating = rating_by_name.get(
            tname
        )

        # Дополнительный публичный lookup,
        # если каталог не дал значение.
        if rating is None:

            rating = _get_rating_from_module(
                competition,
                tname,
            )

        if rating is None:

            raise RuntimeError(
                "Невозможно сформировать паспорт "
                f"клуба «{tname}».\n\n"
                "Для него отсутствует текущий "
                "рейтинг FAJ Club Rating.\n\n"
                "Искусственный стартовый рейтинг "
                "не используется."
            )

        passport = _ensure_team_passport(
            db=db,
            team=team,
            season=season,
            rating=float(rating),
            competition=competition,
        )

        passports[int(tid)] = {
            "team": team,
            "rating": float(rating),
            "passport": passport,
        }

    if len(passports) != len(teams):

        raise RuntimeError(
            "Не все клубы получили паспорта "
            f"сезона {season_name(season)}."
        )

    return passports


# ============================================================
# FULL COMPETITION BOOTSTRAP
# ============================================================

def ensure_competition_data(
    db: FAJDatabase,
    competition: str,
):
    """
    Полный bootstrap соревнования.

    Порядок:

        1. Club Rating существует
        2. сезон 2026/27
        3. команды
        4. паспорта команд
        5. стартовые рейтинги паспортов

    Возвращает:

        season,
        teams,
        passports
    """

    tournaments = get_all_tournaments()

    if competition not in tournaments:
        raise RuntimeError(
            f"Для «{competition}» нет "
            "FAJ Club Rating."
        )

    # --------------------------------------------------------
    # SEASON
    # --------------------------------------------------------

    season = _ensure_season(
        db,
        competition,
    )

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    teams = _ensure_teams(
        db,
        competition,
    )

    if not teams:
        raise RuntimeError(
            f"Для «{competition}» не найдено команд."
        )

    # --------------------------------------------------------
    # PASSPORTS
    # --------------------------------------------------------

    passports = _ensure_passports(
        db=db,
        competition=competition,
        season=season,
        teams=teams,
    )

    return (
        season,
        teams,
        passports,
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.title(
        "🏟️ Управление туром"
    )

    st.caption(
        "FAJ Platform — календарь соревнований"
    )

    db = FAJDatabase()
    match_mgr = MatchManager(db)

    # ========================================================
    # COMPETITION
    # ========================================================

    st.subheader(
        "🏆 Соревнование"
    )

    competition = st.selectbox(
        "Выберите соревнование",
        list(
            COMPETITION_CONFIG.keys()
        ),
        index=0,
        key="tour_competition",
    )

    config = COMPETITION_CONFIG[
        competition
    ]

    is_ucl = (
        config["type"] == "ucl"
    )

    # ========================================================
    # AUTO BOOTSTRAP
    # ========================================================

    try:

        (
            selected_season,
            teams,
            passports,
        ) = ensure_competition_data(
            db,
            competition,
        )

    except Exception as exc:

        st.error(
            f"❌ Не удалось подготовить "
            f"«{competition}» "
            f"для сезона {SEASON_NAME}."
        )

        st.code(
            str(exc)
        )

        st.info(
            "Tour Manager не использует "
            "прямой SQL. "
            "Для паспортов требуется "
            "публичный PassportManager "
            "или публичный API FAJDatabase."
        )

        return

    # ========================================================
    # UCL INFO
    # ========================================================

    if is_ucl:

        st.info(
            "🏆 Лига чемпионов — отдельный "
            "турнирный контур. "
            "Её сезон, клубы и паспорта "
            "не смешиваются с внутренними "
            "чемпионатами."
        )

    # ========================================================
    # SEASON
    # ========================================================

    st.subheader(
        "📆 Сезон"
    )

    st.caption(
        f"Сезон: **{season_name(selected_season)}**"
    )

    sid = int(
        season_id(selected_season)
    )

    # ========================================================
    # PASSPORT STATUS
    # ========================================================

    st.success(
        f"🪪 Паспорта клубов: "
        f"{len(passports)}/{len(teams)} готовы"
    )

    # ========================================================
    # TEAM RATING INFO
    # ========================================================

    with st.expander(
        "📊 Текущая оценка клубов",
        expanded=False,
    ):

        for team in teams:

            tid = int(
                team_id(team)
            )

            data = passports.get(
                tid
            )

            if not data:
                continue

            st.write(
                f"**{team_name(team)}** — "
                f"{data['rating']:.2f}"
            )

    # ========================================================
    # TEAMS
    # ========================================================

    if not teams:

        st.error(
            f"❌ В «{competition}» "
            "нет команд."
        )

        return

    name_to_id = {
        team_name(team): int(
            team_id(team)
        )
        for team in teams
    }

    id_to_name = {
        int(team_id(team)): team_name(team)
        for team in teams
    }

    # ========================================================
    # ROUND
    # ========================================================

    st.subheader(
        "📅 Тур"
    )

    max_rounds = int(
        config["max_rounds"]
    )

    rounds = db.get_rounds(
        sid
    )

    round_number = st.selectbox(
        "Выберите тур",
        list(
            range(
                1,
                max_rounds + 1,
            )
        ),
        index=0,
        key="tour_round_number",
        format_func=lambda number:
            get_round_label(
                competition,
                number,
            ),
    )

    existing_round = None

    for current_round in rounds:

        current_number = row_value(
            current_round,
            "round_number",
        )

        if (
            current_number is not None
            and int(current_number)
            == int(round_number)
        ):

            existing_round = current_round
            break

    # ========================================================
    # CREATE ROUND
    # ========================================================

    if existing_round is None:

        st.info(
            f"⚪ "
            f"{get_round_label(competition, round_number)} "
            "ещё не создан."
        )

        if st.button(
            "➕ Создать тур",
            type="primary",
            use_container_width=True,
            key="create_round",
        ):

            try:

                created_round_id = db.create_round(
                    sid,
                    int(round_number),
                )

                if created_round_id is None:

                    st.error(
                        "❌ База не вернула ID тура."
                    )

                    return

                st.success(
                    f"✅ "
                    f"{get_round_label(competition, round_number)} "
                    "создан."
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    f"❌ Не удалось создать тур: {exc}"
                )

        return

    round_id = int(
        row_value(
            existing_round,
            "id",
        )
    )

    st.success(
        f"🟢 "
        f"{get_round_label(competition, round_number)} "
        "создан"
    )

    # ========================================================
    # MATCHES
    # ========================================================

    matches = match_mgr.get_round_matches(
        round_id
    )

    locked_count = sum(
        1
        for match in matches
        if row_value(
            match,
            "id",
        ) is not None
        and match_is_locked(
            db,
            int(
                row_value(
                    match,
                    "id",
                )
            ),
        )
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Матчей",
            len(matches),
        )

    with col2:

        st.metric(
            "LOCKED",
            locked_count,
        )

    with col3:

        st.metric(
            "Статус",
            (
                "📚 История"
                if locked_count
                else "🛠️ Календарь"
            ),
        )

    # ========================================================
    # MATCH LIST
    # ========================================================

    st.subheader(
        "⚽ Матчи — "
        f"{get_round_label(competition, round_number)}"
    )

    if not matches:

        st.info(
            "В этом туре пока нет матчей."
        )

    else:

        for index, match in enumerate(
            matches,
            start=1,
        ):

            home_id = row_value(
                match,
                "home_team_id",
            )

            away_id = row_value(
                match,
                "away_team_id",
            )

            match_id = row_value(
                match,
                "id",
            )

            home_name = id_to_name.get(
                int(home_id)
                if home_id is not None
                else -1,
                f"Команда #{home_id}",
            )

            away_name = id_to_name.get(
                int(away_id)
                if away_id is not None
                else -1,
                f"Команда #{away_id}",
            )

            if match_id is None:
                continue

            match_id = int(
                match_id
            )

            locked = match_is_locked(
                db,
                match_id,
            )

            col_match, col_delete = st.columns(
                [5, 1]
            )

            with col_match:

                prefix = (
                    "🔒 "
                    if locked
                    else ""
                )

                st.markdown(
                    f"### {prefix}{index}. "
                    f"{home_name} — {away_name}"
                )

                match_date = row_value(
                    match,
                    "date",
                    "",
                )

                if match_date:

                    st.caption(
                        f"📅 {match_date}"
                    )

                st.caption(
                    "Статус: "
                    f"{row_value(match, 'status', 'scheduled')}"
                )

            with col_delete:

                if st.button(
                    "🗑️ Удалить",
                    key=f"delete_match_{match_id}",
                    use_container_width=True,
                ):

                    st.session_state[
                        f"confirm_delete_{match_id}"
                    ] = True

            if st.session_state.get(
                f"confirm_delete_{match_id}",
                False,
            ):

                st.warning(
                    f"Удалить матч "
                    f"**{home_name} — {away_name}**?"
                )

                c1, c2 = st.columns(2)

                with c1:

                    if st.button(
                        "Да, удалить",
                        type="primary",
                        key=(
                            f"confirm_delete_button_"
                            f"{match_id}"
                        ),
                    ):

                        try:

                            deleted = db.delete_match(
                                match_id
                            )

                            st.session_state[
                                f"confirm_delete_{match_id}"
                            ] = False

                            if deleted:

                                st.success(
                                    "✅ Матч удалён."
                                )

                                st.rerun()

                            else:

                                st.warning(
                                    "Матч уже отсутствует."
                                )

                        except Exception as exc:

                            st.error(
                                f"❌ Ошибка удаления: {exc}"
                            )

                with c2:

                    if st.button(
                        "Отмена",
                        key=(
                            f"cancel_delete_"
                            f"{match_id}"
                        ),
                    ):

                        st.session_state[
                            f"confirm_delete_{match_id}"
                        ] = False

                        st.rerun()

            st.divider()

    # ========================================================
    # ADD MATCH
    # ========================================================

    st.subheader(
        "➕ Добавить матч"
    )

    used_team_ids: set[int] = set()

    for match in matches:

        home_id = row_value(
            match,
            "home_team_id",
        )

        away_id = row_value(
            match,
            "away_team_id",
        )

        if home_id is not None:
            used_team_ids.add(
                int(home_id)
            )

        if away_id is not None:
            used_team_ids.add(
                int(away_id)
            )

    available_team_names = [
        name
        for name, tid
        in name_to_id.items()
        if tid not in used_team_ids
    ]

    if not available_team_names:

        st.success(
            "✅ Все команды уже распределены "
            "по матчам этого тура."
        )

    else:

        c1, c2 = st.columns(2)

        with c1:

            home_name = st.selectbox(
                "Хозяева",
                [
                    "— выберите команду —"
                ]
                + available_team_names,
                key="home_team",
            )

        with c2:

            away_options = [
                name
                for name
                in available_team_names
                if name != home_name
            ]

            away_name = st.selectbox(
                "Гости",
                [
                    "— выберите команду —"
                ]
                + away_options,
                key="away_team",
            )

        match_date = st.date_input(
            "Дата матча",
            key="match_date",
        )

        if (
            home_name
            != "— выберите команду —"
            and away_name
            != "— выберите команду —"
        ):

            home_id = name_to_id.get(
                home_name
            )

            away_id = name_to_id.get(
                away_name
            )

            if home_id == away_id:

                st.error(
                    "❌ Команда не может "
                    "играть сама с собой."
                )

            elif st.button(
                "➕ Добавить матч",
                type="primary",
                use_container_width=True,
                key="add_match",
            ):

                duplicate = False

                for existing_match in matches:

                    existing_home = row_value(
                        existing_match,
                        "home_team_id",
                    )

                    existing_away = row_value(
                        existing_match,
                        "away_team_id",
                    )

                    existing_date = str(
                        row_value(
                            existing_match,
                            "date",
                            "",
                        )
                    )

                    if (
                        existing_home is not None
                        and existing_away is not None
                        and int(existing_home)
                        == home_id
                        and int(existing_away)
                        == away_id
                        and existing_date.startswith(
                            str(match_date)
                        )
                    ):

                        duplicate = True
                        break

                if duplicate:

                    st.error(
                        "❌ Такой матч уже существует."
                    )

                else:

                    try:

                        match_id = match_mgr.save_match(
                            {
                                "round_id": round_id,
                                "home_team_id": home_id,
                                "away_team_id": away_id,
                                "date": str(match_date),
                                "competition": competition,
                                "status": "scheduled",
                                "fact_status": "scheduled",
                            }
                        )

                        st.success(
                            f"✅ Матч создан. ID: {match_id}"
                        )

                        st.rerun()

                    except Exception as exc:

                        st.error(
                            f"❌ Ошибка сохранения матча: {exc}"
                        )

    # ========================================================
    # CLEAR ROUND
    # ========================================================

    st.divider()

    st.subheader(
        "🧹 Управление матчами тура"
    )

    if matches:

        st.info(
            "Очистка удаляет только матчи. "
            "Сам тур, сезон, команды и паспорта "
            "остаются."
        )

        if st.button(
            "🧹 Очистить матчи тура",
            key="clear_round_matches",
            use_container_width=True,
        ):

            st.session_state[
                "confirm_clear_round_matches"
            ] = True

    if st.session_state.get(
        "confirm_clear_round_matches",
        False,
    ):

        st.warning(
            "⚠️ Удалить все матчи из "
            f"{get_round_label(competition, round_number)}?"
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⚠️ Да, очистить",
                type="primary",
                key="confirm_clear_round_matches_button",
            ):

                try:

                    deleted_count = 0

                    for match in matches:

                        match_id = row_value(
                            match,
                            "id",
                        )

                        if match_id is not None:

                            if db.delete_match(
                                int(match_id)
                            ):

                                deleted_count += 1

                    st.session_state[
                        "confirm_clear_round_matches"
                    ] = False

                    st.success(
                        f"✅ Удалено матчей: "
                        f"{deleted_count}"
                    )

                    st.rerun()

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка очистки: {exc}"
                    )

        with c2:

            if st.button(
                "Отмена",
                key="cancel_clear_round_matches",
            ):

                st.session_state[
                    "confirm_clear_round_matches"
                ] = False

                st.rerun()

    # ========================================================
    # NEXT
    # ========================================================

    if matches:

        st.divider()

        st.subheader(
            "➡️ Следующий этап"
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "🧠 Прогнозы тура",
                type="primary",
                use_container_width=True,
                key="go_predictions",
            ):

                st.session_state.page = (
                    "predict_round"
                )

                st.session_state.selected_round_id = (
                    round_id
                )

                st.session_state.selected_round_number = (
                    round_number
                )

                st.session_state.selected_league = (
                    competition
                )

                st.session_state.selected_competition = (
                    competition
                )

                st.rerun()

        with c2:

            if st.button(
                "📥 Факты тура",
                use_container_width=True,
                key="go_facts",
            ):

                st.session_state.page = (
                    "import_facts"
                )

                st.session_state.selected_round_id = (
                    round_id
                )

                st.session_state.selected_round_number = (
                    round_number
                )

                st.session_state.selected_league = (
                    competition
                )

                st.session_state.selected_competition = (
                    competition
                )

                st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ TEAM IDENTITY
=================

Единый слой идентификации футбольных команд.

Задача:

    FAJ Club Ratings
            ↓
       canonical name
            ↓
      aliases / variants
            ↓
       Soccer365 / DB
            ↓
       одна команда FAJ

Пример:

    "ЦСКА"
    "ЦСКА Москва"
    "ЦСКА М."
    "PFC CSKA Moscow"

    → "ЦСКА"

ВАЖНО:

1. Этот модуль НЕ хранит рейтинги.
2. Этот модуль НЕ работает с SQLite.
3. Источник canonical-команд:
       app.faj_club_ratings.FAJ_CLUB_RATINGS
4. Модуль не изменяет исходные названия в FAJ Club Ratings.
5. Никаких догадок по частичному совпадению.
6. История, Soccer365 и Predictor должны работать
   через canonical identity.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from app.faj_club_ratings import FAJ_CLUB_RATINGS


# ============================================================
# VERSION
# ============================================================

TEAM_IDENTITY_VERSION = "1.0"


# ============================================================
# BASIC NORMALIZATION
# ============================================================

def normalize_team_name(value: object) -> str:
    """
    Базовая нормализация имени команды.

    Не меняет смысл названия.
    Только приводит строку к стабильному виду.
    """

    if value is None:
        return ""

    text = str(value).strip().lower()

    # ё → е
    text = text.replace("ё", "е")

    # тире
    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )

    # убираем точки
    text = text.replace(".", "")

    # убираем кавычки
    text = (
        text
        .replace('"', "")
        .replace("'", "")
        .replace("«", "")
        .replace("»", "")
    )

    # множественные пробелы
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# EXPLICIT ALIASES
# ============================================================

"""
Явные алиасы нужны там, где Soccer365 / внешний источник
использует другое официальное или распространённое название.

Ключ:
    canonical FAJ name

Значение:
    варианты имени из внешних источников
"""

TEAM_ALIASES: Dict[str, List[str]] = {

    # --------------------------------------------------------
    # РПЛ
    # --------------------------------------------------------

    "Зенит": [
        "Зенит",
        "Зенит Санкт-Петербург",
        "Зенит СПб",
        "Зенит Санкт Петербург",
        "Zenit",
        "Zenit St Petersburg",
        "Zenit St. Petersburg",
    ],

    "Краснодар": [
        "Краснодар",
        "ФК Краснодар",
        "Krasnodar",
        "FC Krasnodar",
    ],

    "ЦСКА": [
        "ЦСКА",
        "ЦСКА Москва",
        "ЦСКА М.",
        "ЦСКА (Москва)",
        "ПФК ЦСКА",
        "ПФК ЦСКА Москва",
        "CSKA",
        "CSKA Moscow",
        "PFC CSKA Moscow",
    ],

    "Спартак": [
        "Спартак",
        "Спартак Москва",
        "Спартак М.",
        "Спартак (Москва)",
        "Spartak",
        "Spartak Moscow",
        "Spartak Moskva",
    ],

    "Динамо Москва": [
        "Динамо Москва",
        "Динамо М.",
        "Динамо (Москва)",
        "Динамо",
        "Динамо Москва ФК",
        "Dynamo Moscow",
        "Dinamo Moscow",
    ],

    "Локомотив": [
        "Локомотив",
        "Локомотив Москва",
        "Локомотив М.",
        "Локомотив (Москва)",
        "Lokomotiv",
        "Lokomotiv Moscow",
    ],

    "Ростов": [
        "Ростов",
        "Ростов-на-Дону",
        "Ростов НД",
        "Rostov",
        "FC Rostov",
    ],

    "Ахмат": [
        "Ахмат",
        "Ахмат Грозный",
        "Ахмат Грозный ФК",
        "Akhmat",
        "Akhmat Grozny",
    ],

    "Рубин": [
        "Рубин",
        "Рубин Казань",
        "Рубин Казань ФК",
        "Rubin",
        "Rubin Kazan",
    ],

    "Крылья Советов": [
        "Крылья Советов",
        "Крылья Советов Самара",
        "Крылья Советов (Самара)",
        "Krylia Sovetov",
        "Krylya Sovetov",
        "Krylya Sovetov Samara",
    ],

    "Балтика": [
        "Балтика",
        "Балтика Калининград",
        "Baltika",
        "Baltika Kaliningrad",
    ],

    "Оренбург": [
        "Оренбург",
        "ФК Оренбург",
        "Orenburg",
        "FC Orenburg",
    ],

    "Факел": [
        "Факел",
        "Факел Воронеж",
        "Fakel",
        "Fakel Voronezh",
    ],

    "Динамо Махачкала": [
        "Динамо Махачкала",
        "Динамо Махачкала ФК",
        "Dynamo Makhachkala",
        "Dinamo Makhachkala",
    ],

    "Акрон": [
        "Акрон",
        "Акрон Тольятти",
        "Акрон Тольятти ФК",
        "Akron",
        "Akron Tolyatti",
    ],

    "Родина": [
        "Родина",
        "Родина Москва",
        "Rodina",
        "Rodina Moscow",
    ],

    # --------------------------------------------------------
    # АПЛ
    # --------------------------------------------------------

    "Арсенал": [
        "Арсенал",
        "Arsenal",
        "Arsenal FC",
    ],

    "Манчестер Сити": [
        "Манчестер Сити",
        "Manchester City",
        "Manchester City FC",
        "Man City",
    ],

    "Ливерпуль": [
        "Ливерпуль",
        "Liverpool",
        "Liverpool FC",
    ],

    "Манчестер Юнайтед": [
        "Манчестер Юнайтед",
        "Manchester United",
        "Manchester United FC",
        "Man United",
        "Man Utd",
    ],

    "Челси": [
        "Челси",
        "Chelsea",
        "Chelsea FC",
    ],

    "Ньюкасл": [
        "Ньюкасл",
        "Ньюкасл Юнайтед",
        "Newcastle",
        "Newcastle United",
        "Newcastle United FC",
    ],

    "Брайтон": [
        "Брайтон",
        "Брайтон энд Хоув Альбион",
        "Brighton",
        "Brighton & Hove Albion",
    ],

    "Астон Вилла": [
        "Астон Вилла",
        "Aston Villa",
        "Aston Villa FC",
    ],

    "Тоттенхэм": [
        "Тоттенхэм",
        "Тоттенхэм Хотспур",
        "Tottenham",
        "Tottenham Hotspur",
        "Spurs",
    ],

    "Ноттингем Форест": [
        "Ноттингем Форест",
        "Nottingham Forest",
        "Nottingham Forest FC",
    ],

    "Брентфорд": [
        "Брентфорд",
        "Brentford",
        "Brentford FC",
    ],

    "Эвертон": [
        "Эвертон",
        "Everton",
        "Everton FC",
    ],

    "Сандерленд": [
        "Сандерленд",
        "Sunderland",
        "Sunderland AFC",
    ],

    "Кристал Пэлас": [
        "Кристал Пэлас",
        "Crystal Palace",
        "Crystal Palace FC",
    ],

    "Фулхэм": [
        "Фулхэм",
        "Fulham",
        "Fulham FC",
    ],

    "Борнмут": [
        "Борнмут",
        "AFC Bournemouth",
        "Bournemouth",
    ],

    "Лидс": [
        "Лидс",
        "Лидс Юнайтед",
        "Leeds",
        "Leeds United",
    ],

    "Халл Сити": [
        "Халл Сити",
        "Hull City",
        "Hull City AFC",
    ],

    "Ипсвич": [
        "Ипсвич",
        "Ипсвич Таун",
        "Ipswich",
        "Ipswich Town",
    ],

    "Ковентри": [
        "Ковентри",
        "Ковентри Сити",
        "Coventry",
        "Coventry City",
    ],

    # --------------------------------------------------------
    # ЛА ЛИГА
    # --------------------------------------------------------

    "Барселона": [
        "Барселона",
        "FC Barcelona",
        "Barcelona",
    ],

    "Реал Мадрид": [
        "Реал Мадрид",
        "Real Madrid",
        "Real Madrid CF",
    ],

    "Атлетико Мадрид": [
        "Атлетико Мадрид",
        "Атлетико",
        "Atletico Madrid",
        "Atlético Madrid",
        "Atletico de Madrid",
    ],

    "Реал Сосьедад": [
        "Реал Сосьедад",
        "Real Sociedad",
        "Real Sociedad de Futbol",
    ],

    "Вильярреал": [
        "Вильярреал",
        "Villarreal",
        "Villarreal CF",
    ],

    "Реал Бетис": [
        "Реал Бетис",
        "Бетис",
        "Real Betis",
        "Real Betis Balompie",
    ],

    "Атлетик Бильбао": [
        "Атлетик Бильбао",
        "Атлетик",
        "Athletic Bilbao",
        "Athletic Club",
    ],

    "Сельта": [
        "Сельта",
        "Сельта Виго",
        "Celta",
        "Celta Vigo",
    ],

    "Хетафе": [
        "Хетафе",
        "Getafe",
        "Getafe CF",
    ],

    "Валенсия": [
        "Валенсия",
        "Valencia",
        "Valencia CF",
    ],

    "Севилья": [
        "Севилья",
        "Sevilla",
        "Sevilla FC",
    ],

    "Райо Вальекано": [
        "Райо Вальекано",
        "Rayo Vallecano",
        "Rayo Vallecano de Madrid",
    ],

    "Осасуна": [
        "Осасуна",
        "Osasuna",
        "CA Osasuna",
    ],

    "Эспаньол": [
        "Эспаньол",
        "Эспаньол Барселона",
        "Espanyol",
        "RCD Espanyol",
    ],

    "Алавес": [
        "Алавес",
        "Депортиво Алавес",
        "Alaves",
        "Deportivo Alaves",
    ],

    "Расинг Сантандер": [
        "Расинг Сантандер",
        "Расинг",
        "Racing Santander",
        "Racing Club Santander",
    ],

    "Леванте": [
        "Леванте",
        "Levante",
        "Levante UD",
    ],

    "Эльче": [
        "Эльче",
        "Elche",
        "Elche CF",
    ],

    "Малага": [
        "Малага",
        "Malaga",
        "Malaga CF",
    ],

    "Депортиво Ла-Корунья": [
        "Депортиво Ла-Корунья",
        "Депортиво",
        "Deportivo",
        "Deportivo La Coruna",
        "Deportivo La Coruña",
    ],

    # --------------------------------------------------------
    # ЛИГА ЧЕМПИОНОВ
    # --------------------------------------------------------

    "ПСЖ": [
        "ПСЖ",
        "Пари Сен-Жермен",
        "Paris Saint-Germain",
        "Paris Saint Germain",
        "PSG",
    ],

    "Бавария": [
        "Бавария",
        "Бавария Мюнхен",
        "Bayern",
        "Bayern Munich",
        "FC Bayern Munich",
    ],

    "Интер": [
        "Интер",
        "Интер Милан",
        "Inter",
        "Inter Milan",
        "Inter Milano",
    ],

    "Боруссия Дортмунд": [
        "Боруссия Дортмунд",
        "Боруссия",
        "Боруссия Д.",
        "Borussia Dortmund",
        "Dortmund",
    ],

    "Рома": [
        "Рома",
        "Roma",
        "AS Roma",
    ],

    "Порту": [
        "Порту",
        "Porto",
        "FC Porto",
    ],

    "Наполи": [
        "Наполи",
        "Napoli",
        "SSC Napoli",
    ],

    "Спортинг": [
        "Спортинг",
        "Спортинг Лиссабон",
        "Sporting",
        "Sporting CP",
        "Sporting Lisbon",
    ],

    "ПСВ": [
        "ПСВ",
        "ПСВ Эйндховен",
        "PSV",
        "PSV Eindhoven",
    ],

    "Галатасарай": [
        "Галатасарай",
        "Galatasaray",
        "Galatasaray SK",
    ],

    "Фенербахче": [
        "Фенербахче",
        "Fenerbahce",
        "Fenerbahçe",
        "Fenerbahce SK",
    ],

    "Фейеноорд": [
        "Фейеноорд",
        "Feyenoord",
        "Feyenoord Rotterdam",
    ],

    "Лейпциг": [
        "Лейпциг",
        "РБ Лейпциг",
        "RB Leipzig",
        "Leipzig",
    ],

    "Брюгге": [
        "Брюгге",
        "Клуб Брюгге",
        "Club Brugge",
        "Club Brugge KV",
    ],

    "Лилль": [
        "Лилль",
        "Lille",
        "Lille OSC",
    ],

    "Ланс": [
        "Ланс",
        "Lens",
        "RC Lens",
    ],

    "Штутгарт": [
        "Штутгарт",
        "Stuttgart",
        "VfB Stuttgart",
    ],

    "Будё-Глимт": [
        "Будё-Глимт",
        "Буде-Глимт",
        "Bodo/Glimt",
        "Bodø/Glimt",
        "Bodo Glimt",
    ],

    "Шахтёр": [
        "Шахтёр",
        "Шахтер",
        "Шахтер Донецк",
        "Shakhtar",
        "Shakhtar Donetsk",
    ],

    "АЕК": [
        "АЕК",
        "АЕК Афины",
        "AEK",
        "AEK Athens",
    ],

    "Слован": [
        "Слован",
        "Слован Братислава",
        "Slovan",
        "Slovan Bratislava",
    ],

    "Славия Прага": [
        "Славия Прага",
        "Славия",
        "Slavia Prague",
        "Slavia Praha",
    ],

    "ЛАСК": [
        "ЛАСК",
        "LASK",
        "LASK Linz",
    ],

    "Викинг": [
        "Викинг",
        "Viking",
        "Viking FK",
    ],

    "Сабах": [
        "Сабах",
        "Sabah",
        "Sabah FK",
    ],

    "Комо": [
        "Комо",
        "Como",
        "Como 1907",
    ],
}


# ============================================================
# INTERNAL INDEX
# ============================================================

def _build_canonical_names() -> List[str]:
    """
    Получить все canonical names непосредственно
    из FAJ_CLUB_RATINGS.
    """

    result: List[str] = []

    for teams in FAJ_CLUB_RATINGS.values():
        for team_name in teams:
            if team_name not in result:
                result.append(team_name)

    return result


def _build_alias_index() -> Dict[str, str]:
    """
    Создаёт:

        normalized alias → canonical name
    """

    index: Dict[str, str] = {}

    canonical_names = _build_canonical_names()

    # Сначала canonical names
    for canonical in canonical_names:
        normalized = normalize_team_name(canonical)

        if normalized:
            index[normalized] = canonical

    # Затем explicit aliases
    for canonical, aliases in TEAM_ALIASES.items():

        # Алиас может существовать только для
        # реально зарегистрированной FAJ команды.
        if canonical not in canonical_names:
            continue

        for alias in aliases:
            normalized = normalize_team_name(alias)

            if normalized:
                index[normalized] = canonical

    return index


_ALIAS_INDEX = _build_alias_index()


# ============================================================
# PUBLIC API
# ============================================================

def resolve_team_name(
    team_name: object,
) -> Optional[str]:
    """
    Преобразовать внешнее название в canonical FAJ name.

    Пример:

        resolve_team_name("ЦСКА Москва")
        → "ЦСКА"

    Если команда неизвестна:
        → None
    """

    normalized = normalize_team_name(team_name)

    if not normalized:
        return None

    return _ALIAS_INDEX.get(normalized)


def same_team(
    first: object,
    second: object,
) -> bool:
    """
    Проверка, являются ли два названия одной командой.
    """

    first_canonical = resolve_team_name(first)
    second_canonical = resolve_team_name(second)

    if first_canonical is None or second_canonical is None:
        return False

    return first_canonical == second_canonical


def canonicalize_team_name(
    team_name: object,
) -> str:
    """
    Вернуть canonical name.

    Если команда неизвестна — возвращаем
    нормализованную исходную строку.

    Это важно: внешний источник не должен
    неожиданно превращаться в None.
    """

    resolved = resolve_team_name(team_name)

    if resolved:
        return resolved

    return normalize_team_name(team_name)


def get_team_aliases(
    canonical_name: str,
) -> List[str]:
    """
    Получить все известные варианты названия.
    """

    if canonical_name not in _build_canonical_names():
        return []

    result = [canonical_name]

    for alias in TEAM_ALIASES.get(canonical_name, []):
        if alias not in result:
            result.append(alias)

    return result


def get_all_canonical_teams() -> List[str]:
    """
    Все уникальные команды FAJ из всех турниров.
    """

    return _build_canonical_names()


def get_canonical_teams_by_tournament(
    tournament: str,
) -> List[str]:
    """
    Команды конкретного турнира.
    """

    return list(
        FAJ_CLUB_RATINGS.get(tournament, {}).keys()
    )


def get_team_tournaments(
    team_name: str,
) -> List[str]:
    """
    Найти турниры, в которых зарегистрирована команда.

    Важно для Лиги чемпионов, где команды
    также присутствуют в национальных лигах.
    """

    canonical = resolve_team_name(team_name)

    if canonical is None:
        return []

    tournaments: List[str] = []

    for tournament, teams in FAJ_CLUB_RATINGS.items():
        if canonical in teams:
            tournaments.append(tournament)

    return tournaments


def identity_info(
    team_name: object,
) -> Dict[str, object]:
    """
    Диагностическая информация.
    """

    canonical = resolve_team_name(team_name)

    return {
        "input": team_name,
        "normalized": normalize_team_name(team_name),
        "canonical": canonical,
        "known": canonical is not None,
        "aliases": get_team_aliases(canonical)
        if canonical
        else [],
        "tournaments": get_team_tournaments(canonical)
        if canonical
        else [],
    }


def validate_identity_registry() -> List[str]:
    """
    Проверка реестра identity.

    Возвращает список ошибок.
    """

    errors: List[str] = []

    canonical_names = set(
        _build_canonical_names()
    )

    for canonical, aliases in TEAM_ALIASES.items():

        if canonical not in canonical_names:
            errors.append(
                f"Alias canonical team отсутствует "
                f"в FAJ_CLUB_RATINGS: {canonical}"
            )

        seen = set()

        for alias in aliases:
            normalized = normalize_team_name(alias)

            if not normalized:
                errors.append(
                    f"{canonical}: пустой alias"
                )
                continue

            if normalized in seen:
                errors.append(
                    f"{canonical}: duplicate alias: {alias}"
                )

            seen.add(normalized)

    # Проверка конфликтов alias
    reverse: Dict[str, str] = {}

    for canonical, aliases in TEAM_ALIASES.items():

        for alias in aliases:
            normalized = normalize_team_name(alias)

            if not normalized:
                continue

            previous = reverse.get(normalized)

            if previous and previous != canonical:
                errors.append(
                    "Конфликт alias: "
                    f"{alias!r} → {previous} / {canonical}"
                )

            reverse[normalized] = canonical

    return errors


# ============================================================
# DEBUG
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("FAJ TEAM IDENTITY")
    print(f"Version: {TEAM_IDENTITY_VERSION}")
    print("=" * 70)

    errors = validate_identity_registry()

    if errors:
        print("\nОШИБКИ:")
        for error in errors:
            print(f" - {error}")

    else:
        print("\nIdentity registry: OK")

    tests = [
        "ЦСКА",
        "ЦСКА Москва",
        "ПФК ЦСКА Москва",
        "Зенит Санкт-Петербург",
        "Зенит",
        "Manchester City",
        "Манчестер Сити",
        "Real Madrid",
        "Реал Мадрид",
        "Боруссия Дортмунд",
        "Borussia Dortmund",
        "неизвестная команда",
    ]

    print("\nTESTS:")

    for value in tests:
        print(
            f"{value!r:35} → "
            f"{resolve_team_name(value)!r}"
        )

    print(
        f"\nВсего canonical команд: "
        f"{len(get_all_canonical_teams())}"
    )

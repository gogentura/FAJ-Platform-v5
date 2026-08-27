#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Club Ratings v1.1
Единый экспертный START_RATING для FAJ.

ВАЖНО:
- файл является Python-модулем и остаётся в app/
- SQLite здесь НЕ используется
- database.py здесь НЕ изменяется
- START_RATING является неизменяемой исторической точкой старта
- будущий CURRENT_RATING будет вести ETC

UI получает данные через:
    get_all_ratings()
    get_league_ratings()
    get_team_rating()
"""

FAJ_RATING_VERSION = "1.1"
FAJ_SEASON = "2026/27"
FAJ_RATING_SOURCE = "expert"


FAJ_CLUB_RATINGS = {
    "РПЛ": {
        "Зенит": 90,
        "Краснодар": 88,
        "ЦСКА": 87,
        "Спартак": 86,
        "Динамо Москва": 84,
        "Локомотив": 83,
        "Ростов": 78,
        "Ахмат": 75,
        "Рубин": 75,
        "Крылья Советов": 74,
        "Балтика": 71,
        "Оренбург": 70,
        "Факел": 69,
        "Динамо Махачкала": 68,
        "Акрон": 67,
        "Родина": 66,
    },

    "АПЛ": {
        "Арсенал": 92,
        "Манчестер Сити": 89,
        "Ливерпуль": 87,
        "Манчестер Юнайтед": 86,
        "Челси": 83,
        "Ньюкасл": 82,
        "Брайтон": 81,
        "Астон Вилла": 80,
        "Тоттенхэм": 79,
        "Ноттингем Форест": 78,
        "Брентфорд": 78,
        "Эвертон": 77,
        "Сандерленд": 76,
        "Кристал Пэлас": 75,
        "Фулхэм": 74,
        "Борнмут": 73,
        "Лидс": 72,
        "Халл Сити": 71,
        "Ипсвич": 69,
        "Ковентри": 67,
    },

    "Ла Лига": {
        "Барселона": 93,
        "Реал Мадрид": 92,
        "Атлетико Мадрид": 88,
        "Реал Сосьедад": 84,
        "Вильярреал": 82,
        "Реал Бетис": 81,
        "Атлетик Бильбао": 78,
        "Сельта": 76,
        "Хетафе": 75,
        "Валенсия": 75,
        "Севилья": 74,
        "Райо Вальекано": 72,
        "Осасуна": 71,
        "Эспаньол": 70,
        "Алавес": 68,
        "Расинг Сантандер": 68,
        "Леванте": 66,
        "Эльче": 65,
        "Малага": 64,
        "Депортиво Ла-Корунья": 63,
    },

    "Лига чемпионов": {
        "ПСЖ": 97,
        "Бавария": 95,
        "Реал Мадрид": 94,
        "Арсенал": 96,
        "Барселона": 94,
        "Манчестер Сити": 90,
        "Интер": 91,
        "Ливерпуль": 87,
        "Атлетико Мадрид": 86,
        "Боруссия Дортмунд": 85,
        "Манчестер Юнайтед": 85,
        "Рома": 84,
        "Порту": 82,
        "Реал Бетис": 82,
        "Наполи": 81,
        "Спортинг": 81,
        "ПСВ": 81,
        "Галатасарай": 81,
        "Фенербахче": 80,
        "Астон Вилла": 80,
        "Фейеноорд": 80,
        "Лейпциг": 79,
        "Брюгге": 79,
        "Вильярреал": 78,
        "Лилль": 78,
        "Ланс": 78,
        "Штутгарт": 77,
        "Будё-Глимт": 77,
        "Шахтёр": 74,
        "АЕК": 72,
        "Слован": 71,
        "Славия Прага": 70,
        "ЛАСК": 69,
        "Викинг": 69,
        "Сабах": 68,
        "Комо": 79,
    },
}


def get_rating(tournament: str, team_name: str):
    """Рейтинг команды в конкретном турнире."""
    return FAJ_CLUB_RATINGS.get(tournament, {}).get(team_name)


def get_team_rating(team_name: str, tournament: str | None = None):
    """
    Получить рейтинг команды.

    Если tournament указан — ищем только там.
    Если нет — возвращаем первое найденное значение.
    """
    if tournament:
        return get_rating(tournament, team_name)

    for teams in FAJ_CLUB_RATINGS.values():
        if team_name in teams:
            return teams[team_name]

    return None


def get_league_ratings(tournament: str):
    """Рейтинги всех команд выбранного турнира."""
    return dict(FAJ_CLUB_RATINGS.get(tournament, {}))


def get_all_ratings():
    """Полная копия реестра рейтингов."""
    return {
        tournament: dict(teams)
        for tournament, teams in FAJ_CLUB_RATINGS.items()
    }


def get_tournament_ratings(tournament: str):
    """Совместимый алиас."""
    return get_league_ratings(tournament)


def get_all_tournaments():
    return list(FAJ_CLUB_RATINGS.keys())


def get_all_teams(tournament: str):
    return list(FAJ_CLUB_RATINGS.get(tournament, {}).keys())


def set_rating(tournament: str, team_name: str, rating: float):
    """
    Административное изменение START_RATING.

    В штатной работе ETC этот метод не используется.
    """
    if tournament not in FAJ_CLUB_RATINGS:
        FAJ_CLUB_RATINGS[tournament] = {}

    value = max(0.0, min(100.0, float(rating)))
    FAJ_CLUB_RATINGS[tournament][team_name] = round(value, 1)


def validate_ratings():
    errors = []

    for tournament, teams in FAJ_CLUB_RATINGS.items():
        if not teams:
            errors.append(f"{tournament}: нет команд")

        for team, rating in teams.items():
            if not isinstance(rating, (int, float)):
                errors.append(
                    f"{tournament} / {team}: рейтинг не число"
                )
            elif not 0 <= rating <= 100:
                errors.append(
                    f"{tournament} / {team}: рейтинг вне 0-100"
                )

    return errors


if __name__ == "__main__":
    print("=" * 60)
    print("FAJ CLUB RATINGS")
    print(f"Version: {FAJ_RATING_VERSION}")
    print(f"Season:  {FAJ_SEASON}")
    print(f"Source:  {FAJ_RATING_SOURCE}")
    print("=" * 60)

    errors = validate_ratings()

    if errors:
        print("\nОШИБКИ:")
        for error in errors:
            print(f" - {error}")
    else:
        print("\nВсе рейтинги валидны.")
        for tournament, teams in FAJ_CLUB_RATINGS.items():
            print(f"\n{tournament}")
            for position, (team, rating) in enumerate(
                sorted(teams.items(), key=lambda item: item[1], reverse=True),
                start=1,
            ):
                print(f"{position:2}. {team:<25} {rating}")
            print(f"Всего команд: {len(teams)}")

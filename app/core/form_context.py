#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FORM CONTEXT v1.0
============================================================

НАЗНАЧЕНИЕ
----------

Простой аналитический слой формы команды перед прогнозом.

Form Context НЕ:

    - собирает данные;
    - парсит Soccer365;
    - записывает данные в SQLite;
    - изменяет рейтинг клуба;
    - изменяет прогноз;
    - обучает модель;
    - рассчитывает итоговые вероятности.

Он только получает уже собранную историю матчей
и превращает её в компактный контекст:

    В-Н-В-П-В

    Дома:
        2-0-1

    В гостях:
        1-1-0

    xG:
        1.74

    xGA:
        0.91

    Матчи:
        лёгкий
        средний
        тяжёлый
        тяжёлый
        средний

============================================================

ГЛАВНЫЙ ПРИНЦИП
---------------

Form Context работает ТОЛЬКО с последними матчами,
которые Predictor уже получил для конкретной команды.

Никаких дополнительных запросов к Soccer365.

Никаких дополнительных запросов к БД.

Никакого изменения существующей архитектуры.

============================================================

ВХОД
----

История матчей может содержать:

    date
    home_team
    away_team
    home_score
    away_score
    home_xg
    away_xg

Допускаются также распространённые варианты названий
полей, используемые существующим Predictor.

============================================================

ВЫХОД
------

Например:

{
    "team": "Зенит",

    "form_string": "В-Н-В-П-В",

    "home_record": "2-0-1",
    "away_record": "1-1-0",

    "home_wins": 2,
    "home_draws": 0,
    "home_losses": 1,

    "away_wins": 1,
    "away_draws": 1,
    "away_losses": 0,

    "avg_xg": 1.74,
    "avg_xga": 0.91,

    "match_levels": [
        "лёгкий",
        "средний",
        "тяжёлый",
        "тяжёлый",
        "средний"
    ],

    "matches_count": 5
}

============================================================

ВАЖНО
------

Уровень матча здесь НЕ является глобальным рейтингом
соперника.

Мы оцениваем только конкретную сыгранную встречу.

Простая логика:

    победа 3:0
        → лёгкий

    победа 2:0
        → средний

    победа 1:0
        → тяжёлый

Но xG используется как дополнительный сигнал.

Это первая версия.

Математику позже можно изменить, не ломая Predictor.

============================================================
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


# ============================================================
# VERSION
# ============================================================

FORM_CONTEXT_VERSION = "1.0"


# ============================================================
# HELPERS
# ============================================================

def _first_value(
    record: Dict[str, Any],
    keys: Iterable[str],
) -> Any:
    """
    Возвращает первое существующее непустое значение.
    """

    for key in keys:
        if key in record and record[key] is not None:
            return record[key]

    return None


def _safe_float(
    value: Any,
) -> Optional[float]:
    """
    Безопасное преобразование в float.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(
    value: Any,
) -> Optional[int]:
    """
    Безопасное преобразование в int.
    """

    if value is None:
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _team_name(
    record: Dict[str, Any],
    home: bool,
) -> Optional[str]:
    """
    Получить название домашней / гостевой команды.
    """

    if home:
        return _first_value(
            record,
            (
                "home_team",
                "home",
                "home_name",
            ),
        )

    return _first_value(
        record,
        (
            "away_team",
            "away",
            "away_name",
        ),
    )


def _score(
    record: Dict[str, Any],
    home: bool,
) -> Optional[int]:
    """
    Получить голы команды.

    Поддерживает:

        home_score / away_score

    и:

        score_home / score_away
    """

    if home:
        value = _first_value(
            record,
            (
                "home_score",
                "score_home",
                "goals_home",
            ),
        )
    else:
        value = _first_value(
            record,
            (
                "away_score",
                "score_away",
                "goals_away",
            ),
        )

    return _safe_int(value)


def _xg(
    record: Dict[str, Any],
    home: bool,
) -> Optional[float]:
    """
    Получить xG команды.
    """

    if home:
        value = _first_value(
            record,
            (
                "home_xg",
                "xg_home",
                "home_expected_goals",
            ),
        )
    else:
        value = _first_value(
            record,
            (
                "away_xg",
                "xg_away",
                "away_expected_goals",
            ),
        )

    return _safe_float(value)


# ============================================================
# RESULT
# ============================================================

def _result_symbol(
    goals_for: Optional[int],
    goals_against: Optional[int],
) -> Optional[str]:
    """
    В / Н / П
    """

    if goals_for is None or goals_against is None:
        return None

    if goals_for > goals_against:
        return "В"

    if goals_for == goals_against:
        return "Н"

    return "П"


# ============================================================
# MATCH LEVEL
# ============================================================

def classify_match_level(
    goals_for: Optional[int],
    goals_against: Optional[int],
    xg_for: Optional[float] = None,
    xg_against: Optional[float] = None,
) -> Optional[str]:
    """
    Определяет уровень конкретного матча.

    Это НЕ рейтинг соперника.

    Базовая логика:

        победа с разницей 3+
            → лёгкий

        победа с разницей 2
            → средний

        победа с разницей 1
            → тяжёлый

        поражение с разницей 3+
            → лёгкий

        поражение с разницей 2
            → средний

        поражение с разницей 1
            → тяжёлый

        ничья
            → зависит от разницы xG

    xG используется только как дополнительный сигнал
    для ничьих и близких матчей.

    Важно:

        это первая простая версия.

    Сейчас НЕ пытаемся построить сложную модель силы
    соперника.
    """

    if goals_for is None or goals_against is None:
        return None

    difference = goals_for - goals_against
    abs_difference = abs(difference)

    # --------------------------------------------------------
    # Крупный перевес по счёту
    # --------------------------------------------------------

    if abs_difference >= 3:
        return "лёгкий"

    # --------------------------------------------------------
    # Разница в два мяча
    # --------------------------------------------------------

    if abs_difference == 2:
        return "средний"

    # --------------------------------------------------------
    # Разница в один мяч
    # --------------------------------------------------------

    if abs_difference == 1:
        return "тяжёлый"

    # --------------------------------------------------------
    # Ничья
    # --------------------------------------------------------

    if xg_for is not None and xg_against is not None:

        xg_difference = xg_for - xg_against

        if xg_difference >= 1.0:
            return "средний"

        if xg_difference <= -1.0:
            return "тяжёлый"

    return "средний"


# ============================================================
# SINGLE MATCH
# ============================================================

def analyze_match(
    team: str,
    record: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Анализ одного исторического матча.

    Возвращает нормализованный аналитический объект.
    """

    if not isinstance(record, dict):
        return None

    home_team = _team_name(
        record,
        home=True,
    )

    away_team = _team_name(
        record,
        home=False,
    )

    if not home_team or not away_team:
        return None

    # --------------------------------------------------------
    # Определяем положение команды
    # --------------------------------------------------------

    team_lower = str(team).strip().lower()

    home_lower = str(home_team).strip().lower()
    away_lower = str(away_team).strip().lower()

    if team_lower == home_lower:
        is_home = True

    elif team_lower == away_lower:
        is_home = False

    else:
        # Команда не найдена в матче.
        return None

    # --------------------------------------------------------
    # Голы
    # --------------------------------------------------------

    home_score = _score(
        record,
        home=True,
    )

    away_score = _score(
        record,
        home=False,
    )

    if is_home:

        goals_for = home_score
        goals_against = away_score

        xg_for = _xg(
            record,
            home=True,
        )

        xg_against = _xg(
            record,
            home=False,
        )

        opponent = away_team

    else:

        goals_for = away_score
        goals_against = home_score

        xg_for = _xg(
            record,
            home=False,
        )

        xg_against = _xg(
            record,
            home=True,
        )

        opponent = home_team

    # --------------------------------------------------------
    # Результат
    # --------------------------------------------------------

    result = _result_symbol(
        goals_for,
        goals_against,
    )

    # --------------------------------------------------------
    # Уровень матча
    # --------------------------------------------------------

    level = classify_match_level(
        goals_for=goals_for,
        goals_against=goals_against,
        xg_for=xg_for,
        xg_against=xg_against,
    )

    # --------------------------------------------------------
    # Дата
    # --------------------------------------------------------

    date = _first_value(
        record,
        (
            "date",
            "match_date",
            "played_at",
            "datetime",
        ),
    )

    return {
        "team": team,
        "opponent": opponent,
        "venue": "home" if is_home else "away",

        "home_team": home_team,
        "away_team": away_team,

        "date": date,

        "goals_for": goals_for,
        "goals_against": goals_against,

        "xg_for": xg_for,
        "xg_against": xg_against,

        "result": result,
        "level": level,
    }


# ============================================================
# FORM CONTEXT
# ============================================================

def build_form_context(
    team: str,
    matches: Iterable[Dict[str, Any]],
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Построить контекст последних матчей команды.

    ВАЖНО:

        порядок матчей должен приходить уже правильно
        сформированным Predictor / DB:

            последний матч
                ↓
            предыдущий
                ↓
            ...
                ↓
            пятый

    Form Context сам НЕ обращается к БД и НЕ определяет
    календарь.

    Это защищает архитектуру от смешивания ответственности.
    """

    analyzed: List[Dict[str, Any]] = []

    if matches is None:
        matches = []

    for record in matches:

        result = analyze_match(
            team=team,
            record=record,
        )

        if result is None:
            continue

        analyzed.append(result)

        if len(analyzed) >= limit:
            break

    # ========================================================
    # FORM
    # ========================================================

    form_symbols: List[str] = []

    for match in analyzed:

        result = match.get("result")

        if result in ("В", "Н", "П"):
            form_symbols.append(result)

    form_string = "-".join(
        form_symbols
    )

    # ========================================================
    # HOME / AWAY
    # ========================================================

    home_wins = 0
    home_draws = 0
    home_losses = 0

    away_wins = 0
    away_draws = 0
    away_losses = 0

    for match in analyzed:

        result = match.get("result")
        venue = match.get("venue")

        if venue == "home":

            if result == "В":
                home_wins += 1

            elif result == "Н":
                home_draws += 1

            elif result == "П":
                home_losses += 1

        elif venue == "away":

            if result == "В":
                away_wins += 1

            elif result == "Н":
                away_draws += 1

            elif result == "П":
                away_losses += 1

    # ========================================================
    # xG
    # ========================================================

    xg_values: List[float] = []
    xga_values: List[float] = []

    for match in analyzed:

        xg_for = match.get("xg_for")
        xg_against = match.get("xg_against")

        if xg_for is not None:
            xg_values.append(
                float(xg_for)
            )

        if xg_against is not None:
            xga_values.append(
                float(xg_against)
            )

    avg_xg = (
        round(
            sum(xg_values) / len(xg_values),
            2,
        )
        if xg_values
        else None
    )

    avg_xga = (
        round(
            sum(xga_values) / len(xga_values),
            2,
        )
        if xga_values
        else None
    )

    # ========================================================
    # MATCH LEVELS
    # ========================================================

    match_levels = [
        match["level"]
        for match in analyzed
        if match.get("level")
    ]

    # ========================================================
    # OPPONENTS
    # ========================================================

    opponents = [
        match["opponent"]
        for match in analyzed
        if match.get("opponent")
    ]

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "version": FORM_CONTEXT_VERSION,

        "team": team,

        "matches_count": len(analyzed),

        "form_string": form_string,

        "home_record": (
            f"{home_wins}-"
            f"{home_draws}-"
            f"{home_losses}"
        ),

        "away_record": (
            f"{away_wins}-"
            f"{away_draws}-"
            f"{away_losses}"
        ),

        "home_wins": home_wins,
        "home_draws": home_draws,
        "home_losses": home_losses,

        "away_wins": away_wins,
        "away_draws": away_draws,
        "away_losses": away_losses,

        "avg_xg": avg_xg,
        "avg_xga": avg_xga,

        "match_levels": match_levels,

        "opponents": opponents,

        "matches": analyzed,
    }


# ============================================================
# DISPLAY
# ============================================================

def format_form_context(
    context: Dict[str, Any],
) -> str:
    """
    Человекочитаемое представление.

    Например:

        Зенит
        В-Н-В-П-В
        Дома 2-0-1
        Гости 1-1-0
        xG 1.74
        xGA 0.91
        Матчи:
        ✓ лёгкий
        ✓ средний
        ✓ тяжёлый
    """

    team = context.get(
        "team",
        "Команда",
    )

    lines: List[str] = []

    lines.append(
        str(team)
    )

    lines.append(
        str(
            context.get(
                "form_string",
                "",
            )
        )
    )

    lines.append(
        f"Дома {context.get('home_record', '0-0-0')}"
    )

    lines.append(
        f"Гости {context.get('away_record', '0-0-0')}"
    )

    avg_xg = context.get(
        "avg_xg"
    )

    avg_xga = context.get(
        "avg_xga"
    )

    lines.append(
        "xG "
        + (
            f"{avg_xg:.2f}"
            if avg_xg is not None
            else "—"
        )
    )

    lines.append(
        "xGA "
        + (
            f"{avg_xga:.2f}"
            if avg_xga is not None
            else "—"
        )
    )

    lines.append(
        "Матчи:"
    )

    for level in context.get(
        "match_levels",
        [],
    ):

        lines.append(
            f"✓ {level}"
        )

    return "\n".join(
        lines
    )


# ============================================================
# SIMPLE API
# ============================================================

def get_form_context(
    team: str,
    matches: Iterable[Dict[str, Any]],
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Основная публичная функция.

    Predictor в будущем сможет делать:

        context = get_form_context(
            team="Зенит",
            matches=history,
        )

    Никаких других зависимостей нет.
    """

    return build_form_context(
        team=team,
        matches=matches,
        limit=limit,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    import json

    sample_matches = [

        {
            "date": "2026-08-29",
            "home_team": "Зенит",
            "away_team": "Ростов",
            "home_score": 3,
            "away_score": 0,
            "home_xg": 2.31,
            "away_xg": 0.42,
        },

        {
            "date": "2026-08-22",
            "home_team": "Краснодар",
            "away_team": "Зенит",
            "home_score": 1,
            "away_score": 1,
            "home_xg": 1.14,
            "away_xg": 1.18,
        },

        {
            "date": "2026-08-18",
            "home_team": "Зенит",
            "away_team": "Ахмат",
            "home_score": 2,
            "away_score": 0,
            "home_xg": 1.72,
            "away_xg": 0.51,
        },

        {
            "date": "2026-08-12",
            "home_team": "Спартак",
            "away_team": "Зенит",
            "home_score": 1,
            "away_score": 0,
            "home_xg": 1.31,
            "away_xg": 0.74,
        },

        {
            "date": "2026-08-07",
            "home_team": "Зенит",
            "away_team": "Динамо Москва",
            "home_score": 1,
            "away_score": 0,
            "home_xg": 1.52,
            "away_xg": 0.88,
        },
    ]

    context = get_form_context(
        team="Зенит",
        matches=sample_matches,
        limit=5,
    )

    print("=" * 60)
    print(
        f"FAJ FORM CONTEXT v{FORM_CONTEXT_VERSION}"
    )
    print("=" * 60)

    print()

    print(
        format_form_context(
            context
        )
    )

    print()

    print(
        json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
        )
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM CONTEXT v1.6
============================================================

НАЗНАЧЕНИЕ
----------

Простой человеческий контекст последних матчей команды.

FORM CONTEXT НЕ является моделью прогноза.

Он только отвечает на вопросы:

    Как команда сыграла?
    Где играла?
    Сколько создала?
    Сколько позволила создать?
    Насколько тяжёлым был матч?
    Что произошло при победе / ничьей / поражении?

FORM CONTEXT НЕ:

    - считает FAJ Rating;
    - изменяет FAJ Rating;
    - обучает модель;
    - изменяет xG;
    - пишет в SQLite;
    - работает с букмекерами;
    - использует таблицу чемпионата;
    - использует рейтинг лиги.

Источник данных:

    последние фактические матчи команды.

Пример результата:

    Зенит

    Последние 6:
        В-Н-В-П-В-Н

    Дома:
        2-0-1

    Гости:
        1-1-1

    xG:
        1.74

    xGA:
        0.91

    Матчи:
        лёгкий
        средний
        тяжёлый
        очень тяжёлый
        средний
        тяжёлый

============================================================
VERSION 1.1
============================================================

Изменения:

    - победы классифицируются по разнице мячей;
    - поражения НЕ зеркалят победы;
    - крупное поражение может быть
      "очень тяжёлым";
    - xG используется для понимания поражения;
    - отсутствие xG не превращается в 0;
    - домашние / гостевые показатели считаются отдельно;
    - порядок матчей сохраняется:
      от самого старого к самому свежему.
      M1 = самый старый матч
      M6 = самый свежий матч
      Это канонический порядок FormContext для FormModel.

============================================================
VERSION 1.2
============================================================

Изменения:

    - Исправлено получение xG из структуры
      xg = {"home": ..., "away": ...}
    - Теперь form_context корректно извлекает xG
      из записей, созданных build_history_record()

============================================================
VERSION 1.3
============================================================

Изменения:

    - DEFAULT_MATCH_LIMIT увеличен с 5 до 6
    - Теперь form_context по умолчанию работает с 6 матчами
    - Синхронизировано с MAX_HISTORY_MATCHES в faj_predictor.py

============================================================
VERSION 1.4
============================================================

Изменения:

    - Добавлена история xG/xGA по матчам в возвращаемый результат
    - Поля recent_xg и recent_xga в том же порядке, что и results/difficulty
    - Это позволяет FormModel анализировать xG в связке с результатом

============================================================
VERSION 1.5
============================================================

Изменения:

    - Исправлен контракт порядка истории
    - Теперь records должны приходить в хронологическом порядке:
      самый старый → ... → самый свежий (M1 → M6)
    - Это соответствует математическому контракту FormModel
      (temporal weights 1..6, OLS trend)
    - Порядок сохраняется без изменения

============================================================
VERSION 1.6
============================================================

Изменения:

    - Окончательно зафиксирован контракт порядка истории
    - Добавлен защитный комментарий в build_form_context()
    - M1 = самый старый, M6 = самый свежий
    - FormModel получает M1 → M6 с весами 1..6
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ============================================================
# VERSION
# ============================================================

FORM_CONTEXT_VERSION = "1.6"

DEFAULT_MATCH_LIMIT = 6


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Безопасное преобразование в float.

    None остаётся None.
    Пустые значения не превращаются в 0.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        text = str(value).strip()

        if not text:
            return None

        text = text.replace(",", ".")

        return float(text)

    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """
    Безопасное преобразование в int.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return int(value)

    except (TypeError, ValueError):
        return None


def _get_value(
    record: Any,
    *keys: str,
) -> Any:
    """
    Унифицированное получение поля из:

        dict
        sqlite3.Row
        объекта с атрибутами
    """

    if record is None:
        return None

    for key in keys:

        # dict
        if isinstance(record, dict):

            if key in record:
                return record[key]

        # sqlite3.Row
        try:

            if key in record.keys():

                return record[key]

        except (AttributeError, TypeError):
            pass

        # object
        try:

            value = getattr(
                record,
                key,
            )

            return value

        except AttributeError:
            pass

    return None


# ============================================================
# MATCH RESULT
# ============================================================

def determine_result(
    team_goals: Optional[int],
    opponent_goals: Optional[int],
) -> Optional[str]:
    """
    Определяет результат команды:

        W = победа
        D = ничья
        L = поражение

    Если счёт неизвестен → None.
    """

    if (
        team_goals is None
        or opponent_goals is None
    ):
        return None

    if team_goals > opponent_goals:
        return "W"

    if team_goals == opponent_goals:
        return "D"

    return "L"


# ============================================================
# MATCH DIFFICULTY
# ============================================================

def classify_match_difficulty(
    result: Optional[str],
    team_goals: Optional[int],
    opponent_goals: Optional[int],
    team_xg: Optional[float] = None,
    opponent_xg: Optional[float] = None,
) -> str:
    """
    Простая классификация сложности матча.

    ВАЖНО:

    Победа:
        +3 и больше → лёгкий
        +2          → средний
        +1          → тяжёлый

    Ничья:
        оценивается по xG, если он доступен.

    Поражение:

        Здесь НЕ зеркалим победу.

        Поражение 1 мяч:
            тяжёлый

        Поражение 2 мяча:
            тяжёлый

        Поражение 3+:
            очень тяжёлый

    Но xG позволяет немного лучше понять ситуацию.

    Например:

        0:3
        xG 1.70 : 1.10

    Это всё равно тяжёлое поражение,
    но команда хотя бы создавала моменты.

    А:

        0:3
        xG 0.25 : 2.40

    Это уже очень тяжёлый матч.

    xG НИКОГДА не отменяет факт поражения.
    """

    if result is None:
        return "неизвестно"

    if (
        team_goals is None
        or opponent_goals is None
    ):
        return "неизвестно"

    difference = abs(
        team_goals - opponent_goals
    )

    # --------------------------------------------------------
    # ПОБЕДА
    # --------------------------------------------------------

    if result == "W":

        if difference >= 3:
            return "лёгкий"

        if difference == 2:
            return "средний"

        return "тяжёлый"

    # --------------------------------------------------------
    # НИЧЬЯ
    # --------------------------------------------------------

    if result == "D":

        if (
            team_xg is not None
            and opponent_xg is not None
        ):

            xg_difference = (
                team_xg - opponent_xg
            )

            # Команда заметно доминировала,
            # но не выиграла.
            if xg_difference >= 0.75:
                return "тяжёлый"

            # Противник заметно доминировал.
            if xg_difference <= -0.75:
                return "очень тяжёлый"

        return "средний"

    # --------------------------------------------------------
    # ПОРАЖЕНИЕ
    # --------------------------------------------------------

    if result == "L":

        # Крупное поражение — всегда серьёзный сигнал.
        if difference >= 3:

            # Если xG команды совсем маленький,
            # а соперник создавал значительно больше,
            # это максимально плохой сценарий.
            if (
                team_xg is not None
                and opponent_xg is not None
            ):

                if (
                    team_xg < 0.75
                    and opponent_xg >= 1.50
                ):
                    return "очень тяжёлый"

            return "очень тяжёлый"

        # Поражение в 2 мяча —
        # серьёзный матч, но не автоматически катастрофа.
        if difference == 2:

            if (
                team_xg is not None
                and opponent_xg is not None
            ):

                # Команда проиграла,
                # но создала сопоставимо много.
                if (
                    team_xg >= 1.20
                    and opponent_xg - team_xg <= 0.50
                ):
                    return "тяжёлый"

            return "тяжёлый"

        # Поражение в один мяч.
        return "тяжёлый"

    return "неизвестно"


# ============================================================
# MATCH CONTEXT
# ============================================================

@dataclass
class MatchContext:

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    opponent: Optional[str] = None

    venue: Optional[str] = None

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result: Optional[str] = None

    result_symbol: Optional[str] = None

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    team_goals: Optional[int] = None

    opponent_goals: Optional[int] = None

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    team_xg: Optional[float] = None

    opponent_xg: Optional[float] = None

    # --------------------------------------------------------
    # Difficulty
    # --------------------------------------------------------

    difficulty: str = "неизвестно"


# ============================================================
# SYMBOL
# ============================================================

def result_symbol(
    result: Optional[str],
) -> str:

    if result == "W":
        return "В"

    if result == "D":
        return "Н"

    if result == "L":
        return "П"

    return "?"


# ============================================================
# BUILD MATCH CONTEXT
# ============================================================

def build_match_context(
    record: Any,
    team_name: str,
) -> MatchContext:
    """
    Преобразует одну запись исторического матча
    в простой MatchContext.

    Поддерживает наиболее распространённые имена полей.
    """

    home_team = _get_value(
        record,
        "home_team",
        "home_name",
        "home",
    )

    away_team = _get_value(
        record,
        "away_team",
        "away_name",
        "away",
    )

    # --------------------------------------------------------
    # Определяем сторону команды
    # --------------------------------------------------------

    is_home = (
        str(home_team).strip().lower()
        == str(team_name).strip().lower()
    )

    is_away = (
        str(away_team).strip().lower()
        == str(team_name).strip().lower()
    )

    # --------------------------------------------------------
    # Fallback: если структура уже содержит venue
    # --------------------------------------------------------

    venue = _get_value(
        record,
        "venue",
        "location",
        "home_away",
    )

    if venue:

        venue_text = str(
            venue
        ).strip().lower()

        if venue_text in (
            "home",
            "дома",
            "h",
        ):
            is_home = True
            is_away = False

        elif venue_text in (
            "away",
            "гости",
            "гостях",
            "a",
        ):
            is_home = False
            is_away = True

    # --------------------------------------------------------
    # Venue
    # --------------------------------------------------------

    if is_home:
        venue_normalized = "дома"

    elif is_away:
        venue_normalized = "гости"

    else:
        venue_normalized = None

    # --------------------------------------------------------
    # Opponent
    # --------------------------------------------------------

    if is_home:

        opponent = away_team

    elif is_away:

        opponent = home_team

    else:

        opponent = _get_value(
            record,
            "opponent",
            "opponent_name",
        )

    # --------------------------------------------------------
    # Goals
    # --------------------------------------------------------

    home_goals = _safe_int(
        _get_value(
            record,
            "home_goals",
            "home_score",
            "goals_home",
        )
    )

    away_goals = _safe_int(
        _get_value(
            record,
            "away_goals",
            "away_score",
            "goals_away",
        )
    )

    # Иногда счёт хранится одной строкой.
    if (
        home_goals is None
        or away_goals is None
    ):

        score = _get_value(
            record,
            "score",
            "result",
        )

        if score:

            import re

            match = re.search(
                r"(\d+)\s*[:\-]\s*(\d+)",
                str(score),
            )

            if match:

                home_goals = _safe_int(
                    match.group(1)
                )

                away_goals = _safe_int(
                    match.group(2)
                )

    # --------------------------------------------------------
    # Team / opponent goals
    # --------------------------------------------------------

    if is_home:

        team_goals = home_goals
        opponent_goals = away_goals

    elif is_away:

        team_goals = away_goals
        opponent_goals = home_goals

    else:

        team_goals = _safe_int(
            _get_value(
                record,
                "team_goals",
            )
        )

        opponent_goals = _safe_int(
            _get_value(
                record,
                "opponent_goals",
            )
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = determine_result(
        team_goals,
        opponent_goals,
    )

    # --------------------------------------------------------
    # xG (UPDATED: извлекаем из структуры xg = {"home": ..., "away": ...})
    # --------------------------------------------------------
    xg_values = _get_value(
        record,
        "xg",
    )

    if not isinstance(
        xg_values,
        dict,
    ):
        xg_values = {}

    home_xg = _safe_float(
        xg_values.get("home")
    )

    away_xg = _safe_float(
        xg_values.get("away")
    )

    if is_home:
        team_xg = home_xg
        opponent_xg = away_xg

    elif is_away:
        team_xg = away_xg
        opponent_xg = home_xg

    else:
        team_xg = _safe_float(
            _get_value(
                record,
                "team_xg",
            )
        )
        opponent_xg = _safe_float(
            _get_value(
                record,
                "opponent_xg",
            )
        )

    # --------------------------------------------------------
    # Difficulty
    # --------------------------------------------------------

    difficulty = classify_match_difficulty(
        result=result,
        team_goals=team_goals,
        opponent_goals=opponent_goals,
        team_xg=team_xg,
        opponent_xg=opponent_xg,
    )

    return MatchContext(
        opponent=(
            str(opponent).strip()
            if opponent
            else None
        ),
        venue=venue_normalized,
        result=result,
        result_symbol=result_symbol(result),
        team_goals=team_goals,
        opponent_goals=opponent_goals,
        team_xg=team_xg,
        opponent_xg=opponent_xg,
        difficulty=difficulty,
    )


# ============================================================
# FORM CONTEXT
# ============================================================

def build_form_context(
    team_name: str,
    records: Iterable[Any],
    limit: int = DEFAULT_MATCH_LIMIT,
) -> Dict[str, Any]:
    """
    Создаёт полный контекст последних матчей команды.

    ============================================================
    ВАЖНО: ПОРЯДОК ИСТОРИИ
    ============================================================

    records должны приходить в хронологическом порядке:

        M1 → M2 → M3 → M4 → M5 → M6

    где:
        M1 = самый старый матч в окне
        M6 = самый свежий матч перед прогнозом

    Этот порядок СОХРАНЯЕТСЯ без изменения.

    FormModel использует этот порядок для:
        - temporal weights (M6 получает вес 6)
        - OLS trend (временная последовательность)

    ============================================================

    Функция НЕ пытается сама угадывать даты.

    Поэтому правильная выборка должна быть сделана
    на уровне Predictor / Database.

    Здесь мы только ограничиваем количество
    последними `limit` переданными записями.
    """

    if limit <= 0:
        limit = DEFAULT_MATCH_LIMIT

    records_list = list(records)

    # ============================================================
    # FormContext canonical order: oldest → newest
    #
    # M1 = oldest match in the window
    # M6 = newest match before the forecast
    #
    # FormModel temporal weights 1..6
    # therefore assign maximum weight to the newest match.
    # ============================================================

    records_list = records_list[:limit]

    matches: List[MatchContext] = []

    for record in records_list:

        context = build_match_context(
            record=record,
            team_name=team_name,
        )

        matches.append(
            context
        )

    # ========================================================
    # FORM STRING
    # ========================================================

    form = "-".join(
        match.result_symbol
        for match in matches
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

    # ========================================================
    # AGGREGATES
    # ========================================================

    xg_values: List[float] = []
    xga_values: List[float] = []

    recent_xg: List[Optional[float]] = []
    recent_xga: List[Optional[float]] = []

    for match in matches:

        if match.venue == "дома":

            if match.result == "W":
                home_wins += 1

            elif match.result == "D":
                home_draws += 1

            elif match.result == "L":
                home_losses += 1

        elif match.venue == "гости":

            if match.result == "W":
                away_wins += 1

            elif match.result == "D":
                away_draws += 1

            elif match.result == "L":
                away_losses += 1

        # Собираем xG для истории
        recent_xg.append(match.team_xg)
        recent_xga.append(match.opponent_xg)

        if match.team_xg is not None:

            xg_values.append(
                match.team_xg
            )

        if match.opponent_xg is not None:

            xga_values.append(
                match.opponent_xg
            )

    # ========================================================
    # AVERAGE XG
    # ========================================================

    average_xg = (
        round(
            sum(xg_values)
            / len(xg_values),
            2,
        )
        if xg_values
        else None
    )

    average_xga = (
        round(
            sum(xga_values)
            / len(xga_values),
            2,
        )
        if xga_values
        else None
    )

    # ========================================================
    # DIFFICULTY LIST
    # ========================================================

    difficulties = [
        match.difficulty
        for match in matches
    ]

    # ========================================================
    # RESULT COUNTS
    # ========================================================

    wins = sum(
        1
        for match in matches
        if match.result == "W"
    )

    draws = sum(
        1
        for match in matches
        if match.result == "D"
    )

    losses = sum(
        1
        for match in matches
        if match.result == "L"
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "version": FORM_CONTEXT_VERSION,

        "team": team_name,

        "matches_count": len(matches),

        "form": form,

        "wins": wins,
        "draws": draws,
        "losses": losses,

        "home": {
            "matches": (
                home_wins
                + home_draws
                + home_losses
            ),
            "wins": home_wins,
            "draws": home_draws,
            "losses": home_losses,
        },

        "away": {
            "matches": (
                away_wins
                + away_draws
                + away_losses
            ),
            "wins": away_wins,
            "draws": away_draws,
            "losses": away_losses,
        },

        "xg": average_xg,

        "xga": average_xga,

        "recent_xg": tuple(recent_xg),
        "recent_xga": tuple(recent_xga),

        "matches": [
            asdict(match)
            for match in matches
        ],

        "difficulty": difficulties,
    }


# ============================================================
# HUMAN SUMMARY
# ============================================================

def format_form_context(
    context: Dict[str, Any],
) -> str:
    """
    Человекочитаемое представление.

    Это только UI/helper.
    Никакой математической логики здесь нет.
    """

    team = context.get(
        "team",
        "Команда",
    )

    form = context.get(
        "form",
        "",
    )

    home = context.get(
        "home",
        {},
    )

    away = context.get(
        "away",
        {},
    )

    xg = context.get(
        "xg",
    )

    xga = context.get(
        "xga",
    )

    difficulties = context.get(
        "difficulty",
        [],
    )

    lines = []

    lines.append(
        str(team)
    )

    lines.append(
        f"Последние {len(difficulties)}: {form or '—'}"
    )

    lines.append(
        "Дома: "
        f"{home.get('wins', 0)}-"
        f"{home.get('draws', 0)}-"
        f"{home.get('losses', 0)}"
    )

    lines.append(
        "Гости: "
        f"{away.get('wins', 0)}-"
        f"{away.get('draws', 0)}-"
        f"{away.get('losses', 0)}"
    )

    lines.append(
        "xG: "
        + (
            f"{xg:.2f}"
            if xg is not None
            else "—"
        )
    )

    lines.append(
        "xGA: "
        + (
            f"{xga:.2f}"
            if xga is not None
            else "—"
        )
    )

    lines.append(
        "Матчи: "
        + (
            " / ".join(
                difficulties
            )
            if difficulties
            else "—"
        )
    )

    return "\n".join(
        lines
    )


# ============================================================
# DEBUG
# ============================================================

if __name__ == "__main__":

    sample = [

        {
            "home_team": "Зенит",
            "away_team": "Краснодар",
            "home_goals": 3,
            "away_goals": 0,
            "xg": {
                "home": 2.10,
                "away": 0.40,
            },
        },

        {
            "home_team": "Спартак",
            "away_team": "Зенит",
            "home_goals": 1,
            "away_goals": 1,
            "xg": {
                "home": 1.20,
                "away": 1.60,
            },
        },

        {
            "home_team": "Зенит",
            "away_team": "ЦСКА Москва",
            "home_goals": 2,
            "away_goals": 1,
            "xg": {
                "home": 1.80,
                "away": 1.20,
            },
        },

        {
            "home_team": "Локомотив Москва",
            "away_team": "Зенит",
            "home_goals": 3,
            "away_goals": 1,
            "xg": {
                "home": 2.20,
                "away": 0.50,
            },
        },

        {
            "home_team": "Зенит",
            "away_team": "Ростов",
            "home_goals": 1,
            "away_goals": 1,
            "xg": {
                "home": 1.40,
                "away": 1.10,
            },
        },
    ]

    context = build_form_context(
        team_name="Зенит",
        records=sample,
        limit=5,
    )

    print(
        format_form_context(
            context
        )
    )

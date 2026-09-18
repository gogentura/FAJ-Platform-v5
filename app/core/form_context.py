#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM CONTEXT v1.9
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
VERSION 1.7
============================================================

Изменения:

    - Расширен MatchContext: добавлены угловые и карточки
    - Добавлены истории: corners_for_history, corners_against_history
    - Добавлены истории: team_cards_history, opponent_cards_history
    - Добавлены агрегаты: corners_for_avg, corners_against_avg
    - Добавлены агрегаты: team_cards_avg, opponent_cards_avg
    - Добавлены истории: goals_for_history, goals_against_history
    - Добавлены истории: team_xg_history, opponent_xg_history
    - Добавлены истории: venue_history, difficulty_history
    - Добавлены истории: results_history
    - Все истории синхронизированы по одной временной оси (старый → новый)
    - None не заменяется на 0
    - Средние считаются только по доступным значениям

============================================================
VERSION 1.8
============================================================

Изменения:

    - Расширен MatchContext статистикой контроля:
        possession
        passes
        pass accuracy
        crosses
        throw-ins
        offsides
        shots
        big chances

    - Добавлены парные значения:
        команда / соперник

    - Добавлены синхронные истории для FormControl

    - Поддерживается несколько возможных структур
      historical record / statistics

    - None не заменяется на 0

    - Статистика не влияет на xG, GoalModel,
      ProbabilityModel или Prediction

    - FormContext остаётся только FACT/context layer

============================================================
VERSION 1.9
============================================================

Изменения:

    - Добавлена история ударов в створ (shots on target):
        shots_on_target_history
        shots_on_target_against_history
    - MatchContext расширен полями:
        shots_on_target
        opponent_shots_on_target
    - Источники: прямые поля / statistics-контейнеры /
      fallback team_shots_on_target / opponent_shots_on_target
    - None не заменяется на 0
    - Поле используется Defence (SOT signals), FormWin
      (sot_signal), FormModel (shots_on_target_avg) и
      SpecialForm (Haaland dimension) — раньше все они
      оставались без данных, так как FormContext не отдавал
      эту историю вообще
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ============================================================
# VERSION
# ============================================================

FORM_CONTEXT_VERSION = "1.9"

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


def _get_stat_value(
    record: Any,
    metric_names: Tuple[str, ...],
    side: str,
) -> Any:
    """
    Извлекает статистику конкретной стороны матча.

    Поддерживает:

        home_possession / away_possession

        possession = {
            "home": ...,
            "away": ...
        }

        statistics = {
            "possession": {
                "home": ...,
                "away": ...
            }
        }

    None остаётся None.
    """

    if record is None:
        return None

    side = str(side).strip().lower()

    if side not in ("home", "away"):
        return None

    # --------------------------------------------------------
    # 1. Прямые поля
    # --------------------------------------------------------

    for metric in metric_names:

        candidates = (
            f"{side}_{metric}",
            f"{metric}_{side}",
        )

        for key in candidates:

            value = _get_value(
                record,
                key,
            )

            if value is not None:
                return value

    # --------------------------------------------------------
    # 2. Контейнеры statistics / stats
    # --------------------------------------------------------

    containers = []

    for container_name in (
        "statistics",
        "stats",
        "match_statistics",
        "match_stats",
    ):

        container = _get_value(
            record,
            container_name,
        )

        if isinstance(container, dict):
            containers.append(container)

    # Сам record также может содержать:
    # possession = {"home": ..., "away": ...}

    if isinstance(record, dict):
        containers.append(record)

    else:

        try:
            if hasattr(record, "keys"):
                containers.append(
                    {
                        key: record[key]
                        for key in record.keys()
                    }
                )
        except (AttributeError, TypeError):
            pass

    # --------------------------------------------------------
    # 3. metric -> {home, away}
    # --------------------------------------------------------

    for container in containers:

        for metric in metric_names:

            value = container.get(metric)

            if not isinstance(value, dict):
                continue

            if side in value:
                return value[side]

            if side == "home":

                for key in (
                    "home",
                    "h",
                    "host",
                ):
                    if key in value:
                        return value[key]

            else:

                for key in (
                    "away",
                    "a",
                    "guest",
                ):
                    if key in value:
                        return value[key]

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
    # Corners
    # --------------------------------------------------------

    corners_for: Optional[int] = None

    corners_against: Optional[int] = None

    # --------------------------------------------------------
    # Cards
    # --------------------------------------------------------

    team_cards: Optional[int] = None

    opponent_cards: Optional[int] = None

    # --------------------------------------------------------
    # MATCH STATISTICS — CONTROL
    # --------------------------------------------------------

    possession: Optional[float] = None
    opponent_possession: Optional[float] = None

    passes: Optional[float] = None
    opponent_passes: Optional[float] = None

    pass_accuracy: Optional[float] = None
    opponent_pass_accuracy: Optional[float] = None

    crosses: Optional[float] = None
    opponent_crosses: Optional[float] = None

    throw_ins: Optional[float] = None
    opponent_throw_ins: Optional[float] = None

    offsides: Optional[float] = None
    opponent_offsides: Optional[float] = None

    shots: Optional[float] = None
    opponent_shots: Optional[float] = None

    # --------------------------------------------------------
    # Shots on target (v1.9)
    # --------------------------------------------------------

    shots_on_target: Optional[float] = None
    opponent_shots_on_target: Optional[float] = None

    big_chances: Optional[float] = None
    opponent_big_chances: Optional[float] = None

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
    # CORNERS
    # --------------------------------------------------------
    home_corners = _safe_int(
        _get_value(
            record,
            "home_corners",
            "corners_home",
        )
    )
    away_corners = _safe_int(
        _get_value(
            record,
            "away_corners",
            "corners_away",
        )
    )

    if is_home:
        corners_for = home_corners
        corners_against = away_corners
    elif is_away:
        corners_for = away_corners
        corners_against = home_corners
    else:
        corners_for = _safe_int(
            _get_value(
                record,
                "corners_for",
            )
        )
        corners_against = _safe_int(
            _get_value(
                record,
                "corners_against",
            )
        )

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------
    home_cards = _safe_int(
        _get_value(
            record,
            "home_yellow_cards",
            "home_cards",
            "yellow_cards_home",
        )
    )
    away_cards = _safe_int(
        _get_value(
            record,
            "away_yellow_cards",
            "away_cards",
            "yellow_cards_away",
        )
    )

    if is_home:
        team_cards = home_cards
        opponent_cards = away_cards
    elif is_away:
        team_cards = away_cards
        opponent_cards = home_cards
    else:
        team_cards = _safe_int(
            _get_value(
                record,
                "team_cards",
            )
        )
        opponent_cards = _safe_int(
            _get_value(
                record,
                "opponent_cards",
            )
        )

    # --------------------------------------------------------
    # MATCH STATISTICS — CONTROL
    # --------------------------------------------------------

    home_possession = _safe_float(
        _get_stat_value(
            record,
            (
                "possession",
                "possession_pct",
                "possession_percent",
            ),
            "home",
        )
    )

    away_possession = _safe_float(
        _get_stat_value(
            record,
            (
                "possession",
                "possession_pct",
                "possession_percent",
            ),
            "away",
        )
    )

    home_passes = _safe_float(
        _get_stat_value(
            record,
            (
                "passes",
                "total_passes",
                "pass_count",
            ),
            "home",
        )
    )

    away_passes = _safe_float(
        _get_stat_value(
            record,
            (
                "passes",
                "total_passes",
                "pass_count",
            ),
            "away",
        )
    )

    home_accuracy = _safe_float(
        _get_stat_value(
            record,
            (
                "pass_accuracy",
                "passing_accuracy",
                "accuracy",
                "pass_accuracy_pct",
            ),
            "home",
        )
    )

    away_accuracy = _safe_float(
        _get_stat_value(
            record,
            (
                "pass_accuracy",
                "passing_accuracy",
                "accuracy",
                "pass_accuracy_pct",
            ),
            "away",
        )
    )

    home_crosses = _safe_float(
        _get_stat_value(
            record,
            (
                "crosses",
                "crosses_total",
            ),
            "home",
        )
    )

    away_crosses = _safe_float(
        _get_stat_value(
            record,
            (
                "crosses",
                "crosses_total",
            ),
            "away",
        )
    )

    home_throw_ins = _safe_float(
        _get_stat_value(
            record,
            (
                "throw_ins",
                "throwins",
                "throw_in",
            ),
            "home",
        )
    )

    away_throw_ins = _safe_float(
        _get_stat_value(
            record,
            (
                "throw_ins",
                "throwins",
                "throw_in",
            ),
            "away",
        )
    )

    home_offsides = _safe_float(
        _get_stat_value(
            record,
            (
                "offsides",
                "offside",
            ),
            "home",
        )
    )

    away_offsides = _safe_float(
        _get_stat_value(
            record,
            (
                "offsides",
                "offside",
            ),
            "away",
        )
    )

    home_shots = _safe_float(
        _get_stat_value(
            record,
            (
                "shots",
                "total_shots",
                "shots_total",
            ),
            "home",
        )
    )

    away_shots = _safe_float(
        _get_stat_value(
            record,
            (
                "shots",
                "total_shots",
                "shots_total",
            ),
            "away",
        )
    )

    # --------------------------------------------------------
    # SHOTS ON TARGET (v1.9)
    # --------------------------------------------------------

    home_shots_on_target = _safe_float(
        _get_stat_value(
            record,
            (
                "shots_on_target",
                "sot",
                "shots_on_target_total",
            ),
            "home",
        )
    )

    away_shots_on_target = _safe_float(
        _get_stat_value(
            record,
            (
                "shots_on_target",
                "sot",
                "shots_on_target_total",
            ),
            "away",
        )
    )

    home_big_chances = _safe_float(
        _get_stat_value(
            record,
            (
                "big_chances",
                "big_chances_created",
                "big_chances_total",
            ),
            "home",
        )
    )

    away_big_chances = _safe_float(
        _get_stat_value(
            record,
            (
                "big_chances",
                "big_chances_created",
                "big_chances_total",
            ),
            "away",
        )
    )

    # --------------------------------------------------------
    # TEAM / OPPONENT ORIENTATION
    # --------------------------------------------------------

    if is_home:

        possession = home_possession
        opponent_possession = away_possession

        passes = home_passes
        opponent_passes = away_passes

        pass_accuracy = home_accuracy
        opponent_pass_accuracy = away_accuracy

        crosses = home_crosses
        opponent_crosses = away_crosses

        throw_ins = home_throw_ins
        opponent_throw_ins = away_throw_ins

        offsides = home_offsides
        opponent_offsides = away_offsides

        shots = home_shots
        opponent_shots = away_shots

        shots_on_target = home_shots_on_target
        opponent_shots_on_target = away_shots_on_target

        big_chances = home_big_chances
        opponent_big_chances = away_big_chances

    elif is_away:

        possession = away_possession
        opponent_possession = home_possession

        passes = away_passes
        opponent_passes = home_passes

        pass_accuracy = away_accuracy
        opponent_pass_accuracy = home_accuracy

        crosses = away_crosses
        opponent_crosses = home_crosses

        throw_ins = away_throw_ins
        opponent_throw_ins = home_throw_ins

        offsides = away_offsides
        opponent_offsides = home_offsides

        shots = away_shots
        opponent_shots = home_shots

        shots_on_target = away_shots_on_target
        opponent_shots_on_target = home_shots_on_target

        big_chances = away_big_chances
        opponent_big_chances = home_big_chances

    else:

        possession = _safe_float(
            _get_value(
                record,
                "team_possession",
            )
        )

        opponent_possession = _safe_float(
            _get_value(
                record,
                "opponent_possession",
            )
        )

        passes = _safe_float(
            _get_value(
                record,
                "team_passes",
            )
        )

        opponent_passes = _safe_float(
            _get_value(
                record,
                "opponent_passes",
            )
        )

        pass_accuracy = _safe_float(
            _get_value(
                record,
                "team_pass_accuracy",
            )
        )

        opponent_pass_accuracy = _safe_float(
            _get_value(
                record,
                "opponent_pass_accuracy",
            )
        )

        crosses = _safe_float(
            _get_value(
                record,
                "team_crosses",
            )
        )

        opponent_crosses = _safe_float(
            _get_value(
                record,
                "opponent_crosses",
            )
        )

        throw_ins = _safe_float(
            _get_value(
                record,
                "team_throw_ins",
            )
        )

        opponent_throw_ins = _safe_float(
            _get_value(
                record,
                "opponent_throw_ins",
            )
        )

        offsides = _safe_float(
            _get_value(
                record,
                "team_offsides",
            )
        )

        opponent_offsides = _safe_float(
            _get_value(
                record,
                "opponent_offsides",
            )
        )

        shots = _safe_float(
            _get_value(
                record,
                "team_shots",
            )
        )

        opponent_shots = _safe_float(
            _get_value(
                record,
                "opponent_shots",
            )
        )

        shots_on_target = _safe_float(
            _get_value(
                record,
                "team_shots_on_target",
            )
        )

        opponent_shots_on_target = _safe_float(
            _get_value(
                record,
                "opponent_shots_on_target",
            )
        )

        big_chances = _safe_float(
            _get_value(
                record,
                "team_big_chances",
            )
        )

        opponent_big_chances = _safe_float(
            _get_value(
                record,
                "opponent_big_chances",
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
        corners_for=corners_for,
        corners_against=corners_against,
        team_cards=team_cards,
        opponent_cards=opponent_cards,

        # ----------------------------------------------------
        # CONTROL STATISTICS
        # ----------------------------------------------------

        possession=possession,
        opponent_possession=opponent_possession,

        passes=passes,
        opponent_passes=opponent_passes,

        pass_accuracy=pass_accuracy,
        opponent_pass_accuracy=opponent_pass_accuracy,

        crosses=crosses,
        opponent_crosses=opponent_crosses,

        throw_ins=throw_ins,
        opponent_throw_ins=opponent_throw_ins,

        offsides=offsides,
        opponent_offsides=opponent_offsides,

        shots=shots,
        opponent_shots=opponent_shots,

        shots_on_target=shots_on_target,
        opponent_shots_on_target=opponent_shots_on_target,

        big_chances=big_chances,
        opponent_big_chances=opponent_big_chances,

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
    # FACT HISTORY
    #
    # ВАЖНО:
    # matches уже отсортированы одним общим временным рядом.
    # Все history строятся из него.
    #
    # Порядок:
    # oldest -> newest
    # ========================================================
    results_history: List[Optional[str]] = []
    goals_for_history: List[Optional[int]] = []
    goals_against_history: List[Optional[int]] = []
    team_xg_history: List[Optional[float]] = []
    opponent_xg_history: List[Optional[float]] = []
    venue_history: List[Optional[str]] = []
    difficulty_history: List[str] = []
    corners_for_history: List[Optional[int]] = []
    corners_against_history: List[Optional[int]] = []
    team_cards_history: List[Optional[int]] = []
    opponent_cards_history: List[Optional[int]] = []

    # --------------------------------------------------------
    # CONTROL STATISTICS HISTORY
    # --------------------------------------------------------
    possession_history: List[Optional[float]] = []
    opponent_possession_history: List[Optional[float]] = []

    passes_history: List[Optional[float]] = []
    opponent_passes_history: List[Optional[float]] = []

    pass_accuracy_history: List[Optional[float]] = []
    opponent_pass_accuracy_history: List[Optional[float]] = []

    crosses_history: List[Optional[float]] = []
    opponent_crosses_history: List[Optional[float]] = []

    throw_ins_history: List[Optional[float]] = []
    opponent_throw_ins_history: List[Optional[float]] = []

    offsides_history: List[Optional[float]] = []
    opponent_offsides_history: List[Optional[float]] = []

    shots_history: List[Optional[float]] = []
    shots_conceded_history: List[Optional[float]] = []

    # --------------------------------------------------------
    # SHOTS ON TARGET HISTORY (v1.9)
    # --------------------------------------------------------
    shots_on_target_history: List[Optional[float]] = []
    shots_on_target_against_history: List[Optional[float]] = []

    big_chances_history: List[Optional[float]] = []
    big_chances_against_history: List[Optional[float]] = []

    # ========================================================
    # DERIVED NUMERIC COLLECTIONS
    # ========================================================
    xg_values: List[float] = []
    xga_values: List[float] = []
    corners_for_values: List[float] = []
    corners_against_values: List[float] = []
    team_cards_values: List[float] = []
    opponent_cards_values: List[float] = []

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

    recent_xg: List[Optional[float]] = []
    recent_xga: List[Optional[float]] = []

    for match in matches:

        # ----------------------------------------------------
        # PRIMARY FACT HISTORY
        # ----------------------------------------------------
        results_history.append(match.result)
        goals_for_history.append(match.team_goals)
        goals_against_history.append(match.opponent_goals)
        team_xg_history.append(match.team_xg)
        opponent_xg_history.append(match.opponent_xg)
        venue_history.append(match.venue)
        difficulty_history.append(match.difficulty)
        corners_for_history.append(match.corners_for)
        corners_against_history.append(match.corners_against)
        team_cards_history.append(match.team_cards)
        opponent_cards_history.append(match.opponent_cards)

        # ----------------------------------------------------
        # CONTROL STATISTICS HISTORY
        # ----------------------------------------------------

        possession_history.append(
            match.possession
        )

        opponent_possession_history.append(
            match.opponent_possession
        )

        passes_history.append(
            match.passes
        )

        opponent_passes_history.append(
            match.opponent_passes
        )

        pass_accuracy_history.append(
            match.pass_accuracy
        )

        opponent_pass_accuracy_history.append(
            match.opponent_pass_accuracy
        )

        crosses_history.append(
            match.crosses
        )

        opponent_crosses_history.append(
            match.opponent_crosses
        )

        throw_ins_history.append(
            match.throw_ins
        )

        opponent_throw_ins_history.append(
            match.opponent_throw_ins
        )

        offsides_history.append(
            match.offsides
        )

        opponent_offsides_history.append(
            match.opponent_offsides
        )

        shots_history.append(
            match.shots
        )

        shots_conceded_history.append(
            match.opponent_shots
        )

        # ------------------------------------------------
        # SHOTS ON TARGET (v1.9)
        # ------------------------------------------------

        shots_on_target_history.append(
            match.shots_on_target
        )

        shots_on_target_against_history.append(
            match.opponent_shots_on_target
        )

        big_chances_history.append(
            match.big_chances
        )

        big_chances_against_history.append(
            match.opponent_big_chances
        )

        # ----------------------------------------------------
        # HOME / AWAY COUNTS
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # xG
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # CORNERS NUMERIC OBSERVATIONS
        # ----------------------------------------------------
        if match.corners_for is not None:
            corners_for_values.append(
                float(match.corners_for)
            )
        if match.corners_against is not None:
            corners_against_values.append(
                float(match.corners_against)
            )

        # ----------------------------------------------------
        # CARDS NUMERIC OBSERVATIONS
        # ----------------------------------------------------
        if match.team_cards is not None:
            team_cards_values.append(
                float(match.team_cards)
            )
        if match.opponent_cards is not None:
            opponent_cards_values.append(
                float(match.opponent_cards)
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
    # AVERAGE CORNERS
    # ========================================================

    corners_for_avg = (
        round(
            sum(corners_for_values)
            / len(corners_for_values),
            2,
        )
        if corners_for_values
        else None
    )

    corners_against_avg = (
        round(
            sum(corners_against_values)
            / len(corners_against_values),
            2,
        )
        if corners_against_values
        else None
    )

    # ========================================================
    # AVERAGE CARDS
    # ========================================================

    team_cards_avg = (
        round(
            sum(team_cards_values)
            / len(team_cards_values),
            2,
        )
        if team_cards_values
        else None
    )

    opponent_cards_avg = (
        round(
            sum(opponent_cards_values)
            / len(opponent_cards_values),
            2,
        )
        if opponent_cards_values
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

        # ====================================================
        # CORNERS AGGREGATES
        # ====================================================

        "corners_for_avg": corners_for_avg,
        "corners_against_avg": corners_against_avg,

        # ====================================================
        # CARDS AGGREGATES
        # ====================================================

        "team_cards_avg": team_cards_avg,
        "opponent_cards_avg": opponent_cards_avg,

        # ====================================================
        # PRIMARY FACT HISTORY
        # ====================================================

        "results": tuple(results_history),
        "goals_for_history": tuple(
            goals_for_history
        ),
        "goals_against_history": tuple(
            goals_against_history
        ),
        "team_xg_history": tuple(
            team_xg_history
        ),
        "opponent_xg_history": tuple(
            opponent_xg_history
        ),
        "venue_history": tuple(
            venue_history
        ),
        "difficulty_history": tuple(
            difficulty_history
        ),

        # ====================================================
        # CORNERS HISTORY
        # ====================================================

        "corners_for_history": tuple(
            corners_for_history
        ),
        "corners_against_history": tuple(
            corners_against_history
        ),

        # ====================================================
        # CARDS HISTORY
        # ====================================================

        "team_cards_history": tuple(
            team_cards_history
        ),
        "opponent_cards_history": tuple(
            opponent_cards_history
        ),

        # ====================================================
        # FORM CONTROL HISTORY
        # ====================================================

        "possession_history": tuple(
            possession_history
        ),
        "opponent_possession_history": tuple(
            opponent_possession_history
        ),

        "passes_history": tuple(
            passes_history
        ),
        "opponent_passes_history": tuple(
            opponent_passes_history
        ),

        "pass_accuracy_history": tuple(
            pass_accuracy_history
        ),
        "opponent_pass_accuracy_history": tuple(
            opponent_pass_accuracy_history
        ),

        "crosses_history": tuple(
            crosses_history
        ),
        "opponent_crosses_history": tuple(
            opponent_crosses_history
        ),

        "throw_ins_history": tuple(
            throw_ins_history
        ),
        "opponent_throw_ins_history": tuple(
            opponent_throw_ins_history
        ),

        "offsides_history": tuple(
            offsides_history
        ),
        "opponent_offsides_history": tuple(
            opponent_offsides_history
        ),

        "shots_history": tuple(
            shots_history
        ),
        "shots_conceded_history": tuple(
            shots_conceded_history
        ),

        # ====================================================
        # SHOTS ON TARGET HISTORY (v1.9)
        # ====================================================

        "shots_on_target_history": tuple(
            shots_on_target_history
        ),
        "shots_on_target_against_history": tuple(
            shots_on_target_against_history
        ),

        "big_chances_history": tuple(
            big_chances_history
        ),
        "big_chances_against_history": tuple(
            big_chances_against_history
        ),

        # ====================================================
        # OLD COMPATIBILITY (will be deprecated)
        # ====================================================

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

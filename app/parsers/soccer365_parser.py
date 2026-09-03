#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCER365 PARSER v1.2.4
============================================================

НАЗНАЧЕНИЕ:

    Soccer365 является источником фактической
    статистики сыгранного матча и xG.

    Parser НЕ:
        - записывает данные в SQLite;
        - изменяет matches;
        - изменяет match_results;
        - создаёт прогнозы;
        - обучает модель.

    Parser только:

        Soccer365 URL
             ↓
        HTML
             ↓
        Блок "Весь матч" (#stat-tp0)
             ↓
        FACTS
             ↓
        import_facts.py


============================================================
ВАЖНО
============================================================

Soccer365 показывает:

    Весь матч (#stat-tp0)
    1-й тайм (#stat-tp1)
    2-й тайм (#stat-tp2)

FAJ использует ТОЛЬКО:

    ВЕСЬ МАТЧ (#stat-tp0)


============================================================
ИЗМЕНЕНИЯ V1.2
============================================================

    - Переход на DOM-парсинг вместо текстового поиска
    - Использование id="clubs_stats" и id="stat-tp0"
    - Прямой парсинг .stats_item
    - Улучшенное извлечение команд
    - Логирование пропущенных полей


============================================================
ИЗМЕНЕНИЯ V1.2.1
============================================================

    - Интеграция с FAJ Team Identity
    - canonicalize_parsed_team()
    - Двойная защита в parse()


============================================================
ИЗМЕНЕНИЯ V1.2.2
============================================================

    - Добавлено извлечение даты матча
    - extract_match_date()
    - match_date сохраняется в результате


============================================================
ИЗМЕНЕНИЯ V1.2.3
============================================================

    - Исправлено извлечение счёта
    - Используется:
          .live_game_goals .live_game_goal span
    - Не используются .score1 / .score2


============================================================
ИЗМЕНЕНИЯ V1.2.4
============================================================

КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ STATISTICS:

    Старый алгоритм позволял частичное совпадение:

        "удары" in "штрафные удары"

    В результате поле:

        home_shots

    могло получить значение:

        штрафные удары

    вместо:

        удары


Исправлено:

    1. Приоритет точного совпадения label.
    2. Удалено опасное частичное совпадение для
       коротких/общих названий.
    3. Добавлен специальный позиционный fallback
       для блока после xG.

На Soccer365:

    Ожидаемые голы (xG)
            ↓
    Удары
            ↓
    Удары в створ
            ↓
    Заблокированные удары

Если стандартный label-парсинг не определяет
эти три поля корректно, используется именно
эта DOM-последовательность.

ВАЖНО:

    Парсится ТОЛЬКО #stat-tp0.
"""


from __future__ import annotations

import logging
import re

from datetime import datetime

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

import requests

from bs4 import BeautifulSoup


# ============================================================
# FAJ TEAM IDENTITY
# ============================================================

from app.core.team_identity import resolve_team_name


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

PARSER_VERSION = "1.2.4"

SOURCE_NAME = "soccer365"

DEFAULT_TIMEOUT = 20


USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)


# ============================================================
# STATISTIC MAP
# ============================================================

STAT_LABELS: Dict[str, List[str]] = {

    "home_xg": [
        "ожидаемые голы (xg)",
        "ожидаемые голы",
        "expected goals",
    ],

    "home_shots": [
        "удары",
        "shots",
    ],

    "home_shots_on_target": [
        "удары в створ",
        "shots on target",
    ],

    "home_blocked_shots": [
        "заблокированные удары",
        "blocked shots",
    ],

    "home_shots_woodwork": [
        "удары в каркас",
        "shots against woodwork",
        "shots hit woodwork",
    ],

    "home_saves": [
        "сейвы",
        "saves",
    ],

    "home_possession": [
        "владение %",
        "possession %",
    ],

    "home_corners": [
        "угловые",
        "corners",
    ],

    "home_free_kicks": [
        "штрафные удары",
        "free kicks",
    ],

    "home_throw_ins": [
        "вбрасывания",
        "throw ins",
        "throw-ins",
    ],

    "home_crosses": [
        "навесы",
        "crosses",
    ],

    "home_fouls": [
        "фолы",
        "fouls",
    ],

    "home_offsides": [
        "офсайды",
        "offsides",
    ],

    "home_yellow_cards": [
        "желтые карточки",
        "жёлтые карточки",
        "yellow cards",
    ],

    "home_red_cards": [
        "красные карточки",
        "red cards",
    ],

    "home_total_passes": [
        "передачи",
        "passes",
    ],

    "home_pass_accuracy": [
        "точность передач %",
        "точность передач",
        "pass accuracy %",
        "pass accuracy",
    ],

    "home_tackles": [
        "отборы",
        "tackles",
    ],

    "home_clearances": [
        "выносы",
        "clearances",
    ],

    "home_big_chances": [
        "голевые моменты",
        "big chances",
    ],

    "home_attacks": [
        "атаки",
        "attacks",
    ],

    "home_dangerous_attacks": [
        "опасные атаки",
        "dangerous attacks",
    ],
}


# ============================================================
# RESULT
# ============================================================

def empty_result() -> Dict[str, Any]:

    return {
        "stats": {},

        "home_team": None,
        "away_team": None,

        "score": None,
        "match_date": None,

        "source": SOURCE_NAME,
        "source_url": None,

        "quality": 0.0,
        "data_quality": 0.0,

        "parser_version": PARSER_VERSION,

        "parsed_at": None,

        "error": None,
    }


# ============================================================
# TEXT
# ============================================================

def normalize_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    text = str(value)

    text = (
        text
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\u202f", " ")
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def normalize_label(
    value: Any,
) -> str:

    text = normalize_text(
        value
    ).lower()

    text = text.replace(
        "ё",
        "е",
    )

    return text.strip()


# ============================================================
# FAJ TEAM IDENTITY
# ============================================================

def canonicalize_parsed_team(
    value: Any,
) -> Optional[str]:
    """
    Приводит название команды из внешнего источника
    к canonical FAJ identity.

    Если команда неизвестна FAJ Identity Registry,
    сохраняется исходное название.
    """

    text = normalize_text(
        value
    )

    if not text:
        return None

    canonical = resolve_team_name(
        text
    )

    if canonical:

        logger.debug(
            "Soccer365 team identity: %r -> %r",
            text,
            canonical,
        )

        return canonical

    logger.warning(
        "Soccer365: команда не найдена "
        "в FAJ Identity Registry: %r",
        text,
    )

    return text


# ============================================================
# NUMBERS
# ============================================================

def safe_int(
    value: Any,
) -> Optional[int]:

    if value is None:
        return None

    text = normalize_text(
        value
    )

    match = re.search(
        r"-?\d+",
        text,
    )

    if not match:
        return None

    try:

        return int(
            match.group(0)
        )

    except ValueError:

        return None


def safe_float(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    text = normalize_text(
        value
    )

    text = text.replace(
        ",",
        ".",
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    if not match:
        return None

    try:

        return float(
            match.group(0)
        )

    except ValueError:

        return None


# ============================================================
# VALUE CONVERSION
# ============================================================

def convert_value(
    key: str,
    value: Any,
) -> Optional[Any]:

    if value is None:
        return None

    if key.endswith(
        "_xg"
    ):

        return safe_float(
            value
        )

    return safe_int(
        value
    )


# ============================================================
# HTTP
# ============================================================

def fetch_html(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[str, str]:

    if not url:

        raise ValueError(
            "Soccer365 URL не указан."
        )

    url = url.strip()

    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),

            "Accept-Language": (
                "ru-RU,ru;q=0.9,"
                "en-US;q=0.8,en;q=0.5"
            ),

            "Cache-Control": "no-cache",
        },

        timeout=timeout,

        allow_redirects=True,
    )

    response.raise_for_status()

    content_type = (
        response.headers
        .get(
            "Content-Type",
            "",
        )
        .lower()
    )

    if "charset=utf-8" in content_type:

        response.encoding = "utf-8"

    elif not response.encoding:

        response.encoding = "utf-8"

    return (
        response.text,
        response.url,
    )


# ============================================================
# SOUP
# ============================================================

def make_soup(
    html: str,
) -> BeautifulSoup:

    return BeautifulSoup(
        html,
        "html.parser",
    )


# ============================================================
# TEAMS
# ============================================================

def extract_teams(
    soup: BeautifulSoup,
) -> Tuple[
    Optional[str],
    Optional[str],
]:

    # --------------------------------------------------------
    # STRATEGY 1
    # --------------------------------------------------------

    home_elem = soup.select_one(
        ".live_game_ht .live_game_tlogo"
    )

    away_elem = soup.select_one(
        ".live_game_at .live_game_tlogo"
    )

    if home_elem and away_elem:

        home = normalize_text(
            home_elem.get_text(
                " ",
                strip=True,
            )
        )

        away = normalize_text(
            away_elem.get_text(
                " ",
                strip=True,
            )
        )

        if home and away:

            return (
                canonicalize_parsed_team(
                    home
                ),

                canonicalize_parsed_team(
                    away
                ),
            )

    # --------------------------------------------------------
    # STRATEGY 2 — META DESCRIPTION
    # --------------------------------------------------------

    meta = soup.find(
        "meta",
        attrs={
            "name": "description"
        },
    )

    if meta:

        content = meta.get(
            "content"
        )

        if content:

            text = normalize_text(
                content
            )

            match = re.search(
                r"Матч\s+(.+?)\s*-\s*(.+?)\.",
                text,
                flags=re.IGNORECASE,
            )

            if match:

                home = normalize_text(
                    match.group(1)
                )

                away = normalize_text(
                    match.group(2)
                )

                if home and away:

                    return (
                        canonicalize_parsed_team(
                            home
                        ),

                        canonicalize_parsed_team(
                            away
                        ),
                    )

    # --------------------------------------------------------
    # STRATEGY 3 — TITLE
    # --------------------------------------------------------

    title = soup.find(
        "title"
    )

    if title:

        text = normalize_text(
            title.get_text(
                " ",
                strip=True,
            )
        )

        match = re.search(
            r"^(.+?)\s*-\s*(.+?):",
            text,
        )

        if match:

            home = normalize_text(
                match.group(1)
            )

            away = normalize_text(
                match.group(2)
            )

            if home and away:

                return (
                    canonicalize_parsed_team(
                        home
                    ),

                    canonicalize_parsed_team(
                        away
                    ),
                )

    # --------------------------------------------------------
    # STRATEGY 4 — SCORE HEADER FALLBACK
    # --------------------------------------------------------

    score1 = soup.select_one(
        ".score1"
    )

    score2 = soup.select_one(
        ".score2"
    )

    if score1 and score2:

        parent = score1.parent

        if parent:

            links = parent.find_all(
                "a"
            )

            team_names = []

            for link in links:

                text = normalize_text(
                    link.get_text(
                        " ",
                        strip=True,
                    )
                )

                if text:

                    team_names.append(
                        text
                    )

            if len(team_names) >= 2:

                return (
                    canonicalize_parsed_team(
                        team_names[0]
                    ),

                    canonicalize_parsed_team(
                        team_names[-1]
                    ),
                )

    return (
        None,
        None,
    )


# ============================================================
# SCORE
# ============================================================

def extract_score(
    soup: BeautifulSoup,
) -> Optional[str]:
    """
    Извлекает финальный счёт.

    Основной источник:

        .live_game_goals
        .live_game_goal span
    """

    goals = soup.select(
        ".live_game_goals .live_game_goal span"
    )

    if len(goals) < 2:

        logger.warning(
            "Soccer365: не найден финальный счёт "
            "в .live_game_goals"
        )

        return None

    home = safe_int(
        goals[0].get_text(
            " ",
            strip=True,
        )
    )

    away = safe_int(
        goals[1].get_text(
            " ",
            strip=True,
        )
    )

    if home is None or away is None:

        logger.warning(
            "Soccer365: не удалось преобразовать "
            "счёт в числа"
        )

        return None

    if home < 0 or away < 0:

        return None

    if home > 20 or away > 20:

        logger.warning(
            "Soccer365: подозрительный счёт "
            "%s:%s",
            home,
            away,
        )

        return None

    return f"{home}:{away}"


# ============================================================
# MATCH DATE
# ============================================================

def extract_match_date(
    soup: BeautifulSoup,
) -> Optional[str]:
    """
    Извлекает дату матча.
    """

    # --------------------------------------------------------
    # STRATEGY 1
    # --------------------------------------------------------

    meta_date = soup.find(
        "meta",
        attrs={
            "property": "article:published_time"
        },
    )

    if meta_date:

        content = meta_date.get(
            "content"
        )

        if content:

            try:

                dt = datetime.fromisoformat(
                    content.replace(
                        "Z",
                        "+00:00",
                    )
                )

                return dt.date().isoformat()

            except (
                ValueError,
                TypeError,
            ):

                if len(content) >= 10:

                    date_str = content[:10]

                    if re.match(
                        r"\d{4}-\d{2}-\d{2}",
                        date_str,
                    ):

                        return date_str

    # --------------------------------------------------------
    # MONTHS
    # --------------------------------------------------------

    months = {

        "января": "01",
        "февраля": "02",
        "марта": "03",
        "апреля": "04",
        "мая": "05",
        "июня": "06",
        "июля": "07",
        "августа": "08",
        "сентября": "09",
        "октября": "10",
        "ноября": "11",
        "декабря": "12",
    }

    # --------------------------------------------------------
    # STRATEGY 2
    # --------------------------------------------------------

    date_elem = soup.select_one(
        ".live_game_date"
    )

    if not date_elem:

        date_elem = soup.select_one(
            ".live_game_datetime"
        )

    if date_elem:

        text = normalize_text(
            date_elem.get_text(
                " ",
                strip=True,
            )
        )

        if text:

            match = re.search(
                r"(\d{2})\.(\d{2})\.(\d{4})",
                text,
            )

            if match:

                day, month, year = (
                    match.groups()
                )

                return (
                    f"{year}-{month}-{day}"
                )

            for (
                month_name,
                month_num,
            ) in months.items():

                if month_name in text.lower():

                    match = re.search(
                        rf"(\d{{1,2}})\s+"
                        rf"{month_name}\s+"
                        rf"(\d{{4}})",
                        text,
                        re.IGNORECASE,
                    )

                    if match:

                        day, year = (
                            match.groups()
                        )

                        return (
                            f"{year}-"
                            f"{month_num}-"
                            f"{int(day):02d}"
                        )

    # --------------------------------------------------------
    # STRATEGY 3 — META DESCRIPTION
    # --------------------------------------------------------

    meta_desc = soup.find(
        "meta",
        attrs={
            "name": "description"
        },
    )

    if meta_desc:

        content = meta_desc.get(
            "content"
        )

        if content:

            text = normalize_text(
                content
            )

            for (
                month_name,
                month_num,
            ) in months.items():

                if month_name in text.lower():

                    match = re.search(
                        rf"(\d{{1,2}})\s+"
                        rf"{month_name}\s+"
                        rf"(\d{{4}})",
                        text,
                        re.IGNORECASE,
                    )

                    if match:

                        day, year = (
                            match.groups()
                        )

                        return (
                            f"{year}-"
                            f"{month_num}-"
                            f"{int(day):02d}"
                        )

            match = re.search(
                r"(\d{2})\.(\d{2})\.(\d{4})",
                text,
            )

            if match:

                day, month, year = (
                    match.groups()
                )

                return (
                    f"{year}-{month}-{day}"
                )

    logger.debug(
        "Soccer365: не удалось извлечь дату матча"
    )

    return None


# ============================================================
# SPECIAL SHOTS POSITIONAL PARSER
# ============================================================

def parse_shots_by_position(
    items: List[Any],
) -> Dict[str, Any]:
    """
    Специальный parser для последовательности:

        xG
        ↓
        Удары
        ↓
        Удары в створ
        ↓
        Заблокированные удары

    Используется как дополнительная защита.

    ВАЖНО:

        Эта функция НЕ ищет данные во всем HTML.

        Она работает только с items,
        которые уже находятся внутри #stat-tp0.
    """

    stats: Dict[str, Any] = {}

    xg_index: Optional[int] = None

    # --------------------------------------------------------
    # Ищем xG
    # --------------------------------------------------------

    for index, item in enumerate(items):

        title = item.find(
            "div",
            class_="stats_title",
        )

        if not title:
            continue

        label = normalize_label(
            title.get_text(
                " ",
                strip=True,
            )
        )

        if label in (
            "ожидаемые голы (xg)",
            "ожидаемые голы",
            "expected goals",
        ):

            xg_index = index

            break

    if xg_index is None:

        logger.warning(
            "Soccer365: xG item не найден "
            "для позиционного shots parser"
        )

        return stats

    # --------------------------------------------------------
    # Берём следующие три stats_item
    # --------------------------------------------------------

    target_positions = [
        (
            xg_index + 1,
            "home_shots",
            "away_shots",
        ),

        (
            xg_index + 2,
            "home_shots_on_target",
            "away_shots_on_target",
        ),

        (
            xg_index + 3,
            "home_blocked_shots",
            "away_blocked_shots",
        ),
    ]

    for (
        index,
        home_key,
        away_key,
    ) in target_positions:

        if index >= len(items):

            continue

        item = items[index]

        infs = item.find_all(
            "div",
            class_="stats_inf",
        )

        title = item.find(
            "div",
            class_="stats_title",
        )

        if len(infs) < 2 or not title:

            continue

        label = normalize_label(
            title.get_text(
                " ",
                strip=True,
            )
        )

        home_value = normalize_text(
            infs[0].get_text(
                " ",
                strip=True,
            )
        )

        away_value = normalize_text(
            infs[1].get_text(
                " ",
                strip=True,
            )
        )

        # ----------------------------------------------------
        # Проверяем, что позиционный item действительно
        # относится к ожидаемому полю.
        #
        # Это не жёсткая проверка:
        # она нужна для диагностики и защиты.
        # ----------------------------------------------------

        expected_labels = {

            "home_shots": {
                "удары",
                "shots",
            },

            "home_shots_on_target": {
                "удары в створ",
                "shots on target",
            },

            "home_blocked_shots": {
                "заблокированные удары",
                "blocked shots",
            },
        }

        expected = expected_labels.get(
            home_key,
            set(),
        )

        if expected and label not in expected:

            logger.warning(
                "Soccer365 positional parser: "
                "ожидалось поле %s, "
                "но получен label=%r",
                home_key,
                label,
            )

            # Не подставляем чужую статистику.
            continue

        stats[home_key] = safe_int(
            home_value
        )

        stats[away_key] = safe_int(
            away_value
        )

        logger.debug(
            "Soccer365 positional stats: "
            "%s/%s = %s/%s",
            home_key,
            away_key,
            stats[home_key],
            stats[away_key],
        )

    return stats


# ============================================================
# STATISTICS — FULL MATCH
# ============================================================

def parse_full_match_statistics(
    soup: BeautifulSoup,
) -> Dict[str, Any]:
    """
    Парсит ТОЛЬКО:

        #clubs_stats
            └── #stat-tp0

    Используется DOM.

    Важное изменение v1.2.4:

        Сначала используется точное совпадение
        label.

        Опасное частичное совпадение:

            "удары" in "штрафные удары"

        больше НЕ используется.

        Для shots / shots_on_target /
        blocked_shots дополнительно используется
        позиционная проверка после xG.
    """

    stats: Dict[str, Any] = {}

    # --------------------------------------------------------
    # 1. clubs_stats
    # --------------------------------------------------------

    stats_block = soup.find(
        "div",
        id="clubs_stats",
    )

    if not stats_block:

        logger.warning(
            "Soccer365: блок #clubs_stats не найден"
        )

        return stats

    # --------------------------------------------------------
    # 2. stat-tp0
    # --------------------------------------------------------

    full_match = stats_block.find(
        "div",
        id="stat-tp0",
    )

    if not full_match:

        logger.warning(
            "Soccer365: блок stat-tp0 "
            "(Весь матч) не найден"
        )

        return stats

    # --------------------------------------------------------
    # 3. stats_item
    # --------------------------------------------------------

    items = full_match.find_all(
        "div",
        class_="stats_item",
    )

    if not items:

        logger.warning(
            "Soccer365: .stats_item "
            "не найдены в stat-tp0"
        )

        return stats

    found_count = 0

    # ========================================================
    # PASS 1
    #
    # ТОЛЬКО ТОЧНОЕ СОПОСТАВЛЕНИЕ LABEL
    # ========================================================

    exact_label_map: Dict[str, str] = {}

    for key, aliases in STAT_LABELS.items():

        for alias in aliases:

            exact_label_map[
                normalize_label(alias)
            ] = key

    for item in items:

        infs = item.find_all(
            "div",
            class_="stats_inf",
        )

        title = item.find(
            "div",
            class_="stats_title",
        )

        if len(infs) < 2 or not title:

            continue

        home_value = normalize_text(
            infs[0].get_text(
                " ",
                strip=True,
            )
        )

        label = normalize_label(
            title.get_text(
                " ",
                strip=True,
            )
        )

        away_value = normalize_text(
            infs[1].get_text(
                " ",
                strip=True,
            )
        )

        key = exact_label_map.get(
            label
        )

        if key is None:

            logger.debug(
                "Soccer365: label не найден "
                "точным сопоставлением: %r",
                label,
            )

            continue

        away_key = key.replace(
            "home_",
            "away_",
            1,
        )

        stats[key] = convert_value(
            key,
            home_value,
        )

        stats[away_key] = convert_value(
            away_key,
            away_value,
        )

        found_count += 1

        logger.debug(
            "Soccer365 exact stat: "
            "%s=%s / %s=%s",
            key,
            stats[key],
            away_key,
            stats[away_key],
        )

    # ========================================================
    # PASS 2
    #
    # СПЕЦИАЛЬНЫЙ SHOTS PARSER
    #
    # Он нужен именно для структуры Soccer365:
    #
    # xG
    # shots
    # shots_on_target
    # blocked_shots
    #
    # Если exact parser уже получил правильные значения,
    # позиционный parser их НЕ перезаписывает.
    # ========================================================

    positional_stats = parse_shots_by_position(
        items
    )

    for key, value in positional_stats.items():

        if value is None:
            continue

        # ----------------------------------------------------
        # Не перезаписываем уже корректно найденные значения.
        # ----------------------------------------------------

        if stats.get(key) is None:

            stats[key] = value

            found_count += 1

            logger.info(
                "Soccer365: %s восстановлено "
                "позиционным parser",
                key,
            )

    # ========================================================
    # DIAGNOSTIC VALIDATION
    # ========================================================

    home_shots = stats.get(
        "home_shots"
    )

    away_shots = stats.get(
        "away_shots"
    )

    home_sot = stats.get(
        "home_shots_on_target"
    )

    away_sot = stats.get(
        "away_shots_on_target"
    )

    # --------------------------------------------------------
    # shots >= shots_on_target
    # --------------------------------------------------------

    if (
        home_shots is not None
        and home_sot is not None
        and home_sot > home_shots
    ):

        logger.warning(
            "Soccer365: некорректные данные: "
            "home_shots=%s < home_shots_on_target=%s",
            home_shots,
            home_sot,
        )

    if (
        away_shots is not None
        and away_sot is not None
        and away_sot > away_shots
    ):

        logger.warning(
            "Soccer365: некорректные данные: "
            "away_shots=%s < away_shots_on_target=%s",
            away_shots,
            away_sot,
        )

    # ========================================================
    # LOGGING
    # ========================================================

    if found_count == 0:

        logger.warning(
            "Soccer365: не найдено ни одного "
            "показателя в stat-tp0"
        )

    else:

        logger.info(
            "Soccer365: найдено %s показателей "
            "в stat-tp0",
            found_count,
        )

    # --------------------------------------------------------
    # Специальный итог для диагностики shots
    # --------------------------------------------------------

    logger.info(
        "Soccer365 shots result: "
        "shots=%s/%s | "
        "shots_on_target=%s/%s | "
        "blocked_shots=%s/%s",
        stats.get("home_shots"),
        stats.get("away_shots"),
        stats.get("home_shots_on_target"),
        stats.get("away_shots_on_target"),
        stats.get("home_blocked_shots"),
        stats.get("away_blocked_shots"),
    )

    return stats


# ============================================================
# QUALITY
# ============================================================

def calculate_quality(
    stats: Dict[str, Any],
) -> float:

    groups = [

        (
            "home_xg",
            "away_xg",
        ),

        (
            "home_shots",
            "away_shots",
        ),

        (
            "home_shots_on_target",
            "away_shots_on_target",
        ),

        (
            "home_possession",
            "away_possession",
        ),

        (
            "home_corners",
            "away_corners",
        ),

        (
            "home_total_passes",
            "away_total_passes",
        ),

        (
            "home_pass_accuracy",
            "away_pass_accuracy",
        ),

        (
            "home_tackles",
            "away_tackles",
        ),
    ]

    available = 0

    for (
        home_key,
        away_key,
    ) in groups:

        if (
            stats.get(home_key) is not None
            or stats.get(away_key) is not None
        ):

            available += 1

    if not groups:

        return 0.0

    return round(
        available / len(groups),
        3,
    )


# ============================================================
# PARSER
# ============================================================

class Soccer365Parser:

    """
    Production parser Soccer365 v1.2.4.

    Совместимость:

        parser.parse(url)

        parser.parse_xg(url)
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
    ):

        self.timeout = timeout

    # --------------------------------------------------------
    # PARSE
    # --------------------------------------------------------

    def parse(
        self,
        url: str,
    ) -> Dict[str, Any]:

        result = empty_result()

        result[
            "source_url"
        ] = (
            url.strip()
            if url
            else None
        )

        result[
            "parsed_at"
        ] = datetime.now().isoformat()

        try:

            # ------------------------------------------------
            # HTTP
            # ------------------------------------------------

            html, final_url = fetch_html(
                url,
                timeout=self.timeout,
            )

            result[
                "source_url"
            ] = final_url

            soup = make_soup(
                html
            )

            # ------------------------------------------------
            # TEAMS
            # ------------------------------------------------

            (
                home_team,
                away_team,
            ) = extract_teams(
                soup
            )

            home_team = canonicalize_parsed_team(
                home_team
            )

            away_team = canonicalize_parsed_team(
                away_team
            )

            result[
                "home_team"
            ] = home_team

            result[
                "away_team"
            ] = away_team

            # ------------------------------------------------
            # SCORE
            # ------------------------------------------------

            result[
                "score"
            ] = extract_score(
                soup
            )

            # ------------------------------------------------
            # MATCH DATE
            # ------------------------------------------------

            result[
                "match_date"
            ] = extract_match_date(
                soup
            )

            # ------------------------------------------------
            # STATISTICS
            # ------------------------------------------------

            stats = parse_full_match_statistics(
                soup
            )

            result[
                "stats"
            ] = stats

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            quality = calculate_quality(
                stats
            )

            result[
                "quality"
            ] = quality

            result[
                "data_quality"
            ] = quality

            return result

        except requests.RequestException as exc:

            logger.exception(
                "Soccer365 HTTP error"
            )

            result[
                "error"
            ] = (
                f"HTTP error: {exc}"
            )

            return result

        except Exception as exc:

            logger.exception(
                "Soccer365 parser error"
            )

            result[
                "error"
            ] = str(exc)

            return result

    # --------------------------------------------------------
    # IMPORT_FACTS COMPATIBILITY
    # --------------------------------------------------------

    def parse_xg(
        self,
        url: str,
    ) -> Dict[str, Any]:

        parsed = self.parse(
            url
        )

        return {

            "stats": parsed.get(
                "stats",
                {},
            ),

            "home_team": parsed.get(
                "home_team"
            ),

            "away_team": parsed.get(
                "away_team"
            ),

            "score": parsed.get(
                "score"
            ),

            "match_date": parsed.get(
                "match_date"
            ),

            "data_quality": parsed.get(
                "quality",
                0.0,
            ),

            "source": parsed.get(
                "source",
                SOURCE_NAME,
            ),

            "source_url": parsed.get(
                "source_url"
            ),

            "parser_version": parsed.get(
                "parser_version",
                PARSER_VERSION,
            ),

            "parsed_at": parsed.get(
                "parsed_at"
            ),

            "error": parsed.get(
                "error"
            ),
        }


# ============================================================
# FUNCTION API
# ============================================================

def parse_soccer365(
    url: str,
) -> Dict[str, Any]:

    parser = Soccer365Parser()

    return parser.parse(
        url
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    import sys
    import json

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "python "
            "app/parsers/"
            "soccer365_parser.py "
            "https://soccer365.ru/games/2478638/"
        )

        raise SystemExit(1)

    url = sys.argv[1]

    parser = Soccer365Parser()

    result = parser.parse(
        url
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

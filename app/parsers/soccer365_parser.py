#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCER365 PARSER v1.1
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
        Блок "Весь матч"
             ↓
        FACTS
             ↓
        import_facts.py

============================================================

ВАЖНО:

    Soccer365 показывает:

        Весь матч
        1-й тайм
        2-й тайм

    FAJ использует ТОЛЬКО:

        ВЕСЬ МАТЧ

============================================================
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

PARSER_VERSION = "1.1"
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
#
# Soccer365 structure:
#
#     HOME
#     LABEL
#     AWAY
#
# Example:
#
#     2.25
#     Ожидаемые голы (xG)
#     1.52
#
# ============================================================

STAT_LABELS = {

    "home_xg": [
        "ожидаемые голы (xg)",
        "ожидаемые голы",
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

def normalize_text(value: Any) -> str:

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


def normalize_label(value: Any) -> str:

    text = normalize_text(
        value
    ).lower()

    text = text.replace(
        "ё",
        "е",
    )

    return text.strip()


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

    # Soccer365 отдаёт UTF-8.
    # Не доверяем apparent_encoding,
    # если сервер уже сообщил charset.

    content_type = (
        response.headers
        .get(
            "Content-Type",
            ""
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
    # META DESCRIPTION
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
                        home,
                        away,
                    )

    # --------------------------------------------------------
    # TITLE
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
                    home,
                    away,
                )

    # --------------------------------------------------------
    # SCORE HEADER FALLBACK
    # --------------------------------------------------------

    score1 = soup.select_one(
        ".score1"
    )

    score2 = soup.select_one(
        ".score2"
    )

    if score1 and score2:

        parent = (
            score1.parent
        )

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
                    team_names[0],
                    team_names[-1],
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

    score1 = soup.select_one(
        ".score1"
    )

    score2 = soup.select_one(
        ".score2"
    )

    if not score1 or not score2:

        return None

    home = safe_int(
        score1.get_text(
            " ",
            strip=True,
        )
    )

    away = safe_int(
        score2.get_text(
            " ",
            strip=True,
        )
    )

    if (
        home is None
        or away is None
    ):

        return None

    if home < 0 or away < 0:

        return None

    if home > 20 or away > 20:

        return None

    return (
        f"{home}:{away}"
    )


# ============================================================
# FULL MATCH BLOCK
# ============================================================

def extract_full_match_block(
    soup: BeautifulSoup,
) -> str:
    """
    Извлекает только статистику:

        ВЕСЬ МАТЧ

    ВАЖНО:

    На Soccer365 порядок такой:

        Статистика матча
        Весь матч
        1-й тайм
        2-й тайм

        2.25
        Ожидаемые голы (xG)
        1.52

        18
        Удары
        14

        ...

    Поэтому нельзя обрезать текст
    на первом "1-й тайм".

    Вместо этого берём:

        первое появление первого
        статистического показателя

    до

        второго появления этого же
        показателя.

    На реальной странице Soccer365
    первый показатель — xG.
    """

    full_text = normalize_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    marker = re.search(
        r"Статистика матча",
        full_text,
        flags=re.IGNORECASE,
    )

    if not marker:

        return ""

    text = full_text[
        marker.end():
    ]

    # --------------------------------------------------------
    # Ищем первое xG.
    # --------------------------------------------------------

    xg_matches = list(
        re.finditer(
            r"Ожидаемые голы\s*\(\s*xg\s*\)",
            text,
            flags=re.IGNORECASE,
        )
    )

    if not xg_matches:

        # fallback для английской версии
        xg_matches = list(
            re.finditer(
                r"expected goals\s*\(\s*xg\s*\)",
                text,
                flags=re.IGNORECASE,
            )
        )

    if not xg_matches:

        return ""

    # --------------------------------------------------------
    # Первый xG = Весь матч.
    # Второй xG = начало следующего
    # блока.
    # --------------------------------------------------------

    start = 0

    end = len(text)

    if len(xg_matches) >= 2:

        end = xg_matches[1].start()

    block = text[
        start:end
    ]

    return normalize_text(
        block
    )


# ============================================================
# STATISTIC EXTRACTION
# ============================================================

def extract_pair_around_label(
    text: str,
    aliases: List[str],
) -> Optional[
    Tuple[
        str,
        str,
    ]
]:
    """
    Soccer365:

        HOME
        LABEL
        AWAY

    Например:

        2.25 Ожидаемые голы (xG) 1.52

    Поэтому ищем число СЛЕВА
    и число СПРАВА от label.
    """

    normalized = normalize_label(
        text
    )

    # --------------------------------------------------------
    # Более длинные alias проверяем первыми.
    # Это защищает:
    #
    # "удары в створ"
    #
    # от простого:
    #
    # "удары"
    # --------------------------------------------------------

    sorted_aliases = sorted(
        aliases,
        key=lambda x: len(x),
        reverse=True,
    )

    for alias in sorted_aliases:

        label = normalize_label(
            alias
        )

        pattern = (
            r"([0-9]+(?:[.,][0-9]+)?)"
            r"\s+"
            + re.escape(label)
            + r"\s+"
            r"([0-9]+(?:[.,][0-9]+)?)"
        )

        match = re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )

        if match:

            return (
                match.group(1),
                match.group(2),
            )

    return None


# ============================================================
# PARSE STATISTICS
# ============================================================

def parse_full_match_statistics(
    soup: BeautifulSoup,
) -> Dict[str, Any]:

    stats: Dict[str, Any] = {}

    block = extract_full_match_block(
        soup
    )

    if not block:

        logger.warning(
            "Soccer365: блок 'Весь матч' не найден."
        )

        return stats

    # --------------------------------------------------------
    # Каждый показатель ищем независимо.
    #
    # Отсутствие одного показателя
    # НЕ является ошибкой.
    # --------------------------------------------------------

    for home_key, aliases in STAT_LABELS.items():

        pair = extract_pair_around_label(
            block,
            aliases,
        )

        if pair is None:

            continue

        home_value, away_value = pair

        away_key = home_key.replace(
            "home_",
            "away_",
            1,
        )

        converted_home = convert_value(
            home_key,
            home_value,
        )

        converted_away = convert_value(
            away_key,
            away_value,
        )

        if converted_home is not None:

            stats[
                home_key
            ] = converted_home

        if converted_away is not None:

            stats[
                away_key
            ] = converted_away

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

    for home_key, away_key in groups:

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
    Production parser Soccer365.

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

            result[
                "home_team"
            ] = home_team

            result[
                "away_team"
            ] = away_team

            # ------------------------------------------------
            # SCORE
            #
            # Только диагностический факт.
            # import_facts решает сам,
            # как использовать счёт.
            # ------------------------------------------------

            result[
                "score"
            ] = extract_score(
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
            "https://soccer365.ru/games/2478604/"
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

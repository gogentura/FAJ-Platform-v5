#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCER365 PARSER v1.0
============================================================

НАЗНАЧЕНИЕ:

    Soccer365 является источником фактической
    статистики сыгранного матча и xG.

    Парсер НЕ отвечает за:
        - ввод фактического счёта в FAJ;
        - прогноз FAJ;
        - обучение;
        - запись в SQLite.

    Его задача:

        Soccer365 URL
             ↓
        HTML
             ↓
        Match Statistics
             ↓
        FACT NORMALIZER
             ↓
        import_facts.py

============================================================

ОСНОВНЫЕ ФАКТЫ:

    xG
    shots
    shots on target
    possession
    corners
    fouls
    offsides
    yellow cards
    red cards
    passes
    pass accuracy
    free kicks
    throw-ins
    crosses
    clearances
    big chances
    tackles

============================================================

ВАЖНО:

    Soccer365 может содержать:

        Весь матч
        1-й тайм
        2-й тайм

    FAJ использует только:

        ВЕСЬ МАТЧ

============================================================

ПРИНЦИПЫ:

    SQLite не используется.

    Parser ничего не записывает в БД.

    Parser ничего не удаляет.

    Parser ничего не изменяет в FAJ.

    None != 0.

    Отсутствующий показатель не является ошибкой.

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

PARSER_VERSION = "1.0"

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

STAT_LABELS = {

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    "home_xg": [
        "ожидаемые голы (xg)",
        "ожидаемые голы",
        "xg",
    ],

    # --------------------------------------------------------
    # SHOTS
    # --------------------------------------------------------

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

    "home_shots_off_target": [
        "удары мимо",
        "shots off target",
    ],

    "home_shots_woodwork": [
        "удары в каркас",
        "shots against woodwork",
        "shots hit woodwork",
    ],

    # --------------------------------------------------------
    # GOALKEEPER
    # --------------------------------------------------------

    "home_saves": [
        "сейвы",
        "saves",
    ],

    # --------------------------------------------------------
    # POSSESSION
    # --------------------------------------------------------

    "home_possession": [
        "владение %",
        "владение",
        "possession %",
        "possession",
    ],

    # --------------------------------------------------------
    # SET PIECES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DISCIPLINE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # PASSES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DEFENCE
    # --------------------------------------------------------

    "home_tackles": [
        "отборы",
        "tackles",
    ],

    "home_clearances": [
        "выносы",
        "clearances",
    ],

    # --------------------------------------------------------
    # CHANCES
    # --------------------------------------------------------

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
# RESULT FACTORY
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

        "parser_version": PARSER_VERSION,

        "parsed_at": None,

        "error": None,
    }


# ============================================================
# TEXT HELPERS
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

    text = text.replace("ё", "е")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def safe_int(
    value: Any,
) -> Optional[int]:

    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    text = normalize_text(value)

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

    text = normalize_text(value)

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
# SCORE
# ============================================================

def clean_score(
    value: Any,
) -> Optional[str]:

    if value is None:
        return None

    text = normalize_text(value)

    match = re.search(
        r"(?<!\d)"
        r"(\d{1,2})"
        r"\s*[:\-]"
        r"\s*"
        r"(\d{1,2})"
        r"(?!\d)",
        text,
    )

    if not match:
        return None

    home = safe_int(
        match.group(1)
    )

    away = safe_int(
        match.group(2)
    )

    if home is None or away is None:
        return None

    if home < 0 or away < 0:
        return None

    if home > 20 or away > 20:
        return None

    return f"{home}:{away}"


# ============================================================
# REQUEST
# ============================================================

def fetch_html(
    url: str,
) -> Tuple[str, str]:

    if not url:
        raise ValueError(
            "Soccer365 URL не указан."
        )

    url = url.strip()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "image/avif,"
            "image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": (
            "ru-RU,ru;q=0.9,"
            "en-US;q=0.7,en;q=0.5"
        ),
        "Cache-Control": "no-cache",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    response.encoding = (
        response.apparent_encoding
        or response.encoding
        or "utf-8"
    )

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
# MATCH TEAMS
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
                    return home, away

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
                return home, away

    return None, None


# ============================================================
# MATCH SCORE
# ============================================================

def extract_score(
    soup: BeautifulSoup,
) -> Optional[str]:

    # Soccer365 score elements.
    score1 = soup.select_one(
        ".score1"
    )

    score2 = soup.select_one(
        ".score2"
    )

    if score1 and score2:

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
            home is not None
            and away is not None
        ):

            return (
                f"{home}:{away}"
            )

    # --------------------------------------------------------
    # FALLBACK: visible text
    # --------------------------------------------------------

    text = normalize_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    # Не пытаемся угадывать любой X:Y
    # на странице, потому что там много
    # прогнозов пользователей.

    return None


# ============================================================
# STATISTICS SECTION
# ============================================================

def find_statistics_container(
    soup: BeautifulSoup,
) -> Optional[Any]:

    # --------------------------------------------------------
    # 1. Ищем заголовок
    # --------------------------------------------------------

    candidates = soup.find_all(
        string=re.compile(
            r"Статистика матча",
            re.IGNORECASE,
        )
    )

    for candidate in candidates:

        parent = getattr(
            candidate,
            "parent",
            None,
        )

        if parent is None:
            continue

        # ----------------------------------------------------
        # Поднимаемся вверх по DOM.
        #
        # Ищем контейнер, содержащий
        # несколько известных статистических
        # названий.
        # ----------------------------------------------------

        current = parent

        for _ in range(8):

            if current is None:
                break

            text = normalize_label(
                current.get_text(
                    " ",
                    strip=True,
                )
            )

            score = 0

            for label in (
                "ожидаемые голы",
                "удары",
                "владение",
                "угловые",
                "фолы",
                "передачи",
            ):

                if label in text:
                    score += 1

            if score >= 3:
                return current

            current = getattr(
                current,
                "parent",
                None,
            )

    return None


# ============================================================
# STAT ROW PARSER
# ============================================================

def parse_stat_rows(
    container: Any,
) -> List[
    Tuple[
        str,
        str,
        str,
    ]
]:

    rows = []

    if container is None:
        return rows

    # --------------------------------------------------------
    # STRATEGY 1
    #
    # Табличная структура.
    # --------------------------------------------------------

    for row in container.select(
        "tr"
    ):

        cells = row.find_all(
            [
                "td",
                "th",
            ]
        )

        values = [
            normalize_text(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )
            for cell in cells
        ]

        values = [
            value
            for value in values
            if value
        ]

        if len(values) >= 3:

            rows.append(
                (
                    values[0],
                    values[1],
                    values[2],
                )
            )

    if rows:
        return rows

    # --------------------------------------------------------
    # STRATEGY 2
    #
    # div-based structure.
    # --------------------------------------------------------

    known_labels = set()

    for aliases in STAT_LABELS.values():

        for alias in aliases:

            known_labels.add(
                normalize_label(
                    alias
                )
            )

    elements = container.find_all(
        [
            "div",
            "span",
            "li",
            "p",
        ]
    )

    for index, element in enumerate(
        elements
    ):

        label = normalize_label(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not label:
            continue

        if label not in known_labels:
            continue

        # ----------------------------------------------------
        # Соседние элементы
        # ----------------------------------------------------

        nearby = []

        parent = element.parent

        if parent:

            children = parent.find_all(
                recursive=False
            )

            for child in children:

                text = normalize_text(
                    child.get_text(
                        " ",
                        strip=True,
                    )
                )

                if text:
                    nearby.append(
                        text
                    )

        # ----------------------------------------------------
        # Если в parent нашли:
        #
        # label / home / away
        # ----------------------------------------------------

        if len(nearby) >= 3:

            try:

                position = nearby.index(
                    normalize_text(
                        element.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

            except ValueError:

                position = 0

            if (
                position + 2
                < len(nearby)
            ):

                rows.append(
                    (
                        nearby[position],
                        nearby[position + 1],
                        nearby[position + 2],
                    )
                )

    return rows


# ============================================================
# TEXT STATISTICS FALLBACK
# ============================================================

def extract_stat_from_text(
    text: str,
    aliases: List[str],
) -> Optional[
    Tuple[
        Any,
        Any,
    ]
]:

    normalized = normalize_text(
        text
    )

    # --------------------------------------------------------
    # Для каждого alias ищем его первое
    # вхождение после начала блока.
    # --------------------------------------------------------

    for alias in aliases:

        alias_text = normalize_text(
            alias
        )

        if not alias_text:
            continue

        pattern = (
            re.escape(
                alias_text
            )
            + r"\s+"
            r"([0-9]+(?:[.,][0-9]+)?)"
            r"\s+"
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
# VALUE TYPE
# ============================================================

def convert_stat_value(
    key: str,
    value: Any,
) -> Optional[Any]:

    if value is None:
        return None

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    if key.endswith(
        "_xg"
    ):

        return safe_float(
            value
        )

    # --------------------------------------------------------
    # Everything else
    # --------------------------------------------------------

    return safe_int(
        value
    )


# ============================================================
# APPLY ROWS
# ============================================================

def apply_stat_rows(
    stats: Dict[str, Any],
    rows: List[
        Tuple[
            str,
            str,
            str,
        ]
    ],
) -> None:

    alias_to_key = {}

    for key, aliases in STAT_LABELS.items():

        for alias in aliases:

            alias_to_key[
                normalize_label(
                    alias
                )
            ] = key

    for label, home, away in rows:

        normalized = normalize_label(
            label
        )

        key = alias_to_key.get(
            normalized
        )

        if key is None:
            continue

        away_key = key.replace(
            "home_",
            "away_",
            1,
        )

        stats[key] = convert_stat_value(
            key,
            home,
        )

        stats[away_key] = convert_stat_value(
            away_key,
            away,
        )


# ============================================================
# TEXT PARSER
# ============================================================

def parse_statistics_text(
    container: Any,
) -> Dict[str, Any]:

    stats = {}

    if container is None:
        return stats

    text = normalize_text(
        container.get_text(
            " ",
            strip=True,
        )
    )

    # --------------------------------------------------------
    # ВАЖНО:
    #
    # Soccer365 после полного матча может
    # содержать статистику 1-го и 2-го тайма.
    #
    # Поэтому сначала пытаемся ограничить
    # поиск первым блоком "Весь матч".
    # --------------------------------------------------------

    first_half_position = re.search(
        r"\b1[- ]й\s+тайм\b",
        text,
        flags=re.IGNORECASE,
    )

    if first_half_position:

        text = text[
            :first_half_position.start()
        ]

    # --------------------------------------------------------
    # Парсим каждый показатель.
    # --------------------------------------------------------

    for key, aliases in STAT_LABELS.items():

        values = extract_stat_from_text(
            text,
            aliases,
        )

        if values is None:
            continue

        home_value, away_value = values

        stats[key] = convert_stat_value(
            key,
            home_value,
        )

        away_key = key.replace(
            "home_",
            "away_",
            1,
        )

        stats[away_key] = convert_stat_value(
            away_key,
            away_value,
        )

    return stats


# ============================================================
# DIRECT FULL TEXT FALLBACK
# ============================================================

def parse_statistics_direct(
    soup: BeautifulSoup,
) -> Dict[str, Any]:

    stats = {}

    full_text = normalize_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    # --------------------------------------------------------
    # Находим начало статистики.
    # --------------------------------------------------------

    marker = re.search(
        r"Статистика матча",
        full_text,
        flags=re.IGNORECASE,
    )

    if not marker:
        return stats

    text = full_text[
        marker.end():
    ]

    # --------------------------------------------------------
    # Останавливаемся перед первым
    # таймом.
    # --------------------------------------------------------

    first_half = re.search(
        r"\b1[- ]й\s+тайм\b",
        text,
        flags=re.IGNORECASE,
    )

    if first_half:

        text = text[
            :first_half.start()
        ]

    # --------------------------------------------------------
    # Парсим показатели.
    # --------------------------------------------------------

    for key, aliases in STAT_LABELS.items():

        values = extract_stat_from_text(
            text,
            aliases,
        )

        if values is None:
            continue

        home_value, away_value = values

        stats[key] = convert_stat_value(
            key,
            home_value,
        )

        away_key = key.replace(
            "home_",
            "away_",
            1,
        )

        stats[away_key] = convert_stat_value(
            away_key,
            away_value,
        )

    return stats


# ============================================================
# QUALITY
# ============================================================

def calculate_quality(
    stats: Dict[str, Any],
) -> float:

    groups = {

        "xg": (
            "home_xg",
            "away_xg",
        ),

        "shots": (
            "home_shots",
            "away_shots",
        ),

        "shots_on_target": (
            "home_shots_on_target",
            "away_shots_on_target",
        ),

        "possession": (
            "home_possession",
            "away_possession",
        ),

        "corners": (
            "home_corners",
            "away_corners",
        ),

        "passes": (
            "home_total_passes",
            "away_total_passes",
        ),

        "pass_accuracy": (
            "home_pass_accuracy",
            "away_pass_accuracy",
        ),

        "tackles": (
            "home_tackles",
            "away_tackles",
        ),
    }

    available = 0

    for keys in groups.values():

        if any(
            stats.get(key) is not None
            for key in keys
        ):
            available += 1

    if not groups:
        return 0.0

    return round(
        available / len(groups),
        3,
    )


# ============================================================
# MAIN PARSER
# ============================================================

class Soccer365Parser:

    """
    Основной parser Soccer365.

    Совместим с текущим import_facts.py:

        parser = Soccer365Parser()

        result = parser.parse_xg(url)

    Но также предоставляет:

        parser.parse(url)

    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
    ):

        self.timeout = timeout

    # --------------------------------------------------------
    # GENERIC PARSE
    # --------------------------------------------------------

    def parse(
        self,
        url: str,
    ) -> Dict[str, Any]:

        result = empty_result()

        result["source_url"] = (
            url.strip()
            if url
            else None
        )

        result["parsed_at"] = (
            datetime.now().isoformat()
        )

        try:

            html, final_url = fetch_html(
                url
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
            # Только для диагностики.
            #
            # import_facts НЕ использует
            # Soccer365 как источник фактического
            # счёта.
            # ------------------------------------------------

            result[
                "score"
            ] = extract_score(
                soup
            )

            # ------------------------------------------------
            # STATISTICS CONTAINER
            # ------------------------------------------------

            container = (
                find_statistics_container(
                    soup
                )
            )

            stats = {}

            # ------------------------------------------------
            # TABLE / DOM PARSER
            # ------------------------------------------------

            if container is not None:

                rows = parse_stat_rows(
                    container
                )

                if rows:

                    apply_stat_rows(
                        stats,
                        rows,
                    )

                # ------------------------------------------------
                # TEXT FALLBACK WITHIN CONTAINER
                # ------------------------------------------------

                text_stats = (
                    parse_statistics_text(
                        container
                    )
                )

                for key, value in text_stats.items():

                    if (
                        stats.get(key)
                        is None
                    ):

                        stats[key] = value

            # ------------------------------------------------
            # GLOBAL TEXT FALLBACK
            # ------------------------------------------------

            if not stats:

                stats = parse_statistics_direct(
                    soup
                )

            else:

                # Дополняем отсутствующие поля
                # глобальным fallback.
                direct_stats = (
                    parse_statistics_direct(
                        soup
                    )
                )

                for key, value in direct_stats.items():

                    if (
                        stats.get(key)
                        is None
                    ):

                        stats[key] = value

            # ------------------------------------------------
            # CLEAN NONE VALUES
            # ------------------------------------------------

            stats = {
                key: value
                for key, value in stats.items()
                if value is not None
            }

            result[
                "stats"
            ] = stats

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            result[
                "quality"
            ] = calculate_quality(
                stats
            )

            return result

        except requests.RequestException as exc:

            logger.exception(
                "Soccer365 HTTP error: %s",
                exc,
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
    # CURRENT IMPORT_Facts COMPATIBILITY
    # --------------------------------------------------------

    def parse_xg(
        self,
        url: str,
    ) -> Dict[str, Any]:

        """
        Совместимость с текущим import_facts.py.

        Несмотря на старое имя parse_xg(),
        теперь Soccer365 возвращает НЕ только xG,
        а всю доступную статистику.

        Формат специально сохранён:

            {
                "stats": {...},
                "home_team": ...,
                "away_team": ...,
                "score": ...,
                "data_quality": ...,
                ...
            }
        """

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

    """
    Удобная функция для прямого использования.
    """

    parser = Soccer365Parser()

    return parser.parse(
        url
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    import sys

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
            "Использование:"
        )

        print(
            "python "
            "app/parsers/"
            "soccer365_parser.py "
            "https://soccer365.ru/games/..."
        )

        raise SystemExit(1)

    url = sys.argv[1]

    parser = Soccer365Parser()

    result = parser.parse(
        url
    )

    print()
    print(
        "=================================================="
    )
    print(
        "SOCCER365 PARSER"
    )
    print(
        "=================================================="
    )

    print(
        f"Source URL: "
        f"{result.get('source_url')}"
    )

    print(
        f"Home: "
        f"{result.get('home_team')}"
    )

    print(
        f"Away: "
        f"{result.get('away_team')}"
    )

    print(
        f"Score: "
        f"{result.get('score')}"
    )

    print(
        f"Quality: "
        f"{result.get('quality')}"
    )

    print(
        f"Error: "
        f"{result.get('error')}"
    )

    print()
    print(
        "STATISTICS:"
    )

    for key, value in (
        result.get(
            "stats",
            {},
        )
        .items()
    ):

        print(
            f"  {key}: {value}"
        )

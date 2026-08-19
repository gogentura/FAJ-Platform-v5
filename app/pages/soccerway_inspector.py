#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY INSPECTOR v1.1
============================================================

Назначение:

    Универсальный HTML Inspector.

    Изначально создан для исследования Soccerway.
    Сейчас используется также для исследования NB-BET.

    Inspector:

        1. Загружает HTML
        2. Определяет HTTP-статус
        3. Ищет команды
        4. Ищет score
        5. Ищет статистические labels
        6. Ищет таблицы и строки статистики
        7. Ищет реальные CSS-классы
        8. Ищет data-* атрибуты
        9. Ищет JSON
        10. Ищет JavaScript
        11. Ищет fetch / API / XMLHttpRequest / axios
        12. Ищет window.* / environment
        13. Ищет iframe
        14. Ищет HTML-фрагменты вокруг команд
        15. Формирует ОДИН копируемый отчёт

ВАЖНО:

    Inspector ничего не записывает в БД.
    Ничего не изменяет.
    Не выполняет INSERT / UPDATE / DELETE / DROP.
============================================================
"""

from __future__ import annotations

import html
import re
from collections import Counter
from typing import List, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

VERSION = "1.1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)

# ============================================================
# NB-BET TEST URL
# ============================================================

DEFAULT_URL = (
    "https://nb-bet.com/Events/"
    "1670580-dinamo-moskva-krylya-sovetov-prognoz-na-match"
)


# ============================================================
# KNOWN TEAMS / MATCH TERMS
# ============================================================

TEAM_TERMS = [
    "динамо",
    "dinamo",
    "dynamo",
    "москва",
    "moskva",
    "moscow",
    "крылья",
    "krylya",
    "советов",
    "sovetov",
    "samara",
    "самара",
]


# ============================================================
# STATISTICS TERMS
# ============================================================

STAT_TERMS = [
    "ожидаемые голы",
    "expected goals",
    "xg",
    "xgot",

    "владение",
    "possession",

    "удары",
    "shots",
    "shots on target",
    "удары в створ",

    "голевые моменты",
    "big chances",

    "угловые",
    "corners",

    "передачи",
    "passes",

    "точность передач",
    "pass accuracy",

    "фолы",
    "fouls",

    "отборы",
    "tackles",

    "дуэли",
    "duels",

    "выносы",
    "clearances",

    "перехваты",
    "interceptions",

    "сэйвы",
    "saves",

    "удары от ворот",
    "goal kicks",

    "офсайды",
    "offsides",

    "желтые карточки",
    "yellow cards",

    "красные карточки",
    "red cards",

    "атаки",
    "attacks",

    "опасные атаки",
    "dangerous attacks",

    "вбрасывания",
    "throw ins",

    "штрафные",
    "free kicks",

    "пенальти",
    "penalties",
]


# ============================================================
# HTTP
# ============================================================

def load_page(url: str) -> Tuple[int, str]:

    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": (
                "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
            ),
            "Referer": "https://nb-bet.com/",
            "Connection": "keep-alive",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.status_code, response.text


# ============================================================
# HELPERS
# ============================================================

def clean_text(value: str) -> str:

    value = value.replace("\xa0", " ")

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def short_text(
    value: str,
    limit: int = 500,
) -> str:

    value = clean_text(value)

    if len(value) > limit:
        return value[:limit] + "..."

    return value


def css_path(element) -> str:

    parts = []

    current = element
    depth = 0

    while (
        current is not None
        and current.name != "[document]"
    ):

        if depth >= 8:
            break

        name = current.name

        element_id = current.get("id")

        classes = current.get("class") or []

        if element_id:

            part = f"{name}#{element_id}"

        elif classes:

            class_str = "".join(
                f".{re.sub(r'[^a-zA-Z0-9_-]', '', str(c))}"
                for c in classes[:3]
            )

            part = name + class_str

        else:

            part = name

        parts.append(part)

        current = current.parent
        depth += 1

    return " > ".join(
        reversed(parts)
    )


# ============================================================
# TEAM SEARCH
# ============================================================

def find_teams(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all(
        ["title", "h1", "h2", "h3", "h4",
         "div", "span", "a", "p", "td"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        normalized = text.lower()

        matched = [
            term
            for term in TEAM_TERMS
            if term in normalized
        ]

        if not matched:
            continue

        results.append(
            "\n".join(
                [
                    "TEXT: " + short_text(text, 500),
                    "MATCHED TERMS: " + ", ".join(matched),
                    "TAG: " + str(element.name),
                    "CLASS: " + str(element.get("class")),
                    "ID: " + str(element.get("id")),
                    "PATH: " + css_path(element),
                    "-" * 70,
                ]
            )
        )

    return list(
        dict.fromkeys(results)
    )[:500]


# ============================================================
# SCORE
# ============================================================

def find_scores(
    soup: BeautifulSoup,
) -> List[str]:

    patterns = [
        re.compile(
            r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)"
        ),
        re.compile(
            r"(?<!\d)(\d{1,2})\s*[–—]\s*(\d{1,2})(?!\d)"
        ),
    ]

    results = []

    # TITLE
    if soup.title:

        text = soup.title.get_text(
            " ",
            strip=True,
        )

        for pattern in patterns:

            for match in pattern.finditer(text):

                results.append(
                    "TITLE | "
                    + match.group(0)
                    + " | "
                    + text
                )

    # BODY ELEMENTS
    for element in soup.find_all():

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        classes = " ".join(
            element.get("class") or []
        ).lower()

        identifier = (
            str(element.get("id") or "")
            .lower()
        )

        relevant = (
            "score" in classes
            or "result" in classes
            or "score" in identifier
            or "result" in identifier
        )

        if not relevant:
            continue

        for pattern in patterns:

            for match in pattern.finditer(text):

                results.append(
                    "ELEMENT | "
                    + match.group(0)
                    + " | TAG="
                    + str(element.name)
                    + " | CLASS="
                    + classes
                    + " | TEXT="
                    + short_text(text, 300)
                )

    # META
    for meta in soup.find_all("meta"):

        content = meta.get("content") or ""

        for pattern in patterns:

            match = pattern.search(content)

            if match:

                results.append(
                    "META | "
                    + match.group(0)
                    + " | "
                    + short_text(content, 500)
                )

    return list(
        dict.fromkeys(results)
    )


# ============================================================
# STAT LABELS
# ============================================================

def find_statistics(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all(
        ["div", "span", "td", "li", "p", "th"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        normalized = text.lower()

        matched_term = None

        for term in STAT_TERMS:

            if normalized == term:

                matched_term = term
                break

        if matched_term is None:
            continue

        parent = element.parent

        parent_text = ""

        if parent:

            parent_text = clean_text(
                parent.get_text(
                    " ",
                    strip=True,
                )
            )

        classes = " ".join(
            element.get("class") or []
        )

        results.append(
            "\n".join(
                [
                    "LABEL: " + text,
                    "MATCH: " + matched_term,
                    "CLASSES: " + (classes or "-"),
                    "PATH: " + css_path(element),
                    "PARENT: " + short_text(parent_text, 700),
                    "-" * 70,
                ]
            )
        )

    return list(
        dict.fromkeys(results)
    )


# ============================================================
# NUMERIC STATISTIC CANDIDATES
# ============================================================

def find_numeric_blocks(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    number_pattern = re.compile(
        r"(?<![\w])"
        r"(\d+(?:[.,]\d+)?%?)"
        r"(?:\s+|\s*[/|]\s*|\s*[-–—]\s*)"
        r"(\d+(?:[.,]\d+)?%?)"
        r"(?![\w])"
    )

    for element in soup.find_all(
        ["div", "span", "td", "li", "tr", "p"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 500:
            continue

        matches = list(
            number_pattern.finditer(text)
        )

        if not matches:
            continue

        normalized = text.lower()

        nearby_stat = any(
            term in normalized
            for term in STAT_TERMS
        )

        if not nearby_stat:
            continue

        for match in matches:

            results.append(
                "\n".join(
                    [
                        "NUMERIC BLOCK: " + match.group(0),
                        "TEXT: " + text,
                        "TAG: " + str(element.name),
                        "CLASS: " + str(element.get("class")),
                        "ID: " + str(element.get("id")),
                        "PATH: " + css_path(element),
                        "-" * 70,
                    ]
                )
            )

    return list(
        dict.fromkeys(results)
    )[:500]


# ============================================================
# TABLES
# ============================================================

def inspect_tables(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for index, table in enumerate(
        soup.find_all("table")
    ):

        text = clean_text(
            table.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        results.append(
            "\n".join(
                [
                    "TABLE #" + str(index),
                    "CLASS: " + str(table.get("class")),
                    "ID: " + str(table.get("id")),
                    "PATH: " + css_path(table),
                    "TEXT: " + short_text(text, 2000),
                    "HTML:",
                    str(table)[:10000],
                    "=" * 100,
                ]
            )
        )

    return results[:100]


# ============================================================
# CLASS FREQUENCY
# ============================================================

def find_relevant_classes(
    soup: BeautifulSoup,
) -> List[str]:

    counter = Counter()

    for element in soup.find_all(
        class_=True
    ):

        classes = element.get("class") or []

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        normalized = text.lower()

        relevant = (
            any(
                term in normalized
                for term in STAT_TERMS
            )
            or any(
                term in normalized
                for term in TEAM_TERMS
            )
            or "score" in normalized
            or "result" in normalized
        )

        if not relevant:
            continue

        for cls in classes:

            counter[str(cls)] += 1

    return [
        str(cls) + "  |  " + str(count)
        for cls, count in counter.most_common(300)
    ]


# ============================================================
# DATA ATTRIBUTES
# ============================================================

def find_data_attributes(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all():

        attrs = element.attrs

        for key, value in attrs.items():

            if not key.startswith("data-"):
                continue

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            results.append(
                key
                + "="
                + str(value)
                + " | tag="
                + str(element.name)
                + " | class="
                + str(element.get("class"))
                + " | text="
                + short_text(text, 250)
            )

    return list(
        dict.fromkeys(results)
    )[:1500]


# ============================================================
# API / JAVASCRIPT
# ============================================================

def inspect_scripts(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    markers = [
        "window.environment",
        "window.",
        "fetch(",
        "fetch (",
        "axios",
        "xmlhttprequest",
        "ajax",
        "/api/",
        "api/",
        "graphql",
        "event_id",
        "eventid",
        "match_id",
        "matchid",
        "statistics",
        "stats",
        "score",
        "participants",
        "teams",
        "events",
        "nb-bet",
        "football",
    ]

    for index, script in enumerate(
        soup.find_all("script")
    ):

        text = script.string or script.get_text()

        if not text:
            continue

        lowered = text.lower()

        interesting = any(
            marker in lowered
            for marker in markers
        )

        if not interesting:
            continue

        results.append(
            "\n".join(
                [
                    "SCRIPT #" + str(index),
                    "TYPE: " + str(script.get("type")),
                    "SRC: " + str(script.get("src")),
                    "CONTENT:",
                    text[:20000],
                    "=" * 100,
                ]
            )
        )

    return results[:200]


# ============================================================
# JSON BLOCKS
# ============================================================

def inspect_json(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for script in soup.find_all(
        "script"
    ):

        script_type = (
            script.get("type") or ""
        ).lower()

        text = script.string or script.get_text()

        if not text:
            continue

        if (
            "json" in script_type
            or "application/ld+json" in script_type
            or "__next_data__" in text.lower()
        ):

            results.append(
                text[:30000]
            )

    return results[:100]


# ============================================================
# API / URL CANDIDATES
# ============================================================

def inspect_urls(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    url_pattern = re.compile(
        r"""https?://[^\s"'<>]+"""
        r"""|["'](/[^"'<>]{1,300})["']"""
    )

    # SCRIPT CONTENT
    for script in soup.find_all("script"):

        text = script.string or script.get_text()

        if not text:
            continue

        for match in url_pattern.finditer(text):

            value = (
                match.group(0)
                .strip("\"'")
            )

            lowered = value.lower()

            if any(
                marker in lowered
                for marker in [
                    "api",
                    "event",
                    "match",
                    "stat",
                    "score",
                    "football",
                    "bet",
                ]
            ):

                results.append(value)

    # LINKS
    for link in soup.find_all("a", href=True):

        href = str(
            link.get("href")
        )

        lowered = href.lower()

        if any(
            marker in lowered
            for marker in [
                "api",
                "event",
                "match",
                "stat",
            ]
        ):

            results.append(href)

    return list(
        dict.fromkeys(results)
    )[:500]


# ============================================================
# IFRAMES
# ============================================================

def inspect_iframes(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for index, iframe in enumerate(
        soup.find_all("iframe")
    ):

        results.append(
            "\n".join(
                [
                    "IFRAME #" + str(index),
                    "SRC: " + str(iframe.get("src")),
                    "TITLE: " + str(iframe.get("title")),
                    "CLASS: " + str(iframe.get("class")),
                    "ID: " + str(iframe.get("id")),
                    "-" * 70,
                ]
            )
        )

    return results


# ============================================================
# MATCH CONTAINERS
# ============================================================

def inspect_match_containers(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    markers = [
        "match",
        "event",
        "summary",
        "statistics",
        "stats",
        "score",
        "team",
        "participant",
        "game",
        "fixture",
    ]

    for element in soup.find_all(
        ["div", "section", "article", "main"]
    ):

        classes = " ".join(
            element.get("class") or []
        )

        element_id = str(
            element.get("id") or ""
        )

        lowered = (
            classes + " " + element_id
        ).lower()

        if not any(
            marker in lowered
            for marker in markers
        ):
            continue

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if len(text) < 5:
            continue

        if len(text) > 2000:
            text = text[:2000] + "..."

        results.append(
            "\n".join(
                [
                    "TAG: " + str(element.name),
                    "CLASS: " + classes,
                    "ID: " + element_id,
                    "PATH: " + css_path(element),
                    "TEXT: " + text,
                    "-" * 70,
                ]
            )
        )

    return results[:500]


# ============================================================
# HTML STAT FRAGMENTS
# ============================================================

def inspect_stat_fragments(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all(
        ["div", "tr", "li", "section"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        normalized = text.lower()

        if not any(
            term in normalized
            for term in STAT_TERMS
        ):
            continue

        if len(text) > 1500:
            continue

        results.append(
            "\n".join(
                [
                    "TAG: " + str(element.name),
                    "CLASS: " + str(element.get("class")),
                    "ID: " + str(element.get("id")),
                    "PATH: " + css_path(element),
                    "HTML:",
                    str(element)[:7000],
                    "=" * 100,
                ]
            )
        )

    return list(
        dict.fromkeys(results)
    )[:400]


# ============================================================
# TEAM HTML FRAGMENTS
# ============================================================

def inspect_team_fragments(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all(
        ["div", "section", "article", "a", "span", "h1", "h2", "h3"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        normalized = text.lower()

        if not any(
            term in normalized
            for term in TEAM_TERMS
        ):
            continue

        if len(text) > 1000:
            continue

        results.append(
            "\n".join(
                [
                    "TAG: " + str(element.name),
                    "CLASS: " + str(element.get("class")),
                    "ID: " + str(element.get("id")),
                    "PATH: " + css_path(element),
                    "TEXT: " + text,
                    "HTML:",
                    str(element)[:5000],
                    "=" * 100,
                ]
            )
        )

    return list(
        dict.fromkeys(results)
    )[:300]


# ============================================================
# RAW HTML SEARCH
# ============================================================

def inspect_raw_html(
    html_text: str,
) -> List[str]:

    results = []

    markers = [
        "динамо",
        "dinamo",
        "dynamo",
        "крылья",
        "krylya",
        "sovetov",
        "1670580",
        "stats",
        "statistics",
        "score",
        "event",
        "match",
        "api",
        "fetch",
    ]

    lowered = html_text.lower()

    for marker in markers:

        positions = []

        start = 0

        while True:

            position = lowered.find(
                marker,
                start,
            )

            if position == -1:
                break

            positions.append(position)

            start = position + len(marker)

            if len(positions) >= 20:
                break

        for position in positions:

            begin = max(
                0,
                position - 700,
            )

            end = min(
                len(html_text),
                position + 1500,
            )

            fragment = html_text[
                begin:end
            ]

            results.append(
                "\n".join(
                    [
                        "MARKER: " + marker,
                        "POSITION: " + str(position),
                        "RAW HTML:",
                        fragment,
                        "=" * 100,
                    ]
                )
            )

    return list(
        dict.fromkeys(results)
    )[:300]


# ============================================================
# REPORT
# ============================================================

def build_report(
    url: str,
    status: int,
    html_text: str,
) -> str:

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    lines = []

    lines.append(
        "============================================================"
    )
    lines.append(
        "FAJ SOCCERWAY INSPECTOR REPORT"
    )
    lines.append(
        "VERSION: " + VERSION
    )
    lines.append(
        "SOURCE: NB-BET TEST"
    )
    lines.append(
        "============================================================"
    )
    lines.append("")

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    lines.append(
        "1. URL"
    )

    lines.append(url)

    lines.append("")

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    lines.append(
        "2. HTTP"
    )

    lines.append(
        "STATUS: " + str(status)
    )

    lines.append(
        "HTML BYTES: "
        + str(
            len(
                html_text.encode("utf-8")
            )
        )
    )

    lines.append("")

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    lines.append(
        "3. TITLE"
    )

    title = (
        soup.title.get_text(
            " ",
            strip=True,
        )
        if soup.title
        else ""
    )

    lines.append(title)

    lines.append("")

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    lines.append(
        "4. TEAM CANDIDATES"
    )

    teams = find_teams(soup)

    if teams:
        lines.extend(teams)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    lines.append(
        "5. SCORE CANDIDATES"
    )

    scores = find_scores(soup)

    if scores:
        lines.extend(scores)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    lines.append(
        "6. STATISTIC LABELS"
    )

    statistics = find_statistics(soup)

    if statistics:
        lines.extend(statistics)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # NUMERIC STATS
    # --------------------------------------------------------

    lines.append(
        "7. NUMERIC STATISTIC BLOCKS"
    )

    numeric_blocks = find_numeric_blocks(soup)

    if numeric_blocks:
        lines.extend(numeric_blocks)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    lines.append(
        "8. HTML TABLES"
    )

    tables = inspect_tables(soup)

    if tables:
        lines.extend(tables)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # CLASSES
    # --------------------------------------------------------

    lines.append(
        "9. RELEVANT CSS CLASSES"
    )

    relevant_classes = find_relevant_classes(soup)

    if relevant_classes:
        lines.extend(relevant_classes)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # MATCH CONTAINERS
    # --------------------------------------------------------

    lines.append(
        "10. MATCH / EVENT / STATS CONTAINERS"
    )

    containers = inspect_match_containers(soup)

    if containers:
        lines.extend(containers)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # STAT HTML
    # --------------------------------------------------------

    lines.append(
        "11. REAL STAT HTML FRAGMENTS"
    )

    fragments = inspect_stat_fragments(soup)

    if fragments:
        lines.extend(fragments)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # TEAM HTML
    # --------------------------------------------------------

    lines.append(
        "12. TEAM HTML FRAGMENTS"
    )

    team_fragments = inspect_team_fragments(soup)

    if team_fragments:
        lines.extend(team_fragments)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # DATA ATTRIBUTES
    # --------------------------------------------------------

    lines.append(
        "13. DATA-* ATTRIBUTES"
    )

    data_attributes = find_data_attributes(soup)

    if data_attributes:
        lines.extend(data_attributes)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    lines.append(
        "14. JSON BLOCKS"
    )

    json_blocks = inspect_json(soup)

    if json_blocks:

        for block in json_blocks:

            lines.append(block)
            lines.append("=" * 100)

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # SCRIPTS
    # --------------------------------------------------------

    lines.append(
        "15. INTERESTING JAVASCRIPT"
    )

    scripts = inspect_scripts(soup)

    if scripts:
        lines.extend(scripts)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # URL / API CANDIDATES
    # --------------------------------------------------------

    lines.append(
        "16. API / URL CANDIDATES"
    )

    urls = inspect_urls(soup)

    if urls:
        lines.extend(urls)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # IFRAMES
    # --------------------------------------------------------

    lines.append(
        "17. IFRAMES"
    )

    iframes = inspect_iframes(soup)

    if iframes:
        lines.extend(iframes)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # RAW HTML MARKERS
    # --------------------------------------------------------

    lines.append(
        "18. RAW HTML MARKER FRAGMENTS"
    )

    raw_fragments = inspect_raw_html(
        html_text
    )

    if raw_fragments:
        lines.extend(raw_fragments)
    else:
        lines.append("NOT FOUND")

    lines.append("")

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    lines.append(
        "============================================================"
    )

    lines.append(
        "END OF REPORT"
    )

    lines.append(
        "============================================================"
    )

    return "\n".join(lines)


# ============================================================
# STREAMLIT PAGE
# ============================================================

def main():

    st.set_page_config(
        page_title="FAJ Soccerway Inspector",
        page_icon="🔎",
        layout="wide",
    )

    st.title(
        "🔎 FAJ — Soccerway Inspector"
    )

    st.caption(
        "Исследование HTML Soccerway / NB-BET "
        "для создания финального парсера статистики."
    )

    url = st.text_input(
        "URL матча",
        value=DEFAULT_URL,
    )

    if st.button(
        "🔎 ИССЛЕДОВАТЬ СТРАНИЦУ",
        type="primary",
        width="stretch",
    ):

        if not url.strip():

            st.error(
                "Введите URL."
            )

            st.stop()

        with st.spinner(
            "Загружаем и исследуем HTML..."
        ):

            try:

                status, html_text = load_page(
                    url.strip()
                )

                report = build_report(
                    url=url.strip(),
                    status=status,
                    html_text=html_text,
                )

                st.session_state[
                    "soccerway_report"
                ] = report

                st.success(
                    "HTTP "
                    + str(status)
                    + " | "
                    + str(
                        len(
                            html_text.encode("utf-8")
                        )
                    )
                    + " байт"
                )

            except Exception as exc:

                st.error(
                    "Ошибка: " + str(exc)
                )

    report = st.session_state.get(
        "soccerway_report"
    )

    if report:

        st.markdown(
            "## 📋 ГОТОВЫЙ ОТЧЁТ"
        )

        st.info(
            "Скопируйте весь отчёт целиком "
            "и пришлите его мне."
        )

        escaped = html.escape(
            report
        )

        component = """
        <textarea
            id="faj-report"
            style="
                width:100%;
                height:700px;
                font-family:monospace;
                font-size:12px;
                padding:12px;
                border:1px solid #888;
                border-radius:8px;
                background:#111;
                color:#eee;
            "
            readonly>""" + escaped + """</textarea>

        <button
            onclick="
                const area =
                    document.getElementById('faj-report');

                area.focus();
                area.select();

                navigator.clipboard.writeText(
                    area.value
                );

                this.innerText =
                    '✅ СКОПИРОВАНО';

                setTimeout(() => {
                    this.innerText =
                        '📋 СКОПИРОВАТЬ ВЕСЬ ОТЧЁТ';
                }, 2000);
            "
            style="
                margin-top:10px;
                padding:12px 20px;
                font-size:16px;
                font-weight:bold;
                border-radius:8px;
                cursor:pointer;
            "
        >
            📋 СКОПИРОВАТЬ ВЕСЬ ОТЧЁТ
        </button>
        """

        import streamlit.components.v1 as components

        components.html(
            component,
            height=760,
            scrolling=True,
        )

        st.download_button(
            "💾 Скачать отчёт TXT",
            data=report,
            file_name="soccerway_inspector_report.txt",
            mime="text/plain",
            width="stretch",
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

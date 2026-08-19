#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY INSPECTOR v1.0
NB-BET MODE
============================================================

ВАЖНО:

    Имя файла и название страницы сохраняются:
        Soccerway Inspector

    НО источник теперь:
        https://nb-bet.com/

Назначение:

    Исследование РЕАЛЬНОГО HTML NB-BET.

    Inspector:
        1. Загружает HTML
        2. Определяет команды
        3. Ищет счёт
        4. Ищет статистические показатели
        5. Ищет xG
        6. Ищет удары
        7. Ищет удары в створ
        8. Ищет угловые
        9. Ищет передачи
       10. Ищет владение
       11. Ищет все найденные строки статистики
       12. Ищет data-* атрибуты
       13. Ищет JSON / scripts
       14. Показывает HTML-фрагменты
       15. Формирует ОДИН копируемый отчёт

ВАЖНО:

    Inspector ничего не записывает в БД.
    Ничего не изменяет.
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

VERSION = "1.0-NB-BET"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)

DEFAULT_URL = (
    "https://nb-bet.com/Events/"
    "1670580-dinamo-moskva-krylya-sovetov-prognoz-na-match"
)


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


def short_text(value: str, limit: int = 500) -> str:

    value = clean_text(value)

    if len(value) > limit:
        return value[:limit] + "..."

    return value


def css_path(element) -> str:

    parts = []

    current = element

    depth = 0

    while current is not None and current.name != "[document]":

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
# TEAM / SCORE
# ============================================================

def find_match_header(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score_patterns = [
        r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)",
        r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?!\d)",
    ]

    scores = []

    for pattern in score_patterns:

        for match in re.finditer(
            pattern,
            page_text,
        ):

            score = match.group(0)

            if score not in scores:

                scores.append(score)

    results.append(
        "SCORE CANDIDATES:"
    )

    if scores:

        results.extend(
            scores[:30]
        )

    else:

        results.append(
            "NOT FOUND"
        )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = ""

    if soup.title:

        title = clean_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

    results.append(
        ""
    )

    results.append(
        "TITLE: " + title
    )

    # --------------------------------------------------------
    # URL-style team names
    # --------------------------------------------------------

    for element in soup.find_all(
        ["h1", "h2", "h3"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if (
            "динамо" in text.lower()
            or "крыл" in text.lower()
        ):

            results.append(
                "HEADER: " + text
            )

    return results


# ============================================================
# NB-BET STATISTICS
# ============================================================

STAT_TERMS = [
    "ожидаемые голы",
    "xg",
    "ожидаемые голы (xg)",
    "удары",
    "удары в створ",
    "угловые",
    "передачи",
    "точность передач",
    "точные передачи",
    "всего передач",
    "владение мячом",
    "владение мячом (%)",
    "офсайды",
    "фолы",
    "желтые карточки",
    "красные карточки",
    "сэйвы",
    "спасения",
]


def find_statistics(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    seen = set()

    # --------------------------------------------------------
    # Ищем элементы с текстом статистики
    # --------------------------------------------------------

    for element in soup.find_all():

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        normalized = text.lower()

        matched = None

        for term in STAT_TERMS:

            if term in normalized:

                matched = term
                break

        if matched is None:
            continue

        # Не берём гигантские контейнеры
        if len(text) > 1500:
            continue

        key = (
            element.name,
            text,
            str(element.get("class")),
        )

        if key in seen:
            continue

        seen.add(key)

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
                    "TERM: " + matched,
                    "TEXT: " + text,
                    "TAG: " + element.name,
                    "CLASSES: " + (classes or "-"),
                    "PATH: " + css_path(element),
                    "PARENT: " + short_text(
                        parent_text,
                        700,
                    ),
                    "-" * 70,
                ]
            )
        )

    return results[:500]


# ============================================================
# NUMERIC STAT BLOCKS
# ============================================================

def find_numeric_stat_blocks(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    # Ищем небольшие элементы, где одновременно
    # присутствуют числа и знакомые статистические слова.

    for element in soup.find_all(
        ["div", "span", "li", "td", "tr"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 1000:
            continue

        normalized = text.lower()

        relevant = any(
            term in normalized
            for term in STAT_TERMS
        )

        if not relevant:
            continue

        numbers = re.findall(
            r"(?<!\d)\d+(?:[.,]\d+)?%?",
            text,
        )

        if not numbers:
            continue

        results.append(
            "\n".join(
                [
                    "TAG: " + element.name,
                    "CLASS: " + str(
                        element.get("class")
                    ),
                    "ID: " + str(
                        element.get("id")
                    ),
                    "PATH: " + css_path(
                        element
                    ),
                    "TEXT: " + text,
                    "NUMBERS: " + ", ".join(
                        numbers
                    ),
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
# CSS CLASSES
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
            or "динамо" in normalized
            or "крыл" in normalized
            or "матч" in normalized
            or "статист" in normalized
            or "xg" in normalized
        )

        if not relevant:
            continue

        for cls in classes:

            counter[str(cls)] += 1

    return [
        str(cls) + "  |  " + str(count)
        for cls, count in counter.most_common(200)
    ]


# ============================================================
# DATA ATTRIBUTES
# ============================================================

def find_data_attributes(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all():

        for key, value in element.attrs.items():

            if not key.startswith("data-"):
                continue

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            results.append(
                key + "=" + str(value)
                + " | tag=" + element.name
                + " | class=" + str(
                    element.get("class")
                )
                + " | text=" + short_text(
                    text,
                    250,
                )
            )

    return list(
        dict.fromkeys(results)
    )[:1000]


# ============================================================
# SCRIPTS
# ============================================================

def inspect_scripts(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for index, script in enumerate(
        soup.find_all("script")
    ):

        text = script.string or script.get_text()

        if not text:
            continue

        lowered = text.lower()

        interesting = any(
            marker in lowered
            for marker in [
                "event",
                "match",
                "stat",
                "xg",
                "score",
                "dinamo",
                "krylya",
                "крыл",
                "динамо",
                "nb-bet",
            ]
        )

        if not interesting:
            continue

        results.append(
            "\n".join(
                [
                    "SCRIPT #" + str(index),
                    "TYPE: " + str(
                        script.get("type")
                    ),
                    "SRC: " + str(
                        script.get("src")
                    ),
                    "CONTENT:",
                    text[:15000],
                    "=" * 100,
                ]
            )
        )

    return results[:100]


# ============================================================
# JSON
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

        if "json" in script_type:

            results.append(
                text[:20000]
            )

    return results[:100]


# ============================================================
# MATCH / STAT CONTAINERS
# ============================================================

def inspect_match_containers(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    markers = [
        "match",
        "event",
        "stat",
        "statistics",
        "score",
        "team",
        "game",
        "xg",
    ]

    for element in soup.find_all(
        ["div", "section", "article", "table"]
    ):

        classes = " ".join(
            element.get("class") or []
        )

        element_id = str(
            element.get("id") or ""
        )

        marker_text = (
            classes + " " + element_id
        ).lower()

        if not any(
            marker in marker_text
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

        if len(text) > 1500:

            text = text[:1500] + "..."

        results.append(
            "\n".join(
                [
                    "TAG: " + element.name,
                    "CLASS: " + classes,
                    "ID: " + element_id,
                    "PATH: " + css_path(
                        element
                    ),
                    "TEXT: " + text,
                    "-" * 70,
                ]
            )
        )

    return list(
        dict.fromkeys(results)
    )[:500]


# ============================================================
# RAW STAT HTML
# ============================================================

def inspect_stat_fragments(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all(
        ["div", "tr", "li", "table"]
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

        if len(text) > 1200:
            continue

        results.append(
            "\n".join(
                [
                    "TAG: " + element.name,
                    "CLASS: " + str(
                        element.get("class")
                    ),
                    "ID: " + str(
                        element.get("id")
                    ),
                    "PATH: " + css_path(
                        element
                    ),
                    "HTML:",
                    str(element)[:8000],
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
        "SOURCE: NB-BET"
    )

    lines.append(
        "VERSION: " + VERSION
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
        "HTML BYTES: " + str(
            len(
                html_text.encode(
                    "utf-8"
                )
            )
        )
    )

    lines.append("")

    # --------------------------------------------------------
    # MATCH HEADER
    # --------------------------------------------------------

    lines.append(
        "3. MATCH HEADER"
    )

    lines.extend(
        find_match_header(
            soup
        )
    )

    lines.append("")

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    lines.append(
        "4. NB-BET STATISTICS"
    )

    statistics = find_statistics(
        soup
    )

    if statistics:

        lines.extend(
            statistics
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # NUMERIC BLOCKS
    # --------------------------------------------------------

    lines.append(
        "5. NUMERIC STATISTIC BLOCKS"
    )

    numeric_blocks = (
        find_numeric_stat_blocks(
            soup
        )
    )

    if numeric_blocks:

        lines.extend(
            numeric_blocks
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # CSS
    # --------------------------------------------------------

    lines.append(
        "6. RELEVANT CSS CLASSES"
    )

    relevant_classes = (
        find_relevant_classes(
            soup
        )
    )

    if relevant_classes:

        lines.extend(
            relevant_classes
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # CONTAINERS
    # --------------------------------------------------------

    lines.append(
        "7. MATCH / STAT CONTAINERS"
    )

    containers = (
        inspect_match_containers(
            soup
        )
    )

    if containers:

        lines.extend(
            containers
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # RAW STAT HTML
    # --------------------------------------------------------

    lines.append(
        "8. REAL STAT HTML FRAGMENTS"
    )

    fragments = (
        inspect_stat_fragments(
            soup
        )
    )

    if fragments:

        lines.extend(
            fragments
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    lines.append(
        "9. DATA-* ATTRIBUTES"
    )

    data_attributes = (
        find_data_attributes(
            soup
        )
    )

    if data_attributes:

        lines.extend(
            data_attributes
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    lines.append(
        "10. JSON BLOCKS"
    )

    json_blocks = inspect_json(
        soup
    )

    if json_blocks:

        for block in json_blocks:

            lines.append(
                block
            )

            lines.append(
                "=" * 100
            )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # SCRIPTS
    # --------------------------------------------------------

    lines.append(
        "11. INTERESTING SCRIPTS"
    )

    scripts = inspect_scripts(
        soup
    )

    if scripts:

        lines.extend(
            scripts
        )

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # RAW HTML SEARCH
    # --------------------------------------------------------

    lines.append(
        "12. RAW HTML KEYWORDS"
    )

    raw_lower = html_text.lower()

    keywords = [
        "xg",
        "ожидаемые голы",
        "удары",
        "удары в створ",
        "угловые",
        "передачи",
        "владение",
        "динамо",
        "крылья",
    ]

    for keyword in keywords:

        count = raw_lower.count(
            keyword.lower()
        )

        lines.append(
            f"{keyword}: {count}"
        )

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
# STREAMLIT
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
        "NB-BET HTML Inspector. "
        "Название Inspector сохранено для совместимости."
    )

    url = st.text_input(
        "URL матча NB-BET",
        value=DEFAULT_URL,
    )

    if st.button(
        "🔎 ИССЛЕДОВАТЬ NB-BET",
        type="primary",
        width="stretch",
    ):

        if not url.strip():

            st.error(
                "Введите URL."
            )

            st.stop()

        with st.spinner(
            "Загружаем и исследуем NB-BET..."
        ):

            try:

                status, html_text = (
                    load_page(
                        url.strip()
                    )
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
                            html_text.encode(
                                "utf-8"
                            )
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
            "Скопируйте весь отчёт и пришлите его сюда. "
            "По нему определим точную HTML-структуру NB-BET "
            "и затем сделаем рабочий NB-BET parser."
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
                const area = document.getElementById('faj-report');
                area.focus();
                area.select();
                navigator.clipboard.writeText(area.value);
                this.innerText='✅ СКОПИРОВАНО';
                setTimeout(() => {
                    this.innerText='📋 СКОПИРОВАТЬ ВЕСЬ ОТЧЁТ';
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


if __name__ == "__main__":
    main()

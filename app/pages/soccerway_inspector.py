#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY INSPECTOR v1.0
============================================================

Назначение:

    Исследование РЕАЛЬНОГО HTML Soccerway.

    Пользователь вставляет URL матча.
    Inspector:
        1. Загружает HTML
        2. Определяет реальные классы
        3. Ищет score
        4. Ищет команды
        5. Ищет строки статистики
        6. Ищет data-* атрибуты
        7. Ищет script/window.environment
        8. Ищет JSON-признаки
        9. Формирует ОДИН копируемый отчёт

ВАЖНО:

    Inspector ничего не записывает в БД.
    Ничего не изменяет.
============================================================
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from typing import List, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

VERSION = "1.0"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)

DEFAULT_URL = (
    "https://ru.soccerway.com/match/"
    "dynamo-moscow-AFWA2jAQ/"
    "krylya-sovetov-samara-SKAE94nJ/"
    "summary/stats/overall/"
    "?mid=C8Coobll"
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
            "Referer": "https://ru.soccerway.com/",
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


def classes_of(element) -> List[str]:

    if not element:
        return []

    return list(
        element.get("class") or []
    )


def css_path(element) -> str:

    """
    Строит приблизительный CSS path
    для найденного элемента.
    """

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
# SCORE
# ============================================================

def find_scores(soup: BeautifulSoup) -> List[str]:

    patterns = [
        re.compile(
            r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)"
        ),
    ]

    results = []

    # title
    if soup.title:

        text = soup.title.get_text(
            " ",
            strip=True,
        )

        for pattern in patterns:

            for match in pattern.finditer(text):

                results.append(
                    "TITLE | " + match.group(0) + " | " + text
                )

    # элементы с score/result
    for element in soup.find_all(
        attrs={
            "class": True,
        }
    ):

        classes = " ".join(
            element.get("class") or []
        ).lower()

        if (
            "score" not in classes
            and "result" not in classes
        ):
            continue

        text = element.get_text(
            " ",
            strip=True,
        )

        for pattern in patterns:

            for match in pattern.finditer(text):

                results.append(
                    "ELEMENT | " + match.group(0) + " | "
                    "classes=" + classes + " | "
                    "text=" + short_text(text, 300)
                )

    # META
    for meta in soup.find_all("meta"):

        content = meta.get("content") or ""

        if re.search(
            r"(?<!\d)\d{1,2}\s*[-:]\s*\d{1,2}(?!\d)",
            content,
        ):

            results.append(
                "META | "
                + short_text(content, 500)
            )

    return list(
        dict.fromkeys(results)
    )


# ============================================================
# STAT LABELS
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
    "ожидаемые ассисты",
    "expected assists",
    "фолы",
    "fouls",
    "отборы",
    "tackles",
    "дуэли",
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
]


def find_statistics(soup: BeautifulSoup) -> List[str]:

    results = []

    for element in soup.find_all(
        ["div", "span", "td", "li", "p"]
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
            or "score" in normalized
            or "динамо" in normalized
            or "крыл" in normalized
            or "заверш" in normalized
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
                key + "=" + str(value) + " | "
                "tag=" + element.name + " | "
                "class=" + str(element.get("class")) + " | "
                "text=" + short_text(text, 250)
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
                "window.environment",
                "event_id",
                "score",
                "stats",
                "statistics",
                "participants",
                "match",
                "soccerway",
            ]
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
                    text[:15000],
                    "=" * 100,
                ]
            )
        )

    return results


# ============================================================
# JSON-LIKE BLOCKS
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
        ):

            results.append(
                text[:20000]
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
    ]

    for element in soup.find_all(
        ["div", "section", "article"]
    ):

        classes = " ".join(
            element.get("class") or []
        )

        if not classes:
            continue

        lowered = classes.lower()

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

        if len(text) > 1500:
            text = text[:1500] + "..."

        results.append(
            "\n".join(
                [
                    "TAG: " + element.name,
                    "CLASS: " + classes,
                    "ID: " + str(element.get("id")),
                    "PATH: " + css_path(element),
                    "TEXT: " + text,
                    "-" * 70,
                ]
            )
        )

    # ограничиваем, чтобы отчёт не стал гигантским
    return results[:500]


# ============================================================
# HTML FRAGMENTS
# ============================================================

def inspect_stat_fragments(
    soup: BeautifulSoup,
) -> List[str]:

    results = []

    for element in soup.find_all(
        ["div", "tr", "li"]
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

        # Только небольшие блоки.
        if len(text) > 1000:
            continue

        results.append(
            "\n".join(
                [
                    "TAG: " + element.name,
                    "CLASS: " + str(element.get("class")),
                    "ID: " + str(element.get("id")),
                    "PATH: " + css_path(element),
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
        "============================================================"
    )
    lines.append("")

    lines.append(
        "1. URL"
    )
    lines.append(url)
    lines.append("")

    lines.append(
        "2. HTTP"
    )
    lines.append(
        "STATUS: " + str(status)
    )
    lines.append(
        "HTML BYTES: " + str(len(html_text.encode("utf-8")))
    )
    lines.append("")

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

    lines.append(
        title
    )
    lines.append("")

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    lines.append(
        "4. SCORE CANDIDATES"
    )

    scores = find_scores(
        soup
    )

    if scores:

        lines.extend(scores)

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    lines.append(
        "5. STATISTIC LABELS"
    )

    statistics = find_statistics(
        soup
    )

    if statistics:

        lines.extend(statistics)

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # CLASSES
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
    # MATCH CONTAINERS
    # --------------------------------------------------------

    lines.append(
        "7. MATCH / STATS CONTAINERS"
    )

    containers = (
        inspect_match_containers(
            soup
        )
    )

    if containers:

        lines.extend(containers)

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # STAT FRAGMENTS
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

        lines.extend(fragments)

    else:

        lines.append(
            "NOT FOUND"
        )

    lines.append("")

    # --------------------------------------------------------
    # DATA ATTRIBUTES
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
        "Получение реальной HTML-структуры Soccerway "
        "для создания финального парсера."
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
                    "HTTP " + str(status) + " | "
                    + str(len(html_text.encode("utf-8"))) + " байт"
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
            "Ниже находится весь отчёт одним блоком. "
            "Нажмите кнопку копирования в правом верхнем углу "
            "поля — и пришлите мне весь текст."
        )

        # ====================================================
        # HTML TEXTAREA
        # ====================================================

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

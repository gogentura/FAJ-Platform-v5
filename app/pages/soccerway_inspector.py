#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
SOCCERWAY INSPECTOR v2

Задача:
    Не парсить матч.
    Не угадывать структуру.

    Найти реальные HTML-элементы Soccerway
    и показать их короткими фрагментами.

    Вывод:
        - title
        - META
        - элементы score/result
        - элементы с названиями команд
        - элементы статистики
        - class
        - id
        - data-* атрибуты
        - HTML-фрагмент элемента
"""

from __future__ import annotations

import re
import requests
import streamlit as st
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

URL_DEFAULT = (
    "https://ru.soccerway.com/match/"
    "dynamo-moscow-AFWA2jAQ/"
    "krylya-sovetov-samara-SKAE94nJ/"
    "summary/stats/overall/?mid=C8Coobll"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)


# ============================================================
# HTTP
# ============================================================

def load_page(url: str):

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

    return response


# ============================================================
# HELPERS
# ============================================================

def clean_text(value: str) -> str:

    if not value:
        return ""

    value = value.replace("\xa0", " ")

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def attrs_for(element):

    result = {}

    for key, value in element.attrs.items():

        if key == "class":
            result["class"] = " ".join(value)

        elif key == "id":
            result["id"] = value

        elif str(key).startswith("data-"):
            result[key] = value

    return result


def short_html(element, limit=2500):

    html = str(element)

    if len(html) > limit:
        html = html[:limit] + "\n... [ОБРЕЗАНО]"

    return html


def show_element(number, element, label):

    text = clean_text(
        element.get_text(
            " ",
            strip=True,
        )
    )

    attrs = attrs_for(element)

    st.markdown(
        f"### {number}. {label}"
    )

    if text:
        st.write(
            f"Текст: `{text[:500]}`"
        )

    if attrs:
        st.json(attrs)

    st.code(
        short_html(element),
        language="html",
    )


# ============================================================
# SCORE CANDIDATES
# ============================================================

def find_score_candidates(soup):

    found = []

    patterns = [
        re.compile(
            r"(?<!\d)\d{1,2}\s*[-:]\s*\d{1,2}(?!\d)"
        ),
    ]

    # META
    for meta in soup.find_all("meta"):

        content = meta.get("content", "")

        for pattern in patterns:

            if pattern.search(str(content)):

                found.append(
                    (
                        "META",
                        meta,
                    )
                )

                break

    # HTML elements
    for element in soup.find_all(
        ["div", "span", "a", "p", "strong", "b", "td"],
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 150:
            continue

        for pattern in patterns:

            if pattern.search(text):

                found.append(
                    (
                        "HTML",
                        element,
                    )
                )

                break

    return found


# ============================================================
# TEAM CANDIDATES
# ============================================================

TEAM_WORDS = [
    "динамо",
    "крылья",
    "советов",
]


def find_team_candidates(soup):

    found = []

    for element in soup.find_all(
        ["div", "span", "a", "p", "strong", "b"],
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 100:
            continue

        low = text.lower()

        if any(
            word in low
            for word in TEAM_WORDS
        ):

            found.append(element)

    return found


# ============================================================
# STAT CANDIDATES
# ============================================================

STAT_WORDS = [
    "ожидаемые голы",
    "xg",
    "владение",
    "удары",
    "удары в створ",
    "голевые моменты",
    "угловые",
    "передачи",
    "xgot",
    "xg ot",
    "ожидаемые ассисты",
    "xa",
    "фолы",
    "отборы",
    "дуэли",
    "выносы",
    "перехваты",
    "сэйвы",
    "сейвы",
    "удары от ворот",
    "офсайды",
    "навесы",
    "последней трети",
]


def find_stat_candidates(soup):

    found = []

    for element in soup.find_all(
        ["div", "span", "td", "li", "p"],
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 250:
            continue

        low = text.lower()

        if any(
            word in low
            for word in STAT_WORDS
        ):

            found.append(element)

    return found


# ============================================================
# MAIN
# ============================================================

def main():

    st.set_page_config(
        page_title="FAJ — Soccerway Inspector",
        page_icon="🔎",
        layout="wide",
    )

    st.title(
        "🔎 FAJ — Soccerway HTML Inspector v2"
    )

    st.caption(
        "Показывает реальные HTML-элементы "
        "Soccerway вместо огромного JavaScript."
    )

    url = st.text_input(
        "URL матча Soccerway",
        value=URL_DEFAULT,
    )

    if not st.button(
        "🔎 ИССЛЕДОВАТЬ СТРАНИЦУ",
        type="primary",
        width="stretch",
    ):
        return

    try:

        with st.spinner(
            "Получаем HTML Soccerway..."
        ):

            response = load_page(
                url.strip()
            )

    except Exception as exc:

        st.error(
            f"Ошибка загрузки: {exc}"
        )

        return

    html = response.text

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # ========================================================
    # BASIC
    # ========================================================

    st.success(
        f"HTTP {response.status_code} | "
        f"{len(html):,} байт"
    )

    st.markdown(
        "## 1. Основная информация"
    )

    st.json(
        {
            "status": response.status_code,
            "html_bytes": len(html),
            "title": (
                soup.title.get_text(
                    " ",
                    strip=True,
                )
                if soup.title
                else None
            ),
        }
    )

    # ========================================================
    # SCORE
    # ========================================================

    st.markdown(
        "## 2. Элементы со счётом"
    )

    scores = find_score_candidates(
        soup
    )

    if not scores:

        st.warning(
            "HTML-элементы со счётом не найдены."
        )

    else:

        # Убираем дубликаты
        seen = set()
        unique = []

        for kind, element in scores:

            marker = str(element)

            if marker in seen:
                continue

            seen.add(marker)

            unique.append(
                (kind, element)
            )

        for index, (kind, element) in enumerate(
            unique[:15],
            start=1,
        ):

            show_element(
                index,
                element,
                f"Score candidate ({kind})",
            )

    # ========================================================
    # TEAMS
    # ========================================================

    st.markdown(
        "## 3. Элементы с командами"
    )

    teams = find_team_candidates(
        soup
    )

    if not teams:

        st.warning(
            "Элементы с названиями команд не найдены."
        )

    else:

        seen = set()
        unique = []

        for element in teams:

            marker = str(element)

            if marker in seen:
                continue

            seen.add(marker)

            unique.append(element)

        for index, element in enumerate(
            unique[:20],
            start=1,
        ):

            show_element(
                index,
                element,
                "Team candidate",
            )

    # ========================================================
    # STATS
    # ========================================================

    st.markdown(
        "## 4. Элементы статистики"
    )

    stats = find_stat_candidates(
        soup
    )

    if not stats:

        st.warning(
            "Элементы статистики не найдены."
        )

    else:

        seen = set()
        unique = []

        for element in stats:

            marker = str(element)

            if marker in seen:
                continue

            seen.add(marker)

            unique.append(element)

        for index, element in enumerate(
            unique[:60],
            start=1,
        ):

            show_element(
                index,
                element,
                "Statistic candidate",
            )

    # ========================================================
    # IMPORTANT: RAW HTML AROUND MATCH
    # ========================================================

    st.markdown(
        "## 5. Компактный поиск match/event элементов"
    )

    match_elements = []

    for element in soup.find_all(True):

        classes = " ".join(
            element.get("class", [])
        )

        element_id = element.get(
            "id",
            "",
        )

        combined = (
            f"{classes} {element_id}"
        ).lower()

        if any(
            word in combined
            for word in (
                "match",
                "event",
                "score",
                "participant",
                "statistics",
                "stats",
            )
        ):

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                text
                and len(text) <= 500
            ):

                match_elements.append(
                    element
                )

    seen = set()
    unique_match = []

    for element in match_elements:

        marker = str(element)

        if marker in seen:
            continue

        seen.add(marker)

        unique_match.append(
            element
        )

    for index, element in enumerate(
        unique_match[:30],
        start=1,
    ):

        show_element(
            index,
            element,
            "Match/Event candidate",
        )

    # ========================================================
    # FINAL
    # ========================================================

    st.success(
        "Инспекция завершена. "
        "Теперь по этому выводу можно определить "
        "реальные селекторы Soccerway."
    )


if __name__ == "__main__":
    main()

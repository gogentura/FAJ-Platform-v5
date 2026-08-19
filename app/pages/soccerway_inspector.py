#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
SOCCERWAY HTML INSPECTOR v1.0

Диагностика реальной HTML-структуры Soccerway.

ВАЖНО:
    - БД не используется
    - ничего не записывается
    - ничего не изменяется
    - задача: увидеть реальные HTML-классы и контейнеры
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import requests
import streamlit as st
from bs4 import BeautifulSoup, Tag


# ============================================================
# CONFIG
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)

DEFAULT_URL = (
    "https://ru.soccerway.com/match/"
    "dynamo-moscow-AFWA2jAQ/"
    "krylya-sovetov-samara-SKAE94nJ/"
    "summary/stats/overall/?mid=C8Coobll"
)


# ============================================================
# HTTP
# ============================================================

def load_page(url: str) -> tuple[str, int]:

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
            "Cache-Control": "no-cache",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.text, response.status_code


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def norm(text: Any) -> str:

    if text is None:
        return ""

    text = str(text)

    text = (
        text
        .replace("\xa0", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# ELEMENT DESCRIPTION
# ============================================================

def describe_element(
    element: Tag,
) -> dict:

    classes = element.get("class") or []

    attrs = {}

    for key, value in element.attrs.items():

        if key == "class":
            continue

        if str(key).startswith("data-"):
            attrs[key] = value

    return {
        "tag": element.name,
        "id": element.get("id"),
        "class": " ".join(
            str(x)
            for x in classes
        ),
        "data": attrs,
        "text": norm(
            element.get_text(
                " ",
                strip=True,
            )
        )[:500],
    }


# ============================================================
# SCORE SEARCH
# ============================================================

def find_score_elements(
    soup: BeautifulSoup,
):

    results = []

    pattern = re.compile(
        r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)"
    )

    seen = set()

    for element in soup.find_all(True):

        text = norm(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        match = pattern.search(text)

        if not match:
            continue

        score = (
            f"{match.group(1)}:"
            f"{match.group(2)}"
        )

        classes = " ".join(
            str(x)
            for x in (
                element.get("class")
                or []
            )
        )

        key = (
            element.name,
            classes,
            score,
            text[:200],
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            {
                "score": score,
                **describe_element(element),
            }
        )

        if len(results) >= 30:
            break

    return results


# ============================================================
# KEYWORD SEARCH
# ============================================================

KEYWORDS = [
    "xg",
    "ожидаемые голы",
    "владение",
    "удары",
    "shots",
    "угловые",
    "corners",
    "передачи",
    "passes",
    "фолы",
    "fouls",
    "xgot",
    "xa",
    "выносы",
    "перехваты",
    "сэйвы",
    "сейвы",
    "goal kicks",
    "удары от ворот",
]


def find_keyword_elements(
    soup: BeautifulSoup,
):

    results = []

    seen = set()

    for element in soup.find_all(
        [
            "div",
            "span",
            "td",
            "li",
            "p",
            "strong",
            "b",
        ]
    ):

        text = norm(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if len(text) > 500:
            continue

        lower = text.lower()

        matched = [
            keyword
            for keyword in KEYWORDS
            if keyword in lower
        ]

        if not matched:
            continue

        description = describe_element(
            element
        )

        key = (
            description["tag"],
            description["class"],
            description["id"],
            description["text"],
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            {
                "matched": ", ".join(
                    matched
                ),
                **description,
            }
        )

        if len(results) >= 150:
            break

    return results


# ============================================================
# CLASSES AROUND KEYWORDS
# ============================================================

def collect_parent_chain(
    element: Tag,
    depth: int = 5,
):

    result = []

    current = element

    for level in range(depth):

        if not current:
            break

        description = describe_element(
            current
        )

        description["level"] = level

        result.append(
            description
        )

        current = current.parent

    return result


def find_best_keyword_chain(
    soup: BeautifulSoup,
    keyword: str,
):

    keyword = keyword.lower()

    for element in soup.find_all(
        [
            "div",
            "span",
            "td",
            "li",
            "p",
            "strong",
            "b",
        ]
    ):

        text = norm(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            continue

        if keyword not in text.lower():
            continue

        # Предпочитаем короткие элементы,
        # потому что именно они чаще являются
        # названием статистического показателя.

        if len(text) > 150:
            continue

        return collect_parent_chain(
            element,
            depth=6,
        )

    return []


# ============================================================
# CLASS FREQUENCY
# ============================================================

def class_frequency(
    soup: BeautifulSoup,
):

    counter = Counter()

    for element in soup.find_all(True):

        for cls in (
            element.get("class")
            or []
        ):

            counter[str(cls)] += 1

    return counter.most_common(100)


# ============================================================
# HTML SNIPPET
# ============================================================

def element_html(
    element: Tag,
) -> str:

    html = str(element)

    if len(html) > 12000:
        html = html[:12000] + "\n...[TRUNCATED]..."

    return html


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
        "🔎 FAJ — Soccerway HTML Inspector"
    )

    st.caption(
        "Диагностика реальной HTML-структуры Soccerway"
    )

    st.warning(
        "Эта страница только читает Soccerway. "
        "База FAJ не используется и не изменяется."
    )

    url = st.text_input(
        "🔗 URL матча Soccerway",
        value=DEFAULT_URL,
    )

    inspect_button = st.button(
        "🔎 Исследовать страницу",
        type="primary",
        use_container_width=True,
    )


    if inspect_button:

        if not url.strip():

            st.error(
                "Введите URL."
            )

            st.stop()

        try:

            with st.spinner(
                "Получаем реальный HTML Soccerway..."
            ):

                html, status_code = load_page(
                    url.strip()
                )

                soup = BeautifulSoup(
                    html,
                    "html.parser",
                )

            st.success(
                f"HTTP {status_code} | "
                f"{len(html):,} байт"
            )

        except Exception as exc:

            st.error(
                f"Ошибка загрузки: {exc}"
            )

            st.stop()

        # ========================================================
        # BASIC
        # ========================================================

        st.header(
            "1. Основная информация"
        )

        title = ""

        if soup.title:

            title = norm(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

        st.write(
            {
                "title": title,
                "html_bytes": len(html),
                "status": status_code,
            }
        )

        # ========================================================
        # SCORE
        # ========================================================

        st.header(
            "2. Реальные элементы со счётом"
        )

        scores = find_score_elements(
            soup
        )

        if scores:

            st.dataframe(
                scores,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.error(
                "Элементы со счётом не найдены."
            )

        # ========================================================
        # KEYWORDS
        # ========================================================

        st.header(
            "3. Реальные элементы статистики"
        )

        keyword_elements = (
            find_keyword_elements(
                soup
            )
        )

        if keyword_elements:

            st.dataframe(
                keyword_elements,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.error(
                "Статистические элементы не найдены."
            )

        # ========================================================
        # XG CHAIN
        # ========================================================

        st.header(
            "4. Родительская структура вокруг xG"
        )

        xg_chain = find_best_keyword_chain(
            soup,
            "xg",
        )

        if xg_chain:

            st.dataframe(
                xg_chain,
                use_container_width=True,
                hide_index=True,
            )

            # HTML последнего найденного элемента

            for item in xg_chain:

                if item["level"] == 0:
                    break

            # Находим снова короткий xG element

            for element in soup.find_all(True):

                text = norm(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    text
                    and "xg" in text.lower()
                    and len(text) <= 150
                ):

                    st.subheader(
                        "HTML элемента xG"
                    )

                    st.code(
                        element_html(
                            element
                        ),
                        language="html",
                    )

                    break

        else:

            st.warning(
                "Элемент xG в HTML не найден."
            )

        # ========================================================
        # POSSESSION
        # ========================================================

        st.header(
            "5. Родительская структура вокруг «Владение»"
        )

        possession_chain = (
            find_best_keyword_chain(
                soup,
                "владение",
            )
        )

        if possession_chain:

            st.dataframe(
                possession_chain,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.warning(
                "Элемент «Владение» не найден."
            )

        # ========================================================
        # SHOTS
        # ========================================================

        st.header(
            "6. Родительская структура вокруг «Удары»"
        )

        shots_chain = (
            find_best_keyword_chain(
                soup,
                "удары",
            )
        )

        if shots_chain:

            st.dataframe(
                shots_chain,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.warning(
                "Элемент «Удары» не найден."
            )

        # ========================================================
        # CLASSES
        # ========================================================

        st.header(
            "7. Часто используемые CSS-классы"
        )

        classes = class_frequency(
            soup
        )

        class_rows = [
            {
                "class": cls,
                "count": count,
            }
            for cls, count in classes
        ]

        st.dataframe(
            class_rows,
                use_container_width=True,
                hide_index=True,
            )

        # ========================================================
        # DATA ATTRIBUTES
        # ========================================================

        st.header(
            "8. Data-* атрибуты"
        )

        data_rows = []

        seen_data = set()

        for element in soup.find_all(True):

            for key, value in element.attrs.items():

                if not str(key).startswith(
                    "data-"
                ):
                    continue

                row = {
                    "tag": element.name,
                    "attribute": key,
                    "value": str(value),
                    "class": " ".join(
                        str(x)
                        for x in (
                            element.get("class")
                            or []
                        )
                    ),
                    "text": norm(
                        element.get_text(
                            " ",
                            strip=True,
                        )
                    )[:200],
                }

                signature = tuple(
                    row.items()
                )

                if signature in seen_data:
                    continue

                seen_data.add(
                    signature
                )

                data_rows.append(
                    row
                )

                if len(data_rows) >= 200:
                    break

            if len(data_rows) >= 200:
                break

        if data_rows:

            st.dataframe(
                data_rows,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.info(
                "data-* атрибуты не обнаружены."
            )

        # ========================================================
        # JSON / SCRIPT
        # ========================================================

        st.header(
            "9. Script / JSON признаки"
        )

        scripts = soup.find_all(
            "script"
        )

        script_rows = []

        for index, script in enumerate(
            scripts
        ):

            text = script.string or script.get_text(
                " ",
                strip=False,
            )

            text = str(text or "")

            if not text.strip():
                continue

            lower = text.lower()

            interesting = any(
                token in lower
                for token in (
                    "xg",
                    "shots",
                    "possession",
                    "match",
                    "statistics",
                    "stats",
                    "home",
                    "away",
                )
            )

            if not interesting:
                continue

            script_rows.append(
                {
                    "index": index,
                    "type": script.get("type"),
                    "id": script.get("id"),
                    "length": len(text),
                    "preview": text[:1000],
                }
            )

            if len(script_rows) >= 30:
                break

        if script_rows:

            st.dataframe(
                script_rows,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.info(
                "Очевидных script-блоков со статистикой не найдено."
            )

        # ========================================================
        # FINAL
        # ========================================================

        st.header(
            "10. Что прислать мне"
        )

        st.success(
            "Inspector завершил исследование."
        )

        st.markdown(
            """
**Не нужно присылать весь HTML.**

Мне нужны результаты разделов:

1. **Реальные элементы со счётом**
2. **Реальные элементы статистики**
3. **Родительская структура вокруг xG**
4. **Родительская структура вокруг «Владение»**
5. **Родительская структура вокруг «Удары»**
6. **Часто используемые CSS-классы**
7. **Data-* атрибуты**
8. **Script / JSON признаки**

После этого я перепишу `soccerway_stats_parser.py` по реальной структуре страницы.
"""
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

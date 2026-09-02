#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
SOCCER365 DIAGNOSTIC
============================================================

Только диагностика структуры страницы.
Ничего не меняет в БД и не изменяет soccer365_parser.py

Назначение:
    - увидеть реальную структуру HTML страницы Soccer365
    - найти элементы счёта, команд, даты
    - определить правильные CSS-селекторы для парсера
    - отладить проблемы с извлечением данных

============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import requests
import streamlit as st
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def text_of(element) -> Optional[str]:
    if not element:
        return None
    value = element.get_text(
        " ",
        strip=True,
    )
    return value or None


def show_selector(
    soup: BeautifulSoup,
    selector: str,
    max_items: int = 30,
) -> None:
    """Показывает элементы, найденные по CSS-селектору."""
    elements = soup.select(selector)
    st.write(
        f"`{selector}` → найдено: **{len(elements)}**"
    )
    if not elements:
        return

    rows = []
    for index, element in enumerate(
        elements[:max_items],
        start=1,
    ):
        rows.append(
            {
                "№": index,
                "text": text_of(element),
                "class": " ".join(
                    element.get("class", [])
                ),
                "id": element.get("id"),
            }
        )

    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
    )


def load_page(url: str):
    """Загружает страницу Soccer365."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) "
            "Version/18.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    response = requests.get(
        url,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Главная функция диагностической страницы."""

    st.set_page_config(
        page_title="Soccer365 Diagnostic",
        page_icon="🔬",
        layout="wide",
    )

    st.title("🔬 Soccer365 — диагностика страницы")

    st.warning(
        "⚠️ Эта страница ничего не сохраняет в БД и не изменяет парсер. "
        "Она нужна только для просмотра того, что реально приходит "
        "с Soccer365."
    )

    st.markdown(
        """
        **Что проверяем:**
        1. Счёт — где лежит, в каких элементах
        2. Команды — как называются, в каких элементах
        3. Дата — в каком формате, где находится
        4. Статистика — какие элементы доступны
        """
    )

    # --------------------------------------------------------
    # URL INPUT
    # --------------------------------------------------------

    url = st.text_input(
        "🔗 URL матча Soccer365",
        placeholder="https://soccer365.ru/games/2478645/",
        help="Вставь ссылку на матч с Soccer365",
    )

    # --------------------------------------------------------
    # DIAGNOSTIC BUTTON
    # --------------------------------------------------------

    if st.button(
        "🔎 Получить структуру страницы",
        type="primary",
        use_container_width=True,
    ):

        if not url.strip():
            st.error("❌ Вставь URL матча Soccer365.")
            st.stop()

        try:
            with st.spinner(
                "Загружаю страницу Soccer365..."
            ):
                response = load_page(
                    url.strip()
                )

            st.success(
                f"✅ Страница получена. "
                f"HTTP {response.status_code}"
            )

            # ----------------------------------------------------
            # BASIC INFO
            # ----------------------------------------------------
            st.subheader("1. Основная информация")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Размер HTML",
                    f"{len(response.text):,} символов",
                )

            with col2:
                st.metric(
                    "Статус",
                    response.status_code,
                )

            with col3:
                st.metric(
                    "Content-Type",
                    response.headers.get(
                        "content-type",
                        "—"
                    ).split(";")[0],
                )

            st.write(
                f"**URL:** `{response.url}`"
            )

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            # ----------------------------------------------------
            # TITLE
            # ----------------------------------------------------
            st.subheader("2. Title")

            title_text = (
                soup.title.get_text(
                    " ",
                    strip=True
                )
                if soup.title
                else "TITLE НЕ НАЙДЕН"
            )

            st.code(
                title_text,
                language="text",
            )

            # ----------------------------------------------------
            # SCORE — САМОЕ ВАЖНОЕ
            # ----------------------------------------------------
            st.subheader("3. 🔥 Счёт — самое важное")

            st.caption(
                "Ищем элементы, которые содержат счёт."
            )

            score_selectors = [
                ".score1",
                ".score2",
                ".score",
                "[class*='score']",
                "[class*='Score']",
                ".live_game_score",
                ".game_score",
                ".match_score",
            ]

            for selector in score_selectors:
                show_selector(
                    soup,
                    selector,
                )

            # ----------------------------------------------------
            # SCORE PARENT — СМОТРИМ КОНТЕКСТ
            # ----------------------------------------------------
            st.subheader(
                "3.1 Контекст вокруг score1 / score2"
            )

            for selector in [
                ".score1",
                ".score2",
            ]:
                elements = soup.select(
                    selector
                )
                if not elements:
                    continue

                st.markdown(
                    f"### `{selector}`"
                )

                for idx, element in enumerate(
                    elements[:5],
                    start=1,
                ):
                    st.write(
                        f"**Элемент №{idx}**"
                    )
                    parent = element.parent
                    if parent:
                        st.code(
                            parent.prettify()[
                                :3000
                            ],
                            language="html",
                        )

            # ----------------------------------------------------
            # TEAMS
            # ----------------------------------------------------
            st.subheader("4. Команды")

            team_selectors = [
                ".team",
                ".team1",
                ".team2",
                ".home",
                ".away",
                "[class*='team']",
                "[class*='Team']",
                ".live_game_ht",
                ".live_game_at",
                ".live_game_tlogo",
            ]

            for selector in team_selectors:
                show_selector(
                    soup,
                    selector,
                )

            # ----------------------------------------------------
            # DATE
            # ----------------------------------------------------
            st.subheader("5. Дата")

            date_selectors = [
                ".date",
                ".game_date",
                ".date_game",
                ".live_game_date",
                ".match_date",
                "[class*='date']",
                "[class*='Date']",
                "[class*='time']",
            ]

            for selector in date_selectors:
                show_selector(
                    soup,
                    selector,
                )

            # ----------------------------------------------------
            # STATISTICS
            # ----------------------------------------------------
            st.subheader("6. Статистика")

            stat_selectors = [
                ".stat-tp0",
                ".stats_tp_body",
                ".stats_item",
                "[class*='stat']",
                "[class*='Stat']",
                "#stat-tp0",
                "#clubs_stats",
            ]

            for selector in stat_selectors:
                show_selector(
                    soup,
                    selector,
                )

            # ----------------------------------------------------
            # SEARCH SCORE TEXT
            # ----------------------------------------------------
            st.subheader(
                "7. Поиск возможных счетов в HTML"
            )

            html = response.text
            score_patterns = [
                r"\b\d{1,2}\s*:\s*\d{1,2}\b",
            ]

            found_scores = []
            for pattern in score_patterns:
                matches = re.findall(
                    pattern,
                    html,
                )
                for value in matches:
                    if value not in found_scores:
                        found_scores.append(
                            value
                        )

            if found_scores:
                st.write(
                    "Найденные значения:"
                )
                st.code(
                    "\n".join(
                        found_scores[:100]
                    )
                )
            else:
                st.warning(
                    "Счётов вида 0:1 / 1:1 / 3:0 "
                    "в HTML не найдено."
                )

            # ----------------------------------------------------
            # RAW HTML
            # ----------------------------------------------------
            st.subheader(
                "8. HTML страницы"
            )

            with st.expander(
                "Показать полный HTML",
                expanded=False,
            ):
                st.code(
                    response.text,
                    language="html",
                )

            # ----------------------------------------------------
            # SAVE HTML
            # ----------------------------------------------------
            st.download_button(
                "💾 Скачать HTML страницы",
                data=response.text,
                file_name="soccer365_debug.html",
                mime="text/html",
                use_container_width=True,
            )

            st.success(
                "✅ Диагностика завершена."
            )

        except requests.RequestException as exc:
            logger.exception(
                "Ошибка загрузки Soccer365"
            )
            st.error(
                f"❌ Ошибка HTTP: {exc}"
            )

        except Exception as exc:
            logger.exception(
                "Ошибка диагностики Soccer365"
            )
            st.error(
                f"❌ Ошибка: {exc}"
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

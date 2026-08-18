#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY STATS PARSER v1.0
============================================================

Источник:
    Soccerway

Назначение:
    Получение:
        - команд
        - счёта
        - статистики матча

Принцип:
    Никаких глобальных поисков случайных чисел.
    Сначала определяем структуру матча.
    Затем ищем показатели статистики.

None = показатель отсутствует.
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class SoccerwayStatsParser:

    VERSION = "1.0"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    )

    STAT_ALIASES = {

        "xg": (
            "xg",
            "expected goals",
            "ожидаемые голы",
        ),

        "possession": (
            "possession",
            "владение",
        ),

        "shots": (
            "shots",
            "удары",
            "total shots",
            "всего ударов",
        ),

        "shots_on_target": (
            "shots on target",
            "shots on goal",
            "удары в створ",
            "удары в ворота",
        ),

        "big_chances": (
            "big chances",
            "голевые моменты",
            "большие моменты",
        ),

        "corners": (
            "corners",
            "угловые",
        ),

        "fouls": (
            "fouls",
            "фолы",
        ),

        "offsides": (
            "offsides",
            "офсайды",
        ),

        "yellow_cards": (
            "yellow cards",
            "желтые карточки",
            "жёлтые карточки",
            "желтые",
            "жёлтые",
        ),

        "red_cards": (
            "red cards",
            "красные карточки",
            "красные",
        ),

        "passes": (
            "passes",
            "передачи",
        ),

        "pass_accuracy": (
            "pass accuracy",
            "точность передач",
        ),

        "xg_ot": (
            "xgot",
            "xg ot",
            "xg после ударов в створ",
        ),

        "xa": (
            "xa",
            "expected assists",
            "ожидаемые ассисты",
        ),

        "clearances": (
            "clearances",
            "выносы",
        ),

        "interceptions": (
            "interceptions",
            "перехваты",
        ),

        "saves": (
            "saves",
            "сэйвы",
            "сейвы",
        ),

        "goal_kicks": (
            "goal kicks",
            "удары от ворот",
        ),

        "penalties": (
            "penalties",
            "пенальти",
        ),
    }

    def __init__(self, timeout: int = 25):
        self.timeout = timeout

    # ========================================================
    # HTTP
    # ========================================================

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:

        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": (
                        "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
                    ),
                    "Referer": "https://ru.soccerway.com/",
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception as exc:

            logger.warning(
                "Soccerway: ошибка загрузки %s: %s",
                url,
                exc,
            )

            return None

    # ========================================================
    # NORMALIZE TEXT
    # ========================================================

    @staticmethod
    def _norm(value: Any) -> str:

        if value is None:
            return ""

        value = str(value)

        value = (
            value.replace("\xa0", " ")
            .replace("–", "-")
            .replace("—", "-")
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip().lower()

    # ========================================================
    # NUMBER EXTRACTION
    # ========================================================

    @staticmethod
    def _numbers(text: str):

        if not text:
            return []

        # 66%, 1.25, 453/539, 21
        matches = re.findall(
            r"\d+(?:[.,]\d+)?%?",
            text,
        )

        return matches

    @staticmethod
    def _parse_value(value: str) -> Optional[float]:

        if not value:
            return None

        value = value.strip()

        percent = value.endswith("%")

        value = value.rstrip("%")
        value = value.replace(",", ".")

        try:

            number = float(value)

            if percent:
                return number

            if number.is_integer():
                return int(number)

            return number

        except ValueError:

            return None

    # ========================================================
    # SCORE
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        # Сначала только элементы, связанные с результатом.
        selectors = [
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
            "[data-testid*='score']",
        ]

        for selector in selectors:

            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for element in elements:

                text = element.get_text(
                    " ",
                    strip=True,
                )

                match = re.search(
                    r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)",
                    text,
                )

                if not match:
                    continue

                home = int(match.group(1))
                away = int(match.group(2))

                if home <= 15 and away <= 15:
                    return home, away

        # Заголовок страницы — безопаснее общего текста.
        title = soup.title

        if title:

            text = title.get_text(
                " ",
                strip=True,
            )

            match = re.search(
                r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)",
                text,
            )

            if match:
                return (
                    int(match.group(1)),
                    int(match.group(2)),
                )

        return None

    # ========================================================
    # TEAMS
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[Optional[str], Optional[str]]:

        home = None
        away = None

        # Основные варианты Soccerway.
        selectors = [
            "[class*='home']",
            "[class*='Home']",
            "[class*='team']",
            "[class*='Team']",
        ]

        candidates = []

        for selector in selectors:

            try:
                for element in soup.select(selector):

                    text = element.get_text(
                        " ",
                        strip=True,
                    )

                    if text:
                        candidates.append(text)

            except Exception:
                continue

        # Проверяем типичные пары.
        cleaned = []

        for value in candidates:

            value = re.sub(
                r"\s+",
                " ",
                value,
            ).strip()

            if (
                len(value) >= 3
                and len(value) <= 80
            ):
                cleaned.append(value)

        for i in range(len(cleaned) - 1):

            h, a = normalize_team_names(
                cleaned[i],
                cleaned[i + 1],
                strict=True,
            )

            if h and a and h != a:

                home = h
                away = a
                break

        return home, away

    # ========================================================
    # STAT ROW
    # ========================================================

    def _extract_pair(
        self,
        text: str,
    ) -> Tuple[Optional[Any], Optional[Any]]:

        if not text:
            return None, None

        # Убираем название показателя.
        numbers = self._numbers(text)

        if len(numbers) < 2:
            return None, None

        # Берём первые два значения.
        home = self._parse_value(
            numbers[0]
        )

        away = self._parse_value(
            numbers[1]
        )

        return home, away

    # ========================================================
    # FIND STATISTIC BY LABEL
    # ========================================================

    def _find_stat(
        self,
        soup: BeautifulSoup,
        aliases,
    ) -> Tuple[Optional[Any], Optional[Any]]:

        alias_set = {
            self._norm(alias)
            for alias in aliases
        }

        # ----------------------------------------------------
        # 1. Ищем элементы, содержащие название показателя.
        # ----------------------------------------------------

        for element in soup.find_all(
            ["div", "span", "td", "li", "p"],
        ):

            label = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not label:
                continue

            matched = False

            for alias in alias_set:

                if label == alias:
                    matched = True
                    break

            if not matched:
                continue

            # ------------------------------------------------
            # Берём родительский блок.
            # ------------------------------------------------

            parent = element.parent

            if parent:

                text = parent.get_text(
                    " ",
                    strip=True,
                )

                home, away = self._extract_pair(
                    text
                )

                if home is not None and away is not None:
                    return home, away

            # ------------------------------------------------
            # Иногда значения лежат рядом.
            # ------------------------------------------------

            siblings = []

            for sibling in element.parent.find_all(
                recursive=False
            ) if element.parent else []:

                text = sibling.get_text(
                    " ",
                    strip=True,
                )

                if text:
                    siblings.append(text)

            combined = " ".join(
                siblings
            )

            home, away = self._extract_pair(
                combined
            )

            if home is not None and away is not None:
                return home, away

        return None, None

    # ========================================================
    # STATISTICS
    # ========================================================

    def _extract_statistics(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:

        result = {}

        for key, aliases in self.STAT_ALIASES.items():

            home, away = self._find_stat(
                soup,
                aliases,
            )

            result[
                f"home_{key}"
            ] = home

            result[
                f"away_{key}"
            ] = away

        # ----------------------------------------------------
        # pass accuracy может быть внутри 453/539 (84%)
        # ----------------------------------------------------

        if (
            result.get("home_pass_accuracy")
            is None
        ):

            home, away = self._find_stat(
                soup,
                (
                    "passes",
                    "передачи",
                ),
            )

            if home is not None and away is not None:

                result["home_passes"] = home
                result["away_passes"] = away

        return result

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        empty = {
            "source": "soccerway",
            "source_url": url,
            "parser_version": self.VERSION,

            "home_team": None,
            "away_team": None,

            "home_goals": None,
            "away_goals": None,

            "home_xg": None,
            "away_xg": None,

            "home_possession": None,
            "away_possession": None,

            "home_shots": None,
            "away_shots": None,

            "home_shots_on_target": None,
            "away_shots_on_target": None,

            "home_corners": None,
            "away_corners": None,

            "home_yellow_cards": None,
            "away_yellow_cards": None,

            "home_fouls": None,
            "away_fouls": None,

            "home_offsides": None,
            "away_offsides": None,

            "home_pass_accuracy": None,
            "away_pass_accuracy": None,
        }

        soup = self._get_soup(url)

        if soup is None:
            return empty

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = self._extract_score(
            soup
        )

        if score:

            empty["home_goals"] = score[0]
            empty["away_goals"] = score[1]

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        home, away = self._extract_teams(
            soup
        )

        empty["home_team"] = home
        empty["away_team"] = away

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        stats = self._extract_statistics(
            soup
        )

        empty.update(stats)

        logger.info(
            "Soccerway: parsed %s | score=%s:%s | xG=%s:%s | shots=%s:%s",
            url,
            empty["home_goals"],
            empty["away_goals"],
            empty["home_xg"],
            empty["away_xg"],
            empty["home_shots"],
            empty["away_shots"],
        )

        return empty


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

RPLStatsParser = SoccerwayStatsParser

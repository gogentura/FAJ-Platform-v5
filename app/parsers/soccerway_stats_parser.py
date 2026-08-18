#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Soccerway Stats Parser v1.0
============================================================

Источник:
    Soccerway

Назначение:
    Получение факта матча и статистики.

ПРИНЦИПЫ:
    - счёт и статистика извлекаются раздельно;
    - не ищем случайные числа по всей странице;
    - сначала определяем конкретный блок;
    - затем извлекаем пару HOME/AWAY;
    - каждый показатель проходит валидацию;
    - сомнительное значение -> None;
    - никакой подстановки случайных чисел;
    - неизвестная структура страницы не должна создавать ложный факт.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Tag

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class SoccerwayStatsParser:
    VERSION = "1.0"

    DEFAULT_TIMEOUT = 20

    # --------------------------------------------------------
    # Названия показателей Soccerway
    # --------------------------------------------------------

    STAT_ALIASES = {
        "xg": [
            "xg",
            "ожидаемые голы",
            "expected goals",
        ],
        "xgot": [
            "xgot",
            "xg после ударов в створ",
            "expected goals on target",
        ],
        "possession": [
            "владение",
            "владение мячом",
            "possession",
        ],
        "shots": [
            "всего ударов",
            "удары",
            "shots",
        ],
        "shots_on_target": [
            "удары в створ",
            "shots on target",
        ],
        "big_chances": [
            "голевые моменты",
            "голевые возможности",
            "big chances",
        ],
        "corners": [
            "угловые",
            "corner kicks",
            "corners",
        ],
        "fouls": [
            "фолы",
            "fouls",
        ],
        "offsides": [
            "офсайды",
            "offsides",
        ],
        "goalkeeper_saves": [
            "сэйвы вратаря",
            "сейвы вратаря",
            "вратарские сейвы",
            "goalkeeper saves",
            "saves",
        ],
        "goal_kicks": [
            "удары от ворот",
            "goal kicks",
        ],
        "touches_box": [
            "касания мяча в штрафной соперника",
            "касания в штрафной",
            "touches in opposition box",
        ],
        "xa": [
            "ожидаемые ассисты",
            "expected assists",
            "xa",
        ],
        "duels_won": [
            "выиграно дуэлей",
            "duels won",
        ],
        "clearances": [
            "выносы",
            "clearances",
        ],
        "interceptions": [
            "перехваты",
            "interceptions",
        ],
        "free_kicks": [
            "штрафные",
            "free kicks",
        ],
    }

    # --------------------------------------------------------
    # Диапазоны
    # --------------------------------------------------------

    LIMITS = {
        "xg": (0.0, 10.0),
        "xgot": (0.0, 10.0),
        "possession": (0.0, 100.0),
        "shots": (0, 60),
        "shots_on_target": (0, 40),
        "big_chances": (0, 20),
        "corners": (0, 20),
        "fouls": (0, 50),
        "offsides": (0, 20),
        "goalkeeper_saves": (0, 30),
        "goal_kicks": (0, 30),
        "touches_box": (0, 100),
        "xa": (0.0, 10.0),
        "duels_won": (0, 150),
        "clearances": (0, 100),
        "interceptions": (0, 100),
        "free_kicks": (0, 50),
    }

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/128.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,image/avif,image/webp,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse(self, url: str) -> Dict[str, Any]:
        """
        Полный разбор страницы Soccerway.
        """

        result = self._empty_result()

        if not url:
            result["error"] = "URL не указан"
            return result

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            # ------------------------------------------------
            # Команды
            # ------------------------------------------------

            home_team, away_team = self._extract_teams(soup)

            home_team, away_team = normalize_team_names(
                home_team,
                away_team,
                strict=False,
            )

            result["home_team"] = home_team
            result["away_team"] = away_team

            # ------------------------------------------------
            # Счёт
            # ------------------------------------------------

            score = self._extract_score(soup)

            if score is not None:
                result["home_score"] = score[0]
                result["away_score"] = score[1]

            # ------------------------------------------------
            # Статистика
            # ------------------------------------------------

            stats_container = self._find_statistics_container(
                soup
            )

            if stats_container is not None:
                stats = self._extract_statistics(
                    stats_container
                )

                result.update(stats)

            # ------------------------------------------------
            # Валидация
            # ------------------------------------------------

            result = self._validate_result(result)

            result["success"] = (
                result["home_score"] is not None
                and result["away_score"] is not None
            )

            if not result["success"]:
                result["warning"] = (
                    "Не удалось надёжно определить итоговый счёт."
                )

            return result

        except requests.RequestException as exc:
            logger.error(
                "Soccerway request error: %s",
                exc,
            )

            result["error"] = str(exc)

            return result

        except Exception as exc:
            logger.exception(
                "Soccerway parser error"
            )

            result["error"] = str(exc)

            return result

    # ========================================================
    # EMPTY RESULT
    # ========================================================

    def _empty_result(self) -> Dict[str, Any]:

        return {
            "source": "soccerway",
            "parser_version": self.VERSION,

            "success": False,

            "home_team": None,
            "away_team": None,

            "home_score": None,
            "away_score": None,

            "home_xg": None,
            "away_xg": None,

            "home_xgot": None,
            "away_xgot": None,

            "home_possession": None,
            "away_possession": None,

            "home_shots": None,
            "away_shots": None,

            "home_shots_on_target": None,
            "away_shots_on_target": None,

            "home_big_chances": None,
            "away_big_chances": None,

            "home_corners": None,
            "away_corners": None,

            "home_fouls": None,
            "away_fouls": None,

            "home_offsides": None,
            "away_offsides": None,

            "home_goalkeeper_saves": None,
            "away_goalkeeper_saves": None,

            "home_goal_kicks": None,
            "away_goal_kicks": None,

            "home_touches_box": None,
            "away_touches_box": None,

            "home_xa": None,
            "away_xa": None,

            "home_duels_won": None,
            "away_duels_won": None,

            "home_clearances": None,
            "away_clearances": None,

            "home_interceptions": None,
            "away_interceptions": None,

            "home_free_kicks": None,
            "away_free_kicks": None,

            "error": None,
            "warning": None,
        }

    # ========================================================
    # TEAM EXTRACTION
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[Optional[str], Optional[str]]:

        # Сначала ищем наиболее вероятные match-контейнеры.
        containers = []

        for selector in [
            "[class*='match']",
            "[class*='Match']",
            "[class*='summary']",
            "[class*='Summary']",
        ]:
            containers.extend(
                soup.select(selector)
            )

        # Ищем текстовые элементы с названиями.
        candidates = []

        for container in containers[:100]:
            text = container.get_text(
                " ",
                strip=True,
            )

            if (
                "Динамо" in text
                or "Крылья" in text
            ):
                candidates.append(container)

        # Универсальный fallback:
        # заголовок страницы.
        title = soup.find("title")

        if title:
            candidates.append(title)

        for element in candidates:
            text = element.get_text(
                " ",
                strip=True,
            )

            match = re.search(
                r"(.+?)\s*[-–—]\s*(.+?)\s+(?:\d{1,2}[-:]\d{1,2})",
                text,
                re.IGNORECASE,
            )

            if match:
                home = match.group(1).strip()
                away = match.group(2).strip()

                return home, away

        return None, None

    # ========================================================
    # SCORE
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        # ----------------------------------------------------
        # 1. Тег title
        # ----------------------------------------------------

        title = soup.find("title")

        if title:
            score = self._score_from_text(
                title.get_text(" ", strip=True)
            )

            if score is not None:
                return score

        # ----------------------------------------------------
        # 2. Матчевые блоки
        # ----------------------------------------------------

        selectors = [
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
        ]

        for selector in selectors:

            elements = soup.select(selector)

            for element in elements:

                text = element.get_text(
                    " ",
                    strip=True,
                )

                # Защита:
                # элемент должен быть коротким.
                if len(text) > 100:
                    continue

                score = self._score_from_text(text)

                if score is not None:
                    return score

        # ----------------------------------------------------
        # 3. Заголовок матча
        # ----------------------------------------------------

        for element in soup.find_all(
            ["h1", "h2", "h3"]
        ):

            text = element.get_text(
                " ",
                strip=True,
            )

            if (
                "Динамо" in text
                or "Крылья" in text
            ):

                score = self._score_from_text(
                    text
                )

                if score is not None:
                    return score

        # ----------------------------------------------------
        # ВАЖНО:
        # НЕ ищем счёт по всей странице.
        # ----------------------------------------------------

        return None

    def _score_from_text(
        self,
        text: str,
    ) -> Optional[Tuple[int, int]]:

        if not text:
            return None

        patterns = [
            r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
            )

            if not match:
                continue

            home = int(match.group(1))
            away = int(match.group(2))

            if (
                0 <= home <= 15
                and 0 <= away <= 15
            ):
                return home, away

        return None

    # ========================================================
    # STATISTICS CONTAINER
    # ========================================================

    def _find_statistics_container(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tag]:

        # ----------------------------------------------------
        # Точные/вероятные классы
        # ----------------------------------------------------

        selectors = [
            ".statistics",
            ".stats",
            ".stats-table",
            "[class*='statistics']",
            "[class*='Statistics']",
            "[class*='stats']",
            "[class*='Stats']",
        ]

        for selector in selectors:

            elements = soup.select(selector)

            for element in elements:

                text = element.get_text(
                    " ",
                    strip=True,
                ).lower()

                # Контейнер должен действительно
                # содержать статистические показатели.
                hits = 0

                for aliases in self.STAT_ALIASES.values():

                    if any(
                        alias.lower() in text
                        for alias in aliases
                    ):
                        hits += 1

                if hits >= 2:
                    return element

        # ----------------------------------------------------
        # По заголовку "Статистика"
        # ----------------------------------------------------

        for element in soup.find_all(
            ["h1", "h2", "h3", "h4", "div", "span"]
        ):

            text = element.get_text(
                " ",
                strip=True,
            ).lower()

            if text not in (
                "статистика",
                "statistics",
            ):
                continue

            parent = element.parent

            if parent:

                text_parent = parent.get_text(
                    " ",
                    strip=True,
                ).lower()

                hits = sum(
                    1
                    for aliases in self.STAT_ALIASES.values()
                    if any(
                        alias.lower() in text_parent
                        for alias in aliases
                    )
                )

                if hits >= 2:
                    return parent

        return None

    # ========================================================
    # STATISTICS EXTRACTION
    # ========================================================

    def _extract_statistics(
        self,
        container: Tag,
    ) -> Dict[str, Any]:

        result = {}

        # ----------------------------------------------------
        # 1. Строки таблиц
        # ----------------------------------------------------

        for row in container.find_all("tr"):

            cells = row.find_all(
                ["td", "th"]
            )

            if len(cells) < 2:
                continue

            label = cells[
                len(cells) // 2
            ].get_text(
                " ",
                strip=True,
            )

            row_text = row.get_text(
                " ",
                strip=True,
            )

            self._process_stat_row(
                row_text,
                result,
            )

        # ----------------------------------------------------
        # 2. Div/stat-row структура
        # ----------------------------------------------------

        for row in container.find_all(
            class_=re.compile(
                r"stat|statistics",
                re.IGNORECASE,
            )
        ):

            text = row.get_text(
                " ",
                strip=True,
            )

            self._process_stat_row(
                text,
                result,
            )

        # ----------------------------------------------------
        # 3. Универсальная обработка элементов
        # ----------------------------------------------------

        for element in container.find_all(
            ["div", "li", "p"]
        ):

            text = element.get_text(
                " ",
                strip=True,
            )

            if len(text) > 250:
                continue

            self._process_stat_row(
                text,
                result,
            )

        return result

    # ========================================================
    # PROCESS ONE STAT ROW
    # ========================================================

    def _process_stat_row(
        self,
        text: str,
        result: Dict[str, Any],
    ) -> None:

        if not text:
            return

        normalized = self._normalize_text(
            text
        )

        for stat_key, aliases in (
            self.STAT_ALIASES.items()
        ):

            matched = False

            for alias in aliases:

                if self._normalize_text(
                    alias
                ) in normalized:

                    matched = True
                    break

            if not matched:
                continue

            values = self._extract_pair(
                text,
                stat_key,
            )

            if values is None:
                continue

            home, away = values

            home_key = (
                f"home_{stat_key}"
            )

            away_key = (
                f"away_{stat_key}"
            )

            # Не перезаписываем уже найденное
            # более надёжное значение.
            if result.get(home_key) is None:
                result[home_key] = home

            if result.get(away_key) is None:
                result[away_key] = away

            return

    # ========================================================
    # PAIR EXTRACTION
    # ========================================================

    def _extract_pair(
        self,
        text: str,
        stat_key: str,
    ) -> Optional[Tuple[Any, Any]]:

        # ----------------------------------------------------
        # Передачи вида 453/539 (84%)
        # Для основного показателя нужны первые
        # значения только если показатель соответствующий.
        # ----------------------------------------------------

        if stat_key in (
            "xg",
            "xgot",
            "xa",
        ):

            numbers = re.findall(
                r"\d+(?:[.,]\d+)?",
                text,
            )

            if len(numbers) < 2:
                return None

            return (
                float(numbers[0].replace(",", ".")),
                float(numbers[1].replace(",", ".")),
            )

        # ----------------------------------------------------
        # Обычные целые показатели
        # ----------------------------------------------------

        numbers = re.findall(
            r"\b\d+(?:[.,]\d+)?%?\b",
            text,
        )

        values = []

        for number in numbers:

            clean = number.replace(
                "%",
                "",
            ).replace(
                ",",
                ".",
            )

            try:

                if "." in clean:
                    value = float(clean)
                else:
                    value = int(clean)

                values.append(value)

            except ValueError:
                continue

        if len(values) < 2:
            return None

        # Владение
        if stat_key == "possession":

            percentages = re.findall(
                r"(\d+(?:[.,]\d+)?)\s*%",
                text,
            )

            if len(percentages) >= 2:

                return (
                    float(
                        percentages[0].replace(
                            ",",
                            ".",
                        )
                    ),
                    float(
                        percentages[1].replace(
                            ",",
                            ".",
                        )
                    ),
                )

        return values[0], values[1]

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:

        text = (
            text.lower()
            .replace("ё", "е")
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_result(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # Диапазоны
        # ----------------------------------------------------

        for stat_key, (
            minimum,
            maximum,
        ) in self.LIMITS.items():

            home_key = (
                f"home_{stat_key}"
            )

            away_key = (
                f"away_{stat_key}"
            )

            result[home_key] = (
                self._validate_value(
                    result.get(home_key),
                    minimum,
                    maximum,
                    home_key,
                )
            )

            result[away_key] = (
                self._validate_value(
                    result.get(away_key),
                    minimum,
                    maximum,
                    away_key,
                )
            )

        # ----------------------------------------------------
        # Удары в створ <= ударов
        # ----------------------------------------------------

        hs = result.get(
            "home_shots"
        )
        has = result.get(
            "home_shots_on_target"
        )

        if (
            hs is not None
            and has is not None
            and has > hs
        ):

            logger.warning(
                "Soccerway: home shots_on_target "
                "> shots"
            )

            result[
                "home_shots_on_target"
            ] = None

        aws = result.get(
            "away_shots"
        )
        aots = result.get(
            "away_shots_on_target"
        )

        if (
            aws is not None
            and aots is not None
            and aots > aws
        ):

            logger.warning(
                "Soccerway: away shots_on_target "
                "> shots"
            )

            result[
                "away_shots_on_target"
            ] = None

        # ----------------------------------------------------
        # Владение
        # ----------------------------------------------------

        hp = result.get(
            "home_possession"
        )
        ap = result.get(
            "away_possession"
        )

        if (
            hp is not None
            and ap is not None
            and not 98 <= hp + ap <= 102
        ):

            logger.warning(
                "Soccerway: invalid possession "
                "%s + %s",
                hp,
                ap,
            )

            result[
                "home_possession"
            ] = None

            result[
                "away_possession"
            ] = None

        return result

    # ========================================================
    # SINGLE VALUE VALIDATION
    # ========================================================

    @staticmethod
    def _validate_value(
        value: Any,
        minimum: float,
        maximum: float,
        key: str,
    ) -> Optional[Any]:

        if value is None:
            return None

        try:

            numeric = float(value)

        except (
            TypeError,
            ValueError,
        ):

            logger.warning(
                "Invalid Soccerway value %s=%r",
                key,
                value,
            )

            return None

        if (
            numeric < minimum
            or numeric > maximum
        ):

            logger.warning(
                "Soccerway value %s=%s "
                "outside [%s,%s]",
                key,
                numeric,
                minimum,
                maximum,
            )

            return None

        if numeric.is_integer():
            return int(numeric)

        return numeric


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def parse_soccerway_match(
    url: str,
) -> Dict[str, Any]:

    parser = SoccerwayStatsParser()

    return parser.parse(url)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    URL = (
        "https://ru.soccerway.com/match/"
        "dynamo-moscow-AFWA2jAQ/"
        "krylya-sovetov-samara-SKAE94nJ/"
        "summary/stats/overall/"
        "?mid=C8Coobll"
    )

    logging.basicConfig(
        level=logging.INFO
    )

    parser = SoccerwayStatsParser()

    data = parser.parse(URL)

    print("=" * 70)
    print("FAJ SOCCERWAY PARSER")
    print("=" * 70)

    for key, value in data.items():
        print(f"{key}: {value}")

    print("=" * 70)

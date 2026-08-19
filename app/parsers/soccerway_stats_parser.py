#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
SOCCERWAY STATS PARSER v2.0-DIAGNOSTIC

Диагностическая версия.

Задача:
    Не угадывать CSS-классы Soccerway,
    а собрать фактическую структуру HTML страницы.

Ничего не пишет в БД.
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

    VERSION = "2.0-diagnostic"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    )

    # ========================================================
    # HTTP
    # ========================================================

    def __init__(self, timeout: int = 25):
        self.timeout = timeout

    def _get_soup(
        self,
        url: str,
    ) -> Optional[BeautifulSoup]:

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
                    "Cache-Control": "no-cache",
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            logger.info(
                "Soccerway HTTP %s | %s bytes",
                response.status_code,
                len(response.text),
            )

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
    # TEXT
    # ========================================================

    @staticmethod
    def _norm(value: Any) -> str:

        if value is None:
            return ""

        value = str(value)

        value = (
            value
            .replace("\xa0", " ")
            .replace("–", "-")
            .replace("—", "-")
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    # ========================================================
    # SCORE
    # ========================================================

    @staticmethod
    def _score_from_text(
        text: str,
    ) -> Optional[Tuple[int, int]]:

        if not text:
            return None

        patterns = [
            r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)",
            r"(?<!\d)(\d{1,2})\s+[-:]\s+(\d{1,2})(?!\d)",
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

            if home <= 15 and away <= 15:
                return home, away

        return None

    def _extract_score(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        # ----------------------------------------------------
        # 1. TITLE
        # ----------------------------------------------------

        if soup.title:

            title = self._norm(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

            score = self._score_from_text(
                title
            )

            if score:
                logger.info(
                    "Soccerway: счёт найден в TITLE: %s:%s",
                    score[0],
                    score[1],
                )

                return score

        # ----------------------------------------------------
        # 2. META
        # ----------------------------------------------------

        for meta in soup.find_all("meta"):

            content = meta.get("content")

            if not content:
                continue

            score = self._score_from_text(
                str(content)
            )

            if score:
                logger.info(
                    "Soccerway: счёт найден в META: %s:%s",
                    score[0],
                    score[1],
                )

                return score

        # ----------------------------------------------------
        # 3. Элементы с классами score/result
        # ----------------------------------------------------

        for element in soup.find_all(True):

            classes = element.get("class") or []

            class_text = " ".join(
                str(x)
                for x in classes
            ).lower()

            if not any(
                token in class_text
                for token in (
                    "score",
                    "result",
                    "match-score",
                    "scoreboard",
                )
            ):
                continue

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            score = self._score_from_text(
                text
            )

            if score:

                logger.info(
                    "Soccerway: счёт найден в классе '%s': %s:%s",
                    class_text,
                    score[0],
                    score[1],
                )

                return score

        # ----------------------------------------------------
        # 4. Заголовки
        # ----------------------------------------------------

        for element in soup.find_all(
            ["h1", "h2", "h3"]
        ):

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            score = self._score_from_text(
                text
            )

            if score:
                return score

        logger.warning(
            "Soccerway: счёт не найден"
        )

        return None

    # ========================================================
    # TEAMS
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[Optional[str], Optional[str]]:

        # ----------------------------------------------------
        # Ищем текст, похожий на названия команд.
        # ----------------------------------------------------

        candidates = []

        for element in soup.find_all(True):

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if len(text) < 3 or len(text) > 80:
                continue

            classes = element.get("class") or []

            class_text = " ".join(
                str(x)
                for x in classes
            ).lower()

            if any(
                token in class_text
                for token in (
                    "team",
                    "participant",
                    "home",
                    "away",
                )
            ):

                candidates.append(
                    (
                        text,
                        class_text,
                    )
                )

        # ----------------------------------------------------
        # Пытаемся найти пару.
        # ----------------------------------------------------

        for i in range(
            len(candidates) - 1
        ):

            first = candidates[i][0]
            second = candidates[i + 1][0]

            try:

                home, away = normalize_team_names(
                    first,
                    second,
                    strict=True,
                )

            except Exception:
                continue

            if (
                home
                and away
                and home != away
            ):

                logger.info(
                    "Soccerway: команды: %s — %s",
                    home,
                    away,
                )

                return home, away

        return None, None

    # ========================================================
    # DIAGNOSTIC HTML STRUCTURE
    # ========================================================

    def _inspect_structure(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:

        diagnostic = {
            "title": None,
            "score_candidates": [],
            "team_candidates": [],
            "stat_candidates": [],
        }

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        if soup.title:

            diagnostic["title"] = self._norm(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

        # ----------------------------------------------------
        # SCORE CANDIDATES
        # ----------------------------------------------------

        seen_scores = set()

        for element in soup.find_all(True):

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            score = self._score_from_text(
                text
            )

            if not score:
                continue

            classes = element.get("class") or []

            class_text = " ".join(
                str(x)
                for x in classes
            )

            key = (
                score,
                class_text,
                text[:150],
            )

            if key in seen_scores:
                continue

            seen_scores.add(key)

            diagnostic[
                "score_candidates"
            ].append(
                {
                    "score": (
                        f"{score[0]}:{score[1]}"
                    ),
                    "tag": element.name,
                    "classes": class_text,
                    "text": text[:150],
                }
            )

            if len(
                diagnostic["score_candidates"]
            ) >= 20:
                break

        # ----------------------------------------------------
        # STATISTIC CANDIDATES
        # ----------------------------------------------------

        stat_words = (
            "xg",
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
        )

        seen_stats = set()

        for element in soup.find_all(
            ["div", "span", "td", "li", "p"]
        ):

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if len(text) > 200:
                continue

            lower = text.lower()

            if not any(
                word in lower
                for word in stat_words
            ):
                continue

            classes = element.get("class") or []

            class_text = " ".join(
                str(x)
                for x in classes
            )

            key = (
                element.name,
                class_text,
                text,
            )

            if key in seen_stats:
                continue

            seen_stats.add(key)

            diagnostic[
                "stat_candidates"
            ].append(
                {
                    "tag": element.name,
                    "classes": class_text,
                    "text": text,
                }
            )

            if len(
                diagnostic["stat_candidates"]
            ) >= 100:
                break

        # ----------------------------------------------------
        # TEAM CANDIDATES
        # ----------------------------------------------------

        seen_teams = set()

        for element in soup.find_all(True):

            classes = element.get("class") or []

            class_text = " ".join(
                str(x)
                for x in classes
            )

            lower_classes = class_text.lower()

            if not any(
                word in lower_classes
                for word in (
                    "team",
                    "participant",
                    "home",
                    "away",
                )
            ):
                continue

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                len(text) < 3
                or len(text) > 80
            ):
                continue

            key = (
                class_text,
                text,
            )

            if key in seen_teams:
                continue

            seen_teams.add(key)

            diagnostic[
                "team_candidates"
            ].append(
                {
                    "tag": element.name,
                    "classes": class_text,
                    "text": text,
                }
            )

            if len(
                diagnostic["team_candidates"]
            ) >= 50:
                break

        return diagnostic

    # ========================================================
    # BASIC STATISTICS
    # ========================================================

    @staticmethod
    def _numbers(
        text: str,
    ):

        if not text:
            return []

        return re.findall(
            r"\d+(?:[.,]\d+)?%?",
            text,
        )

    @staticmethod
    def _parse_number(
        value: str,
    ) -> Optional[Any]:

        if not value:
            return None

        value = value.strip()
        is_percent = value.endswith("%")

        value = value.rstrip("%")
        value = value.replace(",", ".")

        try:

            number = float(value)

            if number.is_integer():
                return int(number)

            return number

        except ValueError:

            return None

    def _extract_pair(
        self,
        text: str,
    ) -> Tuple[Optional[Any], Optional[Any]]:

        numbers = self._numbers(
            text
        )

        if len(numbers) < 2:
            return None, None

        return (
            self._parse_number(numbers[0]),
            self._parse_number(numbers[1]),
        )

    def _find_stat(
        self,
        soup: BeautifulSoup,
        labels,
    ) -> Tuple[Optional[Any], Optional[Any]]:

        normalized_labels = [
            self._norm(x).lower()
            for x in labels
        ]

        for element in soup.find_all(
            ["div", "span", "td", "li", "p"]
        ):

            text = self._norm(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            lower = text.lower()

            if lower not in normalized_labels:
                continue

            # Сам элемент + ближайшие родители.
            current = element

            for _ in range(4):

                if not current:
                    break

                block_text = self._norm(
                    current.get_text(
                        " ",
                        strip=True,
                    )
                )

                home, away = self._extract_pair(
                    block_text
                )

                if (
                    home is not None
                    and away is not None
                ):
                    return home, away

                current = current.parent

        return None, None

    # ========================================================
    # STATISTICS
    # ========================================================

    def _extract_statistics(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:

        aliases = {
            "xg": (
                "xg",
                "ожидаемые голы",
            ),
            "possession": (
                "владение мячом",
                "владение",
                "possession",
            ),
            "shots": (
                "всего ударов",
                "удары",
                "shots",
                "total shots",
            ),
            "shots_on_target": (
                "удары в створ",
                "shots on target",
            ),
            "big_chances": (
                "голевые моменты",
                "big chances",
            ),
            "corners": (
                "угловые",
                "corners",
            ),
            "fouls": (
                "фолы",
                "fouls",
            ),
            "offsides": (
                "офсайды",
                "offsides",
            ),
            "xg_ot": (
                "xgot",
                "xg в створ",
                "xg после ударов в створ",
            ),
            "xa": (
                "ожидаемые ассисты",
                "expected assists",
                "xa",
            ),
            "clearances": (
                "выносы",
                "clearances",
            ),
            "interceptions": (
                "перехваты",
                "interceptions",
            ),
            "saves": (
                "сэйвы вратаря",
                "сэйвы",
                "сейвы",
                "saves",
            ),
            "goal_kicks": (
                "удары от ворот",
                "goal kicks",
            ),
        }

        result = {}

        for key, labels in aliases.items():

            home, away = self._find_stat(
                soup,
                labels,
            )

            result[
                f"home_{key}"
            ] = home

            result[
                f"away_{key}"
            ] = away

        return result

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        result = {
            "source": "soccerway",
            "source_url": url,
            "parser_version": self.VERSION,

            "home_team": None,
            "away_team": None,

            "home_goals": None,
            "away_goals": None,
        }

        soup = self._get_soup(
            url
        )

        if soup is None:
            return result

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = self._extract_score(
            soup
        )

        if score:

            result["home_goals"] = score[0]
            result["away_goals"] = score[1]

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        home, away = self._extract_teams(
            soup
        )

        result["home_team"] = home
        result["away_team"] = away

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        result.update(
            self._extract_statistics(
                soup
            )
        )

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        diagnostic = self._inspect_structure(
            soup
        )

        result["_diagnostic"] = diagnostic

        logger.info(
            "Soccerway parsed | "
            "score=%s:%s | "
            "teams=%s:%s | "
            "xG=%s:%s | "
            "shots=%s:%s",
            result.get("home_goals"),
            result.get("away_goals"),
            result.get("home_team"),
            result.get("away_team"),
            result.get("home_xg"),
            result.get("away_xg"),
            result.get("home_shots"),
            result.get("away_shots"),
        )

        return result


# ============================================================
# COMPATIBILITY
# ============================================================

RPLStatsParser = SoccerwayStatsParser

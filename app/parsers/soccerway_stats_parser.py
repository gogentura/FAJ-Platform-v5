#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY STATS PARSER v4.0
============================================================

Назначение:
    Получение фактического результата и статистики матча
    с Soccerway.

ВАЖНО:
    Не используется глобальный поиск первого числа страницы.

ПРИОРИТЕТ СЧЁТА:

    1. JSON-LD
    2. meta og:title
    3. title страницы
    4. элементы результата / score
    5. текст заголовка матча

Fallback допускается только после проверки контекста.

None != 0
============================================================
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from app.parsers.rpl_normalizer import normalize_team_name


logger = logging.getLogger(__name__)


class SoccerwayStatsParser:

    VERSION = "4.0"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    # ========================================================
    # HTTP
    # ========================================================

    def _get_soup(
        self,
        url: str,
    ) -> Optional[BeautifulSoup]:

        if not url:
            return None

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
                    "Referer": "https://www.google.com/",
                    "Connection": "keep-alive",
                },
                timeout=self.timeout,
                allow_redirects=True,
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
    # TEXT HELPERS
    # ========================================================

    @staticmethod
    def _text(element: Any) -> str:

        if element is None:
            return ""

        return element.get_text(
            " ",
            strip=True,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:

        value = value or ""

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
    # TEAM EXTRACTION
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[
        Optional[str],
        Optional[str],
    ]:

        candidates = []

        # ----------------------------------------------------
        # JSON-LD
        # ----------------------------------------------------

        for script in soup.find_all(
            "script",
            type="application/ld+json",
        ):

            raw = script.string or script.get_text(
                strip=True
            )

            if not raw:
                continue

            try:

                data = json.loads(raw)

            except Exception:
                continue

            objects = (
                data
                if isinstance(data, list)
                else [data]
            )

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                home = obj.get("homeTeam")
                away = obj.get("awayTeam")

                if isinstance(home, dict):
                    home = home.get("name")

                if isinstance(away, dict):
                    away = away.get("name")

                if home and away:
                    candidates.append(
                        (str(home), str(away))
                    )

        # ----------------------------------------------------
        # Meta / title
        # ----------------------------------------------------

        title = ""

        if soup.title:
            title = self._text(
                soup.title
            )

        og_title = soup.find(
            "meta",
            attrs={
                "property": "og:title"
            },
        )

        if og_title:
            content = og_title.get(
                "content"
            )

            if content:
                candidates.append(
                    self._teams_from_text(
                        content
                    )
                )

        candidates.append(
            self._teams_from_text(title)
        )

        for home, away in candidates:

            if not home or not away:
                continue

            home_n = normalize_team_name(
                home,
                strict=True,
            )

            away_n = normalize_team_name(
                away,
                strict=True,
            )

            if home_n and away_n:

                return home_n, away_n

        return None, None

    def _teams_from_text(
        self,
        text: str,
    ) -> Tuple[Optional[str], Optional[str]]:

        if not text:
            return None, None

        text = self._normalize_text(text)

        # Soccerway:
        # Dynamo Moscow v Krylya Sovetov
        # Dynamo Moscow - Krylya Sovetov 0-0

        patterns = [
            r"(.+?)\s+v\s+(.+?)(?:\s+\d{1,2}\s*[-:]\s*\d{1,2}|$)",
            r"(.+?)\s+-\s+(.+?)\s+\d{1,2}\s*[-:]\s*\d{1,2}",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            home = match.group(1).strip()
            away = match.group(2).strip()

            return home, away

        return None, None

    # ========================================================
    # SCORE
    # ========================================================

    @staticmethod
    def _valid_score(
        home: Any,
        away: Any,
    ) -> bool:

        try:

            home = int(home)
            away = int(away)

        except Exception:
            return False

        if home < 0 or away < 0:
            return False

        # Футбольный sanity check
        if home > 15 or away > 15:
            return False

        return True

    @classmethod
    def _score_from_text(
        cls,
        text: str,
    ) -> Optional[Tuple[int, int]]:

        if not text:
            return None

        text = cls._normalize_text(text)

        patterns = [
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
        ]

        for pattern in patterns:

            matches = re.findall(
                pattern,
                text,
            )

            for home, away in matches:

                if cls._valid_score(
                    home,
                    away,
                ):
                    return (
                        int(home),
                        int(away),
                    )

        return None

    def _extract_score(
        self,
        soup: BeautifulSoup,
        home_team: Optional[str],
        away_team: Optional[str],
    ) -> Optional[Tuple[int, int]]:

        # ----------------------------------------------------
        # 1. JSON-LD
        # ----------------------------------------------------

        for script in soup.find_all(
            "script",
            type="application/ld+json",
        ):

            raw = script.string or script.get_text(
                strip=True
            )

            if not raw:
                continue

            try:
                data = json.loads(raw)
            except Exception:
                continue

            objects = (
                data
                if isinstance(data, list)
                else [data]
            )

            for obj in objects:

                if not isinstance(obj, dict):
                    continue

                # Возможные поля
                for key in (
                    "score",
                    "result",
                    "eventStatus",
                ):

                    value = obj.get(key)

                    score = self._score_from_text(
                        str(value)
                        if value is not None
                        else ""
                    )

                    if score:
                        return score

        # ----------------------------------------------------
        # 2. OG TITLE
        # ----------------------------------------------------

        meta = soup.find(
            "meta",
            attrs={
                "property": "og:title"
            },
        )

        if meta:

            score = self._score_from_text(
                meta.get("content", "")
            )

            if score:
                return score

        # ----------------------------------------------------
        # 3. TITLE
        # ----------------------------------------------------

        if soup.title:

            score = self._score_from_text(
                self._text(soup.title)
            )

            if score:
                return score

        # ----------------------------------------------------
        # 4. SCORE / RESULT ELEMENTS
        # ----------------------------------------------------

        selectors = [
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
            "[data-testid*='score']",
            "[data-testid*='result']",
        ]

        for selector in selectors:

            for element in soup.select(
                selector
            ):

                text = self._text(
                    element
                )

                # Не берём огромные контейнеры.
                if len(text) > 200:
                    continue

                score = self._score_from_text(
                    text
                )

                if score:
                    return score

        # ----------------------------------------------------
        # 5. HEADER / MATCH CONTAINER
        # ----------------------------------------------------

        for element in soup.find_all(
            [
                "header",
                "main",
                "article",
            ]
        ):

            text = self._text(
                element
            )

            if len(text) > 1200:
                continue

            # Проверяем наличие хотя бы одной команды
            # перед тем, как искать счёт.
            has_home = (
                home_team
                and home_team.lower()
                in text.lower()
            )

            has_away = (
                away_team
                and away_team.lower()
                in text.lower()
            )

            if has_home or has_away:

                score = self._score_from_text(
                    text
                )

                if score:
                    return score

        # ----------------------------------------------------
        # 6. НЕ ДЕЛАЕМ GLOBAL TEXT FALLBACK
        #
        # Именно это раньше давало ложный счёт 4:0.
        # ----------------------------------------------------

        logger.warning(
            "Soccerway: счёт не найден"
        )

        return None

    # ========================================================
    # STAT VALUE
    # ========================================================

    @staticmethod
    def _number(
        value: str,
    ) -> Optional[float]:

        if not value:
            return None

        value = value.replace(
            "\xa0",
            " ",
        )

        match = re.search(
            r"(-?\d+(?:[.,]\d+)?)",
            value,
        )

        if not match:
            return None

        try:
            return float(
                match.group(1).replace(
                    ",",
                    ".",
                )
            )

        except Exception:
            return None

    # ========================================================
    # STATISTICS
    # ========================================================

    STAT_ALIASES = {

        "xg": [
            "xg",
            "expected goals",
            "ожидаемые голы",
        ],

        "possession": [
            "possession",
            "ball possession",
            "владение",
            "владение мячом",
        ],

        "shots": [
            "total shots",
            "shots",
            "удары",
            "всего ударов",
        ],

        "shots_on_target": [
            "shots on target",
            "on target",
            "удары в створ",
        ],

        "corners": [
            "corners",
            "угловые",
        ],

        "fouls": [
            "fouls",
            "фолы",
        ],

        "offsides": [
            "offsides",
            "офсайды",
            "офсайды",
        ],

        "saves": [
            "saves",
            "сэйвы",
            "сейвы",
        ],

        "passes": [
            "passes",
            "передачи",
        ],

        "pass_accuracy": [
            "accuracy",
            "pass accuracy",
            "точность передач",
        ],

        "yellow_cards": [
            "yellow cards",
            "yellow card",
            "жёлтые карточки",
            "желтые карточки",
            "жк",
        ],

        "red_cards": [
            "red cards",
            "red card",
            "красные карточки",
            "кк",
        ],

        "xgot": [
            "xgot",
            "xg on target",
        ],

        "xa": [
            "xa",
            "expected assists",
            "ожидаемые ассисты",
        ],
    }

    def _find_stat_rows(
        self,
        soup: BeautifulSoup,
    ):

        # ----------------------------------------------------
        # Таблицы
        # ----------------------------------------------------

        for table in soup.find_all("table"):

            for row in table.find_all("tr"):

                cells = row.find_all(
                    ["td", "th"]
                )

                if len(cells) < 2:
                    continue

                texts = [
                    self._text(cell)
                    for cell in cells
                ]

                yield texts

        # ----------------------------------------------------
        # Div rows
        # ----------------------------------------------------

        for row in soup.select(
            "[class*='stat-row'], "
            "[class*='statistics-row'], "
            "[class*='statistic-row']"
        ):

            texts = [
                self._text(child)
                for child in row.find_all(
                    recursive=False
                )
            ]

            if len(texts) >= 2:
                yield texts

    def _match_stat_label(
        self,
        label: str,
    ) -> Optional[str]:

        normalized = (
            label.lower()
            .replace(":", "")
            .strip()
        )

        for key, aliases in self.STAT_ALIASES.items():

            for alias in aliases:

                if alias in normalized:
                    return key

        return None

    def _extract_statistics(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {}

        for row in self._find_stat_rows(
            soup
        ):

            if len(row) < 3:
                continue

            label = row[0]

            stat_key = self._match_stat_label(
                label
            )

            if not stat_key:
                continue

            # Берём первое и последнее значение.
            values = row[1:]

            if len(values) < 2:
                continue

            home_raw = values[0]
            away_raw = values[-1]

            home = self._number(
                home_raw
            )

            away = self._number(
                away_raw
            )

            if home is None or away is None:
                continue

            result[
                f"home_{stat_key}"
            ] = home

            result[
                f"away_{stat_key}"
            ] = away

        return result

    # ========================================================
    # NORMALIZE OUTPUT
    # ========================================================

    @staticmethod
    def _int_if_integer(
        value: Any,
    ) -> Any:

        if isinstance(value, float) and value.is_integer():
            return int(value)

        return value

    def _normalize_stats(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:

        result = dict(stats)

        integer_fields = {
            "home_shots",
            "away_shots",
            "home_shots_on_target",
            "away_shots_on_target",
            "home_corners",
            "away_corners",
            "home_fouls",
            "away_fouls",
            "home_offsides",
            "away_offsides",
            "home_saves",
            "away_saves",
            "home_passes",
            "away_passes",
            "home_yellow_cards",
            "away_yellow_cards",
            "home_red_cards",
            "away_red_cards",
        }

        for key in integer_fields:

            if key in result:

                result[key] = (
                    self._int_if_integer(
                        result[key]
                    )
                )

        return result

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        soup = self._get_soup(
            url
        )

        if soup is None:
            return {}

        home_team, away_team = (
            self._extract_teams(
                soup
            )
        )

        score = self._extract_score(
            soup,
            home_team,
            away_team,
        )

        stats = self._extract_statistics(
            soup
        )

        stats = self._normalize_stats(
            stats
        )

        home_goals = None
        away_goals = None

        if score:

            home_goals, away_goals = score

        result = {
            "parser": "soccerway",
            "parser_version": self.VERSION,

            "source_url": url,

            "home_team": home_team,
            "away_team": away_team,

            "home_goals": home_goals,
            "away_goals": away_goals,

            **stats,
        }

        logger.info(
            "Soccerway parsed: %s vs %s | "
            "score=%s:%s | stats=%d",
            home_team,
            away_team,
            home_goals,
            away_goals,
            len(stats),
        )

        return result


# ============================================================
# COMPATIBILITY
# ============================================================

RPLStatsParser = SoccerwayStatsParser


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    url = (
        "https://ru.soccerway.com/match/"
        "dynamo-moscow-AFWA2jAQ/"
        "krylya-sovetov-samara-SKAE94nJ/"
        "summary/stats/overall/"
        "?mid=C8Coobll"
    )

    parser = SoccerwayStatsParser()

    data = parser.parse_match_page(
        url
    )

    print("=" * 60)
    print("SOCCERWAY TEST")
    print("=" * 60)

    for key, value in data.items():
        print(f"{key}: {value}")

    print("=" * 60)

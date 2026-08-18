#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY STATS PARSER v1.0
============================================================

Назначение:
    Получение результата и статистики завершённого матча
    со страниц Soccerway.

Принцип:

    URL
      ↓
    Soccerway HTML
      ↓
    Match identity
      ↓
    Score
      ↓
    Statistics
      ↓
    Normalized FAJ dictionary

ВАЖНО:

    Этот модуль НЕ работает с БД.

    None означает:
        источник не предоставил показатель.

    None НЕ означает 0.

Источник:
    ru.soccerway.com
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class SoccerwayStatsParser:
    """
    Универсальный парсер страниц матчей Soccerway.

    Основная задача:
        получить команды, счёт и доступную статистику.

    Парсер старается использовать структуру страницы,
    а не глобальный поиск случайных чисел.
    """

    VERSION = "soccerway-v1.0"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    )

    STAT_MAP = {
        # ------------------------------
        # Основные показатели
        # ------------------------------

        "xg": (
            "xG",
            "Ожидаемые голы",
            "Expected Goals",
            "Expected goals",
        ),

        "possession": (
            "Владение",
            "Владение мячом",
            "Possession",
        ),

        "shots": (
            "Всего ударов",
            "Удары",
            "Total shots",
            "Shots",
        ),

        "shots_on_target": (
            "Удары в створ",
            "Shots on target",
        ),

        "big_chances": (
            "Голевые моменты",
            "Большие моменты",
            "Big chances",
        ),

        "corners": (
            "Угловые",
            "Corners",
        ),

        # ------------------------------
        # Оборона
        # ------------------------------

        "fouls": (
            "Фолы",
            "Fouls",
        ),

        "tackles": (
            "Отборы",
            "Tackles",
        ),

        "duels_won": (
            "Выиграно дуэлей",
            "Дуэли",
            "Duels won",
        ),

        "clearances": (
            "Выносы",
            "Clearances",
        ),

        "interceptions": (
            "Перехваты",
            "Interceptions",
        ),

        # ------------------------------
        # Вратари
        # ------------------------------

        "saves": (
            "Сэйвы вратаря",
            "Сэйвы",
            "Saves",
        ),

        "goal_kicks": (
            "Удары от ворот",
            "Goal kicks",
        ),

        # ------------------------------
        # Атака
        # ------------------------------

        "offsides": (
            "Офсайды",
            "Offsides",
        ),

        "free_kicks": (
            "Штрафные",
            "Free kicks",
        ),

        "penalty_area_touches": (
            "Касания мяча в штрафной соперника",
            "Касания в штрафной",
            "Touches in opposition box",
        ),

        # ------------------------------
        # Передачи
        # ------------------------------

        "passes": (
            "Передачи",
            "Passes",
            "Всего передач",
        ),

        "pass_accuracy": (
            "Точность передач",
            "Pass accuracy",
        ),

        "long_passes": (
            "Длинные передачи",
            "Long passes",
        ),

        "final_third_passes": (
            "Передачи в последней трети",
            "Passes in final third",
        ),

        "crosses": (
            "Навесы",
            "Crosses",
        ),

        "xa": (
            "xA",
            "Ожидаемые ассисты",
            "Expected assists",
        ),

        # ------------------------------
        # Ударная статистика
        # ------------------------------

        "xgot": (
            "xGOT",
            "xG после ударов в створ",
            "Expected goals on target",
        ),

        "goals_prevented": (
            "Предотвращённые голы",
            "Goals prevented",
        ),
    }

    def __init__(
        self,
        timeout: int = 20,
    ) -> None:

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
                        "ru-RU,ru;q=0.9,en;q=0.8"
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

            logger.error(
                "Soccerway: ошибка загрузки %s: %s",
                url,
                exc,
            )

            return None

    # ========================================================
    # TEXT HELPERS
    # ========================================================

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        text = str(value)

        text = (
            text.replace("\xa0", " ")
            .replace("\u2009", " ")
            .replace("\u202f", " ")
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    @staticmethod
    def _clean_number(
        value: str,
    ) -> Optional[float]:

        if not value:
            return None

        value = (
            value.replace("%", "")
            .replace(",", ".")
            .strip()
        )

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            value,
        )

        if not match:
            return None

        try:
            return float(match.group(0))
        except ValueError:
            return None

    @staticmethod
    def _int_or_float(
        value: Optional[float],
    ) -> Optional[Any]:

        if value is None:
            return None

        if float(value).is_integer():
            return int(value)

        return value

    # ========================================================
    # SCORE
    # ========================================================

    def _extract_score_from_title(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        title = soup.find("title")

        if not title:
            return None

        text = self._normalize_text(
            title.get_text(
                " ",
                strip=True,
            )
        )

        # Пример:
        # Динамо Москва - Крылья Советов 0-0

        patterns = (
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\s*$",
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\s*$",
        )

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            home = int(match.group(1))
            away = int(match.group(2))

            if home <= 15 and away <= 15:
                return home, away

        return None

    def _extract_score_from_match_header(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        """
        Ищет счёт только в элементах,
        связанных с результатом матча.

        Глобальный поиск чисел НЕ используется.
        """

        selectors = [
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
            "[data-testid*='score']",
        ]

        for selector in selectors:

            elements = soup.select(
                selector
            )

            for element in elements:

                text = self._normalize_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if len(text) > 80:
                    continue

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

        return None

    def _extract_score(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        # Самый надёжный вариант для данной страницы:
        # заголовок матча.

        score = self._extract_score_from_title(
            soup
        )

        if score:
            return score

        # Второй уровень:
        # структурированный score/result блок.

        return self._extract_score_from_match_header(
            soup
        )

    # ========================================================
    # TEAM NAMES
    # ========================================================

    def _extract_teams_from_title(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[
        Optional[str],
        Optional[str],
    ]:

        title = soup.find("title")

        if not title:
            return None, None

        text = self._normalize_text(
            title.get_text(
                " ",
                strip=True,
            )
        )

        # Убираем счёт в конце.

        text = re.sub(
            r"\s+\d{1,2}\s*[-:]\s*\d{1,2}\s*$",
            "",
            text,
        ).strip()

        # Иногда title содержит дополнительную
        # информацию после названий.

        text = re.sub(
            r"\s*\|\s*Soccerway.*$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if " - " not in text:
            return None, None

        home, away = text.split(
            " - ",
            1,
        )

        home = self._normalize_text(home)
        away = self._normalize_text(away)

        if not home or not away:
            return None, None

        return home, away

    def _extract_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[
        Optional[str],
        Optional[str],
    ]:

        return self._extract_teams_from_title(
            soup
        )

    # ========================================================
    # STATISTICS
    # ========================================================

    def _candidate_stat_elements(
        self,
        soup: BeautifulSoup,
    ):

        """
        Возвращает потенциальные элементы статистики.

        Сначала ищем строки/ячейки с понятной структурой.
        """

        selectors = [
            "[class*='stat']",
            "[class*='Stat']",
            "[class*='statistics']",
            "[class*='Statistics']",
        ]

        seen = set()

        for selector in selectors:

            for element in soup.select(selector):

                identity = id(element)

                if identity in seen:
                    continue

                seen.add(identity)

                yield element

    def _extract_pair(
        self,
        element,
    ) -> Optional[Tuple[Any, Any]]:

        """
        Извлекает два числовых значения
        из одного элемента статистики.

        ВАЖНО:
            значения должны находиться
            внутри одного stat element.
        """

        text = self._normalize_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if not text:
            return None

        # Убираем слишком большие блоки.
        if len(text) > 250:
            return None

        # Сначала ищем явную пару:
        # 66% 34%
        # 21 12
        # 453/539 191/280

        numbers = re.findall(
            r"-?\d+(?:[.,]\d+)?",
            text,
        )

        if len(numbers) < 2:
            return None

        # Берём последние два числа только если
        # элемент действительно компактный.

        first = self._clean_number(
            numbers[0]
        )

        second = self._clean_number(
            numbers[1]
        )

        if first is None or second is None:
            return None

        return (
            self._int_or_float(first),
            self._int_or_float(second),
        )

    def _label_matches(
        self,
        text: str,
        aliases: Tuple[str, ...],
    ) -> bool:

        normalized = self._normalize_text(
            text
        ).lower()

        for alias in aliases:

            alias_normalized = (
                self._normalize_text(alias)
                .lower()
            )

            if normalized == alias_normalized:
                return True

        return False

    def _extract_stat_by_label(
        self,
        soup: BeautifulSoup,
        aliases: Tuple[str, ...],
    ) -> Optional[Tuple[Any, Any]]:

        """
        Ищет показатель по его названию,
        затем пытается получить пару значений
        из ближайшего компактного контейнера.

        Не выполняет глобальный поиск двух чисел
        по всей странице.
        """

        # ----------------------------------------------------
        # 1. Табличная структура
        # ----------------------------------------------------

        for row in soup.find_all(
            ["tr", "li"],
        ):

            text = self._normalize_text(
                row.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if not self._label_matches(
                text,
                aliases,
            ):
                continue

            cells = row.find_all(
                ["td", "th", "span", "div"],
            )

            values = []

            for cell in cells:

                cell_text = self._normalize_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )

                if not cell_text:
                    continue

                number = self._clean_number(
                    cell_text
                )

                if number is not None:
                    values.append(
                        self._int_or_float(number)
                    )

            if len(values) >= 2:
                return values[-2], values[-1]

        # ----------------------------------------------------
        # 2. Stat containers
        # ----------------------------------------------------

        for element in self._candidate_stat_elements(
            soup
        ):

            text = self._normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if not any(
                self._normalize_text(alias).lower()
                in text.lower()
                for alias in aliases
            ):
                continue

            pair = self._extract_pair(
                element
            )

            if pair:
                return pair

        return None

    # ========================================================
    # NORMALIZED STATISTICS
    # ========================================================

    def _extract_statistics(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:

        stats: Dict[str, Any] = {}

        for key, aliases in self.STAT_MAP.items():

            pair = self._extract_stat_by_label(
                soup,
                aliases,
            )

            if not pair:
                continue

            home, away = pair

            stats[f"home_{key}"] = home
            stats[f"away_{key}"] = away

        return stats

    # ========================================================
    # MAIN
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {
            "source": "soccerway",
            "source_url": url,
            "parser_version": self.VERSION,

            "home_team": None,
            "away_team": None,

            "home_goals": None,
            "away_goals": None,

            "stats": {},
        }

        soup = self._get_soup(
            url
        )

        if soup is None:
            return result

        # ----------------------------------------------------
        # Teams
        # ----------------------------------------------------

        home_team, away_team = (
            self._extract_teams(
                soup
            )
        )

        result["home_team"] = home_team
        result["away_team"] = away_team

        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        score = self._extract_score(
            soup
        )

        if score:

            result["home_goals"] = score[0]
            result["away_goals"] = score[1]

        else:

            logger.warning(
                "Soccerway: счёт не найден: %s",
                url,
            )

        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------

        result["stats"] = self._extract_statistics(
            soup
        )

        logger.info(
            "Soccerway parsed: %s - %s | %s:%s | stats=%s",
            home_team,
            away_team,
            result["home_goals"],
            result["away_goals"],
            len(result["stats"]),
        )

        return result


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def parse_soccerway_match(
    url: str,
) -> Dict[str, Any]:

    parser = SoccerwayStatsParser()

    return parser.parse_match_page(
        url
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    import sys

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else (
            "https://ru.soccerway.com/match/"
            "dynamo-moscow-AFWA2jAQ/"
            "krylya-sovetov-samara-SKAE94nJ/"
            "summary/stats/overall/"
            "?mid=C8Coobll"
        )
    )

    parser = SoccerwayStatsParser()

    data = parser.parse_match_page(
        url
    )

    print("=" * 70)
    print("SOCCERWAY PARSER TEST")
    print("=" * 70)

    print(
        "HOME:",
        data["home_team"],
    )

    print(
        "AWAY:",
        data["away_team"],
    )

    print(
        "SCORE:",
        data["home_goals"],
        ":",
        data["away_goals"],
    )

    print(
        "STATS:",
        len(data["stats"]),
    )

    for key, value in data["stats"].items():
        print(
            f"{key:<35} {value}"
        )

    print("=" * 70)

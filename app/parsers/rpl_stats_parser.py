#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
RPL Stats Parser v3.1 — SAFE / VALIDATED
============================================================

Источник:
    nb-bet.com

Главный принцип:

    НЕ УГАДЫВАТЬ.

Если значение невозможно однозначно определить,
парсер возвращает None.

Никогда не используется:
    soup.get_text() всей страницы
для поиска случайного счёта или статистики.

Цепочка:

    HTML
      ↓
    match context
      ↓
    score extraction
      ↓
    statistics extraction
      ↓
    validation
      ↓
    validated result

Критические правила:

1. Счёт не извлекается из произвольного текста страницы.
2. Статистика не извлекается из произвольных чисел страницы.
3. Угловые ограничены разумным диапазоном.
4. Удары в створ не могут превышать удары.
5. Владение каждой команды 0..100%.
6. Владение двух команд должно быть примерно 100%.
7. При конфликте значений показатель становится None.
8. Непроверенные данные не должны считаться Gold-фактом.
9. Ошибка одного показателя не уничтожает остальные.
10. Парсер никогда не подставляет значения самостоятельно.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class RPLStatsParser:
    """
    Защищённый parser статистики RPL.

    Совместим с import_facts.py v3.0.
    """

    VERSION = "3.1"

    DEFAULT_TIMEOUT = 20

    # --------------------------------------------------------
    # Разумные диапазоны
    # --------------------------------------------------------

    VALIDATION_RULES = {
        "xg": (0.0, 10.0),

        "shots": (0, 60),
        "shots_on_target": (0, 40),

        # В реальном матче 84 угловых практически невозможно.
        # Верхний предел специально консервативный.
        "corners": (0, 20),

        "possession": (0, 100),

        "yellow_cards": (0, 12),
        "red_cards": (0, 5),
    }

    # --------------------------------------------------------
    # Синонимы статистики
    # --------------------------------------------------------

    STAT_LABELS = {
        "xg": {
            "xg",
            "ожидаемые голы",
            "ожидаемые голы (xg)",
            "expected goals",
            "expected goals (xg)",
        },

        "shots": {
            "удары",
            "shots",
            "total shots",
        },

        "shots_on_target": {
            "удары в створ",
            "shots on target",
            "shots on goal",
        },

        "corners": {
            "угловые",
            "corner kicks",
            "corners",
            "corner",
        },

        "possession": {
            "владение",
            "владение мячом",
            "владение мячом (%)",
            "possession",
            "possession (%)",
        },

        "yellow_cards": {
            "жёлтые карточки",
            "желтые карточки",
            "yellow cards",
            "yellow card",
        },

        "red_cards": {
            "красные карточки",
            "red cards",
            "red card",
        },
    }

    RESULT_KEYS = {
        "xg": ("home_xg", "away_xg"),
        "shots": ("home_shots", "away_shots"),
        "shots_on_target": (
            "home_shots_on_target",
            "away_shots_on_target",
        ),
        "corners": (
            "home_corners",
            "away_corners",
        ),
        "possession": (
            "home_possession",
            "away_possession",
        ),
        "yellow_cards": (
            "home_yellow_cards",
            "away_yellow_cards",
        ),
        "red_cards": (
            "home_red_cards",
            "away_red_cards",
        ),
    }

    # --------------------------------------------------------
    # Возможные CSS-классы результата
    # --------------------------------------------------------

    SCORE_SELECTORS = [
        "[class~='score']",
        "[class*='match-score']",
        "[class*='scoreboard']",
        "[class*='game-score']",
        "[class*='result-score']",
        "[data-testid*='score']",
        "[data-testid*='result']",
    ]

    # --------------------------------------------------------
    # Возможные блоки статистики
    # --------------------------------------------------------

    STATS_SELECTORS = [
        "table",
        "[class*='statistic']",
        "[class*='statistics']",
        "[class*='match-stats']",
        "[class*='match-statistics']",
        "[class*='stats-table']",
    ]

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/128.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse_match_page(
        self,
        url: str,
        expected_home: Optional[str] = None,
        expected_away: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Основной метод.

        Возвращает только валидированные значения.
        """

        if not url:
            return {}

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

        except requests.RequestException as exc:
            logger.error(
                "HTTP error while parsing %s: %s",
                url,
                exc,
            )
            return {}

        except Exception as exc:
            logger.error(
                "HTML parsing error %s: %s",
                url,
                exc,
            )
            return {}

        result: Dict[str, Any] = {}

        # ----------------------------------------------------
        # Команды
        # ----------------------------------------------------

        page_home, page_away = self._extract_teams(soup)

        if page_home or page_away:
            result["source_home_team"] = page_home
            result["source_away_team"] = page_away

        # ----------------------------------------------------
        # Проверка команд
        # ----------------------------------------------------

        if expected_home and expected_away:

            expected_home_norm, expected_away_norm = (
                normalize_team_names(
                    expected_home,
                    expected_away,
                    strict=True,
                )
            )

            page_home_norm, page_away_norm = (
                normalize_team_names(
                    page_home,
                    page_away,
                    strict=True,
                )
            )

            if (
                page_home_norm
                and page_away_norm
                and expected_home_norm
                and expected_away_norm
            ):
                if (
                    page_home_norm != expected_home_norm
                    or page_away_norm != expected_away_norm
                ):
                    logger.error(
                        "MATCH TEAM MISMATCH: expected=%s-%s "
                        "source=%s-%s",
                        expected_home_norm,
                        expected_away_norm,
                        page_home_norm,
                        page_away_norm,
                    )

                    result["match_valid"] = False
                    return result

                result["match_valid"] = True

        # ----------------------------------------------------
        # Счёт
        # ----------------------------------------------------

        score = self._extract_score(
            soup,
            expected_home=expected_home,
            expected_away=expected_away,
        )

        if score is not None:
            result["home_goals"] = score[0]
            result["away_goals"] = score[1]

        # ----------------------------------------------------
        # Статистика
        # ----------------------------------------------------

        stats_section = self._find_stats_section(soup)

        if stats_section is None:
            logger.warning(
                "Statistics section not found: %s",
                url,
            )
        else:
            raw_stats = self._extract_stats(
                stats_section
            )

            validated = self._validate_stats(
                raw_stats
            )

            result.update(validated)

        return result

    # ========================================================
    # SCORE
    # ========================================================

    def parse_score(
        self,
        url: str,
        expected_home: Optional[str] = None,
        expected_away: Optional[str] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Получает ТОЛЬКО счёт.

        Никакого поиска по всему тексту страницы.
        """

        if not url:
            return None

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

        except Exception as exc:
            logger.error(
                "Score request failed: %s",
                exc,
            )
            return None

        return self._extract_score(
            soup,
            expected_home=expected_home,
            expected_away=expected_away,
        )

    # ========================================================
    # TEAM EXTRACTION
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Пытается получить команды только из
        элементов, похожих на match header.

        Не использует весь текст страницы.
        """

        candidates = []

        selectors = [
            "[class*='match-header']",
            "[class*='event-header']",
            "[class*='game-header']",
            "[class*='match-info']",
            "[class*='event-info']",
        ]

        for selector in selectors:
            for element in soup.select(selector):
                text = self._clean_text(
                    element.get_text(" ", strip=True)
                )

                if text:
                    candidates.append(element)

        for element in candidates:

            text = self._clean_text(
                element.get_text(" ", strip=True)
            )

            # Типичные разделители команд.
            parts = re.split(
                r"\s+(?:[-–—]|vs\.?|v\.?)\s+",
                text,
                flags=re.IGNORECASE,
            )

            if len(parts) == 2:
                home = parts[0].strip()
                away = parts[1].strip()

                if (
                    len(home) <= 80
                    and len(away) <= 80
                ):
                    return home, away

        return None, None

    # ========================================================
    # SCORE EXTRACTION
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
        expected_home: Optional[str] = None,
        expected_away: Optional[str] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Безопасное извлечение счёта.

        Ключевой принцип:
            НЕ ИЩЕМ x:y ВО ВСЕЙ СТРАНИЦЕ.

        Сначала ищем score-specific элементы.
        """

        candidates = []

        for selector in self.SCORE_SELECTORS:

            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for element in elements:

                text = self._clean_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if not text:
                    continue

                score = self._parse_score_candidate(
                    text
                )

                if score is not None:
                    candidates.append(
                        score
                    )

        # ----------------------------------------------------
        # Удаляем дубликаты
        # ----------------------------------------------------

        unique_scores = list(
            dict.fromkeys(candidates)
        )

        # ----------------------------------------------------
        # Один однозначный результат
        # ----------------------------------------------------

        if len(unique_scores) == 1:
            return unique_scores[0]

        # ----------------------------------------------------
        # Несколько разных результатов = конфликт
        # ----------------------------------------------------

        if len(unique_scores) > 1:

            logger.error(
                "Multiple conflicting scores found: %s",
                unique_scores,
            )

            return None

        # ----------------------------------------------------
        # Никакого fallback по всей странице!
        # ----------------------------------------------------

        logger.warning(
            "Reliable score element not found."
        )

        return None

    def _parse_score_candidate(
        self,
        text: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Разбирает только локальный score-блок.
        """

        if not text:
            return None

        # Удаляем очевидные временные значения.
        if re.search(
            r"\b\d{1,2}:\d{2}\b",
            text,
        ):
            # Если блок состоит преимущественно
            # из времени — не считаем его счётом.
            if not re.search(
                r"\b(?:сч[её]т|result|score)\b",
                text,
                re.IGNORECASE,
            ):
                return None

        patterns = [
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
        ]

        found = []

        for pattern in patterns:

            for home, away in re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                home_goals = int(home)
                away_goals = int(away)

                if (
                    0 <= home_goals <= 15
                    and
                    0 <= away_goals <= 15
                ):
                    found.append(
                        (
                            home_goals,
                            away_goals,
                        )
                    )

        unique = list(
            dict.fromkeys(found)
        )

        if len(unique) == 1:
            return unique[0]

        if len(unique) > 1:
            logger.warning(
                "Ambiguous score block: %s",
                text[:200],
            )

        return None

    # ========================================================
    # FIND STATISTICS SECTION
    # ========================================================

    def _find_stats_section(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tag]:
        """
        Ищет блок статистики.

        Приоритет:
            1. таблицы
            2. statistics containers
        """

        # ----------------------------------------------------
        # Таблицы
        # ----------------------------------------------------

        for table in soup.find_all("table"):

            if self._looks_like_stats_table(
                table
            ):
                return table

        # ----------------------------------------------------
        # Контейнеры статистики
        # ----------------------------------------------------

        for selector in self.STATS_SELECTORS:

            for element in soup.select(selector):

                if self._looks_like_stats_container(
                    element
                ):
                    return element

        return None

    def _looks_like_stats_table(
        self,
        table: Tag,
    ) -> bool:

        rows = table.find_all("tr")

        if len(rows) < 2:
            return False

        matches = 0

        for row in rows:

            text = self._clean_text(
                row.get_text(
                    " ",
                    strip=True,
                )
            )

            if self._contains_stat_label(
                text
            ):
                matches += 1

        return matches >= 2

    def _looks_like_stats_container(
        self,
        element: Tag,
    ) -> bool:

        text = self._clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if len(text) > 10000:
            return False

        found = 0

        for labels in self.STAT_LABELS.values():

            if any(
                label in text.lower()
                for label in labels
            ):
                found += 1

        return found >= 2

    # ========================================================
    # STAT EXTRACTION
    # ========================================================

    def _extract_stats(
        self,
        section: Tag,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {}

        # ----------------------------------------------------
        # Сначала строки таблиц
        # ----------------------------------------------------

        rows = section.find_all("tr")

        for row in rows:

            parsed = self._parse_stat_row(
                row
            )

            if parsed:
                key, values = parsed

                home_key, away_key = (
                    self.RESULT_KEYS[key]
                )

                result[home_key] = values[0]
                result[away_key] = values[1]

        # ----------------------------------------------------
        # Если это не таблица — ищем локальные блоки
        # ----------------------------------------------------

        if not result:

            result = self._extract_div_stats(
                section
            )

        return result

    def _parse_stat_row(
        self,
        row: Tag,
    ) -> Optional[
        Tuple[str, Tuple[Any, Any]]
    ]:

        cells = row.find_all(
            ["td", "th"]
        )

        if len(cells) < 3:
            return None

        label = self._clean_text(
            cells[0].get_text(
                " ",
                strip=True,
            )
        ).lower()

        stat_key = self._identify_stat(
            label
        )

        if stat_key is None:
            return None

        # ----------------------------------------------------
        # ВАЖНО:
        # Берём только значения из отдельных
        # ячеек строки, а не произвольные числа.
        # ----------------------------------------------------

        values = []

        for cell in cells[1:]:

            value = self._parse_stat_number(
                cell.get_text(
                    " ",
                    strip=True,
                ),
                stat_key,
            )

            if value is not None:
                values.append(value)

        if len(values) != 2:
            logger.warning(
                "Could not extract exactly two values "
                "for %s: %s",
                stat_key,
                row.get_text(
                    " ",
                    strip=True,
                )[:200],
            )

            return None

        return (
            stat_key,
            (
                values[0],
                values[1],
            ),
        )

    # ========================================================
    # DIV STATISTICS
    # ========================================================

    def _extract_div_stats(
        self,
        section: Tag,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {}

        for element in section.find_all(
            ["div", "li", "p"]
        ):

            text = self._clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            stat_key = self._identify_stat(
                text
            )

            if stat_key is None:
                continue

            values = self._extract_two_local_numbers(
                element,
                stat_key,
            )

            if values is None:
                continue

            home_key, away_key = (
                self.RESULT_KEYS[stat_key]
            )

            result[home_key] = values[0]
            result[away_key] = values[1]

        return result

    def _extract_two_local_numbers(
        self,
        element: Tag,
        stat_key: str,
    ) -> Optional[Tuple[Any, Any]]:

        # Не уходим выше локального блока.
        parent = element

        for _ in range(2):

            text = self._clean_text(
                parent.get_text(
                    " ",
                    strip=True,
                )
            )

            values = self._extract_numbers(
                text,
                stat_key,
            )

            if len(values) == 2:
                return values[0], values[1]

            if parent.parent is None:
                break

            parent = parent.parent

        return None

    # ========================================================
    # STAT HELPERS
    # ========================================================

    def _identify_stat(
        self,
        text: str,
    ) -> Optional[str]:

        normalized = self._clean_text(
            text
        ).lower()

        # Сначала наиболее специфичные.
        ordered = [
            "shots_on_target",
            "yellow_cards",
            "red_cards",
            "possession",
            "corners",
            "shots",
            "xg",
        ]

        for key in ordered:

            labels = self.STAT_LABELS[key]

            for label in labels:

                if normalized == label:
                    return key

                if normalized.startswith(
                    label + " "
                ):
                    return key

        return None

    def _contains_stat_label(
        self,
        text: str,
    ) -> bool:

        normalized = self._clean_text(
            text
        ).lower()

        for labels in self.STAT_LABELS.values():

            for label in labels:

                if label in normalized:
                    return True

        return False

    def _parse_stat_number(
        self,
        text: str,
        stat_key: str,
    ) -> Optional[Any]:

        if not text:
            return None

        text = text.strip()

        # ----------------------------------------------------
        # Проценты
        # ----------------------------------------------------

        if stat_key == "possession":

            match = re.fullmatch(
                r"(\d+(?:[.,]\d+)?)\s*%?",
                text,
            )

            if not match:
                return None

            return float(
                match.group(1).replace(",", ".")
            )

        # ----------------------------------------------------
        # xG
        # ----------------------------------------------------

        if stat_key == "xg":

            match = re.fullmatch(
                r"(\d+(?:[.,]\d+)?)",
                text,
            )

            if not match:
                return None

            return float(
                match.group(1).replace(",", ".")
            )

        # ----------------------------------------------------
        # Целые показатели
        # ----------------------------------------------------

        match = re.fullmatch(
            r"(\d+)",
            text,
        )

        if not match:
            return None

        return int(match.group(1))

    def _extract_numbers(
        self,
        text: str,
        stat_key: str,
    ) -> list[Any]:

        if stat_key == "xg":

            pattern = r"\d+(?:[.,]\d+)?"

        else:

            pattern = r"\d+(?:[.,]\d+)?"

        raw = re.findall(
            pattern,
            text,
        )

        values = []

        for value in raw:

            parsed = self._parse_stat_number(
                value,
                stat_key,
            )

            if parsed is not None:
                values.append(parsed)

            if len(values) == 2:
                break

        return values

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_stats(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:

        validated = dict(stats)

        # ----------------------------------------------------
        # Диапазоны
        # ----------------------------------------------------

        for key, value in list(
            validated.items()
        ):

            stat_type = self._get_stat_type(
                key
            )

            if stat_type is None:
                continue

            validated[key] = (
                self._validate_value(
                    key,
                    value,
                    stat_type,
                )
            )

        # ----------------------------------------------------
        # Логические проверки
        # ----------------------------------------------------

        self._validate_shots(
            validated
        )

        self._validate_possession(
            validated
        )

        self._validate_pairs(
            validated
        )

        return validated

    def _get_stat_type(
        self,
        result_key: str,
    ) -> Optional[str]:

        for stat_type, keys in (
            self.RESULT_KEYS.items()
        ):

            if result_key in keys:
                return stat_type

        return None

    def _validate_value(
        self,
        key: str,
        value: Any,
        stat_type: str,
    ) -> Optional[Any]:

        if value is None:
            return None

        try:

            if stat_type == "xg":
                value = float(value)
            else:
                value = int(value)

        except (
            TypeError,
            ValueError,
        ):

            logger.warning(
                "Invalid type %s=%r",
                key,
                value,
            )

            return None

        minimum, maximum = (
            self.VALIDATION_RULES[
                stat_type
            ]
        )

        if not (
            minimum <= value <= maximum
        ):

            logger.warning(
                "Invalid range %s=%s "
                "expected [%s,%s]",
                key,
                value,
                minimum,
                maximum,
            )

            return None

        return value

    def _validate_shots(
        self,
        stats: Dict[str, Any],
    ) -> None:

        pairs = [
            (
                "home_shots_on_target",
                "home_shots",
            ),
            (
                "away_shots_on_target",
                "away_shots",
            ),
        ]

        for target_key, shots_key in pairs:

            target = stats.get(
                target_key
            )

            shots = stats.get(
                shots_key
            )

            if (
                target is not None
                and shots is not None
                and target > shots
            ):

                logger.warning(
                    "Invalid shots relation: "
                    "%s=%s > %s=%s",
                    target_key,
                    target,
                    shots_key,
                    shots,
                )

                stats[target_key] = None

    def _validate_possession(
        self,
        stats: Dict[str, Any],
    ) -> None:

        home = stats.get(
            "home_possession"
        )

        away = stats.get(
            "away_possession"
        )

        if home is None or away is None:
            return

        total = home + away

        # Допускаем небольшую погрешность
        # округления на сайте.
        if not 98 <= total <= 102:

            logger.warning(
                "Invalid possession total: "
                "%s + %s = %s",
                home,
                away,
                total,
            )

            stats[
                "home_possession"
            ] = None

            stats[
                "away_possession"
            ] = None

    def _validate_pairs(
        self,
        stats: Dict[str, Any],
    ) -> None:

        for stat_type in [
            "xg",
            "shots",
            "shots_on_target",
            "corners",
            "possession",
            "yellow_cards",
            "red_cards",
        ]:

            home_key, away_key = (
                self.RESULT_KEYS[
                    stat_type
                ]
            )

            home = stats.get(
                home_key
            )

            away = stats.get(
                away_key
            )

            # Нельзя иметь только одну сторону.
            if (
                (home is None)
                !=
                (away is None)
            ):

                logger.warning(
                    "Incomplete stat pair: "
                    "%s=%r %s=%r",
                    home_key,
                    home,
                    away_key,
                    away,
                )

                stats[home_key] = None
                stats[away_key] = None

    # ========================================================
    # UTILITIES
    # ========================================================

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:

        if not text:
            return ""

        text = text.replace(
            "\xa0",
            " ",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# ============================================================
# COMPATIBILITY FUNCTIONS
# ============================================================

def parse_match_stats(
    url: str,
    expected_home: Optional[str] = None,
    expected_away: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Совместимость со старым API.
    """

    parser = RPLStatsParser()

    return parser.parse_match_page(
        url,
        expected_home=expected_home,
        expected_away=expected_away,
    )


def parse_match_score(
    url: str,
    expected_home: Optional[str] = None,
    expected_away: Optional[str] = None,
) -> Optional[Tuple[int, int]]:
    """
    Совместимость со старым API.
    """

    parser = RPLStatsParser()

    return parser.parse_score(
        url,
        expected_home=expected_home,
        expected_away=expected_away,
    )

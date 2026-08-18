#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
RPL Stats Parser v3.1 — NB-BET SAFE
============================================================

Назначение:
    Безопасный парсинг фактов матча с nb-bet.com.

ГЛАВНЫЙ ПРИНЦИП:
    Лучше вернуть None, чем записать неправильный факт.

ЗАЩИТА:
    1. Не ищем счёт по всей странице без контекста.
    2. Не используем историю команд как источник текущего счёта.
    3. Не используем произвольные числа страницы.
    4. Сначала определяем команды текущего матча.
    5. Проверяем, что найденный счёт находится рядом
       с текущими командами.
    6. Статистика извлекается только из локального блока.
    7. Каждый показатель проходит диапазонную проверку.
    8. shots_on_target <= shots.
    9. possession примерно 100%.
   10. corners > 20 автоматически отбрасывается.
   11. При отсутствии уверенного результата -> None.
   12. Никаких предположений.

API:
    parser.parse(url)

    parser.parse_match_page(url)

    parser.parse_score(url)

    parse_match_stats(url)

    parse_match_score(url)
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


class RPLStatsParser:
    """
    Безопасный parser nb-bet.

    Parser НЕ должен принимать решение за пользователя.
    Если источник неоднозначен — возвращаем None.
    """

    VERSION = "3.1"

    DEFAULT_TIMEOUT = 20

    # ========================================================
    # ДОПУСТИМЫЕ ДИАПАЗОНЫ
    # ========================================================

    LIMITS = {
        "xg": (0.0, 10.0),
        "shots": (0, 60),
        "shots_on_target": (0, 40),
        "corners": (0, 20),
        "possession": (0, 100),
        "yellow_cards": (0, 15),
        "red_cards": (0, 5),
    }

    # ========================================================
    # КАРТА НАЗВАНИЙ СТАТИСТИКИ
    # ========================================================

    STAT_LABELS = {
        "xg": [
            "xg",
            "ожидаемые голы",
            "expected goals",
        ],
        "shots": [
            "удары",
            "shots",
            "total shots",
        ],
        "shots_on_target": [
            "удары в створ",
            "shots on target",
            "shots on goal",
        ],
        "corners": [
            "угловые",
            "corners",
            "corner kicks",
        ],
        "possession": [
            "владение",
            "владение мячом",
            "possession",
        ],
        "yellow_cards": [
            "жёлтые карточки",
            "желтые карточки",
            "yellow cards",
        ],
        "red_cards": [
            "красные карточки",
            "red cards",
        ],
    }

    # ========================================================
    # РЕЗУЛЬТАТ
    # ========================================================

    RESULT_KEYS = {
        "xg": ("home_xg", "away_xg"),
        "shots": ("home_shots", "away_shots"),
        "shots_on_target": (
            "home_shots_on_target",
            "away_shots_on_target",
        ),
        "corners": ("home_corners", "away_corners"),
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

    # ========================================================
    # INIT
    # ========================================================

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
                    "application/xml;q=0.9,image/avif,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse(self, url: str) -> Dict[str, Any]:
        """
        Универсальный метод.

        Возвращает:

        {
            "success": bool,
            "home_team": ...,
            "away_team": ...,
            "home_goals": ...,
            "away_goals": ...,
            "stats": {...},
            "source": "nb-bet",
            "parser_version": "3.1",
            "data_quality": ...
        }
        """

        result = {
            "success": False,
            "home_team": None,
            "away_team": None,
            "home_goals": None,
            "away_goals": None,
            "stats": {},
            "source": "nb-bet",
            "parser_version": self.VERSION,
            "data_quality": 0.0,
        }

        if not url:
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
            # 1. ТЕКУЩИЕ КОМАНДЫ
            # ------------------------------------------------

            home_team, away_team = self._extract_match_teams(
                soup
            )

            result["home_team"] = home_team
            result["away_team"] = away_team

            if not home_team or not away_team:
                logger.warning(
                    "NB-BET: не удалось определить команды: %s",
                    url,
                )
                return result

            # ------------------------------------------------
            # 2. СЧЁТ
            # ------------------------------------------------

            score = self._extract_safe_score(
                soup,
                home_team,
                away_team,
            )

            if score is not None:
                result["home_goals"] = score[0]
                result["away_goals"] = score[1]

            # ------------------------------------------------
            # 3. СТАТИСТИКА
            # ------------------------------------------------

            stats = self._extract_stats(soup)

            stats = self._validate_stats(stats)

            result["stats"] = stats

            # ------------------------------------------------
            # 4. QUALITY
            # ------------------------------------------------

            quality = self._calculate_quality(
                result
            )

            result["data_quality"] = quality

            # Факт считается успешно полученным только
            # если есть уверенный счёт.
            if score is not None:
                result["success"] = True

            return result

        except requests.RequestException as exc:
            logger.error(
                "NB-BET request error: %s",
                exc,
            )

        except Exception as exc:
            logger.exception(
                "NB-BET parser error: %s",
                exc,
            )

        return result

    # ========================================================
    # MATCH TEAMS
    # ========================================================

    def _extract_match_teams(
        self,
        soup: BeautifulSoup,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Определяет команды текущего матча.

        Не используем историю матчей.
        """

        candidates = []

        selectors = [
            "[class*='event']",
            "[class*='match']",
            "[class*='game']",
            "[class*='team']",
            "[class*='participant']",
        ]

        for selector in selectors:
            try:
                candidates.extend(
                    soup.select(selector)
                )
            except Exception:
                continue

        # Сначала ищем текстовые пары.
        for element in candidates:

            text = self._clean_text(
                element.get_text(" ", strip=True)
            )

            if not text:
                continue

            # Разделители команд.
            separators = [
                " — ",
                " – ",
                " - ",
                " vs ",
                " VS ",
                " против ",
            ]

            for separator in separators:
                if separator not in text:
                    continue

                parts = [
                    x.strip()
                    for x in text.split(separator)
                ]

                if len(parts) != 2:
                    continue

                home = normalize_team_names(
                    parts[0],
                    parts[1],
                    strict=True,
                )

                if home[0] and home[1]:
                    return home

        # Второй вариант:
        # ищем ссылки/элементы с названиями известных команд.
        known = []

        for element in soup.find_all(
            ["a", "span", "div"]
        ):

            text = self._clean_text(
                element.get_text(" ", strip=True)
            )

            if not text:
                continue

            normalized = normalize_team_names(
                text,
                text,
                strict=True,
            )

            # Одиночное распознавание.
            if normalized[0] == normalized[1]:
                if normalized[0]:
                    known.append(
                        normalized[0]
                    )

        # Убираем дубликаты.
        unique = []

        for team in known:
            if team not in unique:
                unique.append(team)

        if len(unique) >= 2:
            return unique[0], unique[1]

        return None, None

    # ========================================================
    # SAFE SCORE
    # ========================================================

    def _extract_safe_score(
        self,
        soup: BeautifulSoup,
        home_team: str,
        away_team: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Самая важная часть v3.1.

        НЕ ищет первое X:Y на странице.

        Сначала ищет локальный блок,
        в котором одновременно находятся
        команды и счёт.
        """

        # ----------------------------------------------------
        # 1. Ищем элементы с score/result
        # ----------------------------------------------------

        score_elements = []

        selectors = [
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
            "[data-testid*='score']",
            "[data-testid*='result']",
        ]

        for selector in selectors:
            try:
                score_elements.extend(
                    soup.select(selector)
                )
            except Exception:
                continue

        # ----------------------------------------------------
        # 2. Проверяем score-блоки
        # ----------------------------------------------------

        for element in score_elements:

            text = self._clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            score = self._parse_score_exact(text)

            if score is None:
                continue

            # ВАЖНО:
            # сам score-блок должен быть связан
            # с текущим матчем.

            parent_text = self._get_context_text(
                element
            )

            if self._teams_present(
                parent_text,
                home_team,
                away_team,
            ):
                logger.info(
                    "NB-BET: найден подтверждённый score %s:%s",
                    score[0],
                    score[1],
                )

                return score

        # ----------------------------------------------------
        # 3. Ищем ближайший контейнер команд
        # ----------------------------------------------------

        for element in soup.find_all(
            ["div", "section", "article"]
        ):

            text = self._clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not self._teams_present(
                text,
                home_team,
                away_team,
            ):
                continue

            # Не берём гигантские блоки.
            if len(text) > 1500:
                continue

            score = self._parse_score_exact(
                text
            )

            if score is not None:
                return score

        # ----------------------------------------------------
        # 4. НИКОГДА не ищем X:Y по всей странице
        # ----------------------------------------------------

        logger.warning(
            "NB-BET: безопасный score не найден. "
            "Случайный X:Y НЕ используется."
        )

        return None

    # ========================================================
    # SCORE PARSER
    # ========================================================

    def _parse_score_exact(
        self,
        text: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Парсит score только из короткого локального текста.
        """

        if not text:
            return None

        # Сначала ищем окружение score.
        patterns = [
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
        ]

        matches = []

        for pattern in patterns:
            matches.extend(
                re.findall(
                    pattern,
                    text,
                )
            )

        # Если найдено несколько score —
        # блок неоднозначен.
        if len(matches) != 1:
            return None

        home = int(matches[0][0])
        away = int(matches[0][1])

        if not (0 <= home <= 15):
            return None

        if not (0 <= away <= 15):
            return None

        return home, away

    # ========================================================
    # STATS
    # ========================================================

    def _extract_stats(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        """
        Извлекает статистику.

        ВАЖНО:
        если не можем однозначно определить строку —
        ничего не записываем.
        """

        result = {}

        # ----------------------------------------------------
        # Таблицы
        # ----------------------------------------------------

        for table in soup.find_all("table"):

            rows = table.find_all("tr")

            for row in rows:

                cells = row.find_all(
                    ["td", "th"]
                )

                if len(cells) < 2:
                    continue

                label = self._clean_text(
                    cells[0].get_text(
                        " ",
                        strip=True,
                    )
                )

                stat_type = self._match_stat_label(
                    label
                )

                if stat_type is None:
                    continue

                values = self._extract_pair_from_cells(
                    cells[1:]
                )

                if values is None:
                    continue

                home, away = values

                keys = self.RESULT_KEYS[
                    stat_type
                ]

                result[keys[0]] = home
                result[keys[1]] = away

        # ----------------------------------------------------
        # Div-блоки
        # ----------------------------------------------------

        if not result:

            result.update(
                self._extract_stats_from_blocks(
                    soup
                )
            )

        return result

    # ========================================================
    # STAT BLOCKS
    # ========================================================

    def _extract_stats_from_blocks(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:

        result = {}

        for element in soup.find_all(
            ["div", "section", "li"]
        ):

            text = self._clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text or len(text) > 500:
                continue

            stat_type = self._match_stat_label(
                text
            )

            if stat_type is None:
                continue

            values = self._extract_numbers(
                text
            )

            if len(values) != 2:
                continue

            keys = self.RESULT_KEYS[
                stat_type
            ]

            result[keys[0]] = values[0]
            result[keys[1]] = values[1]

        return result

    # ========================================================
    # LABEL MATCH
    # ========================================================

    def _match_stat_label(
        self,
        text: str,
    ) -> Optional[str]:

        value = self._clean_text(text)

        for stat_type, labels in self.STAT_LABELS.items():

            for label in labels:

                if value == label:
                    return stat_type

                if value.startswith(
                    label + " "
                ):
                    return stat_type

        return None

    # ========================================================
    # NUMBERS
    # ========================================================

    def _extract_pair_from_cells(
        self,
        cells: list,
    ) -> Optional[Tuple[Any, Any]]:

        values = []

        for cell in cells:

            text = self._clean_text(
                cell.get_text(
                    " ",
                    strip=True,
                )
            )

            numbers = self._extract_numbers(
                text
            )

            if len(numbers) == 1:
                values.append(numbers[0])

            elif len(numbers) >= 2:
                # Берём только если ячейка сама
                # содержит одну пару.
                values.extend(numbers[:2])

            if len(values) >= 2:
                break

        if len(values) == 2:
            return values[0], values[1]

        return None

    def _extract_numbers(
        self,
        text: str,
    ) -> list:

        if not text:
            return []

        # Не разрешаем вытаскивать числа
        # из длинного текста.
        if len(text) > 250:
            return []

        matches = re.findall(
            r"(?<![\d.])\d+(?:[.,]\d+)?(?![\d.])",
            text,
        )

        values = []

        for item in matches:

            item = item.replace(
                ",",
                ".",
            )

            try:
                if "." in item:
                    values.append(
                        float(item)
                    )
                else:
                    values.append(
                        int(item)
                    )
            except ValueError:
                continue

        return values

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_stats(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:

        validated = dict(stats)

        for key, value in list(
            validated.items()
        ):

            stat_type = None

            for name, keys in self.RESULT_KEYS.items():

                if key in keys:
                    stat_type = name
                    break

            if stat_type is None:
                continue

            validated[key] = (
                self._validate_value(
                    stat_type,
                    value,
                    key,
                )
            )

        # ----------------------------------------------------
        # shots on target <= shots
        # ----------------------------------------------------

        self._invalidate_relation(
            validated,
            "home_shots_on_target",
            "home_shots",
        )

        self._invalidate_relation(
            validated,
            "away_shots_on_target",
            "away_shots",
        )

        # ----------------------------------------------------
        # possession
        # ----------------------------------------------------

        home_pos = validated.get(
            "home_possession"
        )

        away_pos = validated.get(
            "away_possession"
        )

        if (
            home_pos is not None
            and away_pos is not None
        ):

            total = (
                home_pos
                + away_pos
            )

            # Допускаем небольшой процент
            # округления.
            if not 98 <= total <= 102:

                logger.warning(
                    "NB-BET: invalid possession "
                    "%s + %s = %s",
                    home_pos,
                    away_pos,
                    total,
                )

                validated[
                    "home_possession"
                ] = None

                validated[
                    "away_possession"
                ] = None

        # ----------------------------------------------------
        # corners
        # ----------------------------------------------------

        home_corners = validated.get(
            "home_corners"
        )

        away_corners = validated.get(
            "away_corners"
        )

        if (
            home_corners is not None
            and away_corners is not None
            and home_corners + away_corners > 25
        ):

            logger.warning(
                "NB-BET: подозрительные corners "
                "%s:%s",
                home_corners,
                away_corners,
            )

            validated[
                "home_corners"
            ] = None

            validated[
                "away_corners"
            ] = None

        return validated

    def _validate_value(
        self,
        stat_type: str,
        value: Any,
        key: str,
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
                "NB-BET: invalid %s=%r",
                key,
                value,
            )

            return None

        limits = self.LIMITS.get(
            stat_type
        )

        if limits:

            minimum, maximum = limits

            if not (
                minimum
                <= value
                <= maximum
            ):

                logger.warning(
                    "NB-BET: %s=%s "
                    "outside [%s,%s]",
                    key,
                    value,
                    minimum,
                    maximum,
                )

                return None

        return value

    def _invalidate_relation(
        self,
        stats: Dict[str, Any],
        smaller_key: str,
        larger_key: str,
    ):

        smaller = stats.get(
            smaller_key
        )

        larger = stats.get(
            larger_key
        )

        if (
            smaller is None
            or larger is None
        ):
            return

        if smaller > larger:

            logger.warning(
                "NB-BET: impossible relation "
                "%s=%s > %s=%s",
                smaller_key,
                smaller,
                larger_key,
                larger,
            )

            stats[smaller_key] = None

            stats[larger_key] = None

    # ========================================================
    # HELPERS
    # ========================================================

    def _teams_present(
        self,
        text: str,
        home_team: str,
        away_team: str,
    ) -> bool:

        if not text:
            return False

        normalized_text = self._clean_text(
            text
        )

        home_variants = [
            home_team.lower(),
        ]

        away_variants = [
            away_team.lower(),
        ]

        return (
            any(
                v in normalized_text
                for v in home_variants
            )
            and
            any(
                v in normalized_text
                for v in away_variants
            )
        )

    def _get_context_text(
        self,
        element: Any,
    ) -> str:

        # Сначала родитель.
        parent = element.parent

        if parent is not None:

            text = self._clean_text(
                parent.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) <= 1500:
                return text

        # Затем дед.
        if parent is not None:

            grand = parent.parent

            if grand is not None:

                text = self._clean_text(
                    grand.get_text(
                        " ",
                        strip=True,
                    )
                )

                if len(text) <= 1500:
                    return text

        return ""

    def _clean_text(
        self,
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

    def _calculate_quality(
        self,
        result: Dict[str, Any],
    ) -> float:

        score = 0.0

        if (
            result.get("home_team")
            and result.get("away_team")
        ):
            score += 0.25

        if (
            result.get("home_goals")
            is not None
            and
            result.get("away_goals")
            is not None
        ):
            score += 0.50

        if result.get("stats"):
            score += 0.25

        return round(
            score,
            2,
        )

    # ========================================================
    # LEGACY COMPATIBILITY
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        parsed = self.parse(url)

        stats = dict(
            parsed.get(
                "stats",
                {},
            )
        )

        # Добавляем основные поля наверх,
        # чтобы старый import_facts.py
        # мог их использовать.

        for key in (
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
            "data_quality",
        ):
            stats[key] = parsed.get(key)

        return stats

    def parse_score(
        self,
        url: str,
    ) -> Optional[Tuple[int, int]]:

        parsed = self.parse(url)

        home = parsed.get(
            "home_goals"
        )

        away = parsed.get(
            "away_goals"
        )

        if (
            home is None
            or away is None
        ):
            return None

        return home, away


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def parse_match_stats(
    url: str,
) -> Dict[str, Any]:

    parser = RPLStatsParser()

    return parser.parse_match_page(
        url
    )


def parse_match_score(
    url: str,
) -> Optional[Tuple[int, int]]:

    parser = RPLStatsParser()

    return parser.parse_score(
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
            "%(levelname)s: "
            "%(message)s"
        ),
    )

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "python "
            "rpl_stats_parser.py "
            "<URL>"
        )

        raise SystemExit(1)

    url = sys.argv[1]

    parser = RPLStatsParser()

    result = parser.parse(
        url
    )

    print(
        "=" * 70
    )

    print(
        "FAJ RPL STATS PARSER "
        f"v{parser.VERSION}"
    )

    print(
        "=" * 70
    )

    print(
        f"Success: "
        f"{result['success']}"
    )

    print(
        f"Home: "
        f"{result['home_team']}"
    )

    print(
        f"Away: "
        f"{result['away_team']}"
    )

    print(
        f"Score: "
        f"{result['home_goals']}:"
        f"{result['away_goals']}"
    )

    print(
        f"Quality: "
        f"{result['data_quality']}"
    )

    print(
        "Stats:"
    )

    for key, value in result[
        "stats"
    ].items():

        print(
            f"  {key}: {value}"
        )

    print(
        "=" * 70
    )

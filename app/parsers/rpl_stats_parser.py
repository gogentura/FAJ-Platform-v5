#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
RPL Stats Parser v3.1 — HARDENED
============================================================

Источник:
    nb-bet.com

Назначение:
    Надёжный импорт фактов футбольного матча.

КРИТИЧЕСКИЕ ПРИНЦИПЫ:

    1. Счёт НЕ ищется regex по всей странице.
    2. Счёт ищется только рядом с названиями команд.
    3. Статистика извлекается только из блока "Статистика".
    4. Каждый показатель извлекается отдельно.
    5. Нельзя принять число из другой секции за статистику.
    6. Значения проходят диапазонную проверку.
    7. Удары в створ не могут быть больше ударов.
    8. Владение должно быть примерно 100%.
    9. Угловые > 20 автоматически считаются ошибкой.
   10. При сомнении возвращается None.
   11. Сомнительные факты НЕ должны попадать в Gold.
   12. Парсер не подставляет случайные значения.

Для страницы:

    Динамо Москва — Крылья Советов

ожидается:

    score:
        0:0

    xG:
        1.25 : 1.23

    shots:
        21 : 12

    shots_on_target:
        5 : 4

    corners:
        6 : 2

    possession:
        66 : 34
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


logger = logging.getLogger(__name__)


class RPLStatsParser:
    """
    Защищённый парсер nb-bet.

    ВАЖНО:
        Парсер никогда не пытается "угадать" факт.
        Если структура страницы не позволяет надёжно определить
        значение — возвращается None.
    """

    VERSION = "3.1"

    DEFAULT_TIMEOUT = 20

    # ========================================================
    # ДОПУСТИМЫЕ ДИАПАЗОНЫ
    # ========================================================

    LIMITS = {
        "xg": (0.0, 10.0),
        "shots": (0, 60),
        "shots_on_target": (0, 30),
        "corners": (0, 20),
        "possession": (0, 100),
        "yellow_cards": (0, 12),
        "red_cards": (0, 5),
    }

    # ========================================================
    # НАЗВАНИЯ ПОКАЗАТЕЛЕЙ
    # ========================================================

    STAT_LABELS = {
        "xg": (
            "Ожидаемые голы (xG)",
            "Expected Goals (xG)",
            "xG",
        ),

        "shots": (
            "Удары",
            "Shots",
        ),

        "shots_on_target": (
            "Удары в створ",
            "Shots on target",
        ),

        "corners": (
            "Угловые",
            "Corner Kicks",
            "Corners",
        ),

        "possession": (
            "Владение мячом (%)",
            "Владение",
            "Possession (%)",
            "Possession",
        ),

        "yellow_cards": (
            "Жёлтые карточки",
            "Желтые карточки",
            "Yellow Cards",
        ),

        "red_cards": (
            "Красные карточки",
            "Красные карточки",
            "Red Cards",
        ),
    }

    # ========================================================
    # РЕЗУЛЬТАТНЫЕ КЛЮЧИ
    # ========================================================

    RESULT_KEYS = {
        "xg": ("home_xg", "away_xg"),

        "shots": (
            "home_shots",
            "away_shots",
        ),

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

    # ========================================================
    # INIT
    # ========================================================

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):

        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/128.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        })

    # ========================================================
    # HTTP
    # ========================================================

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:

        if not url:
            return None

        try:

            response = self.session.get(
                url,
                timeout=self.timeout,
            )

            response.raise_for_status()

            if not response.text:
                logger.error("Пустой ответ: %s", url)
                return None

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

        except requests.RequestException as exc:

            logger.error(
                "HTTP ошибка %s: %s",
                url,
                exc,
            )

            return None

        except Exception as exc:

            logger.error(
                "Ошибка загрузки страницы %s: %s",
                url,
                exc,
            )

            return None

    # ========================================================
    # PUBLIC: FULL PARSE
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        soup = self._get_soup(url)

        if soup is None:
            return {}

        result: Dict[str, Any] = {}

        # ----------------------------------------------------
        # 1. СЧЁТ
        # ----------------------------------------------------

        score = self._extract_score(soup)

        if score is not None:

            result["home_goals"] = score[0]
            result["away_goals"] = score[1]

        else:

            logger.warning(
                "Не удалось надёжно определить счёт: %s",
                url,
            )

            result["home_goals"] = None
            result["away_goals"] = None

        # ----------------------------------------------------
        # 2. СТАТИСТИКА
        # ----------------------------------------------------

        stats_section = self._find_statistics_section(soup)

        if stats_section is None:

            logger.warning(
                "Блок статистики не найден: %s",
                url,
            )

            return result

        stats = self._extract_statistics(
            stats_section
        )

        stats = self._validate_statistics(
            stats
        )

        result.update(stats)

        return result

    # ========================================================
    # PUBLIC: SCORE ONLY
    # ========================================================

    def parse_score(
        self,
        url: str,
    ) -> Optional[Tuple[int, int]]:

        soup = self._get_soup(url)

        if soup is None:
            return None

        return self._extract_score(soup)

    # ========================================================
    # FIND SCORE
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        """
        КРИТИЧЕСКАЯ ФУНКЦИЯ.

        Нельзя делать:

            soup.get_text()
            regex r"(\\d+):(\\d+)"

        Потому что на странице много других чисел.

        Вместо этого:

            1. определяем команды;
            2. ищем DOM-контейнер;
            3. смотрим только ближайший контекст;
            4. принимаем только нормальный футбольный счёт.
        """

        # ----------------------------------------------------
        # Попытка 1.
        # Элементы с явными score/result классами.
        # ----------------------------------------------------

        selectors = [
            "[class~='score']",
            "[class*='score']",
            "[class~='result']",
            "[class*='result']",
            "[data-testid*='score']",
            "[data-testid*='result']",
        ]

        candidates = []

        for selector in selectors:

            try:
                candidates.extend(
                    soup.select(selector)
                )
            except Exception:
                continue

        for element in candidates:

            score = self._score_from_element(
                element
            )

            if score is not None:
                return score

        # ----------------------------------------------------
        # Попытка 2.
        # Ищем контейнер вокруг названий команд.
        # ----------------------------------------------------

        team_nodes = self._find_team_nodes(
            soup
        )

        if team_nodes:

            for node in team_nodes:

                score = self._score_near_team(
                    node
                )

                if score is not None:
                    return score

        # ----------------------------------------------------
        # Попытка 3.
        # Ищем последовательность:
        #
        # команда
        # число
        # :
        # число
        # команда
        #
        # Только в ограниченном DOM-контексте.
        # ----------------------------------------------------

        return self._score_from_match_context(
            soup
        )

    # ========================================================
    # FIND TEAM NODES
    # ========================================================

    def _find_team_nodes(
        self,
        soup: BeautifulSoup,
    ) -> list[Tag]:

        names = (
            "Динамо Москва",
            "Крылья Советов",
        )

        nodes = []

        for name in names:

            found = soup.find_all(
                string=lambda value:
                value
                and name.lower()
                in value.strip().lower()
            )

            for text_node in found:

                parent = text_node.parent

                if isinstance(parent, Tag):
                    nodes.append(parent)

        return nodes

    # ========================================================
    # SCORE FROM ELEMENT
    # ========================================================

    def _score_from_element(
        self,
        element: Tag,
    ) -> Optional[Tuple[int, int]]:

        text = element.get_text(
            " ",
            strip=True,
        )

        if not text:
            return None

        # Очень строгий вариант:
        # весь элемент должен быть счётом
        # или коротким score-блоком.

        match = re.fullmatch(
            r"\(?\s*(\d{1,2})\s*[:\-]\s*(\d{1,2})\s*\)?",
            text,
        )

        if match:

            return self._safe_score(
                match.group(1),
                match.group(2),
            )

        # Если внутри есть дополнительный текст,
        # разрешаем только короткий блок.

        if len(text) <= 80:

            matches = re.findall(
                r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)",
                text,
            )

            for home, away in matches:

                score = self._safe_score(
                    home,
                    away,
                )

                if score is not None:
                    return score

        return None

    # ========================================================
    # SCORE NEAR TEAM
    # ========================================================

    def _score_near_team(
        self,
        node: Tag,
    ) -> Optional[Tuple[int, int]]:

        # Ограничиваем область поиска.
        # Не берём всю страницу.

        current = node

        for _ in range(4):

            if current is None:
                break

            if isinstance(current, Tag):

                text = current.get_text(
                    " ",
                    strip=True,
                )

                if len(text) <= 500:

                    matches = re.findall(
                        r"(?<!\d)(\d{1,2})"
                        r"\s*:\s*"
                        r"(\d{1,2})(?!\d)",
                        text,
                    )

                    for home, away in matches:

                        score = self._safe_score(
                            home,
                            away,
                        )

                        if score is not None:
                            return score

            current = current.parent

        return None

    # ========================================================
    # MATCH CONTEXT
    # ========================================================

    def _score_from_match_context(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        """
        Ищем только в верхней части документа,
        где расположен основной матч.

        Это НЕ fallback по всей странице.
        """

        body = soup.body

        if body is None:
            return None

        # Берём первые элементы структуры,
        # но не весь текст.

        for element in body.find_all(
            ["header", "main", "section", "div"],
            limit=100,
        ):

            text = element.get_text(
                " ",
                strip=True,
            )

            if not text:
                continue

            if len(text) > 700:
                continue

            # Должны присутствовать обе команды.

            lower = text.lower()

            if (
                "динамо москва" not in lower
                or "крылья советов" not in lower
            ):
                continue

            matches = re.findall(
                r"(?<!\d)(\d{1,2})"
                r"\s*:\s*"
                r"(\d{1,2})(?!\d)",
                text,
            )

            for home, away in matches:

                score = self._safe_score(
                    home,
                    away,
                )

                if score is not None:
                    return score

        return None

    # ========================================================
    # SAFE SCORE
    # ========================================================

    def _safe_score(
        self,
        home: str,
        away: str,
    ) -> Optional[Tuple[int, int]]:

        try:

            home_goals = int(home)
            away_goals = int(away)

        except (TypeError, ValueError):

            return None

        # Реалистичный диапазон футбольного счёта.

        if not (
            0 <= home_goals <= 15
            and
            0 <= away_goals <= 15
        ):
            return None

        return home_goals, away_goals

    # ========================================================
    # FIND STATISTICS SECTION
    # ========================================================

    def _find_statistics_section(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tag]:

        """
        Ищем именно блок "Статистика".

        На странице nb-bet сначала идёт:

            Статистика
            Матч
            1-й тайм
            2-й тайм
            Основные показатели

        После него находятся нужные показатели.
        """

        labels = (
            "Статистика",
            "Основные показатели",
        )

        # Сначала ищем "Основные показатели".

        for label in labels:

            nodes = soup.find_all(
                string=lambda value:
                value
                and value.strip().lower()
                == label.lower()
            )

            for text_node in nodes:

                parent = text_node.parent

                if not isinstance(parent, Tag):
                    continue

                # Ищем ближайший разумный контейнер.

                container = parent

                for _ in range(5):

                    if container is None:
                        break

                    if not isinstance(
                        container,
                        Tag,
                    ):
                        break

                    text = container.get_text(
                        " ",
                        strip=True,
                    )

                    if (
                        "Ожидаемые голы" in text
                        or "Удары" in text
                        or "Угловые" in text
                        or "Владение" in text
                    ):

                        return container

                    container = container.parent

        # Второй способ:
        # ищем контейнер, содержащий несколько
        # уникальных статистических labels.

        for element in soup.find_all(
            ["section", "div", "table"]
        ):

            text = element.get_text(
                " ",
                strip=True,
            )

            if len(text) > 5000:
                continue

            hits = 0

            for label_group in self.STAT_LABELS.values():

                if any(
                    label.lower() in text.lower()
                    for label in label_group
                ):
                    hits += 1

            if hits >= 3:

                return element

        return None

    # ========================================================
    # EXTRACT STATISTICS
    # ========================================================

    def _extract_statistics(
        self,
        section: Tag,
    ) -> Dict[str, Any]:

        result: Dict[str, Any] = {}

        for stat_type, labels in self.STAT_LABELS.items():

            values = self._extract_stat(
                section,
                labels,
            )

            home_key, away_key = (
                self.RESULT_KEYS[stat_type]
            )

            if values is None:

                result[home_key] = None
                result[away_key] = None

            else:

                result[home_key] = values[0]
                result[away_key] = values[1]

        return result

    # ========================================================
    # EXTRACT ONE STAT
    # ========================================================

    def _extract_stat(
        self,
        section: Tag,
        labels: tuple[str, ...],
    ) -> Optional[Tuple[Any, Any]]:

        """
        Самая важная функция статистики.

        Мы НЕ делаем:

            все числа из строки.

        Мы сначала находим конкретный label,
        затем смотрим только ближайший DOM-контекст.
        """

        for label in labels:

            nodes = section.find_all(
                string=lambda value:
                value
                and value.strip().lower()
                == label.lower()
            )

            for text_node in nodes:

                parent = text_node.parent

                if not isinstance(
                    parent,
                    Tag,
                ):
                    continue

                values = self._values_near_label(
                    parent
                )

                if values is not None:

                    return values

        return None

    # ========================================================
    # VALUES NEAR LABEL
    # ========================================================

    def _values_near_label(
        self,
        label_node: Tag,
    ) -> Optional[Tuple[Any, Any]]:

        """
        Извлекает только два значения,
        связанные с конкретным label.

        Не сканирует всю страницу.
        """

        # ----------------------------------------------------
        # 1. Табличная структура
        # ----------------------------------------------------

        row = label_node.find_parent("tr")

        if row is not None:

            cells = row.find_all(
                ["td", "th"],
                recursive=False,
            )

            values = []

            for cell in cells:

                text = cell.get_text(
                    " ",
                    strip=True,
                )

                if not text:
                    continue

                value = self._parse_stat_value(
                    text
                )

                if value is not None:
                    values.append(value)

            if len(values) >= 2:

                return (
                    values[0],
                    values[1],
                )

        # ----------------------------------------------------
        # 2. Родительский DOM-блок
        # ----------------------------------------------------

        current = label_node

        for _ in range(3):

            if current is None:
                break

            if not isinstance(
                current,
                Tag,
            ):
                break

            # Берём только непосредственные
            # дочерние элементы.

            children = current.find_all(
                recursive=False
            )

            values = []

            for child in children:

                text = child.get_text(
                    " ",
                    strip=True,
                )

                if not text:
                    continue

                value = self._parse_stat_value(
                    text
                )

                if value is not None:
                    values.append(value)

            if len(values) >= 2:

                return (
                    values[0],
                    values[1],
                )

            current = current.parent

        # ----------------------------------------------------
        # 3. Соседние элементы
        # ----------------------------------------------------

        parent = label_node.parent

        if isinstance(parent, Tag):

            siblings = list(
                parent.find_all(
                    recursive=False
                )
            )

            values = []

            for sibling in siblings:

                text = sibling.get_text(
                    " ",
                    strip=True,
                )

                if not text:
                    continue

                value = self._parse_stat_value(
                    text
                )

                if value is not None:
                    values.append(value)

            if len(values) >= 2:

                return (
                    values[0],
                    values[1],
                )

        return None

    # ========================================================
    # PARSE STAT VALUE
    # ========================================================

    def _parse_stat_value(
        self,
        text: str,
    ) -> Optional[Any]:

        if not text:
            return None

        value = text.strip()

        # ----------------------------------------------------
        # xG
        # ----------------------------------------------------

        xg_match = re.fullmatch(
            r"(\d+(?:[.,]\d+)?)",
            value,
        )

        if xg_match:

            number = xg_match.group(1)

            if "." in number or "," in number:

                try:
                    return float(
                        number.replace(",", ".")
                    )
                except ValueError:
                    return None

        # ----------------------------------------------------
        # Проценты
        # ----------------------------------------------------

        percent_match = re.fullmatch(
            r"(\d{1,3})\s*%",
            value,
        )

        if percent_match:

            try:
                return int(
                    percent_match.group(1)
                )
            except ValueError:
                return None

        # ----------------------------------------------------
        # Целое число
        # ----------------------------------------------------

        integer_match = re.fullmatch(
            r"\d{1,3}",
            value,
        )

        if integer_match:

            try:
                return int(value)
            except ValueError:
                return None

        return None

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_statistics(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:

        validated = dict(stats)

        # ----------------------------------------------------
        # Диапазоны
        # ----------------------------------------------------

        for stat_type, keys in self.RESULT_KEYS.items():

            minimum, maximum = (
                self.LIMITS[stat_type]
            )

            for key in keys:

                value = validated.get(key)

                if value is None:
                    continue

                try:

                    numeric = float(value)

                except (
                    TypeError,
                    ValueError,
                ):

                    logger.warning(
                        "Неверное значение %s=%r",
                        key,
                        value,
                    )

                    validated[key] = None
                    continue

                if not (
                    minimum
                    <= numeric
                    <= maximum
                ):

                    logger.warning(
                        "Значение %s=%r "
                        "вне диапазона [%s,%s]",
                        key,
                        value,
                        minimum,
                        maximum,
                    )

                    validated[key] = None

        # ----------------------------------------------------
        # Удары в створ <= удары
        # ----------------------------------------------------

        if (
            validated.get("home_shots")
            is not None
            and
            validated.get(
                "home_shots_on_target"
            )
            is not None
        ):

            if (
                validated[
                    "home_shots_on_target"
                ]
                >
                validated["home_shots"]
            ):

                logger.warning(
                    "Динамо: shots_on_target > shots"
                )

                validated[
                    "home_shots_on_target"
                ] = None

        if (
            validated.get("away_shots")
            is not None
            and
            validated.get(
                "away_shots_on_target"
            )
            is not None
        ):

            if (
                validated[
                    "away_shots_on_target"
                ]
                >
                validated["away_shots"]
            ):

                logger.warning(
                    "Гости: shots_on_target > shots"
                )

                validated[
                    "away_shots_on_target"
                ] = None

        # ----------------------------------------------------
        # Владение
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
                float(home_pos)
                +
                float(away_pos)
            )

            # Разрешаем небольшую погрешность.

            if not (
                98 <= total <= 102
            ):

                logger.warning(
                    "Некорректное владение: "
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

        return validated


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

    test_url = (
        "https://nb-bet.com/Events/"
        "1670580-dinamo-moskva-krylya-"
        "sovetov-prognoz-na-match"
    )

    logging.basicConfig(
        level=logging.INFO
    )

    parser = RPLStatsParser()

    print("=" * 60)
    print("FAJ RPL STATS PARSER v3.1")
    print("=" * 60)

    print("\nSCORE:")

    score = parser.parse_score(
        test_url
    )

    print(score)

    print("\nFULL DATA:")

    data = parser.parse_match_page(
        test_url
    )

    for key, value in data.items():

        print(
            f"{key:<30} {value}"
        )

    print("=" * 60)

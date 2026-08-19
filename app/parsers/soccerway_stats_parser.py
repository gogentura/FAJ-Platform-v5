#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCERWAY STATS PARSER v2.0
============================================================

Источник:
    Soccerway

Назначение:
    Надёжное получение:
        - команд
        - счёта
        - статистики матча

Принцип:

    1. Загружаем страницу.
    2. Определяем команды.
    3. Определяем счёт.
    4. Определяем строки статистики.
    5. Извлекаем пару HOME / AWAY.
    6. None означает отсутствие данных.

ВАЖНО:

    Никакого поиска "первого числа" на странице.

    Счёт не извлекается из общей статистики.

    Статистика не смешивается с датами,
    рекламой, заголовками и другими числами.

Совместимость:

    RPLStatsParser = SoccerwayStatsParser
============================================================
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class SoccerwayStatsParser:

    VERSION = "2.0"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0 Safari/537.36"
    )

    # ========================================================
    # КАНОНИЧЕСКИЕ ПОКАЗАТЕЛИ
    # ========================================================

    STAT_ALIASES = {

        "xg": (
            "xg",
            "expected goals",
            "ожидаемые голы",
        ),

        "xg_ot": (
            "xgot",
            "xg ot",
            "xg после ударов в створ",
            "ожидаемые голы после ударов в створ",
        ),

        "possession": (
            "possession",
            "владение",
            "владение мячом",
        ),

        "shots": (
            "shots",
            "total shots",
            "удары",
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
            "yellow",
            "желтые карточки",
            "жёлтые карточки",
            "желтые",
            "жёлтые",
        ),

        "red_cards": (
            "red cards",
            "red",
            "красные карточки",
            "красные",
        ),

        "passes": (
            "passes",
            "передачи",
            "передачи (точные/всего)",
            "точные передачи",
        ),

        "long_passes": (
            "long passes",
            "длинные передачи",
            "длинные передачи (успешные/всего)",
        ),

        "final_third_passes": (
            "passes in final third",
            "передачи в последней трети",
            "передачи в последней трети (успешные/всего)",
        ),

        "crosses": (
            "crosses",
            "навесы",
            "навесы (успешные/всего)",
        ),

        "pass_accuracy": (
            "pass accuracy",
            "точность передач",
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

        "tackles": (
            "tackles",
            "отборы",
            "отборы (успешные/всего)",
        ),

        "duels_won": (
            "duels won",
            "выиграно дуэлей",
            "дуэли",
        ),

        "saves": (
            "saves",
            "goalkeeper saves",
            "сэйвы",
            "сейвы",
            "сэйвы вратаря",
        ),

        "prevented_goals": (
            "goals prevented",
            "prevented goals",
            "предотвращенные голы",
            "предотвращённые голы",
        ),

        "goal_kicks": (
            "goal kicks",
            "удары от ворот",
        ),

        "touches_box": (
            "touches in opposition box",
            "touches in the opposition box",
            "касания мяча в штрафной соперника",
        ),

        "hit_woodwork": (
            "hit woodwork",
            "woodwork",
            "попадание в штангу",
        ),
    }

    # ========================================================
    # ПУБЛИЧНЫЕ ПОЛЯ
    # ========================================================

    BASE_FIELDS = (
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
    )

    STAT_FIELDS = tuple(
        f"{side}_{key}"
        for key in STAT_ALIASES
        for side in ("home", "away")
    )

    def __init__(self, timeout: int = 25):
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
                    "Referer": "https://ru.soccerway.com/",
                    "Connection": "keep-alive",
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            # Soccerway обычно отдаёт UTF-8.
            # requests может определить кодировку неправильно,
            # поэтому при наличии apparent_encoding используем
            # UTF-8 только если ответ явно не декодирован.
            if not response.encoding:
                response.encoding = "utf-8"

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
    # TEXT NORMALIZATION
    # ========================================================

    @staticmethod
    def _norm(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        value = str(value)

        value = (
            value.replace("\xa0", " ")
            .replace("\u200b", " ")
            .replace("–", "-")
            .replace("—", "-")
            .replace("−", "-")
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip().lower()

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        value = str(value)

        value = (
            value.replace("\xa0", " ")
            .replace("\u200b", " ")
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    # ========================================================
    # EMPTY RESULT
    # ========================================================

    def _empty_result(
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

        for key in self.STAT_FIELDS:
            result[key] = None

        return result

    # ========================================================
    # SCORE VALIDATION
    # ========================================================

    @staticmethod
    def _valid_score(
        home: int,
        away: int,
    ) -> bool:

        if home < 0 or away < 0:
            return False

        # Для футбольного матча более 15 голов
        # практически всегда является ложным совпадением.
        if home > 15 or away > 15:
            return False

        return True

    @staticmethod
    def _score_from_text(
        text: str,
    ) -> Optional[Tuple[int, int]]:

        if not text:
            return None

        # Только компактная запись счёта.
        patterns = (
            r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?!\d)",
            r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)",
        )

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
            )

            if not match:
                continue

            home = int(match.group(1))
            away = int(match.group(2))

            if SoccerwayStatsParser._valid_score(
                home,
                away,
            ):
                return home, away

        return None

    # ========================================================
    # SCORE FROM TITLE
    # ========================================================

    def _score_from_title(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        if soup.title:

            title = self._clean_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

            score = self._score_from_text(
                title
            )

            if score:
                return score

        # og:title часто содержит именно
        # название матча + счёт.
        meta = soup.find(
            "meta",
            attrs={
                "property": "og:title"
            },
        )

        if meta:

            content = self._clean_text(
                meta.get("content")
            )

            score = self._score_from_text(
                content
            )

            if score:
                return score

        return None

    # ========================================================
    # SCORE FROM MATCH CONTAINERS
    # ========================================================

    def _score_from_match_container(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        selectors = (
            "[class*='match']",
            "[class*='Match']",
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
        )

        checked = set()

        for selector in selectors:

            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for element in elements:

                # Не рассматриваем огромные контейнеры страницы.
                text = self._clean_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if not text:
                    continue

                if len(text) > 1000:
                    continue

                marker = id(element)

                if marker in checked:
                    continue

                checked.add(marker)

                score = self._score_from_text(
                    text
                )

                if score:
                    return score

        return None

    # ========================================================
    # SCORE FROM SCORE ELEMENT
    # ========================================================

    def _score_from_score_elements(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        selectors = (
            ".score",
            ".Score",
            "[class~='score']",
            "[class~='Score']",
            "[data-testid='score']",
            "[data-testid*='score']",
        )

        for selector in selectors:

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

                score = self._score_from_text(
                    text
                )

                if score:
                    return score

        return None

    # ========================================================
    # SCORE
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Tuple[int, int]]:

        # Порядок принципиален.
        #
        # 1. score element
        # 2. match container
        # 3. title / og:title
        #
        # Никакого общего soup.get_text().

        score = self._score_from_score_elements(
            soup
        )

        if score:
            return score

        score = self._score_from_match_container(
            soup
        )

        if score:
            return score

        score = self._score_from_title(
            soup
        )

        if score:
            return score

        return None

    # ========================================================
    # TEAM HELPERS
    # ========================================================

    @staticmethod
    def _slug_to_candidate(
        slug: str,
    ) -> str:

        slug = unquote(
            slug or ""
        )

        slug = slug.split("?")[0]

        # Soccerway ID обычно находится после имени.
        slug = re.sub(
            r"-[A-Za-z0-9]{6,}$",
            "",
            slug,
        )

        slug = slug.replace(
            "-",
            " ",
        )

        return slug.strip()

    def _teams_from_url(
        self,
        url: str,
    ) -> Tuple[Optional[str], Optional[str]]:

        try:

            path = urlparse(
                url
            ).path

        except Exception:

            return None, None

        parts = [
            part
            for part in path.split("/")
            if part
        ]

        # Ищем сегмент перед match / games / summary.
        #
        # Для Soccerway:
        #
        # /match/
        #   dynamo-moscow-AFWA2jAQ/
        #   krylya-sovetov-samara-SKAE94nJ/
        #   summary/...

        try:

            index = parts.index(
                "match"
            )

        except ValueError:

            return None, None

        if len(parts) <= index + 2:
            return None, None

        home_raw = parts[index + 1]
        away_raw = parts[index + 2]

        home_candidate = (
            self._slug_to_candidate(
                home_raw
            )
        )

        away_candidate = (
            self._slug_to_candidate(
                away_raw
            )
        )

        home, away = normalize_team_names(
            home_candidate,
            away_candidate,
            strict=True,
        )

        if home and away:
            return home, away

        return None, None

    # ========================================================
    # TEAM EXTRACTION
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
        url: str,
    ) -> Tuple[Optional[str], Optional[str]]:

        # Сначала URL.
        # Он значительно надёжнее случайных элементов
        # class='team' на странице.

        home, away = self._teams_from_url(
            url
        )

        if home and away:
            return home, away

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title_text = ""

        if soup.title:

            title_text = self._clean_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

        # Ищем текст вокруг счёта.
        if title_text:

            title_without_score = re.sub(
                r"\d{1,2}\s*[-:]\s*\d{1,2}",
                " ",
                title_text,
            )

            parts = re.split(
                r"\s+[-:]\s+|\s+-\s+",
                title_without_score,
            )

            if len(parts) >= 2:

                h, a = normalize_team_names(
                    parts[0],
                    parts[1],
                    strict=True,
                )

                if h and a:
                    return h, a

        return None, None

    # ========================================================
    # LEAF TEXT
    # ========================================================

    def _leaf_texts(
        self,
        element: Tag,
    ) -> List[str]:

        values = []

        for child in element.find_all(
            recursive=False
        ):

            text = self._clean_text(
                child.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                values.append(text)

        return values

    # ========================================================
    # NUMBER PARSING
    # ========================================================

    @staticmethod
    def _parse_number(
        value: str,
    ) -> Optional[Any]:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        text = (
            text.replace("\xa0", "")
            .replace(",", ".")
            .strip()
        )

        percent = text.endswith("%")

        text = text.rstrip("%")

        # Оставляем только число.
        match = re.fullmatch(
            r"\d+(?:\.\d+)?",
            text,
        )

        if not match:
            return None

        number = float(
            match.group(0)
        )

        if number.is_integer():
            number = int(number)

        if percent:
            return number

        return number

    # ========================================================
    # PAIR FROM VALUE TEXT
    # ========================================================

    def _parse_pair_text(
        self,
        text: str,
    ) -> Tuple[Optional[Any], Optional[Any]]:

        if not text:
            return None, None

        text = self._clean_text(
            text
        )

        # ----------------------------------------------------
        # 1. Формат:
        #
        # 453/539 (84%) 191/280 (68%)
        #
        # Для общего passes возвращаем
        # первые числовые показатели.
        # ----------------------------------------------------

        slash_values = re.findall(
            r"(\d+)\s*/\s*(\d+)",
            text,
        )

        if len(slash_values) >= 2:

            first_home = (
                int(slash_values[0][0])
            )

            first_away = (
                int(slash_values[1][0])
            )

            return (
                first_home,
                first_away,
            )

        # ----------------------------------------------------
        # 2. Обычный формат:
        #
        # 66% 34%
        # 21 12
        # 1.25 1.23
        # ----------------------------------------------------

        values = re.findall(
            r"(?<![\d/])"
            r"\d+(?:[.,]\d+)?%?"
            r"(?![\d/])",
            text,
        )

        if len(values) < 2:
            return None, None

        home = self._parse_number(
            values[0]
        )

        away = self._parse_number(
            values[1]
        )

        return home, away

    # ========================================================
    # LABEL MATCH
    # ========================================================

    def _matches_alias(
        self,
        label: str,
        aliases: Iterable[str],
    ) -> bool:

        label_norm = self._norm(
            label
        )

        if not label_norm:
            return False

        for alias in aliases:

            alias_norm = self._norm(
                alias
            )

            if label_norm == alias_norm:
                return True

        return False

    # ========================================================
    # STAT ROW CANDIDATES
    # ========================================================

    def _candidate_rows(
        self,
        soup: BeautifulSoup,
    ) -> Iterable[Tag]:

        # Сначала настоящие таблицы.
        for row in soup.find_all("tr"):
            yield row

        # Затем типичные контейнеры строк.
        for element in soup.find_all(
            ["li", "div"],
        ):

            classes = " ".join(
                element.get("class", [])
            ).lower()

            if any(
                marker in classes
                for marker in (
                    "stat",
                    "statistics",
                    "stats",
                    "row",
                )
            ):

                yield element

    # ========================================================
    # STAT ROW PARSER
    # ========================================================

    def _parse_stat_row(
        self,
        row: Tag,
        aliases: Iterable[str],
    ) -> Tuple[
        Optional[Any],
        Optional[Any],
    ]:

        # ----------------------------------------------------
        # Получаем дочерние текстовые элементы.
        # ----------------------------------------------------

        children = self._leaf_texts(
            row
        )

        if len(children) < 2:
            children = [
                self._clean_text(
                    item
                )
                for item in row.stripped_strings
            ]

        if not children:
            return None, None

        # ----------------------------------------------------
        # Ищем label среди дочерних элементов.
        # ----------------------------------------------------

        label_index = None

        for index, text in enumerate(
            children
        ):

            if self._matches_alias(
                text,
                aliases,
            ):

                label_index = index
                break

        if label_index is None:

            # Иногда label объединён с частью
            # строки.
            full_text = self._clean_text(
                row.get_text(
                    " ",
                    strip=True,
                )
            )

            for alias in aliases:

                alias_norm = self._norm(
                    alias
                )

                if alias_norm in self._norm(
                    full_text
                ):

                    pair = self._parse_pair_text(
                        full_text
                    )

                    if (
                        pair[0] is not None
                        and pair[1] is not None
                    ):
                        return pair

            return None, None

        # ----------------------------------------------------
        # После label должны находиться
        # HOME и AWAY.
        # ----------------------------------------------------

        values = children[
            label_index + 1:
        ]

        parsed_values = []

        for value in values:

            # Пропускаем служебные тексты.
            pair_match = re.fullmatch(
                r"\d+(?:[.,]\d+)?\s*/\s*\d+"
                r"(?:\s*\(\d+(?:[.,]\d+)?%\))?",
                value,
            )

            if pair_match:
                parsed_values.append(
                    value
                )
                continue

            parsed = self._parse_number(
                value
            )

            if parsed is not None:
                parsed_values.append(
                    parsed
                )

        # ----------------------------------------------------
        # Два обычных значения.
        # ----------------------------------------------------

        if (
            len(parsed_values) >= 2
            and not isinstance(
                parsed_values[0],
                str,
            )
        ):

            return (
                parsed_values[0],
                parsed_values[1],
            )

        # ----------------------------------------------------
        # Два slash-значения.
        # ----------------------------------------------------

        slash_pairs = []

        for value in values:

            match = re.fullmatch(
                r"(\d+)\s*/\s*(\d+)"
                r"(?:\s*\((\d+(?:[.,]\d+)?)%\))?",
                value,
            )

            if match:

                slash_pairs.append(
                    (
                        int(match.group(1)),
                        int(match.group(2)),
                    )
                )

        if len(slash_pairs) >= 2:

            return (
                slash_pairs[0][0],
                slash_pairs[1][0],
            )

        # ----------------------------------------------------
        # Последняя попытка — текст строки.
        # ----------------------------------------------------

        full_text = self._clean_text(
            row.get_text(
                " ",
                strip=True,
            )
        )

        return self._parse_pair_text(
            full_text
        )

    # ========================================================
    # FIND STAT
    # ========================================================

    def _find_stat(
        self,
        soup: BeautifulSoup,
        aliases: Iterable[str],
    ) -> Tuple[
        Optional[Any],
        Optional[Any],
    ]:

        # ----------------------------------------------------
        # Метод 1: строки статистики.
        # ----------------------------------------------------

        checked = set()

        for row in self._candidate_rows(
            soup
        ):

            marker = id(row)

            if marker in checked:
                continue

            checked.add(marker)

            result = self._parse_stat_row(
                row,
                aliases,
            )

            if (
                result[0] is not None
                and result[1] is not None
            ):
                return result

        # ----------------------------------------------------
        # Метод 2: label element + ближайший контейнер.
        #
        # Важно:
        # не берём весь parent без ограничения.
        # ----------------------------------------------------

        for element in soup.find_all(
            ["span", "div", "td", "li", "p"],
        ):

            label = self._clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not self._matches_alias(
                label,
                aliases,
            ):
                continue

            parent = element.parent

            depth = 0

            while (
                parent is not None
                and depth < 3
            ):

                text = self._clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                )

                # Ограничиваем размер контейнера,
                # чтобы не захватить всю страницу.
                if 0 < len(text) <= 300:

                    pair = self._parse_pair_text(
                        text
                    )

                    if (
                        pair[0] is not None
                        and pair[1] is not None
                    ):
                        return pair

                parent = parent.parent
                depth += 1

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

        return result

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        result = self._empty_result(
            url
        )

        soup = self._get_soup(
            url
        )

        if soup is None:
            return result

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        home, away = self._extract_teams(
            soup,
            url,
        )

        result["home_team"] = home
        result["away_team"] = away

        # ----------------------------------------------------
        # SCORE
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
        # STATISTICS
        # ----------------------------------------------------

        stats = self._extract_statistics(
            soup
        )

        result.update(
            stats
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        logger.info(
            "Soccerway: parsed | "
            "home=%s | away=%s | "
            "score=%s:%s | "
            "xG=%s:%s | "
            "shots=%s:%s | "
            "possession=%s:%s | "
            "corners=%s:%s",
            result["home_team"],
            result["away_team"],
            result["home_goals"],
            result["away_goals"],
            result["home_xg"],
            result["away_xg"],
            result["home_shots"],
            result["away_shots"],
            result["home_possession"],
            result["away_possession"],
            result["home_corners"],
            result["away_corners"],
        )

        return result


# ============================================================
# COMPATIBILITY
# ============================================================

RPLStatsParser = SoccerwayStatsParser

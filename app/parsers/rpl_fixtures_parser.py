#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
RPL FIXTURES PARSER
===========================================================

Назначение:
    Загрузка календаря РПЛ 2026/27.

Источники:

    1. Smart Tables
    2. Championat
    3. Soccerland

Архитектура:

    SOURCE
       ↓
    HTML
       ↓
    extraction
       ↓
    normalization
       ↓
    validation
       ↓
    deduplication
       ↓
    unified match records
       ↓
    load_calendar.py
       ↓
    SQLite

ВАЖНО:

    Этот модуль НЕ изменяет БД.

    Он только загружает и нормализует данные.

===========================================================
"""

from __future__ import annotations

import logging
import re

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from app.parsers.rpl_normalizer import (
    CANONICAL_TEAMS,
    normalize_team_name,
)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# SOURCES
# ============================================================

SMART_TABLES_URL = (
    "https://smart-tables.ru/league/Russia/Premier_League"
)

CHAMPIONAT_URL = (
    "https://www.championat.com/football/"
    "_russiapl/tournament/7096/calendar/"
)

SOCCERLAND_URL = (
    "https://soccerland.ru/russia/premier-liga/2026-2027"
)


# ============================================================
# SEASON
# ============================================================

SEASON_NAME = "РПЛ 2026-2027"
SEASON_YEAR = "2026-2027"
LEAGUE_NAME = "РПЛ"

EXPECTED_ROUNDS = 30
EXPECTED_MATCHES = 240


# ============================================================
# HTTP
# ============================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept-Language": (
        "ru-RU,ru;q=0.9,en;q=0.8"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
}


# ============================================================
# RESULT
# ============================================================

def _empty_result() -> Dict[str, Any]:
    """
    Единый объект результата.
    """

    return {
        "matches": [],
        "sources": {},
        "errors": [],
        "warnings": [],
        "duplicates": [],
        "started_at": None,
        "finished_at": None,
    }


# ============================================================
# PARSER
# ============================================================

class RPLFixturesParser:
    """
    Универсальный парсер календаря РПЛ.

    Основной метод:

        parse()

    Возвращает:

        {
            "matches": [...],
            "sources": {...},
            "errors": [...],
            "warnings": [...],
            "duplicates": [...],
        }
    """

    def __init__(
        self,
        timeout: int = 20,
        headers: Optional[
            Dict[str, str]
        ] = None,
    ) -> None:

        self.timeout = timeout

        self.headers = (
            headers.copy()
            if headers
            else DEFAULT_HEADERS.copy()
        )

        self.session = requests.Session()

        self.session.headers.update(
            self.headers
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse(self) -> Dict[str, Any]:
        """
        Загружает календарь из всех источников.
        """

        result = _empty_result()

        result["started_at"] = (
            datetime.now().isoformat()
        )

        source_parsers = [
            (
                "smart_tables",
                SMART_TABLES_URL,
                self._parse_smart_tables,
            ),
            (
                "championat",
                CHAMPIONAT_URL,
                self._parse_championat,
            ),
            (
                "soccerland",
                SOCCERLAND_URL,
                self._parse_soccerland,
            ),
        ]

        all_matches: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # Источники
        # ----------------------------------------------------

        for (
            source_name,
            url,
            parser_func,
        ) in source_parsers:

            try:

                logger.info(
                    "Загрузка календаря: %s",
                    source_name,
                )

                html = self._download(
                    url
                )

                if not html:

                    result["sources"][
                        source_name
                    ] = {
                        "status": "error",
                        "url": url,
                        "matches": 0,
                    }

                    result["errors"].append(
                        f"{source_name}: "
                        "HTML не получен"
                    )

                    continue

                matches = parser_func(
                    html=html,
                    source=source_name,
                    url=url,
                )

                result["sources"][
                    source_name
                ] = {
                    "status": "ok",
                    "url": url,
                    "matches": len(matches),
                }

                all_matches.extend(
                    matches
                )

            except Exception as exc:

                logger.exception(
                    "Ошибка источника %s",
                    source_name,
                )

                result["sources"][
                    source_name
                ] = {
                    "status": "error",
                    "url": url,
                    "matches": 0,
                }

                result["errors"].append(
                    f"{source_name}: {exc}"
                )

        # ----------------------------------------------------
        # Объединение
        # ----------------------------------------------------

        matches, duplicates = (
            self._merge_matches(
                all_matches
            )
        )

        result["matches"] = matches

        result["duplicates"] = (
            duplicates
        )

        # ----------------------------------------------------
        # Проверка календаря
        # ----------------------------------------------------

        self._validate_calendar(
            matches=matches,
            result=result,
        )

        result["finished_at"] = (
            datetime.now().isoformat()
        )

        logger.info(
            "Итого уникальных матчей: %s",
            len(matches),
        )

        return result

    # ========================================================
    # HTTP
    # ========================================================

    def _download(
        self,
        url: str,
    ) -> Optional[str]:
        """
        Загружает HTML.
        """

        try:

            response = self.session.get(
                url,
                timeout=self.timeout,
            )

            response.raise_for_status()

            if not response.text:
                return None

            return response.text

        except requests.RequestException as exc:

            logger.error(
                "HTTP ошибка %s: %s",
                url,
                exc,
            )

            return None

    # ========================================================
    # SMART TABLES
    # ========================================================

    def _parse_smart_tables(
        self,
        html: str,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        matches: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # TABLES
        # ----------------------------------------------------

        for table in soup.find_all(
            "table"
        ):

            current_round = None

            for row in table.find_all(
                "tr"
            ):

                cells = row.find_all(
                    ["td", "th"]
                )

                texts = [
                    self._clean_text(
                        cell.get_text(
                            " ",
                            strip=True,
                        )
                    )
                    for cell in cells
                ]

                row_text = " ".join(
                    texts
                )

                detected_round = (
                    self._extract_round(
                        row_text
                    )
                )

                if detected_round:
                    current_round = (
                        detected_round
                    )

                match = self._parse_row(
                    texts=texts,
                    row_text=row_text,
                    current_round=current_round,
                    source=source,
                    url=url,
                )

                if match:
                    matches.append(
                        match
                    )

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if not matches:

            matches.extend(
                self._parse_generic_text(
                    soup=soup,
                    source=source,
                    url=url,
                )
            )

        return self._validate_matches(
            matches
        )

    # ========================================================
    # CHAMPIONAT
    # ========================================================

    def _parse_championat(
        self,
        html: str,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        matches: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # 1. Сначала пробуем таблицы
        # ----------------------------------------------------

        matches.extend(
            self._parse_tables_generic(
                soup=soup,
                source=source,
                url=url,
            )
        )

        # ----------------------------------------------------
        # 2. Ищем элементы с "Тур N"
        # ----------------------------------------------------

        if not matches:

            round_nodes = soup.find_all(
                string=re.compile(
                    r"\bТур\s*\d+\b",
                    re.IGNORECASE,
                )
            )

            for round_node in round_nodes:

                text = (
                    round_node.get_text()
                    if hasattr(
                        round_node,
                        "get_text",
                    )
                    else str(
                        round_node
                    )
                )

                round_number = (
                    self._extract_round(
                        text
                    )
                )

                if not round_number:
                    continue

                parent = (
                    round_node.parent
                    if round_node
                    else None
                )

                if not parent:
                    continue

                container = parent

                for _ in range(5):

                    if not container:
                        break

                    container_text = (
                        self._clean_text(
                            container.get_text(
                                " ",
                                strip=True,
                            )
                        )
                    )

                    if len(
                        container_text
                    ) > 40:

                        break

                    container = (
                        container.parent
                    )

                if not container:
                    continue

                matches.extend(
                    self._extract_matches_from_container(
                        container=container,
                        round_number=round_number,
                        source=source,
                        url=url,
                    )
                )

        # ----------------------------------------------------
        # 3. Общий fallback
        # ----------------------------------------------------

        if not matches:

            matches.extend(
                self._parse_generic_text(
                    soup=soup,
                    source=source,
                    url=url,
                )
            )

        return self._validate_matches(
            matches
        )

    # ========================================================
    # SOCCERLAND
    # ========================================================

    def _parse_soccerland(
        self,
        html: str,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        matches: List[
            Dict[str, Any]
        ] = []

        matches.extend(
            self._parse_tables_generic(
                soup=soup,
                source=source,
                url=url,
            )
        )

        if not matches:

            matches.extend(
                self._parse_generic_text(
                    soup=soup,
                    source=source,
                    url=url,
                )
            )

        return self._validate_matches(
            matches
        )

    # ========================================================
    # GENERIC TABLE PARSER
    # ========================================================

    def _parse_tables_generic(
        self,
        soup: BeautifulSoup,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        matches: List[
            Dict[str, Any]
        ] = []

        current_round = None

        for table in soup.find_all(
            "table"
        ):

            for row in table.find_all(
                "tr"
            ):

                cells = row.find_all(
                    ["td", "th"]
                )

                texts = [
                    self._clean_text(
                        cell.get_text(
                            " ",
                            strip=True,
                        )
                    )
                    for cell in cells
                ]

                row_text = " ".join(
                    texts
                )

                detected_round = (
                    self._extract_round(
                        row_text
                    )
                )

                if detected_round:

                    current_round = (
                        detected_round
                    )

                match = self._parse_row(
                    texts=texts,
                    row_text=row_text,
                    current_round=current_round,
                    source=source,
                    url=url,
                )

                if match:
                    matches.append(
                        match
                    )

        return matches

    # ========================================================
    # ROW PARSER
    # ========================================================

    def _parse_row(
        self,
        texts: List[str],
        row_text: str,
        current_round: Optional[int],
        source: str,
        url: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        if not row_text:
            return None

        # ----------------------------------------------------
        # Тур
        # ----------------------------------------------------

        round_number = (
            self._extract_round(
                row_text
            )
            or current_round
        )

        # ----------------------------------------------------
        # Команды
        # ----------------------------------------------------

        (
            home_team,
            away_team,
        ) = self._extract_teams(
            texts=texts,
            row_text=row_text,
        )

        if not home_team or not away_team:
            return None

        home_team = normalize_team_name(
            home_team,
            strict=True,
        )

        away_team = normalize_team_name(
            away_team,
            strict=True,
        )

        if not home_team or not away_team:
            return None

        if home_team == away_team:
            return None

        # ----------------------------------------------------
        # Дата
        # ----------------------------------------------------

        date_value = (
            self._extract_date(
                row_text
            )
        )

        # ----------------------------------------------------
        # Время
        # ----------------------------------------------------

        time_value = (
            self._extract_time(
                row_text
            )
        )

        # ----------------------------------------------------
        # Счёт
        # ----------------------------------------------------

        score = self._extract_score(
            row_text
        )

        home_goals = None
        away_goals = None

        if score is not None:

            home_goals, away_goals = (
                score
            )

        status = (
            "finished"
            if score is not None
            else "scheduled"
        )

        return {
            "season": SEASON_NAME,
            "season_year": SEASON_YEAR,
            "league": LEAGUE_NAME,
            "round": round_number,
            "home_team": home_team,
            "away_team": away_team,
            "date": date_value,
            "time": time_value,
            "status": status,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "source": source,
            "source_url": url,
        }

    # ========================================================
    # TEAM EXTRACTION
    # ========================================================

    def _extract_teams(
        self,
        texts: List[str],
        row_text: str,
    ) -> Tuple[
        Optional[str],
        Optional[str],
    ]:
        """
        Ищет две известные команды РПЛ.

        Для надёжности сначала смотрим отдельные
        ячейки, затем всю строку.
        """

        found: List[str] = []

        candidates = []

        # ----------------------------------------------------
        # Сначала отдельные элементы
        # ----------------------------------------------------

        candidates.extend(
            texts
        )

        # ----------------------------------------------------
        # Затем вся строка
        # ----------------------------------------------------

        candidates.append(
            row_text
        )

        # ----------------------------------------------------
        # Проверяем варианты
        # ----------------------------------------------------

        for candidate in candidates:

            candidate = (
                self._clean_text(
                    candidate
                )
            )

            if not candidate:
                continue

            lower_candidate = (
                candidate.lower()
            )

            for canonical in (
                CANONICAL_TEAMS
            ):

                if canonical in found:
                    continue

                variants = (
                    self._name_variants(
                        canonical
                    )
                )

                matched = False

                for variant in variants:

                    if (
                        variant.lower()
                        in lower_candidate
                    ):

                        found.append(
                            canonical
                        )

                        matched = True

                        break

                if matched and len(
                    found
                ) >= 2:

                    return (
                        found[0],
                        found[1],
                    )

        if len(found) < 2:

            return None, None

        return (
            found[0],
            found[1],
        )

    # ========================================================
    # NAME VARIANTS
    # ========================================================

    def _name_variants(
        self,
        canonical: str,
    ) -> List[str]:

        mapping = {

            "Зенит": [
                "Зенит",
                "Зенит Санкт-Петербург",
            ],

            "Спартак": [
                "Спартак",
                "Спартак М",
                "Спартак Москва",
            ],

            "ЦСКА": [
                "ЦСКА",
                "ЦСКА Москва",
                "ПФК ЦСКА",
            ],

            "Динамо Москва": [
                "Динамо Москва",
                "Динамо М",
                "Динамо (Москва)",
            ],

            "Локомотив": [
                "Локомотив",
                "Локомотив М",
                "Локомотив Москва",
            ],

            "Ростов": [
                "Ростов",
                "Ростов-на-Дону",
            ],

            "Ахмат": [
                "Ахмат",
                "Ахмат Грозный",
            ],

            "Рубин": [
                "Рубин",
                "Рубин Казань",
            ],

            "Крылья Советов": [
                "Крылья Советов",
                "Крылья Советов Самара",
            ],

            "Факел": [
                "Факел",
                "Факел Воронеж",
            ],

            "Акрон": [
                "Акрон",
                "Акрон Тольятти",
            ],

            "Балтика": [
                "Балтика",
                "Балтика Калининград",
            ],

            "Родина": [
                "Родина",
                "Родина Москва",
            ],

            "Динамо Махачкала": [
                "Динамо Махачкала",
                "Динамо Мх",
                "Динамо (Махачкала)",
            ],

            "Краснодар": [
                "Краснодар",
            ],

            "Оренбург": [
                "Оренбург",
            ],

            "Акрон": [
                "Акрон",
                "Акрон Тольятти",
            ],
        }

        return mapping.get(
            canonical,
            [canonical],
        )

    # ========================================================
    # DATE
    # ========================================================

    def _extract_date(
        self,
        text: str,
    ) -> Optional[str]:

        if not text:
            return None

        patterns = [
            r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
            )

            if not match:
                continue

            day, month, year = (
                match.groups()
            )

            return (
                f"{year}-"
                f"{int(month):02d}-"
                f"{int(day):02d}"
            )

        return None

    # ========================================================
    # TIME
    # ========================================================

    def _extract_time(
        self,
        text: str,
    ) -> Optional[str]:

        if not text:
            return None

        match = re.search(
            r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
            text,
        )

        if not match:
            return None

        return match.group(0)

    # ========================================================
    # SCORE
    # ========================================================

    def _extract_score(
        self,
        text: str,
    ) -> Optional[
        Tuple[int, int]
    ]:

        if not text:
            return None

        # ----------------------------------------------------
        # Важное правило:
        #
        # "– : –" НЕ является результатом.
        # ----------------------------------------------------

        patterns = [
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
        ]

        for pattern in patterns:

            matches = re.findall(
                pattern,
                text,
            )

            for home, away in matches:

                h = int(home)
                a = int(away)

                # ------------------------------------------------
                # Реалистичный диапазон футбольного счёта
                # ------------------------------------------------

                if h > 15 or a > 15:
                    continue

                return h, a

        return None

    # ========================================================
    # ROUND
    # ========================================================

    def _extract_round(
        self,
        text: str,
    ) -> Optional[int]:

        if not text:
            return None

        patterns = [
            r"\bтур\s*(\d+)\b",
            r"\b(\d+)\s*[-–]?\s*й\s*тур\b",
            r"\bround\s*(\d+)\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            value = int(
                match.group(1)
            )

            if (
                1
                <= value
                <= EXPECTED_ROUNDS
            ):

                return value

        return None

    # ========================================================
    # GENERIC TEXT
    # ========================================================

    def _parse_generic_text(
        self,
        soup: BeautifulSoup,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        matches: List[
            Dict[str, Any]
        ] = []

        text = soup.get_text(
            "\n",
            strip=True,
        )

        lines = [
            self._clean_text(
                line
            )
            for line in text.splitlines()
        ]

        lines = [
            line
            for line in lines
            if line
        ]

        current_round = None

        for line in lines:

            detected_round = (
                self._extract_round(
                    line
                )
            )

            if detected_round:

                current_round = (
                    detected_round
                )

            match = self._parse_row(
                texts=[line],
                row_text=line,
                current_round=current_round,
                source=source,
                url=url,
            )

            if match:

                matches.append(
                    match
                )

        return matches

    # ========================================================
    # CONTAINER MATCH EXTRACTION
    # ========================================================

    def _extract_matches_from_container(
        self,
        container,
        round_number: int,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        matches: List[
            Dict[str, Any]
        ] = []

        rows = container.find_all(
            ["tr", "li"]
        )

        for row in rows:

            texts = [
                self._clean_text(
                    x.get_text(
                        " ",
                        strip=True,
                    )
                )
                for x in row.find_all(
                    recursive=False
                )
            ]

            if not texts:

                texts = [
                    self._clean_text(
                        row.get_text(
                            " ",
                            strip=True,
                        )
                    )
                ]

            row_text = " ".join(
                texts
            )

            match = self._parse_row(
                texts=texts,
                row_text=row_text,
                current_round=round_number,
                source=source,
                url=url,
            )

            if match:

                matches.append(
                    match
                )

        return matches

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_matches(
        self,
        matches: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:

        result = []

        for match in matches:

            home = normalize_team_name(
                match.get(
                    "home_team"
                ),
                strict=True,
            )

            away = normalize_team_name(
                match.get(
                    "away_team"
                ),
                strict=True,
            )

            if not home or not away:
                continue

            if home == away:
                continue

            round_number = match.get(
                "round"
            )

            if round_number is None:
                continue

            try:

                round_number = int(
                    round_number
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            if not (
                1
                <= round_number
                <= EXPECTED_ROUNDS
            ):

                continue

            match["home_team"] = home
            match["away_team"] = away
            match["round"] = (
                round_number
            )

            result.append(
                match
            )

        return result

    # ========================================================
    # MERGE
    # ========================================================

    def _merge_matches(
        self,
        matches: List[
            Dict[str, Any]
        ],
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:

        unique: Dict[
            Tuple[Any, ...],
            Dict[str, Any],
        ] = {}

        duplicates: List[
            Dict[str, Any]
        ] = []

        for match in matches:

            key = (
                match.get(
                    "season_year"
                ),
                match.get(
                    "round"
                ),
                match.get(
                    "home_team"
                ),
                match.get(
                    "away_team"
                ),
            )

            if key not in unique:

                item = dict(
                    match
                )

                item["sources"] = [
                    {
                        "source": match.get(
                            "source"
                        ),
                        "url": match.get(
                            "source_url"
                        ),
                    }
                ]

                unique[key] = item

                continue

            # ------------------------------------------------
            # Дубликат
            # ------------------------------------------------

            existing = unique[key]

            existing_sources = (
                existing.setdefault(
                    "sources",
                    [],
                )
            )

            existing_sources.append(
                {
                    "source": match.get(
                        "source"
                    ),
                    "url": match.get(
                        "source_url"
                    ),
                }
            )

            duplicates.append(
                {
                    "key": key,
                    "source": match.get(
                        "source"
                    ),
                }
            )

            # ------------------------------------------------
            # Дополняем дату
            # ------------------------------------------------

            if (
                not existing.get(
                    "date"
                )
                and match.get(
                    "date"
                )
            ):

                existing["date"] = (
                    match["date"]
                )

            # ------------------------------------------------
            # Дополняем время
            # ------------------------------------------------

            if (
                not existing.get(
                    "time"
                )
                and match.get(
                    "time"
                )
            ):

                existing["time"] = (
                    match["time"]
                )

            # ------------------------------------------------
            # Дополняем результат
            # ------------------------------------------------

            if (
                existing.get(
                    "home_goals"
                )
                is None
                and match.get(
                    "home_goals"
                )
                is not None
            ):

                existing[
                    "home_goals"
                ] = match[
                    "home_goals"
                ]

                existing[
                    "away_goals"
                ] = match[
                    "away_goals"
                ]

                existing[
                    "status"
                ] = "finished"

        return (
            list(
                unique.values()
            ),
            duplicates,
        )

    # ========================================================
    # CALENDAR VALIDATION
    # ========================================================

    def _validate_calendar(
        self,
        matches: List[
            Dict[str, Any]
        ],
        result: Dict[str, Any],
    ) -> None:
        """
        Проверяет полноту календаря.

        Для РПЛ:
            30 туров
            8 матчей в каждом
            240 матчей всего.
        """

        if not matches:

            result["warnings"].append(
                "Календарь пуст."
            )

            return

        # ----------------------------------------------------
        # По турам
        # ----------------------------------------------------

        round_counts = {
            round_number: 0
            for round_number in range(
                1,
                EXPECTED_ROUNDS + 1,
            )
        }

        for match in matches:

            round_number = match.get(
                "round"
            )

            if round_number in round_counts:

                round_counts[
                    round_number
                ] += 1

        incomplete_rounds = []

        for (
            round_number,
            count,
        ) in round_counts.items():

            if count != 8:

                incomplete_rounds.append(
                    {
                        "round": round_number,
                        "matches": count,
                        "expected": 8,
                    }
                )

        if incomplete_rounds:

            result["warnings"].append(
                "Найдены неполные туры: "
                + ", ".join(
                    (
                        f"тур {item['round']} "
                        f"({item['matches']}/8)"
                    )
                    for item
                    in incomplete_rounds
                )
            )

        # ----------------------------------------------------
        # Общее количество
        # ----------------------------------------------------

        total = len(matches)

        if total != EXPECTED_MATCHES:

            result["warnings"].append(
                f"Календарь содержит "
                f"{total} матчей вместо "
                f"{EXPECTED_MATCHES}."
            )

        else:

            logger.info(
                "✅ Полный календарь: "
                "%s/%s матчей",
                total,
                EXPECTED_MATCHES,
            )

    # ========================================================
    # TEXT CLEAN
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
# CONVENIENCE FUNCTION
# ============================================================

def parse_rpl_fixtures() -> Dict[str, Any]:
    """
    Удобная функция для load_all.py.
    """

    parser = RPLFixturesParser()

    return parser.parse()


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(message)s"
        ),
    )

    parser = RPLFixturesParser()

    result = parser.parse()

    print()
    print("=" * 70)
    print(
        "FAJ RPL FIXTURES PARSER v12.1"
    )
    print("=" * 70)

    print(
        f"Найдено матчей: "
        f"{len(result['matches'])}"
    )

    print(
        f"Дубликатов: "
        f"{len(result['duplicates'])}"
    )

    print(
        f"Ошибок: "
        f"{len(result['errors'])}"
    )

    print(
        f"Предупреждений: "
        f"{len(result['warnings'])}"
    )

    print()
    print("ИСТОЧНИКИ:")

    for (
        source,
        info,
    ) in result[
        "sources"
    ].items():

        print(
            f"  {source}: "
            f"{info['status']} "
            f"({info['matches']} матчей)"
        )

    print()
    print("ПРЕДУПРЕЖДЕНИЯ:")

    for warning in result[
        "warnings"
    ]:

        print(
            f"  ⚠️ {warning}"
        )

    print()
    print("ПЕРВЫЕ МАТЧИ:")

    for match in result[
        "matches"
    ][:10]:

        print(
            f"Тур {match.get('round')}: "
            f"{match.get('home_team')} — "
            f"{match.get('away_team')} | "
            f"{match.get('date')} "
            f"{match.get('time') or ''} | "
            f"{match.get('status')}"
        )

    print("=" * 70)

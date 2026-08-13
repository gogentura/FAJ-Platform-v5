#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
RPL FIXTURES PARSER v2.1
===========================================================

Назначение:
    Загрузка и строгая проверка календаря РПЛ 2026/27.

Архитектура:

    SOURCE
       ↓
    HTML
       ↓
    extraction
       ↓
    normalization
       ↓
    deduplication
       ↓
    STRICT VALIDATION
       ↓
    unified match records
       ↓
    load_calendar.py
       ↓
    SQLite

ВАЖНО:

    Этот модуль НЕ изменяет БД.

Календарь разрешается передавать дальше
ТОЛЬКО если:

    30 туров
    8 матчей в каждом туре
    240 матчей
    16 команд
    каждая команда играет 1 матч в туре
    нет повторных пар
    нет зеркальных пар
    нет неизвестных команд
    нет матчей команда-команда

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
EXPECTED_TEAMS = 16
EXPECTED_MATCHES_PER_ROUND = 8


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
    return {
        "matches": [],
        "sources": {},
        "errors": [],
        "warnings": [],
        "duplicates": [],
        "validation_errors": [],
        "validation": {},
        "calendar_valid": False,
        "started_at": None,
        "finished_at": None,
    }


# ============================================================
# PARSER
# ============================================================

class RPLFixturesParser:

    VERSION = "2.1"

    def __init__(
        self,
        timeout: int = 20,
        headers: Optional[Dict[str, str]] = None,
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

        all_matches: List[Dict[str, Any]] = []

        # ----------------------------------------------------
        # SOURCES
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

                html = self._download(url)

                if not html:

                    result["sources"][
                        source_name
                    ] = {
                        "status": "error",
                        "url": url,
                        "matches": 0,
                    }

                    result["errors"].append(
                        f"{source_name}: HTML не получен"
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

                all_matches.extend(matches)

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
        # MERGE
        # ----------------------------------------------------

        matches, duplicates = (
            self._merge_matches(
                all_matches
            )
        )

        result["matches"] = matches
        result["duplicates"] = duplicates

        # ----------------------------------------------------
        # STRICT VALIDATION
        # ----------------------------------------------------

        self._validate_calendar(
            matches=matches,
            result=result,
        )

        result["finished_at"] = (
            datetime.now().isoformat()
        )

        logger.info(
            "Парсинг завершён | "
            "matches=%s | "
            "duplicates=%s | "
            "valid=%s",
            len(matches),
            len(duplicates),
            result["calendar_valid"],
        )

        return result

    # ========================================================
    # HTTP
    # ========================================================

    def _download(
        self,
        url: str,
    ) -> Optional[str]:

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

        matches = []

        for table in soup.find_all("table"):

            current_round = None

            for row in table.find_all("tr"):

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

                row_text = " ".join(texts)

                detected_round = (
                    self._extract_round(
                        row_text
                    )
                )

                if detected_round:
                    current_round = detected_round

                match = self._parse_row(
                    texts=texts,
                    row_text=row_text,
                    current_round=current_round,
                    source=source,
                    url=url,
                )

                if match:
                    matches.append(match)

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

        matches = []

        matches.extend(
            self._parse_tables_generic(
                soup=soup,
                source=source,
                url=url,
            )
        )

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
                    else str(round_node)
                )

                round_number = (
                    self._extract_round(text)
                )

                if not round_number:
                    continue

                parent = round_node.parent

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

                    if len(container_text) > 40:
                        break

                    container = container.parent

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

        matches = []

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

        matches = []

        current_round = None

        for table in soup.find_all("table"):

            for row in table.find_all("tr"):

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

                row_text = " ".join(texts)

                detected_round = (
                    self._extract_round(
                        row_text
                    )
                )

                if detected_round:
                    current_round = detected_round

                match = self._parse_row(
                    texts=texts,
                    row_text=row_text,
                    current_round=current_round,
                    source=source,
                    url=url,
                )

                if match:
                    matches.append(match)

        return matches

    # ========================================================
    # ROW
    # ========================================================

    def _parse_row(
        self,
        texts: List[str],
        row_text: str,
        current_round: Optional[int],
        source: str,
        url: str,
    ) -> Optional[Dict[str, Any]]:

        if not row_text:
            return None

        round_number = (
            self._extract_round(row_text)
            or current_round
        )

        home_team, away_team = (
            self._extract_teams(
                texts=texts,
                row_text=row_text,
            )
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

        date_value = self._extract_date(
            row_text
        )

        time_value = self._extract_time(
            row_text
        )

        score = self._extract_score(
            row_text
        )

        home_goals = None
        away_goals = None

        if score is not None:

            home_goals, away_goals = score

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

        found = []

        candidates = list(texts)
        candidates.append(row_text)

        for candidate in candidates:

            candidate = self._clean_text(
                candidate
            )

            if not candidate:
                continue

            lower_candidate = (
                candidate.lower()
            )

            for canonical in CANONICAL_TEAMS:

                if canonical in found:
                    continue

                variants = self._name_variants(
                    canonical
                )

                for variant in variants:

                    if (
                        variant.lower()
                        in lower_candidate
                    ):

                        found.append(
                            canonical
                        )

                        break

                if len(found) >= 2:

                    return (
                        found[0],
                        found[1],
                    )

        if len(found) < 2:
            return None, None

        return found[0], found[1]

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

            "Краснодар": [
                "Краснодар",
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

            "Оренбург": [
                "Оренбург",
            ],

            "Балтика": [
                "Балтика",
                "Балтика Калининград",
            ],

            "Акрон": [
                "Акрон",
                "Акрон Тольятти",
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

        match = re.search(
            r"\b(\d{1,2})[./-]"
            r"(\d{1,2})[./-]"
            r"(20\d{2})\b",
            text,
        )

        if not match:
            return None

        day, month, year = match.groups()

        return (
            f"{year}-"
            f"{int(month):02d}-"
            f"{int(day):02d}"
        )

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
    ) -> Optional[Tuple[int, int]]:

        if not text:
            return None

        patterns = [
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
        ]

        for pattern in patterns:

            for home, away in re.findall(
                pattern,
                text,
            ):

                h = int(home)
                a = int(away)

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

            value = int(match.group(1))

            if 1 <= value <= EXPECTED_ROUNDS:
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

        matches = []

        text = soup.get_text(
            "\n",
            strip=True,
        )

        lines = [
            self._clean_text(line)
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
                self._extract_round(line)
            )

            if detected_round:
                current_round = detected_round

            match = self._parse_row(
                texts=[line],
                row_text=line,
                current_round=current_round,
                source=source,
                url=url,
            )

            if match:
                matches.append(match)

        return matches

    # ========================================================
    # CONTAINER
    # ========================================================

    def _extract_matches_from_container(
        self,
        container,
        round_number: int,
        source: str,
        url: str,
    ) -> List[Dict[str, Any]]:

        matches = []

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

            row_text = " ".join(texts)

            match = self._parse_row(
                texts=texts,
                row_text=row_text,
                current_round=round_number,
                source=source,
                url=url,
            )

            if match:
                matches.append(match)

        return matches

    # ========================================================
    # MATCH VALIDATION
    # ========================================================

    def _validate_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        result = []

        for match in matches:

            home = normalize_team_name(
                match.get("home_team"),
                strict=True,
            )

            away = normalize_team_name(
                match.get("away_team"),
                strict=True,
            )

            if not home or not away:
                continue

            if home == away:
                continue

            round_number = match.get(
                "round"
            )

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
            match["round"] = round_number

            result.append(match)

        return result

    # ========================================================
    # MERGE
    # ========================================================

    def _merge_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:

        unique = {}

        duplicates = []

        for match in matches:

            key = (
                match.get("season_year"),
                match.get("round"),
                match.get("home_team"),
                match.get("away_team"),
            )

            if key not in unique:

                item = dict(match)

                item["sources"] = [
                    {
                        "source":
                            match.get("source"),
                        "url":
                            match.get("source_url"),
                    }
                ]

                unique[key] = item

                continue

            existing = unique[key]

            existing.setdefault(
                "sources",
                [],
            ).append(
                {
                    "source":
                        match.get("source"),
                    "url":
                        match.get("source_url"),
                }
            )

            duplicates.append(
                {
                    "key": key,
                    "source":
                        match.get("source"),
                }
            )

            if (
                not existing.get("date")
                and match.get("date")
            ):
                existing["date"] = (
                    match["date"]
                )

            if (
                not existing.get("time")
                and match.get("time")
            ):
                existing["time"] = (
                    match["time"]
                )

            if (
                existing.get("home_goals")
                is None
                and match.get("home_goals")
                is not None
            ):

                existing["home_goals"] = (
                    match["home_goals"]
                )

                existing["away_goals"] = (
                    match["away_goals"]
                )

                existing["status"] = (
                    "finished"
                )

        return (
            list(unique.values()),
            duplicates,
        )

    # ========================================================
    # STRICT CALENDAR VALIDATION
    # ========================================================

    def _validate_calendar(
        self,
        matches: List[Dict[str, Any]],
        result: Dict[str, Any],
    ) -> None:

        errors = []
        warnings = []

        # ----------------------------------------------------
        # EMPTY
        # ----------------------------------------------------

        if not matches:

            errors.append(
                "Календарь пуст."
            )

            result["validation_errors"] = errors
            result["warnings"] = warnings
            result["calendar_valid"] = False

            return

        # ----------------------------------------------------
        # TEAM SET
        # ----------------------------------------------------

        expected_teams = set(
            CANONICAL_TEAMS
        )

        found_teams = set()

        for match in matches:

            found_teams.add(
                match["home_team"]
            )

            found_teams.add(
                match["away_team"]
            )

        unknown_teams = (
            found_teams
            - expected_teams
        )

        missing_teams = (
            expected_teams
            - found_teams
        )

        if unknown_teams:

            errors.append(
                "Неизвестные команды: "
                + ", ".join(
                    sorted(unknown_teams)
                )
            )

        if missing_teams:

            errors.append(
                "Команды отсутствуют: "
                + ", ".join(
                    sorted(missing_teams)
                )
            )

        if len(found_teams) != EXPECTED_TEAMS:

            errors.append(
                f"Найдено команд: "
                f"{len(found_teams)} "
                f"вместо {EXPECTED_TEAMS}."
            )

        # ----------------------------------------------------
        # TOTAL
        # ----------------------------------------------------

        total = len(matches)

        if total != EXPECTED_MATCHES:

            errors.append(
                f"Календарь содержит "
                f"{total} матчей вместо "
                f"{EXPECTED_MATCHES}."
            )

        # ----------------------------------------------------
        # ROUND COUNTS
        # ----------------------------------------------------

        round_counts = {
            number: 0
            for number in range(
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

        for (
            round_number,
            count,
        ) in round_counts.items():

            if count != EXPECTED_MATCHES_PER_ROUND:

                errors.append(
                    f"Тур {round_number}: "
                    f"{count} матчей "
                    f"вместо "
                    f"{EXPECTED_MATCHES_PER_ROUND}."
                )

        # ----------------------------------------------------
        # STRICT ROUND VALIDATION
        # ----------------------------------------------------

        duplicate_pairs = []
        duplicate_teams = []

        for round_number in range(
            1,
            EXPECTED_ROUNDS + 1,
        ):

            round_matches = [
                match
                for match in matches
                if match.get("round")
                == round_number
            ]

            teams_in_round = {}

            pairs_in_round = set()

            for match in round_matches:

                home = match["home_team"]
                away = match["away_team"]

                # --------------------------------------------
                # TEAM APPEARS TWICE
                # --------------------------------------------

                if home in teams_in_round:

                    duplicate_teams.append(
                        {
                            "round":
                                round_number,
                            "team":
                                home,
                            "first_match":
                                teams_in_round[
                                    home
                                ],
                            "second_match":
                                (
                                    home,
                                    away
                                ),
                        }
                    )

                else:

                    teams_in_round[home] = (
                        home,
                        away
                    )

                if away in teams_in_round:

                    duplicate_teams.append(
                        {
                            "round":
                                round_number,
                            "team":
                                away,
                            "first_match":
                                teams_in_round[
                                    away
                                ],
                            "second_match":
                                (
                                    home,
                                    away
                                ),
                        }
                    )

                else:

                    teams_in_round[away] = (
                        home,
                        away
                    )

                # --------------------------------------------
                # PAIR WITHOUT DIRECTION
                # --------------------------------------------

                pair = frozenset(
                    {
                        home,
                        away,
                    }
                )

                if pair in pairs_in_round:

                    duplicate_pairs.append(
                        {
                            "round":
                                round_number,
                            "home":
                                home,
                            "away":
                                away,
                        }
                    )

                else:

                    pairs_in_round.add(
                        pair
                    )

            # --------------------------------------------
            # 8 MATCHES MUST MEAN 16 TEAM APPEARANCES
            # --------------------------------------------

            if len(round_matches) == 8:

                if len(teams_in_round) != 16:

                    errors.append(
                        f"Тур {round_number}: "
                        f"участвуют "
                        f"{len(teams_in_round)} "
                        f"команд вместо 16."
                    )

        # ----------------------------------------------------
        # DUPLICATE PAIRS
        # ----------------------------------------------------

        for item in duplicate_pairs:

            errors.append(
                f"Тур {item['round']}: "
                f"повторная пара "
                f"{item['home']} — "
                f"{item['away']}."
            )

        # ----------------------------------------------------
        # DUPLICATE TEAM
        # ----------------------------------------------------

        for item in duplicate_teams:

            errors.append(
                f"Тур {item['round']}: "
                f"команда {item['team']} "
                f"играет более одного матча."
            )

        # ----------------------------------------------------
        # SAME TEAM
        # ----------------------------------------------------

        self_matches = []

        for match in matches:

            if (
                match["home_team"]
                == match["away_team"]
            ):

                self_matches.append(match)

                errors.append(
                    f"Тур {match['round']}: "
                    f"{match['home_team']} "
                    f"играет сама с собой."
                )

        # ----------------------------------------------------
        # ROUND COMPLETENESS
        # ----------------------------------------------------

        complete_rounds = sum(
            1
            for count
            in round_counts.values()
            if count == 8
        )

        # ----------------------------------------------------
        # FINAL RESULT
        # ----------------------------------------------------

        valid = (
            total == EXPECTED_MATCHES
            and complete_rounds
            == EXPECTED_ROUNDS
            and len(found_teams)
            == EXPECTED_TEAMS
            and not unknown_teams
            and not missing_teams
            and not duplicate_pairs
            and not duplicate_teams
            and not self_matches
            and not errors
        )

        result["validation"] = {

            "expected_rounds":
                EXPECTED_ROUNDS,

            "found_rounds":
                EXPECTED_ROUNDS,

            "complete_rounds":
                complete_rounds,

            "expected_matches":
                EXPECTED_MATCHES,

            "found_matches":
                total,

            "expected_teams":
                EXPECTED_TEAMS,

            "found_teams":
                len(found_teams),

            "duplicate_pairs":
                len(duplicate_pairs),

            "duplicate_team_appearances":
                len(duplicate_teams),

            "self_matches":
                len(self_matches),

            "status":
                "valid"
                if valid
                else "invalid",
        }

        result["validation_errors"] = errors
        result["warnings"] = warnings
        result["calendar_valid"] = valid

        if valid:

            logger.info(
                "================================================"
            )

            logger.info(
                "✅ КАЛЕНДАРЬ ПРОШЁЛ СТРОГУЮ ПРОВЕРКУ"
            )

            logger.info(
                "30 туров / 240 матчей / 16 команд"
            )

            logger.info(
                "================================================"
            )

        else:

            logger.error(
                "================================================"
            )

            logger.error(
                "❌ КАЛЕНДАРЬ НЕ ПРОШЁЛ ПРОВЕРКУ"
            )

            logger.error(
                "Найдено ошибок: %s",
                len(errors),
            )

            logger.error(
                "================================================"
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
# CONVENIENCE
# ============================================================

def parse_rpl_fixtures() -> Dict[str, Any]:

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
        "FAJ RPL FIXTURES PARSER v12.1 / 2.1"
    )
    print("=" * 70)

    print(
        f"Найдено матчей: "
        f"{len(result['matches'])}"
    )

    print(
        f"Дубликатов источников: "
        f"{len(result['duplicates'])}"
    )

    print(
        f"Ошибок источников: "
        f"{len(result['errors'])}"
    )

    print(
        f"Ошибок проверки: "
        f"{len(result['validation_errors'])}"
    )

    print(
        f"Календарь корректен: "
        f"{'ДА' if result['calendar_valid'] else 'НЕТ'}"
    )

    print()
    print("ПРОВЕРКА:")

    validation = result.get(
        "validation",
        {}
    )

    print(
        f"  Туров: "
        f"{validation.get('complete_rounds', 0)}/30"
    )

    print(
        f"  Матчей: "
        f"{validation.get('found_matches', 0)}/240"
    )

    print(
        f"  Команд: "
        f"{validation.get('found_teams', 0)}/16"
    )

    print(
        f"  Повторных пар: "
        f"{validation.get('duplicate_pairs', 0)}"
    )

    print(
        f"  Команд с двумя матчами: "
        f"{validation.get('duplicate_team_appearances', 0)}"
    )

    print(
        f"  Само-матчей: "
        f"{validation.get('self_matches', 0)}"
    )

    print()
    print("ИСТОЧНИКИ:")

    for (
        source,
        info,
    ) in result["sources"].items():

        print(
            f"  {source}: "
            f"{info['status']} "
            f"({info['matches']} матчей)"
        )

    print()
    print("ОШИБКИ ПРОВЕРКИ:")

    for error in result[
        "validation_errors"
    ]:

        print(
            f"  ❌ {error}"
        )

    print("=" * 70)

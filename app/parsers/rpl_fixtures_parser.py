#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
RPL Fixtures Parser

Источники:
    - Чемпионат
    - Soccerland
    - Smart Tables

Назначение:
    получение календаря РПЛ 2026/27.

Результат:
    единый список матчей FAJ.
"""

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.parsers.rpl_normalizer import normalize_team_name
from app.parsers.rpl_sources import RPL_SOURCES, SEASON, LEAGUE


logger = logging.getLogger(__name__)


class RPLFixturesParser:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    # ---------------------------------------------------------
    # HTTP
    # ---------------------------------------------------------

    def _get(self, url: str) -> Optional[BeautifulSoup]:

        try:
            response = requests.get(
                url,
                headers=self.HEADERS,
                timeout=self.timeout,
            )

            response.raise_for_status()

            return BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception as exc:
            logger.error(
                "Fixture parser HTTP error: %s | %s",
                url,
                exc,
            )
            return None

    # ---------------------------------------------------------
    # PUBLIC
    # ---------------------------------------------------------

    def parse(self) -> list[dict]:

        results = []

        # Сначала Чемпионат — основной источник календаря
        championat = self._parse_championat()

        if championat:
            results.extend(championat)

        # Если Чемпионат ничего не дал,
        # пробуем Soccerland
        if not results:
            soccerland = self._parse_soccerland()
            results.extend(soccerland)

        results = self._deduplicate(results)

        logger.info(
            "RPL fixtures parsed: %s",
            len(results),
        )

        return results

    # ---------------------------------------------------------
    # CHAMPIONAT
    # ---------------------------------------------------------

    def _parse_championat(self) -> list[dict]:

        url = RPL_SOURCES["championat"]["url"]

        soup = self._get(url)

        if not soup:
            return []

        matches = []

        current_round = None

        # Чемпионат отдаёт календарь таблицей.
        for row in soup.find_all("tr"):

            text = row.get_text(
                " ",
                strip=True,
            )

            if not text:
                continue

            round_match = re.search(
                r"\bТур\s*(\d+)",
                text,
                re.IGNORECASE,
            )

            if round_match:
                current_round = int(
                    round_match.group(1)
                )

            # Иногда номер тура находится отдельно
            if current_round is None:
                number_match = re.search(
                    r"^\s*(\d{1,2})\s+",
                    text,
                )

                if number_match:
                    current_round = int(
                        number_match.group(1)
                    )

            parsed = self._parse_match_text(
                text,
                current_round,
            )

            if parsed:
                parsed["source"] = "championat"
                matches.append(parsed)

        return matches

    # ---------------------------------------------------------
    # SOCCERLAND
    # ---------------------------------------------------------

    def _parse_soccerland(self) -> list[dict]:

        url = RPL_SOURCES["soccerland"]["url"]

        soup = self._get(url)

        if not soup:
            return []

        matches = []

        # Soccerland имеет текстовую структуру
        # "дата время | команда | счет | команда".
        # Используем ссылки команд как основной ориентир.

        for block in soup.find_all(
            ["div", "tr", "li"]
        ):

            text = block.get_text(
                " ",
                strip=True,
            )

            if not text:
                continue

            parsed = self._parse_match_text(
                text,
                None,
            )

            if parsed:
                parsed["source"] = "soccerland"
                matches.append(parsed)

        return self._deduplicate(matches)

    # ---------------------------------------------------------
    # MATCH PARSER
    # ---------------------------------------------------------

    def _parse_match_text(
        self,
        text: str,
        round_number: Optional[int],
    ) -> Optional[dict]:

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        # -----------------------------------------------------
        # DATE
        # -----------------------------------------------------

        date_match = re.search(
            r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})",
            text,
        )

        date_value = None

        if date_match:

            day, month, year = date_match.groups()

            try:
                date_value = (
                    f"{year}-{int(month):02d}-{int(day):02d}"
                )
            except ValueError:
                date_value = None

        # -----------------------------------------------------
        # TIME
        # -----------------------------------------------------

        time_match = re.search(
            r"\b(\d{1,2}):(\d{2})\b",
            text,
        )

        time_value = (
            time_match.group(0)
            if time_match
            else None
        )

        # -----------------------------------------------------
        # SCORE
        # -----------------------------------------------------

        score_match = re.search(
            r"\b(\d+)\s*[:\-]\s*(\d+)\b",
            text,
        )

        home_goals = None
        away_goals = None

        if score_match:

            home_goals = int(
                score_match.group(1)
            )

            away_goals = int(
                score_match.group(2)
            )

        # -----------------------------------------------------
        # TEAMS
        # -----------------------------------------------------

        teams = self._find_teams(text)

        if len(teams) < 2:
            return None

        home_team = normalize_team_name(
            teams[0]
        )

        away_team = normalize_team_name(
            teams[1]
        )

        if not home_team or not away_team:
            return None

        # -----------------------------------------------------
        # STATUS
        # -----------------------------------------------------

        if home_goals is not None:
            status = "finished"
        else:
            status = "scheduled"

        return {
            "season": SEASON,
            "league": LEAGUE,
            "competition": LEAGUE,
            "round": round_number,
            "date": date_value,
            "time": time_value,
            "home_team": home_team,
            "away_team": away_team,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "status": status,
        }

    # ---------------------------------------------------------
    # TEAM DETECTION
    # ---------------------------------------------------------

    def _find_teams(self, text: str) -> list[str]:

        known = [
            "Динамо Махачкала",
            "Динамо Мх",
            "Динамо Москва",
            "Динамо М",
            "Крылья Советов",
            "Крылья Советов Самара",
            "Спартак Москва",
            "Спартак М",
            "Локомотив Москва",
            "Локомотив М",
            "Ростов",
            "Ахмат",
            "Рубин",
            "Оренбург",
            "Факел",
            "Акрон",
            "Балтика",
            "Родина",
            "Краснодар",
            "Зенит",
            "Спартак",
            "ЦСКА",
            "Локомотив",
        ]

        found = []

        # Сначала длинные названия
        known.sort(
            key=len,
            reverse=True,
        )

        for team in known:

            if team in text:

                if team not in found:
                    found.append(team)

        return found[:2]

    # ---------------------------------------------------------
    # DEDUP
    # ---------------------------------------------------------

    def _deduplicate(
        self,
        matches: list[dict],
    ) -> list[dict]:

        result = {}
        
        for match in matches:

            key = (
                match.get("round"),
                match.get("date"),
                match.get("home_team"),
                match.get("away_team"),
            )

            if key not in result:
                result[key] = match
            else:
                # Предпочитаем запись с результатом
                old = result[key]

                if (
                    old.get("home_goals") is None
                    and match.get("home_goals") is not None
                ):
                    result[key] = match

        return list(result.values())

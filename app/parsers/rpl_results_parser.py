#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
RPL Results Parser

Источники:
    Чемпионат
    Soccerland

Назначение:
    получение фактических результатов сыгранных матчей.
"""

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.parsers.rpl_normalizer import normalize_team_name
from app.parsers.rpl_sources import RPL_SOURCES, SEASON


logger = logging.getLogger(__name__)


class RPLResultsParser:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/128.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def parse(self) -> list[dict]:

        matches = []

        matches.extend(
            self._parse_source(
                "championat"
            )
        )

        matches.extend(
            self._parse_source(
                "soccerland"
            )
        )

        return self._deduplicate(matches)

    def _parse_source(
        self,
        source_name: str,
    ) -> list[dict]:

        url = RPL_SOURCES[
            source_name
        ]["url"]

        try:

            response = requests.get(
                url,
                headers=self.HEADERS,
                timeout=self.timeout,
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

        except Exception as exc:

            logger.error(
                "Results parser error: %s | %s",
                source_name,
                exc,
            )

            return []

        result = []

        current_round = None

        for row in soup.find_all(
            ["tr", "div", "li"]
        ):

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

            score = re.search(
                r"\b(\d+)\s*[:\-]\s*(\d+)\b",
                text,
            )

            if not score:
                continue

            teams = self._find_teams(text)

            if len(teams) < 2:
                continue

            date_match = re.search(
                r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})",
                text,
            )

            date_value = None

            if date_match:

                day, month, year = date_match.groups()

                date_value = (
                    f"{year}-{int(month):02d}-{int(day):02d}"
                )

            result.append({
                "season": SEASON,
                "round": current_round,
                "date": date_value,
                "home_team": normalize_team_name(
                    teams[0]
                ),
                "away_team": normalize_team_name(
                    teams[1]
                ),
                "home_goals": int(
                    score.group(1)
                ),
                "away_goals": int(
                    score.group(2)
                ),
                "status": "finished",
                "source": source_name,
            })

        return result

    def _find_teams(self, text: str):

        known = [
            "Динамо Махачкала",
            "Динамо Мх",
            "Динамо Москва",
            "Динамо М",
            "Крылья Советов",
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

        known.sort(
            key=len,
            reverse=True,
        )

        found = []

        for team in known:

            if team in text:
                if team not in found:
                    found.append(team)

        return found[:2]

    def _deduplicate(
        self,
        matches: list[dict],
    ) -> list[dict]:

        unique = {}

        for match in matches:

            key = (
                match.get("round"),
                match.get("home_team"),
                match.get("away_team"),
            )

            # Если две записи — оставляем одну
            unique[key] = match

        return list(unique.values())

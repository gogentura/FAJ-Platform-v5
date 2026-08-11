#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
RPL Statistics Parser

Извлекает доступную матчевую статистику.
Если конкретный источник не предоставляет показатель,
возвращается None.

ВАЖНО:
None означает "данных нет",
а не 0.
"""

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class RPLStatsParser:

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/128.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def parse_match_page(
        self,
        url: str,
    ) -> Optional[dict]:

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
                "Stats parser error: %s",
                exc,
            )

            return None

        text = soup.get_text(
            " ",
            strip=True,
        )

        stats = {
            "home_xg": None,
            "away_xg": None,

            "home_shots": None,
            "away_shots": None,

            "home_shots_on_target": None,
            "away_shots_on_target": None,

            "home_possession": None,
            "away_possession": None,

            "home_corners": None,
            "away_corners": None,

            "home_yellow_cards": None,
            "away_yellow_cards": None,

            "home_pass_accuracy": None,
            "away_pass_accuracy": None,
        }

        # xG
        match = re.search(
            r"(?:xG|Ожидаемые голы)"
            r".{0,100}?"
            r"(\d+[.,]\d+)"
            r".{0,100}?"
            r"(\d+[.,]\d+)",
            text,
            re.IGNORECASE,
        )

        if match:

            stats["home_xg"] = self._float(
                match.group(1)
            )

            stats["away_xg"] = self._float(
                match.group(2)
            )

        # Владение
        match = re.search(
            r"Владение.{0,100}?"
            r"(\d+)%"
            r".{0,100}?"
            r"(\d+)%",
            text,
            re.IGNORECASE,
        )

        if match:

            stats["home_possession"] = int(
                match.group(1)
            )

            stats["away_possession"] = int(
                match.group(2)
            )

        # Удары
        match = re.search(
            r"Удары(?!\s+в\s+створ)"
            r".{0,100}?"
            r"(\d+)"
            r".{0,100}?"
            r"(\d+)",
            text,
            re.IGNORECASE,
        )

        if match:

            stats["home_shots"] = int(
                match.group(1)
            )

            stats["away_shots"] = int(
                match.group(2)
            )

        # Удары в створ
        match = re.search(
            r"Удары\s+в\s+створ"
            r".{0,100}?"
            r"(\d+)"
            r".{0,100}?"
            r"(\d+)",
            text,
            re.IGNORECASE,
        )

        if match:

            stats["home_shots_on_target"] = int(
                match.group(1)
            )

            stats["away_shots_on_target"] = int(
                match.group(2)
            )

        # Угловые
        match = re.search(
            r"Угловые"
            r".{0,100}?"
            r"(\d+)"
            r".{0,100}?"
            r"(\d+)",
            text,
            re.IGNORECASE,
        )

        if match:

            stats["home_corners"] = int(
                match.group(1)
            )

            stats["away_corners"] = int(
                match.group(2)
            )

        # Желтые
        match = re.search(
            r"(?:Желтые|ЖК)"
            r".{0,100}?"
            r"(\d+)"
            r".{0,100}?"
            r"(\d+)",
            text,
            re.IGNORECASE,
        )

        if match:

            stats["home_yellow_cards"] = int(
                match.group(1)
            )

            stats["away_yellow_cards"] = int(
                match.group(2)
            )

        return stats

    @staticmethod
    def _float(value):

        try:
            return float(
                str(value).replace(",", ".")
            )
        except Exception:
            return None

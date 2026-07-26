# =====================================================
# FAJ Platform v7.0
# Soccer365 Calendar Source
#
# Источник календаря РПЛ
# =====================================================

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class Soccer365Calendar:

    URL = "https://soccer365.ru/competitions/13/"

    BASE_URL = "https://soccer365.ru"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64)"
        )
    }

    # ==========================================
    # HTML
    # ==========================================

    def get_html(self):

        try:

            r = requests.get(

                self.URL,

                headers=self.HEADERS,

                timeout=20

            )

            if r.status_code != 200:

                logger.error(

                    f"Soccer365 HTTP {r.status_code}"

                )

                return None

            return r.text

        except Exception as e:

            logger.exception(e)

            return None

    # ==========================================
    # TEAM NORMALIZATION
    # ==========================================

    @staticmethod
    def normalize_team(name):

        mapping = {

            "Спартак Москва": "Спартак",
            "Локомотив Москва": "Локомотив",
            "Динамо Москва": "Динамо М",
            "Динамо Махачкала": "Динамо Мх",
            "ЦСКА Москва": "ЦСКА"

        }

        return mapping.get(

            name.strip(),

            name.strip()

        )

    # ==========================================
    # DATE
    # ==========================================

    @staticmethod
    def convert_date(value):

        day, month = value.split(".")

        year = datetime.now().year

        return f"{year}-{month}-{day}"

    # ==========================================
    # MATCH URL
    # ==========================================

    def extract_match_url(self, href):

        if not href:

            return None

        if href.startswith("http"):

            return href

        return self.BASE_URL + href

    # ==========================================
    # CALENDAR
    # ==========================================

    def get_calendar(self):

        html = self.get_html()

        if not html:

            return []

        soup = BeautifulSoup(

            html,

            "html.parser"

        )

        fixtures = []

        links = soup.find_all("a", href=True)

        pattern = re.compile(

            r"(\d{2}\.\d{2}),\s*"
            r"(\d{2}:\d{2})\s+"
            r"(.+?)\s*-\s*"
            r"(.+?)$"

        )

        for link in links:

            text = link.get_text(

                " ",

                strip=True

            )

            m = pattern.search(text)

            if not m:

                continue

            fixture = {

                "league": "RPL",

                "season": "2026/27",

                "date": self.convert_date(
                    m.group(1)
                ),

                "time": m.group(2),

                "home_team": self.normalize_team(
                    m.group(3)
                ),

                "away_team": self.normalize_team(
                    m.group(4)
                ),

                "status": "scheduled",

                "match_url": self.extract_match_url(
                    link.get("href")
                )

            }

            fixtures.append(fixture)

        logger.info(

            f"Calendar parsed: {len(fixtures)}"

        )

        return fixtures

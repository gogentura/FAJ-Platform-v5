# =====================================================
# FAJ Platform v6.2
# Soccer365 Statistics Source
# =====================================================

import logging
import re

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class Soccer365StatsSource:

    BASE_URL = "https://soccer365.ru"

    HEADERS = {
        "User-Agent": "Mozilla/5.0"
    }

    # ==================================================
    # HTML
    # ==================================================

    def get_html(self, url: str):

        try:

            response = requests.get(

                url,

                headers=self.HEADERS,

                timeout=20

            )

            if response.status_code != 200:

                logger.error(
                    f"Soccer365 HTTP {response.status_code}"
                )

                return None

            return response.text

        except Exception as e:

            logger.exception(e)

            return None

    # ==================================================
    # FIND MATCH PAGE
    # ==================================================

    def find_match_url(

        self,

        home_team,

        away_team

    ):

        """
        Пока используется поиск по Soccer365.
        Позже будем брать URL прямо из fixtures.
        """

        query = (
            f"{home_team} {away_team}"
        )

        search_url = (
            f"https://soccer365.ru/search/?q={query}"
        )

        html = self.get_html(search_url)

        if not html:

            return None

        soup = BeautifulSoup(html, "html.parser")

        for link in soup.find_all("a", href=True):

            href = link["href"]

            if "/live/" in href or "/matches/" in href:

                return self.BASE_URL + href

        return None

    # ==================================================
    # PARSE STATISTICS
    # ==================================================

    def load_statistics(

        self,

        home_team,

        away_team

    ):

        url = self.find_match_url(

            home_team,

            away_team

        )

        if not url:

            logger.warning(
                "Match URL not found"
            )

            return None

        html = self.get_html(url)

        if not html:

            return None

        soup = BeautifulSoup(html, "html.parser")

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

            "home_yellow": None,
            "away_yellow": None,

            "home_red": None,
            "away_red": None

        }

        text = soup.get_text(" ", strip=True)

        # ==========================================
        # xG
        # ==========================================

        xg = re.findall(

            r"xG\s*([\d.]+)",

            text

        )

        if len(xg) >= 2:

            stats["home_xg"] = float(xg[0])

            stats["away_xg"] = float(xg[1])

        # ==========================================
        # Дальше будут постепенно добавляться:
        #
        # удары
        # владение
        # угловые
        # карточки
        #
        # после анализа HTML.
        # ==========================================

        return stats

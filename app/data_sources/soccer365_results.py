# =====================================================
# FAJ Platform v7.0
# Soccer365 Results Source
# =====================================================

import logging
import re

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class Soccer365Results:

    URL = "https://soccer365.ru/competitions/13/results/"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64)"
        )
    }

    # =================================================
    # HTML
    # =================================================

    def get_html(self):

        try:

            response = requests.get(

                self.URL,

                headers=self.HEADERS,

                timeout=20

            )

            if response.status_code != 200:

                logger.error(
                    f"HTTP {response.status_code}"
                )

                return None

            return response.text

        except Exception as e:

            logger.exception(e)

            return None

    # =================================================
    # TEAM NORMALIZATION
    # =================================================

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

    # =================================================
    # RESULTS
    # =================================================

    def get_results(self):

        html = self.get_html()

        if not html:

            return []

        soup = BeautifulSoup(

            html,

            "html.parser"

        )

        text = soup.get_text(

            " ",

            strip=True

        )

        results = []

        pattern = re.compile(

            r"([А-ЯA-Za-zЁё\s\-]+?)\s+"
            r"(\d+)\s*:\s*(\d+)\s+"
            r"([А-ЯA-Za-zЁё\s\-]+)"

        )

        matches = pattern.findall(text)

        for match in matches:

            home = self.normalize_team(match[0])

            away = self.normalize_team(match[3])

            home_score = int(match[1])

            away_score = int(match[2])

            results.append({

                "home_team": home,

                "away_team": away,

                "home_score": home_score,

                "away_score": away_score,

                "status": "finished"

            })

        logger.info(

            f"Soccer365 results parsed: {len(results)}"

        )

        return results

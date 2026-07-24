# =====================================================
# FAJ Platform v6.2
# Soccer365 Source v2
# RPL Calendar Parser
# =====================================================

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class Soccer365Source:


    URL = (
        "https://soccer365.ru/competitions/13/"
    )


    HEADERS = {

        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    }


    # =================================================
    # LOAD HTML
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

                    f"Soccer365 HTTP {response.status_code}"

                )

                return None


            return response.text


        except Exception as e:

            logger.exception(e)

            return None



    # =================================================
    # PARSE CALENDAR
    # =================================================

    def parse_calendar(self):


        html = self.get_html()


        if not html:

            return []


        soup = BeautifulSoup(

            html,

            "html.parser"

        )


        fixtures = []


        links = soup.find_all("a")


        for link in links:


            text = link.get_text(

                " ",

                strip=True

            )


            if not text:

                continue



            # -----------------------------------------
            # ищем строки матчей
            #
            # пример:
            #
            # 25.07, 06:15 Акрон - Зенит -
            #
            # -----------------------------------------


            match = re.search(

                r"(\d{2}\.\d{2}),\s*"
                r"(\d{2}:\d{2})\s+"
                r"(.+?)\s+-\s+"
                r"(.+?)\s+-$",

                text

            )


            if not match:

                continue



            date = match.group(1)

            time = match.group(2)

            home = match.group(3).strip()

            away = match.group(4).strip()



            # фильтр мусора

            banned = [

                "Видео",

                "Обзор",

                "Турнир",

                "Лига",

                "Премьер-Лига"

            ]


            if any(

                x in home

                for x in banned

            ):

                continue



            if any(

                x in away

                for x in banned

            ):

                continue



            fixtures.append(

                {

                    "league":
                    "RPL",


                    "season":
                    "2026/27",


                    "date":
                    self.convert_date(date),


                    "time":
                    time,


                    "home_team":
                    self.normalize_team(home),


                    "away_team":
                    self.normalize_team(away),


                    "status":
                    "scheduled"

                }

            )



        logger.info(

            f"Soccer365 parsed fixtures: {len(fixtures)}"

        )


        return fixtures



    # =================================================
    # DATE
    # =================================================

    def convert_date(
        self,
        value
    ):

        day, month = value.split(".")


        year = datetime.now().year


        return (
            f"{year}-"
            f"{month}-"
            f"{day}"
        )



    # =================================================
    # TEAM NORMALIZATION
    # =================================================

    def normalize_team(
        self,
        name
    ):


        mapping = {


            "Динамо Махачкала":
            "Динамо Мх",


            "Динамо Москва":
            "Динамо М",


            "Локомотив Москва":
            "Локомотив",


            "Спартак Москва":
            "Спартак",


            "Ростов":
            "Ростов",


            "Акрон":
            "Акрон",


            "Зенит":
            "Зенит"

        }


        return mapping.get(

            name,

            name

        )

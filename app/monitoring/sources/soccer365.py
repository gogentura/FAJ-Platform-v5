# =====================================================
# FAJ Platform v6.3
# Soccer365 Source v3
#
# RPL Calendar + Match URL
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


    BASE_URL = (
        "https://soccer365.ru"
    )


    HEADERS = {

        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

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
                    f"Soccer365 HTTP {response.status_code}"
                )

                return None


            return response.text


        except Exception as e:

            logger.exception(e)

            return None



    # =================================================
    # CALENDAR PARSER
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



        links = soup.find_all(

            "a",

            href=True

        )



        for link in links:


            text = link.get_text(

                " ",

                strip=True

            )



            if not text:

                continue



            # пример:
            #
            # 25.07, 06:15 Акрон - Зенит -
            #


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



            banned = [

                "Видео",

                "Обзор",

                "Лига",

                "Премьер"

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



            fixture_url = self.extract_match_url(

                link

            )



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
                    "scheduled",


                    "match_url":
                    fixture_url

                }

            )



        logger.info(

            f"Soccer365 parsed fixtures: {len(fixtures)}"

        )


        return fixtures




    # =================================================
    # MATCH URL
    # =================================================

    def extract_match_url(

        self,

        link

    ):


        href = link.get(

            "href"

        )


        if not href:

            return None



        # матчи Soccer365 обычно:

        if (

            "/live/" in href

            or

            "/matches/" in href

        ):


            if href.startswith("http"):

                return href


            return (

                self.BASE_URL

                +

                href

            )



        return None




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


            "Динамо Москва":
            "Динамо М",


            "Динамо Махачкала":
            "Динамо Мх",


            "Локомотив Москва":
            "Локомотив",


            "Спартак Москва":
            "Спартак"

        }



        return mapping.get(

            name,

            name

        )

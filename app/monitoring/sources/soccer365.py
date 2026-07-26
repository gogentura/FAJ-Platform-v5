# =====================================================
# FAJ Platform v6.8
# app/monitoring/sources/soccer365.py
#
# Soccer365 Source
#
# Calendar + Results Parser
# RPL
# =====================================================


import logging
import re

from datetime import datetime

import requests

from bs4 import BeautifulSoup



logger = logging.getLogger(__name__)




class Soccer365Source:



    # =================================================
    # URLS
    # =================================================


    CALENDAR_URL = (

        "https://soccer365.ru/competitions/13/"

    )


    RESULTS_URL = (

        "https://soccer365.ru/competitions/13/results/"

    )


    TABLE_URL = (

        "https://soccer365.ru/competitions/13/table/"

    )


    BASE_URL = (

        "https://soccer365.ru"

    )



    HEADERS = {


        "User-Agent":

        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


    }




    # =================================================
    # HTML REQUEST
    # =================================================


    def get_html(
        self,
        url
    ):


        try:


            response = requests.get(

                url,

                headers=self.HEADERS,

                timeout=20

            )



            if response.status_code != 200:


                logger.error(

                    f"SOC365 HTTP {response.status_code}"

                )

                return None



            return response.text



        except Exception as e:


            logger.exception(e)

            return None





    # =================================================
    # CALENDAR
    # =================================================


    def parse_calendar(self):


        html = self.get_html(

            self.CALENDAR_URL

        )


        if not html:

            return []



        soup = BeautifulSoup(

            html,

            "html.parser"

        )


        fixtures = []



        for block in soup.select(

            ".game_block"

        ):



            text = block.get_text(

                " ",

                strip=True

            )



            match = re.search(

                r"(\d{2}\.\d{2})"
                r".*?"
                r"(\d{2}:\d{2})"
                r".*?"
                r"(.+?)"
                r"\s-\s"
                r"(.+?)$",

                text

            )



            if not match:

                continue



            fixtures.append(

                {

                    "league":
                    "RPL",


                    "season":
                    "2026/27",


                    "date":
                    self.convert_date(

                        match.group(1)

                    ),


                    "time":
                    match.group(2),


                    "home_team":
                    self.normalize_team(

                        match.group(3)

                    ),


                    "away_team":
                    self.normalize_team(

                        match.group(4)

                    ),


                    "status":

                    "scheduled",



                    "match_url":

                    self.extract_url(

                        block

                    )

                }

            )



        logger.info(

            f"Calendar parsed: {len(fixtures)}"

        )


        return fixtures





    # =================================================
    # RESULTS
    # =================================================


    def get_results(self):


        html = self.get_html(

            self.RESULTS_URL

        )


        if not html:


            return []



        soup = BeautifulSoup(

            html,

            "html.parser"

        )



        results = []



        blocks = soup.select(

            ".game_block"

        )



        for block in blocks:



            text = block.get_text(

                " ",

                strip=True

            )



            # ищем счёт

            score = re.search(

                r"(\d+)\s*:\s*(\d+)",

                text

            )



            if not score:

                continue



            # команды


            teams = re.search(

                r"(.+?)\s-\s(.+?)",

                text

            )



            if not teams:

                continue



            home = teams.group(1).strip()

            away = teams.group(2).strip()



            # защита от меню


            if home in [

                "Россия",

                "Премьер-Лига",

                "Результаты"

            ]:

                continue



            results.append(

                {


                    "home_team":

                    self.normalize_team(

                        home

                    ),


                    "away_team":

                    self.normalize_team(

                        away

                    ),


                    "home_score":

                    int(score.group(1)),


                    "away_score":

                    int(score.group(2)),


                    "status":

                    "finished"

                }

            )



        logger.info(

            f"Results parsed: {len(results)}"

        )


        return results





    # =================================================
    # MATCH URL
    # =================================================


    def extract_url(

        self,

        block

    ):


        link = block.find(

            "a",

            href=True

        )



        if not link:

            return None



        href = link.get(

            "href"

        )



        if href.startswith(

            "http"

        ):

            return href



        return (

            self.BASE_URL

            +

            href

        )





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
    # TEAM NORMALIZE
    # =================================================


    def normalize_team(

        self,

        name

    ):


        name = name.strip()



        mapping = {


            "Динамо Москва":

            "Динамо М",



            "Динамо Махачкала":

            "Динамо Мх",



            "Локомотив Москва":

            "Локомотив",



            "Спартак Москва":

            "Спартак",



            "ЦСКА Москва":

            "ЦСКА"


        }



        return mapping.get(

            name,

            name

        )

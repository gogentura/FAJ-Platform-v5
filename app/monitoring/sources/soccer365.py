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


    BASE_URL = (
        "https://soccer365.ru"
    )



    HEADERS = {

        "User-Agent":

        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    }





    # =================================================
    # LOAD HTML
    # =================================================


    def get_html(
        self,
        url=None
    ):


        try:


            if url is None:

                url = self.CALENDAR_URL



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





    # =================================================
    # CALENDAR PARSER
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



        blocks = soup.select(

            ".game_block"

        )



        for block in blocks:


            text = block.get_text(

                " ",

                strip=True

            )



            match = re.search(

                r"(\d{2}\.\d{2}).*?"
                r"(\d{2}:\d{2}).*?"
                r"(.+?)\s-\s(.+?)(?:\s|$)",

                text

            )



            if not match:

                continue



            home = self.normalize_team(

                match.group(3)

            )


            away = self.normalize_team(

                match.group(4)

            )



            if not home or not away:

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

                    home,


                    "away_team":

                    away,


                    "status":

                    "scheduled",


                    "match_url":

                    self.extract_url(

                        block

                    )

                }

            )



        logger.info(

            f"Calendar fixtures: {len(fixtures)}"

        )



        return fixtures





    # =================================================
    # RESULTS PARSER
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



            # ищем команды


            teams = re.search(

                r"(.+?)\s-\s(.+?)",

                text

            )



            if not teams:

                continue



            # ищем счет


            score = re.search(

                r"(\d+)\s*:\s*(\d+)",

                text

            )



            if not score:

                continue



            home = self.normalize_team(

                teams.group(1)

            )


            away = self.normalize_team(

                teams.group(2)

            )



            # исключаем меню сайта


            banned = [

                "Россия",

                "Премьер",

                "Результаты",

                "Таблица",

                "Статистика"

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




            results.append(

                {


                    "home_team":

                    home,


                    "away_team":

                    away,


                    "home_score":

                    int(

                        score.group(1)

                    ),


                    "away_score":

                    int(

                        score.group(2)

                    ),


                    "status":

                    "finished"

                }

            )



        logger.info(

            f"Results found: {len(results)}"

        )



        return results





    # =================================================
    # COMPATIBILITY
    # =================================================


    def parse_results(self):

        """
        Старый интерфейс FAJ v6.2-v6.5

        Используется:
        debug_results
        старые handler
        """

        return self.get_results()





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
    # DATE CONVERT
    # =================================================


    def convert_date(

        self,

        value

    ):


        try:


            day, month = value.split(".")



            year = datetime.now().year



            return (

                f"{year}-"

                f"{month}-"

                f"{day}"

            )


        except:


            return None





    # =================================================
    # TEAM NORMALIZATION
    # =================================================


    def normalize_team(

        self,

        name

    ):


        if not name:

            return ""



        name = (

            name

            .replace(

                "\n",

                " "

            )

            .strip()

        )



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

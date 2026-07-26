# =====================================================
# FAJ Platform v6.8
# app/monitoring/sources/soccer365.py
#
# Soccer365 Source
#
# Calendar + Results Parser
# =====================================================


import logging
import re

from datetime import datetime

import requests

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class Soccer365Source:


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
    # HTML
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
    # CALENDAR
    # =================================================


    def parse_calendar(self):


        html = self.get_html(

            self.CALENDAR_URL

        )


        if not html:

            return []



        text = BeautifulSoup(

            html,

            "html.parser"

        ).get_text(

            " ",

            strip=True

        )



        fixtures = []



        pattern = re.compile(

            r"(\d{2}\.\d{2}),\s*(\d{2}:\d{2}).{0,100}?"
            r"([А-Яа-яЁё\s]+)"
            r"\s[-―]\s"
            r"([А-Яа-яЁё\s]+)"

        )



        matches = pattern.findall(text)



        for item in matches:


            fixtures.append(

                {

                    "league":
                    "RPL",

                    "season":
                    "2026/27",

                    "date":
                    self.convert_date(
                        item[0]
                    ),

                    "time":
                    item[1],

                    "home_team":
                    self.normalize_team(
                        item[2]
                    ),

                    "away_team":
                    self.normalize_team(
                        item[3]
                    ),

                    "status":
                    "scheduled"

                }

            )



        logger.info(

            f"Calendar found {len(fixtures)}"

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


        text = soup.get_text(

            "\n",

            strip=True

        )



        results = []



        # ищем:
        #
        # Акрон
        # -
        # Зенит
        # 0
        # :
        # 5
        #


        pattern = re.compile(

            r"([А-Яа-яЁё\s]+)"
            r"\s[-―]\s"
            r"([А-Яа-яЁё\s]+)"
            r".{0,150}?"
            r"(\d+)"
            r"\s*:\s*"
            r"(\d+)",

            re.S

        )



        matches = pattern.findall(

            text

        )



        for item in matches:


            home = self.normalize_team(

                item[0]

            )


            away = self.normalize_team(

                item[1]

            )



            if not home or not away:

                continue



            if self.is_garbage_team(
                home
            ):

                continue



            if self.is_garbage_team(
                away
            ):

                continue



            results.append(

                {

                    "home_team":
                    home,

                    "away_team":
                    away,

                    "home_score":
                    int(item[2]),

                    "away_score":
                    int(item[3]),

                    "status":
                    "finished"

                }

            )



        logger.info(

            f"Soccer365 results: {len(results)}"

        )



        return results





    # =================================================
    # OLD COMPATIBILITY
    # =================================================


    def parse_results(self):

        return self.get_results()





    # =================================================
    # URL
    # =================================================


    def extract_match_url(
        self,
        href
    ):


        if not href:

            return None



        if href.startswith("http"):

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


        try:

            day, month = value.split(".")


            year = datetime.now().year


            return (

                f"{year}-{month}-{day}"

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


            "Динамо Махачкала ":
            "Динамо Мх",


            "ЦСКА Москва":
            "ЦСКА",


            "Спартак Москва":
            "Спартак",


            "Локомотив Москва":
            "Локомотив",


            "Акрон Тольятти":
            "Акрон",


            "Ростов-на-Дону":
            "Ростов"

        }



        return mapping.get(

            name,

            name

        )





    # =================================================
    # FILTER
    # =================================================


    def is_garbage_team(

        self,

        name

    ):


        garbage = [

            "Россия",

            "Премьер",

            "Результаты",

            "Таблица",

            "Матчи",

            "Новости",

            "Соревнования",

            "Soccer365"

        ]



        for word in garbage:

            if word.lower() in name.lower():

                return True



        return False

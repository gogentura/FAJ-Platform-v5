# =====================================================
# FAJ Platform v6.7
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



    # ===============================
    # URLS
    # ===============================


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
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "Chrome/120 Safari/537.36"
        )

    }






    # =====================================================
    # HTML REQUEST
    # =====================================================


    def request_html(
        self,
        url
    ):


        try:


            response = requests.get(

                url,

                headers=self.HEADERS,

                timeout=20

            )


            logger.info(

                f"Soccer365 HTTP {url}: {response.status_code}"

            )



            if response.status_code != 200:

                return None



            logger.info(

                f"HTML size: {len(response.text)}"

            )



            return response.text



        except Exception as e:


            logger.exception(e)

            return None






    # =====================================================
    # CALENDAR HTML
    # =====================================================


    def get_html(self):


        return self.request_html(

            self.CALENDAR_URL

        )






    # =====================================================
    # RESULTS HTML
    # =====================================================


    def get_results_html(self):


        return self.request_html(

            self.RESULTS_URL

        )







    # =====================================================
    # CALENDAR PARSER
    # =====================================================


    def parse_calendar(self):


        html = self.get_html()



        if not html:

            return []



        soup = BeautifulSoup(

            html,

            "html.parser"

        )



        fixtures = []



        for link in soup.find_all(

            "a",

            href=True

        ):



            text = link.get_text(

                " ",

                strip=True

            )



            match = re.search(

                r"(\d{2}\.\d{2}),\s*"
                r"(\d{2}:\d{2})\s+"
                r"(.+?)\s+-\s+"
                r"(.+?)(?:\s+-|\s)$",

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



                    "match_date":

                    self.convert_date(

                        match.group(1)

                    ),



                    "match_time":

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

                    self.extract_match_url(

                        link

                    )

                }

            )



        logger.info(

            f"Calendar fixtures: {len(fixtures)}"

        )



        return fixtures







    # =====================================================
    # RESULTS PARSER
    # =====================================================


    def parse_results(self):


        html = self.get_results_html()



        if not html:


            logger.warning(

                "Results html empty"

            )

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




        patterns = [


            # Динамо М - Крылья Советов 0:0

            r"(.+?)\s-\s(.+?)\s(\d+):(\d+)",



            # Динамо М - Крылья Советов (0:0)

            r"(.+?)\s-\s(.+?)\s\((\d+):(\d+)\)",



            # Динамо М 0 - Крылья Советов 0

            r"(.+?)\s(\d+)\s-\s(.+?)\s(\d+)"

        ]





        found = False



        for pattern in patterns:



            matches = re.findall(

                pattern,

                text

            )



            if not matches:

                continue



            found = True



            logger.info(

                f"Result pattern matched: {len(matches)}"

            )



            for m in matches:


                try:


                    if len(m) == 4:



                        home = m[0]

                        away = m[1]

                        hs = int(m[2])

                        aws = int(m[3])



                    else:

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

                            hs,



                            "away_score":

                            aws,



                            "status":

                            "finished"

                        }

                    )


                except:


                    continue



            break




        logger.info(

            f"Final results parsed: {len(results)}"

        )



        return results







    # =====================================================
    # URL
    # =====================================================


    def extract_match_url(

        self,

        link

    ):


        href = link.get(

            "href"

        )



        if not href:

            return None



        if href.startswith(

            "http"

        ):

            return href



        return (

            self.BASE_URL

            +

            href

        )







    # =====================================================
    # DATE
    # =====================================================


    def convert_date(

        self,

        value

    ):


        day, month = value.split(".")



        year = datetime.now().year



        return (

            f"{year}-{month}-{day}"

        )







    # =====================================================
    # TEAM NORMALIZATION
    # =====================================================


    def normalize_team(

        self,

        name

    ):


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

            "Спартак"

        }



        return mapping.get(

            name,

            name

        )

# =====================================================
# FAJ Platform v6.6
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



    URL = (
        "https://soccer365.ru/competitions/13/"
    )


    BASE_URL = (
        "https://soccer365.ru"
    )



    HEADERS = {

        "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        )

    }





    # =================================================
    # HTML LOAD
    # =================================================


    def get_html(self):


        try:


            response = requests.get(

                self.URL,

                headers=self.HEADERS,

                timeout=20

            )



            logger.info(

                f"Soccer365 HTTP: {response.status_code}"

            )



            if response.status_code != 200:

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




            match = re.search(

                r"(\d{2}\.\d{2}),\s*"
                r"(\d{2}:\d{2})\s+"
                r"(.+?)\s+-\s+"
                r"(.+?)(?:\s+-|\s)$",

                text

            )



            if not match:

                continue



            day_month = match.group(1)

            match_time = match.group(2)

            home = match.group(3).strip()

            away = match.group(4).strip()



            fixtures.append(

                {

                    "league":

                    "RPL",



                    "season":

                    "2026/27",



                    "match_date":

                    self.convert_date(

                        day_month

                    ),



                    "match_time":

                    match_time,



                    "home_team":

                    self.normalize_team(

                        home

                    ),



                    "away_team":

                    self.normalize_team(

                        away

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

            f"Soccer365 fixtures parsed: {len(fixtures)}"

        )



        return fixtures







    # =================================================
    # RESULTS PARSER
    # =================================================


    def parse_results(self):


        html = self.get_html()



        if not html:

            logger.warning(

                "Soccer365 empty html"

            )

            return []




        logger.info(

            f"Soccer365 html length: {len(html)}"

        )



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



            # Акрон - Зенит 0:5

            r"(.+?)\s-\s(.+?)\s"
            r"(\d+):(\d+)",



            # Акрон - Зенит (0:5)

            r"(.+?)\s-\s(.+?)\s"
            r"\((\d+):(\d+)\)",



            # Акрон 0 Зенит 5

            r"(.+?)\s(\d+)\s+"
            r"(.+?)\s(\d+)"

        ]




        for pattern in patterns:



            matches = re.findall(

                pattern,

                text

            )



            if not matches:

                continue



            logger.info(

                f"Pattern results found: {len(matches)}"

            )



            for match in matches:



                try:



                    if len(match) == 4:



                        home = match[0]

                        home_score = int(

                            match[1]

                        )


                        away = match[2]

                        away_score = int(

                            match[3]

                        )



                    else:

                        continue





                    results.append(

                        {


                        "home_team":

                        self.normalize_team(

                            home.strip()

                        ),



                        "away_team":

                        self.normalize_team(

                            away.strip()

                        ),



                        "home_score":

                        home_score,



                        "away_score":

                        away_score,



                        "status":

                        "finished"


                        }

                    )



                except Exception:


                    continue



            break




        logger.info(

            f"Soccer365 results parsed: {len(results)}"

        )



        return results







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



            "Ростов":

            "Ростов"

        }



        return mapping.get(

            name,

            name

        )

# =====================================================
# FAJ Platform v6.2
# Soccer365 Source
# RPL Calendar + Results
# =====================================================

import requests
from bs4 import BeautifulSoup

import logging


logger = logging.getLogger(__name__)


class Soccer365Source:


    URL = (
        "https://soccer365.ru/competitions/13/"
    )


    HEADERS = {

        "User-Agent":
        "Mozilla/5.0"

    }


    # ================================================
    # LOAD HTML
    # ================================================

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



    # ================================================
    # PARSE CALENDAR
    # ================================================

    def parse_calendar(self):


        html = self.get_html()


        if not html:

            return []


        soup = BeautifulSoup(

            html,

            "html.parser"

        )


        fixtures = []


        # --------------------------------------------
        # Здесь будет адаптация под HTML Soccer365
        #
        # Пока проверяем структуру.
        # --------------------------------------------


        links = soup.find_all(
            "a"
        )


        for link in links:


            text = link.get_text(

                " ",

                strip=True

            )


            if "-" in text:


                fixtures.append(

                    {

                        "raw":

                        text

                    }

                )



        logger.info(

            f"Soccer365 found {len(fixtures)} objects"

        )


        return fixtures

# =====================================================
# FAJ Platform v6.1
# app/monitoring/sources/sportexpress.py
#
# Sport-Express Data Source
# =====================================================


import requests

from requests.exceptions import (
    RequestException,
    Timeout,
    ConnectionError
)




# =====================================================
# SOURCE CONFIG
# =====================================================


class SportExpressSource:


    BASE_URL = (

        "https://www.sport-express.ru"

    )



    HEADERS = {


        "User-Agent":

        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        ),


        "Accept":

        (
            "text/html,"
            "application/xhtml+xml,"
            "application/xml;q=0.9,"
            "*/*;q=0.8"
        ),


        "Accept-Language":

        "ru-RU,ru;q=0.9,en;q=0.8",


    }



    TIMEOUT = 20




    # =================================================
    # GET PAGE
    # =================================================


    def get_page(
        self,
        url: str
    ):


        try:


            response = requests.get(

                url,

                headers=self.HEADERS,

                timeout=self.TIMEOUT

            )



            response.raise_for_status()



            return response.text




        except Timeout:



            print(

                "SPORTEXPRESS TIMEOUT:",

                url

            )


            return None





        except ConnectionError:



            print(

                "SPORTEXPRESS CONNECTION ERROR:",

                url

            )


            return None





        except RequestException as e:



            print(

                "SPORTEXPRESS REQUEST ERROR:",

                e

            )


            return None





        except Exception as e:



            print(

                "SPORTEXPRESS UNKNOWN ERROR:",

                e

            )


            return None





    # =================================================
    # CHECK SOURCE
    # =================================================


    def check_source(
        self
    ):


        try:


            response = requests.get(

                self.BASE_URL,

                headers=self.HEADERS,

                timeout=self.TIMEOUT

            )



            return response.status_code == 200



        except:



            return False

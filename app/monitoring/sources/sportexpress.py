# =====================================================
# FAJ Platform v6.1
# Sport Express Source
# =====================================================

import requests


class SportExpressSource:


    HEADERS = {

        "User-Agent":
        "Mozilla/5.0"

    }



    def get_page(self, url):

        try:

            response = requests.get(

                url,

                headers=self.HEADERS,

                timeout=15

            )


            response.raise_for_status()


            return response.text



        except Exception as e:


            print(
                "SportExpress error:",
                e
            )


            return None

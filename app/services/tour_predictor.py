# =====================================================
# FAJ Platform v6.3.4
# app/services/tour_predictor.py
#
# FAJ Tour Predictor
#
# Создание прогнозов всего тура
# =====================================================


import logging


from app.database import get_connection

from app.core.faj_core import FAJCore

from app.journal import Journal


logger = logging.getLogger(__name__)



# =====================================================
# TOUR PREDICTOR
# =====================================================


class TourPredictor:



    def __init__(

        self,

        core: FAJCore

    ):


        self.core = core

        self.journal = Journal()



    # =================================================
    # GET FIXTURES
    # =================================================


    def get_tour_fixtures(

        self,

        league="RPL",

        season="2026/27"

    ):


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """

            SELECT *

            FROM fixtures

            WHERE league=%s

            AND season=%s

            AND status != 'finished'

            ORDER BY date

            """,

            (

                league,

                season

            )

        )


        rows = cur.fetchall()



        cur.close()

        conn.close()



        return rows



    # =================================================
    # CREATE ONE PREDICTION
    # =================================================


    def predict_fixture(

        self,

        fixture

    ):


        try:


            home = fixture["home_team"]

            away = fixture["away_team"]



            prediction = self.core.predict(

                home,

                away,

                fixture.get(

                    "league",

                    "RPL"

                )

            )



            return prediction



        except Exception as e:


            logger.error(

                f"Prediction error {fixture}: {e}",

                exc_info=True

            )


            return None



    # =================================================
    # GENERATE TOUR
    # =================================================


    def generate_tour_predictions(

        self,

        league="RPL",

        season="2026/27"

    ):


        fixtures = self.get_tour_fixtures(

            league,

            season

        )



        results = []



        for fixture in fixtures:



            prediction = self.predict_fixture(

                fixture

            )



            if not prediction:

                continue



            fixture_id = fixture.get(

                "id"

            )



            # сохраняем в журнал

            self.journal.save(

                fixture,

                prediction,

                fixture_id

            )



            results.append(

                {

                    "fixture": fixture,

                    "prediction": prediction

                }

            )



        logger.info(

            f"Tour predictions generated: {len(results)}"

        )



        return results



# =====================================================
# SERVICE FUNCTION
# =====================================================


def create_tour_predictions(

    core,

    league="RPL",

    season="2026/27"

):


    predictor = TourPredictor(

        core

    )


    return predictor.generate_tour_predictions(

        league,

        season

    )

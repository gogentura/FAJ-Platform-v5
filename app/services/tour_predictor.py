# =====================================================
# FAJ Platform v6.3.4
# app/services/tour_predictor.py
#
# Generate predictions for whole RPL tour
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



    def __init__(self, core=None):

        self.core = core or FAJCore()

        self.journal = Journal()



    # =================================================
    # GET UPCOMING FIXTURES
    # =================================================


    def get_fixtures(

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
    # GENERATE ONE PREDICTION
    # =================================================


    def predict_fixture(

        self,

        fixture

    ):


        try:


            home = fixture["home_team"]

            away = fixture["away_team"]



            result = self.core.predict(

                home,

                away,

                fixture.get(
                    "league",
                    "RPL"
                )

            )



            return result



        except Exception as e:


            logger.error(

                f"Prediction error {fixture}: {e}",

                exc_info=True

            )


            return None



    # =================================================
    # GENERATE TOUR
    # =================================================


    def generate_tour(

        self,

        league="RPL",

        season="2026/27"

    ):


        fixtures = self.get_fixtures(

            league,

            season

        )


        generated = 0

        errors = []



        for fixture in fixtures:


            try:


                prediction = self.predict_fixture(

                    fixture

                )


                if not prediction:

                    continue



                fixture_id = fixture["id"]



                prediction["home_team"] = fixture["home_team"]

                prediction["away_team"] = fixture["away_team"]

                prediction["league"] = league



                # сохраняем в журнал

                self.journal.save(

                    fixture,

                    prediction,

                    fixture_id

                )



                generated += 1



            except Exception as e:


                errors.append(

                    str(e)

                )



        return {


            "generated": generated,


            "errors": errors

        }



# =====================================================
# SERVICE FUNCTION
# =====================================================


def generate_tour_predictions(

    league="RPL",

    season="2026/27",

    core=None

):


    predictor = TourPredictor(

        core

    )


    return predictor.generate_tour(

        league,

        season

    )

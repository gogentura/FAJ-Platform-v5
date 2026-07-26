# =====================================================
# FAJ Platform v6.7
# app/services/prediction_pipeline.py
#
# Prediction Pipeline
# Bridge between Tour Predictor and FAJ Core
# =====================================================


import logging


from app.core.faj_core import FAJCore


logger = logging.getLogger(__name__)





# =====================================================
# PIPELINE CLASS
# =====================================================


class PredictionPipeline:


    VERSION = "6.7"



    def __init__(self):

        self.core = FAJCore()

        logger.info(
            "FAJ Prediction Pipeline %s initialized",
            self.VERSION
        )





    # =================================================
    # PREDICT MATCH
    # =================================================


    def predict_match(

        self,

        home_team,

        away_team,

        league="RPL",

        season="2026/27"

    ):


        try:


            logger.info(

                "Pipeline prediction: %s - %s",

                home_team,

                away_team

            )



            result = self.core.predict_match(

                home_team,

                away_team,

                league

            )



            if not result:


                logger.warning(

                    "Empty Core result: %s - %s",

                    home_team,

                    away_team

                )


                return None




            # добавляем служебные данные

            result["pipeline_version"] = self.VERSION

            result["season"] = season



            return result




        except Exception as e:


            logger.error(

                "Pipeline prediction error %s - %s: %s",

                home_team,

                away_team,

                e,

                exc_info=True

            )


            raise







    # =================================================
    # BATCH PREDICTION
    # =================================================


    def predict_fixtures(

        self,

        fixtures

    ):


        results = []



        for fixture in fixtures:


            try:


                prediction = self.predict_match(

                    fixture.get(
                        "home_team"
                    ),

                    fixture.get(
                        "away_team"
                    ),

                    fixture.get(
                        "league",
                        "RPL"
                    ),

                    fixture.get(
                        "season",
                        "2026/27"
                    )

                )



                if prediction:


                    prediction["fixture_id"] = fixture.get(
                        "id"
                    )


                    results.append(
                        prediction
                    )



            except Exception as e:


                logger.error(

                    "Fixture prediction failed: %s",

                    fixture,

                    exc_info=True

                )



        return results







    # =================================================
    # INFO
    # =================================================


    def info(self):


        return {


            "pipeline":

            "FAJ Prediction Pipeline",


            "version":

            self.VERSION,


            "core":

            self.core.info()

        }







# =====================================================
# SINGLETON INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()

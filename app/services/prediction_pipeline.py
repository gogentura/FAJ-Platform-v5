# =====================================================
# FAJ Platform v6.7
# app/services/prediction_pipeline.py
#
# Prediction Pipeline Layer
# Bridge:
# Handler -> Pipeline -> FAJCore
# =====================================================


import logging


from app.core.faj_core import FAJCore


logger = logging.getLogger(__name__)




# =====================================================
# GLOBAL CORE
# =====================================================


_core = None




def get_core():

    global _core


    if _core is None:

        _core = FAJCore()


    return _core






# =====================================================
# MAIN PIPELINE CLASS
# =====================================================


class PredictionPipeline:


    def __init__(self):

        self.core = get_core()



    # -------------------------------------------------
    # SINGLE MATCH
    # -------------------------------------------------

    def predict_match(

        self,

        home_team,

        away_team,

        league="RPL",

        season="2026/27"

    ):


        try:


            result = self.core.predict_match(

                home_team,

                away_team,

                league

            )



            if not result:

                logger.warning(

                    "Empty FAJ Core result %s-%s",

                    home_team,

                    away_team

                )



                return None



            # добавляем метаданные

            result["season"] = season



            return result



        except Exception as e:


            logger.error(

                "Pipeline prediction error %s-%s: %s",

                home_team,

                away_team,

                e,

                exc_info=True

            )


            return None







# =====================================================
# GLOBAL PIPELINE INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()







# =====================================================
# COMPATIBILITY FUNCTION
#
# ВАЖНО:
# Этот импорт нужен старым handler/debug файлам
# =====================================================


def predict_match_pipeline(

    home_team,

    away_team,

    league="RPL",

    season="2026/27"

):


    return prediction_pipeline.predict_match(

        home_team,

        away_team,

        league,

        season

    )







# =====================================================
# SHORT API
# =====================================================


def predict_match(

    home_team,

    away_team,

    league="RPL",

    season="2026/27"

):


    return predict_match_pipeline(

        home_team,

        away_team,

        league,

        season

    )

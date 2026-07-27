# =====================================================
# FAJ Platform v6.9.3
# app/core/confidence_engine.py
#
# FAJ Confidence Calibration Engine
#
# Calculates final prediction confidence
#
# Input:
#   xG
#   FAJ Rating
#   Data Quality
#   Season Phase
#
# Output:
#   confidence %
#   risk
#   category
# =====================================================


import logging


logger = logging.getLogger(__name__)





# =====================================================
# SAFE FLOAT
# =====================================================


def safe_float(

    value,

    default=0.0

):

    try:

        if value is None:

            return default


        return float(value)


    except Exception:

        return default







# =====================================================
# CONFIDENCE ENGINE
# =====================================================


class ConfidenceEngine:


    VERSION = "6.9.3"




    # =============================================
    # MAIN CALCULATION
    # =============================================


    def calculate(

        self,

        xg_home=0,

        xg_away=0,

        rating_home=0,

        rating_away=0,

        quality_home=1,

        quality_away=1,

        season_phase="start",

        home_advantage=True

    ):


        try:



            xg_home = safe_float(
                xg_home
            )


            xg_away = safe_float(
                xg_away
            )


            rating_home = safe_float(
                rating_home
            )


            rating_away = safe_float(
                rating_away
            )



            quality_home = safe_float(
                quality_home,
                1
            )


            quality_away = safe_float(
                quality_away,
                1
            )



            # =====================================
            # BASE
            # =====================================


            base = 35.0



            # =====================================
            # xG DIFFERENCE
            # =====================================


            xg_diff = abs(

                xg_home - xg_away

            )



            xg_bonus = min(

                xg_diff * 18,

                15

            )



            # =====================================
            # RATING DIFFERENCE
            # =====================================


            rating_diff = abs(

                rating_home - rating_away

            )



            rating_bonus = min(

                rating_diff * 0.7,

                12

            )




            # =====================================
            # DATA QUALITY
            # =====================================


            quality = (

                quality_home +

                quality_away

            ) / 2



            quality_bonus = (

                quality * 10

            )



            if quality > 1:

                quality_bonus = (

                    quality / 100

                ) * 10





            # =====================================
            # HOME ADVANTAGE
            # =====================================


            home_bonus = 3 if home_advantage else 0





            # =====================================
            # SEASON PHASE
            # =====================================


            phase_penalty = 0



            if season_phase == "start":

                phase_penalty = -5



            elif season_phase == "mid":

                phase_penalty = 0



            elif season_phase == "end":

                phase_penalty = 2





            # =====================================
            # FINAL
            # =====================================


            confidence = (

                base

                +

                xg_bonus

                +

                rating_bonus

                +

                quality_bonus

                +

                home_bonus

                +

                phase_penalty

            )



            # limits


            confidence = max(

                20,

                min(

                    confidence,

                    90

                )

            )



            risk = self.risk(

                confidence

            )


            category = self.category(

                confidence

            )



            return {


                "confidence":
                    round(
                        confidence,
                        1
                    ),


                "risk":
                    risk,


                "category":
                    category,


                "engine_version":
                    self.VERSION


            }



        except Exception as e:


            logger.error(

                "Confidence Engine error: %s",

                e,

                exc_info=True

            )


            return {


                "confidence":0,

                "risk":"Высокий",

                "category":"D",

                "engine_version":
                    self.VERSION

            }







# =====================================================
# RISK
# =====================================================


    def risk(

        self,

        confidence

    ):


        if confidence >= 70:

            return "Низкий"



        elif confidence >= 50:

            return "Средний"



        elif confidence >= 35:

            return "Высокий"



        else:

            return "Очень высокий"







# =====================================================
# CATEGORY
# =====================================================


    def category(

        self,

        confidence

    ):


        if confidence >= 70:

            return "A"



        elif confidence >= 55:

            return "B"



        elif confidence >= 40:

            return "C"



        else:

            return "D"







# =====================================================
# PUBLIC API
# =====================================================


def calculate_confidence(

    **kwargs

):


    engine = ConfidenceEngine()


    return engine.calculate(

        **kwargs

    )

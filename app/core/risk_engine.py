# =====================================================
# FAJ Platform v6.9.6
# app/core/risk_engine.py
#
# FAJ Risk & Confidence Engine
#
# Confidence
# Risk
# Category
# =====================================================


class RiskEngine:


    VERSION = "6.9.6"



    # =================================================
    # CONFIDENCE CATEGORY
    # =================================================

    def get_grade(
        self,
        confidence
    ):


        confidence = float(
            confidence
        )



        if confidence >= 75:


            return {

                "code": "AAA",

                "name":
                    "Очень сильный прогноз"

            }



        elif confidence >= 65:


            return {

                "code": "AA",

                "name":
                    "Высокая уверенность"

            }



        elif confidence >= 55:


            return {

                "code": "A",

                "name":
                    "Хороший прогноз"

            }



        elif confidence >= 45:


            return {

                "code": "B",

                "name":
                    "Рабочий прогноз"

            }



        elif confidence >= 35:


            return {

                "code": "C",

                "name":
                    "Осторожный прогноз"

            }



        else:


            return {

                "code": "D",

                "name":
                    "Высокий риск"

            }




    # =================================================
    # MATCH RISK
    # =================================================

    def calculate_risk(

        self,

        winner_probability,

        rating_difference,

        xg_difference

    ):


        winner_probability = float(
            winner_probability
        )


        rating_difference = abs(
            float(
                rating_difference
            )
        )


        xg_difference = abs(
            float(
                xg_difference
            )
        )



        # =============================================
        # LOW RISK
        # =============================================

        if (

            winner_probability >= 65

            and

            rating_difference >= 10

            and

            xg_difference >= 0.5

        ):


            return "Низкий"



        # =============================================
        # HIGH RISK
        # =============================================

        if (

            winner_probability < 45

            or

            rating_difference < 4

            or

            xg_difference < 0.25

        ):


            return "Высокий"



        # =============================================
        # MEDIUM
        # =============================================

        return "Средний"





    # =================================================
    # RISK ICON
    # =================================================

    def risk_badge(
        self,
        risk
    ):


        if risk == "Низкий":

            return "🟢 Низкий"



        if risk == "Средний":

            return "🟡 Средний"



        return "🔴 Высокий"





    # =================================================
    # FULL ANALYSIS
    # =================================================

    def analyze(

        self,

        confidence,

        home_rating,

        away_rating,

        winner_probability,

        xg_home,

        xg_away

    ):


        home_rating = float(
            home_rating
        )


        away_rating = float(
            away_rating
        )


        xg_home = float(
            xg_home
        )


        xg_away = float(
            xg_away
        )



        rating_difference = (

            home_rating

            -

            away_rating

        )



        xg_difference = (

            xg_home

            -

            xg_away

        )



        grade = self.get_grade(
            confidence
        )



        risk = self.calculate_risk(

            winner_probability,

            rating_difference,

            xg_difference

        )



        return {


            "confidence":

                round(
                    float(confidence),
                    1
                ),



            "grade":

                grade["code"],



            "grade_name":

                grade["name"],



            "risk":

                risk,



            "risk_badge":

                self.risk_badge(
                    risk
                ),



            "rating_difference":

                round(
                    rating_difference,
                    1
                ),



            "xg_difference":

                round(
                    xg_difference,
                    2
                )

        }





# =====================================================
# GLOBAL INSTANCE
# =====================================================

risk_engine = RiskEngine()

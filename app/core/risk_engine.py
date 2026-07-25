# =====================================================
# FAJ Platform v6.3
# app/core/risk_engine.py
#
# FAJ Risk & Confidence Engine
# =====================================================


class RiskEngine:


    VERSION = "6.3"


    # =================================================
    # CONFIDENCE GRADE
    # =================================================

    def get_grade(
        self,
        confidence
    ):

        confidence = float(confidence)


        if confidence >= 90:

            return {
                "code": "AAA",
                "name": "Очень сильный прогноз"
            }


        elif confidence >= 80:

            return {
                "code": "AA",
                "name": "Высокая уверенность"
            }


        elif confidence >= 70:

            return {
                "code": "A",
                "name": "Хороший прогноз"
            }


        elif confidence >= 60:

            return {
                "code": "B",
                "name": "Рабочий прогноз"
            }


        else:

            return {
                "code": "C",
                "name": "Высокий риск"
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
            float(rating_difference)
        )


        xg_difference = abs(
            float(xg_difference)
        )



        # ===============================
        # LOW RISK
        # ===============================

        if (

            winner_probability >= 65

            and

            rating_difference >= 12

            and

            xg_difference >= 0.6

        ):

            return "Низкий"



        # ===============================
        # HIGH RISK
        # ===============================

        if (

            winner_probability < 55

            or

            rating_difference < 5

        ):

            return "Высокий"



        # ===============================
        # MEDIUM
        # ===============================

        return "Средний"



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


        rating_difference = (

            float(home_rating)

            -

            float(away_rating)

        )


        xg_difference = (

            float(xg_home)

            -

            float(xg_away)

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

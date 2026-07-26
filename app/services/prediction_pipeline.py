# =====================================================
# FAJ Platform v6.8
# app/services/prediction_pipeline.py
#
# Main Prediction Pipeline
# =====================================================


import logging


from app.core.faj_core import FAJCore


from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


logger = logging.getLogger(__name__)





# =====================================================
# PIPELINE
# =====================================================


class PredictionPipeline:



    VERSION = "6.8"



    def __init__(self):


        self.core = FAJCore()



    # =================================================
    # MAIN API
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

                "FAJ Pipeline start %s - %s",

                home_team,

                away_team

            )



            # ---------------------------------
            # PASSPORT CHECK
            # ---------------------------------


            home_passport = self.get_passport(

                home_team

            )


            away_passport = self.get_passport(

                away_team

            )



            if not home_passport:


                raise Exception(

                    f"Нет паспорта хозяев: {home_team}"

                )



            if not away_passport:


                raise Exception(

                    f"Нет паспорта гостей: {away_team}"

                )





            # ---------------------------------
            # CORE
            # ---------------------------------


            result = self.core.predict_match(

                home_team,

                away_team,

                league

            )





            # ---------------------------------
            # EXTRA LAYERS
            # ---------------------------------


            decision = result.get(

                "decision",

                {}

            )



            confidence = decision.get(

                "confidence",

                0

            )



            risk = self.calculate_risk(

                confidence

            )



            grade = self.calculate_grade(

                confidence

            )





            factors = self.generate_factors(

                result,

                home_passport,

                away_passport

            )





            # ---------------------------------
            # FINAL
            # ---------------------------------


            decision.update(


                {

                "risk": risk,


                "grade": grade,


                "factors": factors,


                }

            )



            result["decision"] = decision



            result["season"] = season



            result["pipeline_version"] = self.VERSION



            result["passport_quality"] = {


                "home":

                self.passport_quality(

                    home_passport

                ),


                "away":

                self.passport_quality(

                    away_passport

                )


            }



            result["season_phase"] = self.get_phase()



            logger.info(

                "FAJ Pipeline finished %s - %s",

                home_team,

                away_team

            )



            return result




        except Exception as e:



            logger.error(

                "Pipeline error %s",

                e,

                exc_info=True

            )


            raise





    # =================================================
    # PASSPORT
    # =================================================


    def get_passport(

        self,

        team

    ):


        real_team = get_team_by_alias(

            team

        )


        if real_team:

            team = real_team



        return load_passport(

            team

        )





    # =================================================
    # RISK ENGINE
    # =================================================


    def calculate_risk(

        self,

        confidence

    ):


        try:


            confidence=float(

                confidence

            )



        except:


            return "Высокий"




        if confidence >= 70:

            return "Низкий"



        if confidence >= 45:

            return "Средний"



        return "Высокий"





    # =================================================
    # GRADE ENGINE
    # =================================================


    def calculate_grade(

        self,

        confidence

    ):


        try:

            confidence=float(

                confidence

            )


        except:


            return "C"



        if confidence >= 80:

            return "A"



        if confidence >= 60:

            return "B"



        if confidence >= 40:

            return "C"



        return "D"







    # =================================================
    # FACTOR ENGINE
    # =================================================


    def generate_factors(

        self,

        result,

        home,

        away

    ):


        factors=[]



        decision=result.get(

            "decision",

            {}

        )



        winner=decision.get(

            "winner"

        )




        if winner=="home":


            factors.append(

                "🏹 Преимущество хозяев"

            )



        elif winner=="away":


            factors.append(

                "🏹 Преимущество гостей"

            )



        else:


            factors.append(

                "⚖️ Равная сила команд"

            )




        xg=result.get(

            "xg",

            {}

        ).get(

            "predicted",

            {}

        )



        if xg:



            if xg.get("home",0) > xg.get("away",0):

                factors.append(

                    f"📈 xG преимущество хозяев ({xg.get('home')})"

                )


            elif xg.get("away",0) > xg.get("home",0):

                factors.append(

                    f"📈 xG преимущество гостей ({xg.get('away')})"

                )





        factors.append(

            f"🏆 Турнир: {result.get('league','RPL')}"

        )



        return factors







    # =================================================
    # PASSPORT QUALITY
    # =================================================


    def passport_quality(

        self,

        passport

    ):


        fields=[

            "attack",

            "defense",

            "control",

            "form",

            "fitness"

        ]



        score=0



        count=0



        for field in fields:


            if passport.get(field) is not None:


                score += float(

                    passport.get(field)

                )


                count+=1




        if count==0:

            return 0



        return round(

            score/count,

            1

        )







    # =================================================
    # SEASON PHASE
    # =================================================


    def get_phase(self):


        return "START"







# =====================================================
# GLOBAL INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v9.3.1

FAJ Core Compatibility Fix

Главный управляющий модуль.

Совместимость:

Streamlit 9.7
Passport Updater 9.2
Memory Engine 9.2


"""



from datetime import datetime


from app.passport_updater import PassportUpdater
from app.memory_engine import MemoryEngine




class FAJCore:



    def __init__(self):


        self.version = "9.3.1"


        self.passport = PassportUpdater()


        self.memory = MemoryEngine()



        self.LEAGUE_XG = 1.35


        self.HOME_ADVANTAGE = 1.12





    # ==================================================
    # STATUS
    # ==================================================


    def status(self):


        """
        Формат для Streamlit

        Возвращает только dict

        """



        teams = 0


        if hasattr(

            self.passport,

            "passports"

        ):


            teams = len(

                self.passport.passports

            )



        memory_count = 0



        if hasattr(

            self.memory,

            "memory"

        ):


            memory_count = len(

                self.memory.memory

            )



        return {


            "version":

            self.version,



            "teams":

            teams,



            "memory":

            memory_count,



            "date":

            datetime.now().strftime(

                "%Y-%m-%d"

            )


        }





    # ==================================================
    # TEAM
    # ==================================================


    def get_team(

        self,

        name

    ):


        return self.passport.find_team(

            name

        )





    # ==================================================
    # BASIC PREDICTOR
    # ==================================================


    def predict_match(

        self,

        home,

        away

    ):



        home_team = self.get_team(

            home

        )


        away_team = self.get_team(

            away

        )



        if not home_team or not away_team:


            return {


                "status":

                "ERROR",


                "message":

                "Команда не найдена"


            }





        xg_home, xg_away = self.calculate_xg(

            home_team,

            away_team

        )



        probability = self.calculate_probability(

            xg_home,

            xg_away

        )



        return {



            "status":

            "READY",



            "match":

            f"{home} - {away}",



            "xG":

            {


                "home":

                xg_home,


                "away":

                xg_away


            },



            "probability":

            probability,



            "score":

            self.calculate_score(

                xg_home,

                xg_away

            )



        }





    # ==================================================
    # xG
    # ==================================================


    def calculate_xg(

        self,

        home,

        away

    ):



        attack_home = self.num(

            home.get(

                "attack"

            )

        )


        attack_away = self.num(

            away.get(

                "attack"

            )

        )



        defense_home = self.num(

            home.get(

                "defense"

            )

        )


        defense_away = self.num(

            away.get(

                "defense"

            )

        )



        form_home = self.num(

            home.get(

                "form"

            )

        )


        form_away = self.num(

            away.get(

                "form"

            )

        )





        xg_home = (

            self.LEAGUE_XG

            *

            (1 + (attack_home-75)/200)

            *

            (1 - (defense_away-75)/250)

            *

            (1 + (form_home-75)/300)

            *

            self.HOME_ADVANTAGE

        )





        xg_away = (

            self.LEAGUE_XG

            *

            (1 + (attack_away-75)/200)

            *

            (1 - (defense_home-75)/250)

            *

            (1 + (form_away-75)/300)

        )





        return (

            round(

                self.limit_xg(xg_home),

                2

            ),


            round(

                self.limit_xg(xg_away),

                2

            )

        )







    # ==================================================
    # PROBABILITY
    # ==================================================


    def calculate_probability(

        self,

        home_xg,

        away_xg

    ):



        total = home_xg + away_xg



        if total == 0:


            return {


                "P1":33.3,

                "X":33.3,

                "P2":33.3


            }



        p1 = round(

            home_xg / total * 100,

            1

        )


        p2 = round(

            away_xg / total * 100,

            1

        )


        draw = round(

            100-p1-p2,

            1

        )



        return {


            "P1":

            p1,


            "X":

            draw,


            "P2":

            p2


        }





    # ==================================================
    # SCORE PLACEHOLDER
    # ==================================================


    def calculate_score(

        self,

        home,

        away

    ):



        return {


            "main":

            f"{round(home)}:{round(away)}",



            "alternatives":

            [

                "1:1",

                "1:0",

                "2:1"

            ]


        }





    # ==================================================
    # UTILS
    # ==================================================


    def num(

        self,

        value

    ):


        try:

            return float(value)


        except:

            return 70





    def limit_xg(

        self,

        value

    ):


        return max(

            0.1,

            min(

                value,

                4.0

            )

        )





if __name__ == "__main__":


    faj = FAJCore()


    print(

        faj.status()

    )


    print(

        faj.predict_match(

            "Динамо М",

            "Крылья Советов"

        )

    )

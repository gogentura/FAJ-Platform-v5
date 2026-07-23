import time
import numpy as np
from math import exp, factorial

from app.database import get_db
from app.passport_manager import get_team_by_alias


class FAJCore:

    VERSION = "5.2"


    def __init__(self):
        self.version = self.VERSION



    # ==========================================
    # ОСНОВНОЙ ПРОГНОЗ
    # ==========================================

    def predict_match(
        self,
        home_team,
        away_team,
        league="RPL"
    ):

        start = time.time()


        home_pass = self.load_team(home_team)
        away_pass = self.load_team(away_team)



        if not home_pass or not away_pass:

            return {
                "error":
                f"Паспорт не найден: {home_team} или {away_team}"
            }



        home_xg = self.calculate_xg(
            home_pass,
            away_pass,
            True
        )


        away_xg = self.calculate_xg(
            away_pass,
            home_pass,
            False
        )


        home_xg = max(
            0.1,
            min(4.0, home_xg)
        )

        away_xg = max(
            0.1,
            min(4.0, away_xg)
        )



        simulation = self.simulate(
            home_xg,
            away_xg
        )


        decision = self.make_decision(
            simulation,
            home_xg,
            away_xg
        )


        return {

            "home_team": home_team,
            "away_team": away_team,

            "league": league,


            "xg": {

                "predicted": {

                    "home": round(home_xg,2),
                    "away": round(away_xg,2)

                },

                "historical": {

                    "home":
                    home_pass.get(
                        "historical_xg_value"
                    ),

                    "away":
                    away_pass.get(
                        "historical_xg_value"
                    )

                }

            },


            "simulation": simulation,


            "decision": decision,


            "btts":
            self.btts_probability(
                home_xg,
                away_xg
            ),


            "over25":
            self.over25_probability(
                home_xg,
                away_xg
            ),


            "top_scores":
            simulation["top_scores"],


            "processing_time":
            round(
                time.time()-start,
                3
            ),


            "version":
            self.version
        }




    # ==========================================
    # ЗАГРУЗКА ПАСПОРТА
    # ==========================================

    def load_team(self, team):

        real_team = get_team_by_alias(team)


        if not real_team:
            real_team = team



        conn = get_db()


        row = conn.execute(
            """
            SELECT *
            FROM passports
            WHERE team = ?
            """,
            (real_team,)
        ).fetchone()


        conn.close()


        if row:
            return dict(row)


        return None




    # ==========================================
    # РАСЧЁТ xG
    # ==========================================

    def calculate_xg(
        self,
        team,
        opponent,
        home=True
    ):


        base_xg = (
            team.get(
                "historical_xg_value"
            )
            or 1.3
        )


        attack = (
            team.get(
                "attack"
            )
            or 70
        )


        opponent_defense = (
            opponent.get(
                "defense"
            )
            or 70
        )


        form = (
            team.get(
                "form_index"
            )
            or 70
        )


        control = (
            team.get(
                "control"
            )
            or 70
        )



        factor = 1.0



        # атака

        factor *= (
            1 +
            (attack-70)/200
        )



        # защита соперника

        factor *= (
            1 +
            (70-opponent_defense)/250
        )



        # форма

        factor *= (
            1 +
            (form-70)/300
        )



        # контроль

        factor *= (
            1 +
            (control-70)/500
        )



        # домашний / выездной фактор

        if home:

            home_rating = (
                team.get(
                    "home_rating"
                )
                or 70
            )


            factor *= (
                1 +
                (home_rating-70)/300
            )


        else:

            away_rating = (
                team.get(
                    "away_rating"
                )
                or 70
            )


            factor *= (
                1 +
                (away_rating-70)/300
            )



        # тренер

        coach = (
            team.get(
                "coach_factor"
            )
            or 70
        )


        factor *= (
            1+
            (coach-70)/500
        )



        # травмы и усталость

        injury = (
            team.get(
                "injury_index"
            )
            or 0
        )


        fatigue = (
            team.get(
                "fatigue_index"
            )
            or 0
        )


        factor *= (
            1 -
            (injury+fatigue)/500
        )



        return base_xg * factor

    # ==========================================
    # MONTE CARLO SIMULATION
    # ==========================================

    def simulate(
        self,
        home_xg,
        away_xg,
        n=10000
    ):

        np.random.seed(42)


        home_goals = np.random.poisson(
            home_xg,
            n
        )

        away_goals = np.random.poisson(
            away_xg,
            n
        )


        home_win = np.sum(
            home_goals > away_goals
        )

        draw = np.sum(
            home_goals == away_goals
        )

        away_win = np.sum(
            home_goals < away_goals
        )



        scores = {}


        for h, a in zip(
            home_goals,
            away_goals
        ):

            key = (
                int(h),
                int(a)
            )

            scores[key] = (
                scores.get(key,0)+1
            )



        top_scores = sorted(
            scores.items(),
            key=lambda x:x[1],
            reverse=True
        )[:5]



        formatted_scores = []


        for score,count in top_scores:

            formatted_scores.append(
                (
                    f"{score[0]}-{score[1]}",
                    round(
                        count/n,
                        3
                    )
                )
            )



        return {

            "home_win_prob":
            round(
                home_win/n,
                3
            ),


            "draw_prob":
            round(
                draw/n,
                3
            ),


            "away_win_prob":
            round(
                away_win/n,
                3
            ),


            "top_scores":
            formatted_scores
        }





    # ==========================================
    # ОБЕ ЗАБЬЮТ
    # ==========================================

    def btts_probability(
        self,
        home_xg,
        away_xg
    ):

        p_home_zero = exp(
            -home_xg
        )

        p_away_zero = exp(
            -away_xg
        )


        probability = (
            1
            -
            p_home_zero
            -
            p_away_zero
            +
            p_home_zero*p_away_zero
        )


        return round(
            probability,
            3
        )





    # ==========================================
    # ТОТАЛ 2.5
    # ==========================================

    def over25_probability(
        self,
        home_xg,
        away_xg
    ):


        probability = 0


        for h in range(0,8):

            for a in range(0,8):

                if h+a > 2:


                    probability += (

                        (
                            exp(-home_xg)
                            *
                            home_xg**h
                            /
                            factorial(h)
                        )

                        *

                        (
                            exp(-away_xg)
                            *
                            away_xg**a
                            /
                            factorial(a)
                        )

                    )



        return round(
            probability,
            3
        )





    # ==========================================
    # ИТОГОВОЕ РЕШЕНИЕ
    # ==========================================

    def make_decision(
        self,
        simulation,
        home_xg,
        away_xg
    ):


        home = simulation[
            "home_win_prob"
        ]

        draw = simulation[
            "draw_prob"
        ]

        away = simulation[
            "away_win_prob"
        ]



        if home >= away and home >= draw:

            winner = "home"

            winner_name = "Хозяева"



        elif away >= home and away >= draw:

            winner = "away"

            winner_name = "Гости"



        else:

            winner = "draw"

            winner_name = "Ничья"




        probability = max(
            home,
            draw,
            away
        )



        # самый вероятный счёт

        if simulation["top_scores"]:

            expected_score = (
                simulation["top_scores"][0][0]
            )

        else:

            expected_score = (
                f"{round(home_xg)}-{round(away_xg)}"
            )




        confidence = int(
            50 +
            probability*40
        )



        return {


            "winner":

            winner,


            "winner_name":

            winner_name,


            "winner_probability":

            round(
                probability*100,
                1
            ),



            "home_prob":

            round(
                home*100,
                1
            ),



            "draw_prob":

            round(
                draw*100,
                1
            ),



            "away_prob":

            round(
                away*100,
                1
            ),



            "expected_score":

            expected_score,



            "confidence":

            confidence

        }

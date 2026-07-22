import time
import math
import numpy as np

from app.passport_manager import load_passport


class FAJCore:
    """
    FAJ Engine v5.1 Core

    Основной модуль:
    - загрузка паспортов команд
    - расчёт xG
    - симуляция счёта
    - вероятности исходов
    - BTTS
    - Total 2.5
    """

    def __init__(self):
        self.version = "5.1 Stable"


    def predict_match(self, home_team, away_team, league="RPL"):

        start = time.time()

        home_pass = load_passport(home_team)
        away_pass = load_passport(away_team)


        if not home_pass or not away_pass:
            return {
                "error": "Паспорт не найден. Обновите: /update_team"
            }


        hist_xg_home = home_pass.get(
            "historical_xg_value",
            home_pass.get("xg", 1.35)
        )

        hist_xg_away = away_pass.get(
            "historical_xg_value",
            away_pass.get("xg", 1.35)
        )


        home_attack = home_pass.get("attack", 70)
        home_defense = home_pass.get("defense", 70)
        home_form = home_pass.get("form_index", 70)


        away_attack = away_pass.get("attack", 70)
        away_defense = away_pass.get("defense", 70)
        away_form = away_pass.get("form_index", 70)



        home_xg = (
            hist_xg_home *
            (1 + (home_attack - 70) / 200) *
            (1 + (home_form - 70) / 300)
        )


        away_xg = (
            hist_xg_away *
            (1 + (away_attack - 70) / 200) *
            (1 + (away_form - 70) / 300)
        )


        home_adv = 1.12 if league == "RPL" else 1.10


        home_xg *= home_adv
        away_xg /= home_adv


        home_xg = round(
            max(0.2, min(4.0, home_xg)),
            2
        )

        away_xg = round(
            max(0.2, min(4.0, away_xg)),
            2
        )


        simulation = self._simulate(
            home_xg,
            away_xg
        )


        result = {

            "home_team": home_team,
            "away_team": away_team,

            "league": league,

            "xg": {

                "home": home_xg,
                "away": away_xg

            },


            "simulation": simulation,

            "btts": self._btts_prob(
                home_xg,
                away_xg
            ),


            "over25": self._over25_prob(
                home_xg,
                away_xg
            ),


            "decision": self._decide(
                simulation,
                home_xg,
                away_xg
            ),


            "processing_time":
                round(
                    time.time() - start,
                    3
                ),


            "version":
                self.version

        }


        return result



    def _simulate(self, home_xg, away_xg):

        scores = []


        for _ in range(5000):

            home_goals = np.random.poisson(
                home_xg
            )

            away_goals = np.random.poisson(
                away_xg
            )


            scores.append(
                (
                    home_goals,
                    away_goals
                )
            )


        home_win = sum(
            1 for h,a in scores
            if h > a
        ) / len(scores)


        draw = sum(
            1 for h,a in scores
            if h == a
        ) / len(scores)


        away_win = sum(
            1 for h,a in scores
            if h < a
        ) / len(scores)



        counter = {}

        for score in scores:

            counter[score] = (
                counter.get(score,0)
                +1
            )


        top_scores = sorted(
            counter.items(),
            key=lambda x:x[1],
            reverse=True
        )[:5]


        return {

            "home_win":
                round(home_win,3),

            "draw":
                round(draw,3),

            "away_win":
                round(away_win,3),

            "top_scores":
                [
                    {
                        "score":
                            f"{s[0]}:{s[1]}",

                        "prob":
                            round(
                                p/len(scores),
                                3
                            )
                    }

                    for s,p in top_scores
                ]
        }



    def _btts_prob(self, home_xg, away_xg):

        simulations = 3000

        yes = 0


        for _ in range(simulations):

            h = np.random.poisson(home_xg)
            a = np.random.poisson(away_xg)


            if h > 0 and a > 0:
                yes += 1


        return round(
            yes / simulations,
            3
        )



    def _over25_prob(self, home_xg, away_xg):

        simulations = 3000

        yes = 0


        for _ in range(simulations):

            total = (
                np.random.poisson(home_xg)
                +
                np.random.poisson(away_xg)
            )


            if total >= 3:
                yes += 1


        return round(
            yes / simulations,
            3
        )



    def _decide(
        self,
        simulation,
        home_xg,
        away_xg
    ):

        if simulation["home_win"] > max(
            simulation["draw"],
            simulation["away_win"]
        ):

            outcome = "HOME"


        elif simulation["away_win"] > simulation["home_win"]:

            outcome = "AWAY"


        else:

            outcome = "DRAW"


        return {

            "outcome":
                outcome,

            "confidence":
                round(
                    max(
                        simulation["home_win"],
                        simulation["draw"],
                        simulation["away_win"]
                    ),
                    3
                ),

            "expected_score":
                f"{round(home_xg)}:{round(away_xg)}"

        }

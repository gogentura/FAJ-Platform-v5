# ==============================================
    # FINAL DECISION
    # ==============================================

    def make_decision(

        self,

        simulation,

        home_xg,

        away_xg

    ):

        home = simulation["home_win_prob"]
        draw = simulation["draw_prob"]
        away = simulation["away_win_prob"]

        if home >= draw and home >= away:

            winner = "home"
            winner_name = "Хозяева"

        elif away >= draw and away >= home:

            winner = "away"
            winner_name = "Гости"

        else:

            winner = "draw"
            winner_name = "Ничья"

        confidence = int(
            50 + max(home, draw, away) * 40
        )

        top_score = "1-1"

        if simulation["top_scores"]:

            top_score = simulation["top_scores"][0]["score"]

        return {
            "winner": winner,
            "winner_name": winner_name,
            "winner_probability":
                round(
                    max(home, draw, away) * 100,
                    1
                ),
            "home_probability":
                round(
                    home * 100,
                    1
                ),
            "draw_probability":
                round(
                    draw * 100,
                    1
                ),
            "away_probability":
                round(
                    away * 100,
                    1
                ),
            "home_prob":
                round(
                    home * 100,
                    1
                ),
            "draw_prob":
                round(
                    draw * 100,
                    1
                ),
            "away_prob":
                round(
                    away * 100,
                    1
                ),
            "expected_score":
                top_score,
            "confidence":
                confidence,
            "btts":
                self.btts_probability(
                    home_xg,
                    away_xg
                ),
            "over15":
                self.over15_probability(
                    home_xg,
                    away_xg
                ),
            "over25":
                self.over25_probability(
                    home_xg,
                    away_xg
                ),
            "under25":
                self.under25_probability(
                    home_xg,
                    away_xg
                ),
            "over35":
                self.over35_probability(
                    home_xg,
                    away_xg
                )
        }

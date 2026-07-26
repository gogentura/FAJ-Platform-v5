# =====================================================
# FAJ Platform v6.7
# app/utils/explainer.py
#
# FAJ Prediction Explanation Layer
# =====================================================


import logging


logger = logging.getLogger(__name__)





# =====================================================
# SAFE TEXT
# =====================================================


def safe_text(value):

    if value is None:

        return None


    try:

        text = str(value).strip()


        if not text:

            return None


        return text


    except Exception:

        return None





# =====================================================
# FACTOR BUILDER
# =====================================================


def add_factor(

    factors,

    text

):


    text = safe_text(text)


    if text:

        factors.append(text)





# =====================================================
# MAIN EXPLAINER
# =====================================================


def explain_prediction(

    home_passport,

    away_passport,

    xg_home,

    xg_away,

    league="RPL"

):


    factors = []



    try:


        # ==========================================
        # PASSPORT CHECK
        # ==========================================


        if not home_passport:

            home_passport = {}


        if not away_passport:

            away_passport = {}





        # ==========================================
        # ATTACK
        # ==========================================


        home_attack = home_passport.get(
            "attack"
        )


        away_attack = away_passport.get(
            "attack"
        )



        if home_attack is not None and away_attack is not None:


            if float(home_attack) > float(away_attack):

                add_factor(

                    factors,

                    "🏹 Преимущество хозяев в атаке"

                )


            elif float(home_attack) < float(away_attack):

                add_factor(

                    factors,

                    "🏹 Преимущество гостей в атаке"

                )





        # ==========================================
        # DEFENSE
        # ==========================================


        home_def = home_passport.get(
            "defense"
        )


        away_def = away_passport.get(
            "defense"
        )



        if home_def is not None and away_def is not None:


            if float(home_def) > float(away_def):

                add_factor(

                    factors,

                    "🛡 Более стабильная оборона хозяев"

                )


            elif float(home_def) < float(away_def):

                add_factor(

                    factors,

                    "🛡 Более стабильная оборона гостей"

                )





        # ==========================================
        # FORM
        # ==========================================


        home_form = home_passport.get(
            "form"
        )


        away_form = away_passport.get(
            "form"
        )



        if home_form is not None and away_form is not None:


            if float(home_form) > float(away_form):

                add_factor(

                    factors,

                    "🔥 Хозяева лучше по текущей форме"

                )


            elif float(home_form) < float(away_form):

                add_factor(

                    factors,

                    "🔥 Гости лучше по текущей форме"

                )





        # ==========================================
        # xG
        # ==========================================


        if xg_home > xg_away:


            add_factor(

                factors,

                f"📈 xG преимущество хозяев ({xg_home:.2f})"

            )


        elif xg_home < xg_away:


            add_factor(

                factors,

                f"📈 xG преимущество гостей ({xg_away:.2f})"

            )


        else:


            add_factor(

                factors,

                "📊 xG команд близкие"

            )





        # ==========================================
        # LEAGUE
        # ==========================================


        add_factor(

            factors,

            f"🏆 Турнир: {league}"

        )





    except Exception as e:


        logger.exception(

            f"Explainer error: {e}"

        )





    # ==========================================
    # FALLBACK
    # ==========================================


    if not factors:


        factors = [

            "📊 Недостаточно данных паспорта"

        ]



    return factors

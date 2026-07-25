# =====================================================
# FAJ Platform v6.3
# app/utils/explainer.py
#
# Prediction Explainer Layer
# =====================================================


def safe_number(value):

    try:
        return float(value)

    except Exception:
        return 0.0



def safe_passport(passport):

    if isinstance(passport, dict):
        return passport

    return {}



# =====================================================
# EXPLAIN PREDICTION
# =====================================================


def explain_prediction(

    home_passport,

    away_passport,

    xg_home,

    xg_away,

    league

):


    factors = []


    home_passport = safe_passport(
        home_passport
    )


    away_passport = safe_passport(
        away_passport
    )


    xg_home = safe_number(
        xg_home
    )


    xg_away = safe_number(
        xg_away
    )



    # =============================================
    # ATTACK
    # =============================================

    home_attack = safe_number(
        home_passport.get(
            "attack",
            0
        )
    )


    away_attack = safe_number(
        away_passport.get(
            "attack",
            0
        )
    )


    if home_attack > away_attack:

        factors.append(
            "Преимущество хозяев в атаке"
        )

    elif away_attack > home_attack:

        factors.append(
            "Преимущество гостей в атаке"
        )



    # =============================================
    # DEFENSE
    # =============================================

    home_defense = safe_number(
        home_passport.get(
            "defense",
            0
        )
    )


    away_defense = safe_number(
        away_passport.get(
            "defense",
            0
        )
    )


    if home_defense > away_defense:

        factors.append(
            "Хозяева надёжнее в обороне"
        )

    elif away_defense > home_defense:

        factors.append(
            "Гости сильнее в обороне"
        )



    # =============================================
    # FORM
    # =============================================

    home_form = safe_number(
        home_passport.get(
            "form",
            home_passport.get(
                "form_index",
                0
            )
        )
    )


    away_form = safe_number(
        away_passport.get(
            "form",
            away_passport.get(
                "form_index",
                0
            )
        )
    )


    if home_form > away_form:

        factors.append(
            "Лучшая текущая форма хозяев"
        )

    elif away_form > home_form:

        factors.append(
            "Лучшее текущее состояние гостей"
        )



    # =============================================
    # CONTROL
    # =============================================

    home_control = safe_number(
        home_passport.get(
            "control",
            0
        )
    )


    away_control = safe_number(
        away_passport.get(
            "control",
            0
        )
    )


    if home_control > away_control:

        factors.append(
            "Хозяева лучше контролируют игру"
        )


    elif away_control > home_control:

        factors.append(
            "Гости лучше контролируют игру"
        )



    # =============================================
    # XG DIFFERENCE
    # =============================================

    xg_diff = xg_home - xg_away


    if xg_diff > 0.3:

        factors.append(
            f"Разница xG в пользу хозяев +{xg_diff:.2f}"
        )


    elif xg_diff < -0.3:

        factors.append(
            f"Разница xG в пользу гостей +{abs(xg_diff):.2f}"
        )



    # =============================================
    # HOME FACTOR
    # =============================================

    if league == "RPL":

        factors.append(
            "Фактор домашнего поля"
        )



    # =============================================
    # EMPTY
    # =============================================

    if not factors:

        factors.append(
            "Команды близки по силе"
        )


    return factors

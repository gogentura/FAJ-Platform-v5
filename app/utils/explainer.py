# =====================================================
# FAJ Platform v6.3
# app/utils/explainer.py
#
# Prediction Explanation Layer
# PostgreSQL compatible
# =====================================================


def explain_prediction(
    home_passport,
    away_passport,
    xg_home,
    xg_away,
    league="RPL"
):

    factors = []


    # Если паспорта отсутствуют
    if not home_passport or not away_passport:

        factors.append(
            "Недостаточно данных паспортов"
        )

        return factors



    # ==========================================
    # ATTACK
    # ==========================================

    home_attack = float(
        home_passport.get(
            "attack",
            0
        )
    )

    away_attack = float(
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



    # ==========================================
    # DEFENSE
    # ==========================================

    home_def = float(
        home_passport.get(
            "defense",
            0
        )
    )

    away_def = float(
        away_passport.get(
            "defense",
            0
        )
    )


    if home_def > away_def:

        factors.append(
            "Хозяева сильнее в обороне"
        )

    elif away_def > home_def:

        factors.append(
            "Гости сильнее в обороне"
        )



    # ==========================================
    # FORM
    # ==========================================

    home_form = float(
        home_passport.get(
            "form",
            0
        )
    )

    away_form = float(
        away_passport.get(
            "form",
            0
        )
    )


    if home_form > away_form:

        factors.append(
            "Лучшее текущее состояние хозяев"
        )

    elif away_form > home_form:

        factors.append(
            "Лучшее текущее состояние гостей"
        )



    # ==========================================
    # CONTROL
    # ==========================================

    home_control = float(
        home_passport.get(
            "control",
            0
        )
    )

    away_control = float(
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



    # ==========================================
    # xG DIFFERENCE
    # ==========================================

    diff = xg_home - xg_away


    if diff > 0.30:

        factors.append(
            f"xG преимущество хозяев +{diff:.2f}"
        )


    elif diff < -0.30:

        factors.append(
            f"xG преимущество гостей {diff:.2f}"
        )



    # ==========================================
    # HOME FIELD
    # ==========================================

    if league.upper() == "RPL":

        factors.append(
            "Учтён фактор домашнего поля"
        )



    # ==========================================
    # EMPTY
    # ==========================================

    if not factors:

        factors.append(
            "Команды близки по аналитическим показателям"
        )


    return factors

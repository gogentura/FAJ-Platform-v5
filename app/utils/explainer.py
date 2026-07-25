# =====================================================
# FAJ Platform v6.3
# Prediction Explainer
# =====================================================


def explain_prediction(
    home_passport,
    away_passport,
    xg_home,
    xg_away,
    league
):

    factors = []


    if home_passport and away_passport:


        if (
            home_passport.get("attack",0)
            >
            away_passport.get("attack",0)
        ):

            factors.append(
                "Преимущество хозяев в атаке"
            )

        elif (
            away_passport.get("attack",0)
            >
            home_passport.get("attack",0)
        ):

            factors.append(
                "Преимущество гостей в атаке"
            )


        if (
            home_passport.get("defense",0)
            >
            away_passport.get("defense",0)
        ):

            factors.append(
                "Хозяева надёжнее в обороне"
            )

        elif (
            away_passport.get("defense",0)
            >
            home_passport.get("defense",0)
        ):

            factors.append(
                "Гости сильнее в обороне"
            )


        if (
            home_passport.get("form",0)
            >
            away_passport.get("form",0)
        ):

            factors.append(
                "Лучшая текущая форма хозяев"
            )

        elif (
            away_passport.get("form",0)
            >
            home_passport.get("form",0)
        ):

            factors.append(
                "Лучшее текущее состояние гостей"
            )


        if (
            home_passport.get("control",0)
            >
            away_passport.get("control",0)
        ):

            factors.append(
                "Хозяева лучше контролируют игру"
            )

        elif (
            away_passport.get("control",0)
            >
            home_passport.get("control",0)
        ):

            factors.append(
                "Гости лучше контролируют игру"
            )


    diff = xg_home - xg_away


    if diff > 0.3:

        factors.append(
            f"Разница xG в пользу хозяев +{diff:.2f}"
        )


    elif diff < -0.3:

        factors.append(
            f"Разница xG в пользу гостей +{abs(diff):.2f}"
        )


    if league == "RPL":

        factors.append(
            "Фактор домашнего поля"
        )


    if not factors:

        factors.append(
            "Команды близки по силе"
        )


    return factors

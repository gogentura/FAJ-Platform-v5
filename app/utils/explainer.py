def explain_prediction(home_passport, away_passport, xg_home, xg_away, league):
    factors = []
    if home_passport and away_passport:
        if home_passport.get("attack", 0) > away_passport.get("attack", 0):
            factors.append("Преимущество в атаке")
        if home_passport.get("defense", 0) > away_passport.get("defense", 0):
            factors.append("Надёжнее в защите")
        if home_passport.get("form_index", 0) > away_passport.get("form_index", 0):
            factors.append("Лучшая текущая форма")
        if home_passport.get("control", 0) > away_passport.get("control", 0):
            factors.append("Контроль мяча")
    if xg_home - xg_away > 0.3:
        factors.append(f"Разница xG +{xg_home - xg_away:.2f}")
    if league == "RPL":
        factors.append("Фактор домашнего поля")
    if not factors:
        factors.append("Команды близки по силе")
    return factors

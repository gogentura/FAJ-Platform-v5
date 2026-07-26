# =====================================================
# FAJ Platform v6.7
# app/utils/formatter.py
#
# Prediction Formatter
#
# Safe None Protection
# =====================================================



# =====================================================
# SAFE TEXT
# =====================================================


def safe_text(value, default=""):

    if value is None:

        return default


    try:

        return str(value)

    except Exception:

        return default





# =====================================================
# CONFIDENCE LABEL
# =====================================================


def get_confidence_label(confidence):

    confidence = float(confidence or 0)


    if confidence >= 90:

        return "AAA", "Очень сильный прогноз"


    elif confidence >= 80:

        return "AA", "Высокая уверенность"


    elif confidence >= 70:

        return "A", "Хороший прогноз"


    elif confidence >= 60:

        return "B", "Рабочий прогноз"


    else:

        return "C", "Высокий риск"





# =====================================================
# RISK LABEL
# =====================================================


def get_risk_label(risk):

    if isinstance(risk,str):

        return risk


    risk=float(risk or 0)


    if risk>=70:

        return "Высокий"


    elif risk>=40:

        return "Средний"


    return "Низкий"





# =====================================================
# FORMAT PREDICTION
# =====================================================


def format_prediction(

    home,

    away,

    league,

    xg,

    decision,

    top_scores,

    btts,

    over25,

    factors,

    faj_rating=None,

    risk="Средний",

    confidence=None

):


    lines=[]



    home=safe_text(home,"-")
    away=safe_text(away,"-")


    decision = decision or {}

    xg = xg or {}

    factors = factors or []



    # HEADER


    lines.append(
        f"⚽ *{home} — {away}*"
    )


    lines.append(
        f"🏆 *Лига:* {league}"
    )


    lines.append(
        "──────────────"
    )



    # XG


    lines.append(
        "📊 *xG*"
    )


    lines.append(

        f"FAJ: "
        f"{float(xg.get('home',0)):.2f}"
        f" — "
        f"{float(xg.get('away',0)):.2f}"

    )



    # PROBABILITIES


    lines.append("")

    lines.append(
        "📈 *Вероятности*"
    )


    lines.append(

        f"П1 "
        f"{safe_text(decision.get('home_probability',
        decision.get('home_prob',0)))}%  "

        f"Х "
        f"{safe_text(decision.get('draw_probability',
        decision.get('draw_prob',0)))}%  "

        f"П2 "
        f"{safe_text(decision.get('away_probability',
        decision.get('away_prob',0)))}%"

    )



    lines.append(
        "──────────────"
    )



    # SCORE


    lines.append(
        "🎯 *Наиболее вероятный счёт*"
    )



    if top_scores:


        medals=[
            "1️⃣",
            "2️⃣",
            "3️⃣"
        ]


        for i,score in enumerate(top_scores[:3]):


            if score is None:

                continue



            if isinstance(score,dict):


                value=safe_text(
                    score.get("score")
                )


                probability=float(
                    score.get(
                        "probability",
                        0
                    )
                    or 0
                )


            else:


                value=safe_text(score)

                probability=0



            lines.append(

                f"{medals[i]} "
                f"{value}"
                +

                (
                    f" ({probability:.1f}%)"
                    if probability
                    else ""
                )

            )



    else:


        lines.append(

            safe_text(

                decision.get(
                    "expected_score"
                ),

                "-"

            )

        )



    # MARKETS


    lines.append("")


    btts_value=float(btts or 0)


    lines.append(

        f"🤝 Обе забьют: "
        f"{'Да ✅' if btts_value>0.5 else 'Нет ❌'} "
        f"({btts_value*100:.1f}%)"

    )



    over_value=float(over25 or 0)


    lines.append(

        f"⚽ Тотал >2.5: "
        f"{'Да ✅' if over_value>0.5 else 'Нет ❌'} "
        f"({over_value*100:.1f}%)"

    )



    lines.append(
        "──────────────"
    )



    # ANALYSIS


    lines.append(
        "📌 *Аналитический вывод*"
    )



    winner_probability=float(

        decision.get(
            "winner_probability",
            0
        )
        or 0

    )


    winner=safe_text(

        decision.get(
            "winner_name",
            decision.get(
                "winner"
            )
        ),

        "-"

    )



    if winner_probability>=55:


        lines.append(

            f"Преимущество: *{winner}*"

        )


    elif winner_probability>=45:


        lines.append(
            "Матч сбалансирован"
        )


    else:


        lines.append(
            "Высокий риск"
        )



    # FACTORS


    clean_factors=[]


    for factor in factors:


        if factor is not None:


            clean_factors.append(
                str(factor)
            )



    if clean_factors:


        lines.append("")

        lines.append(
            "🧠 *Ключевые факторы*"
        )


        for factor in clean_factors[:4]:


            lines.append(
                f"• {factor}"
            )



    # RATING


    if faj_rating:


        lines.append("")

        lines.append(
            "🧠 *FAJ Rating*"
        )


        lines.append(

            f"{home}: "
            f"{float(faj_rating.get(home,0)):.1f}"

        )


        lines.append(

            f"{away}: "
            f"{float(faj_rating.get(away,0)):.1f}"

        )



    # CONFIDENCE


    if confidence is not None:


        label,description = get_confidence_label(
            confidence
        )


        lines.append("")


        lines.append(

            f"⚠️ Риск: {get_risk_label(risk)}"

        )


        lines.append(

            f"🎯 Уверенность FAJ: {float(confidence):.1f}%"

        )


        lines.append(

            f"🏷 Категория: *{label}*"

        )


        lines.append(

            f"📌 {description}"

        )



    # FINAL SAFE JOIN


    return "\n".join(

        str(line)

        for line in lines

        if line is not None

    )

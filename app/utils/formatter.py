# =====================================================
# FAJ Platform v6.3
# app/utils/formatter.py
#
# Prediction Formatter
# =====================================================


# =====================================================
# CONFIDENCE LABEL
# =====================================================

def get_confidence_label(confidence):

    confidence = float(confidence or 0)


    if confidence >= 90:

        return (
            "AAA",
            "Очень сильный прогноз"
        )


    elif confidence >= 80:

        return (
            "AA",
            "Высокая уверенность"
        )


    elif confidence >= 70:

        return (
            "A",
            "Хороший прогноз"
        )


    elif confidence >= 60:

        return (
            "B",
            "Рабочий прогноз"
        )


    else:

        return (
            "C",
            "Высокий риск"
        )



# =====================================================
# RISK LABEL
# =====================================================

def get_risk_label(risk):

    if isinstance(risk, str):

        return risk


    risk = float(risk or 0)


    if risk >= 70:

        return "Высокий"


    elif risk >= 40:

        return "Средний"


    else:

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


    lines = []


    # ================================================
    # HEADER
    # ================================================

    lines.append(
        f"⚽ *{home} — {away}*"
    )


    lines.append(
        f"🏆 *Лига:* {league}"
    )


    lines.append(
        "──────────────"
    )



    # ================================================
    # XG
    # ================================================

    lines.append(
        "📊 *xG*"
    )


    lines.append(

        f"FAJ: "
        f"{float(xg.get('home',0)):.2f}"
        f" — "
        f"{float(xg.get('away',0)):.2f}"

    )



    # ================================================
    # PROBABILITIES
    # ================================================

    lines.append("")

    lines.append(
        "📈 *Вероятности*"
    )


    lines.append(

        f"П1 "
        f"{decision.get('home_probability',
                        decision.get('home_prob',0))}%  "
        f"Х "
        f"{decision.get('draw_probability',
                        decision.get('draw_prob',0))}%  "
        f"П2 "
        f"{decision.get('away_probability',
                        decision.get('away_prob',0))}%"

    )


    lines.append(
        "──────────────"
    )



    # ================================================
    # SCORE
    # ================================================

    lines.append(
        "🎯 *Наиболее вероятные счета*"
    )


    if top_scores:


        medals = [
            "1️⃣",
            "2️⃣",
            "3️⃣"
        ]


        for i, score in enumerate(top_scores[:3]):

            lines.append(

                f"{medals[i]} "
                f"{score.get('score','')}"
                f" "
                f"({float(score.get('probability',0)):.1f}%)"

            )


    else:


        lines.append(

            decision.get(
                "expected_score",
                ""
            )

        )



    # ================================================
    # MARKETS
    # ================================================

    lines.append("")


    lines.append(
        "🤝 *Обе забьют*"
    )


    btts_value = float(btts or 0)


    lines.append(

        f"{'Да ✅' if btts_value > 0.5 else 'Нет ❌'} "
        f"({btts_value*100:.1f}%)"

    )



    lines.append("")


    lines.append(
        "⚽ *Тотал >2.5*"
    )


    over_value = float(over25 or 0)


    lines.append(

        f"{'Да ✅' if over_value > 0.5 else 'Нет ❌'} "
        f"({over_value*100:.1f}%)"

    )



    lines.append(
        "──────────────"
    )



    # ================================================
    # ANALYSIS
    # ================================================

    lines.append(
        "📌 *Аналитический вывод*"
    )


    winner_probability = float(

        decision.get(
            "winner_probability",
            0
        )

    )


    if winner_probability >= 55:


        lines.append(

            f"Преимущество: "
            f"*{decision.get('winner_name','')}*"

        )


    elif winner_probability >= 45:


        lines.append(
            "Матч сбалансирован, явного фаворита нет"
        )


    else:


        lines.append(
            "Высокий риск, прогноз нестабилен"
        )



    # ================================================
    # FACTORS
    # ================================================

    if factors:


        lines.append("")

        lines.append(
            "🧠 *Ключевые факторы*"
        )


        for factor in factors[:4]:

            lines.append(
                f"• {factor}"
            )



    # ================================================
    # FAJ RATING
    # ================================================

    if faj_rating:


        lines.append("")

        lines.append(
            "━━━━━━━━━━━━━━"
        )


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



    # ================================================
    # RISK + CONFIDENCE
    # ================================================

    if confidence is not None:


        label, description = get_confidence_label(
            confidence
        )


        lines.append("")


        lines.append(

            f"⚠️ Риск: "
            f"{get_risk_label(risk)}"

        )


        lines.append("")


        lines.append(

            f"🎯 Уверенность FAJ: "
            f"{float(confidence):.1f}%"

        )


        lines.append(

            f"🏷 Категория: *{label}*"

        )


        lines.append(

            f"📌 {description}"

        )


    return "\n".join(lines)

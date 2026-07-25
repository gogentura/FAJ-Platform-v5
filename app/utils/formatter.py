# =====================================================
# FAJ Platform v6.3
# formatter.py
# PostgreSQL / FAJ Core v6.3 compatible
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
    factors
):

    lines = []


    lines.append(
        f"⚽ *{home} — {away}*"
    )

    lines.append(
        f"🏆 *Лига:* {league}"
    )

    lines.append(
        "──────────────"
    )


    # ==========================
    # xG
    # ==========================

    lines.append(
        "📊 *xG*"
    )

    lines.append(
        f"FAJ: {xg['home']:.2f} — {xg['away']:.2f}"
    )


    lines.append("")


    # ==========================
    # PROBABILITIES
    # ==========================

    lines.append(
        "📈 *Вероятности*"
    )


    lines.append(

        f"П1 {decision.get('home_probability',0):.1f}%  "
        f"Х {decision.get('draw_probability',0):.1f}%  "
        f"П2 {decision.get('away_probability',0):.1f}%"

    )


    lines.append(
        "──────────────"
    )


    # ==========================
    # SCORES
    # ==========================

    lines.append(
        "🎯 *Три наиболее вероятных счёта*"
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
                f"{score.get('score','')} "
                f"({score.get('probability',0):.1f}%)"

            )


    else:

        lines.append(

            decision.get(
                "expected_score",
                "—"
            )

        )


    lines.append("")


    # ==========================
    # BTTS
    # ==========================

    lines.append(
        "🤝 *Обе забьют*"
    )


    lines.append(

        f"{'Да ✅' if btts > 0.5 else 'Нет ❌'} "
        f"({btts*100:.1f}%)"

    )


    lines.append("")


    # ==========================
    # TOTAL
    # ==========================

    lines.append(
        "⚽ *Тотал >2.5*"
    )


    lines.append(

        f"{'Да ✅' if over25 > 0.5 else 'Нет ❌'} "
        f"({over25*100:.1f}%)"

    )


    lines.append(
        "──────────────"
    )


    # ==========================
    # DECISION
    # ==========================

    lines.append(
        "📌 *Аналитический вывод*"
    )


    probability = decision.get(
        "winner_probability",
        0
    )


    if probability >= 55:


        lines.append(

            f"Преимущество: "
            f"*{decision.get('winner_name','')}*"

        )


        confidence = decision.get(
            "confidence",
            0
        )


        if confidence >= 80:

            lines.append(
                "Надёжность: *AA*"
            )

        elif confidence >= 70:

            lines.append(
                "Надёжность: *A*"
            )

        else:

            lines.append(
                "Надёжность: *B*"
            )


    elif probability >=45:


        lines.append(
            "Матч сбалансирован"
        )

        lines.append(
            "Надёжность: *B*"
        )


    else:


        lines.append(
            "Высокий риск"
        )

        lines.append(
            "Надёжность: *C*"
        )


    # ==========================
    # FACTORS
    # ==========================

    if factors:

        lines.append("")

        lines.append(
            "🧠 *Ключевые факторы*"
        )


        for factor in factors[:4]:

            lines.append(
                f"• {factor}"
            )


    return "\n".join(lines)

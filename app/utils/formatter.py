# =====================================================
# FAJ Platform v6.3
# Formatter
# PostgreSQL compatible
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


    # ===============================
    # xG
    # ===============================

    lines.append(
        "📊 *xG*"
    )

    lines.append(
        f"FAJ: {xg.get('home',0):.2f} — {xg.get('away',0):.2f}"
    )


    lines.append("")


    # ===============================
    # PROBABILITIES
    # ===============================

    home_prob = decision.get(
        "home_probability",
        decision.get("home_prob",0)
    )

    draw_prob = decision.get(
        "draw_probability",
        decision.get("draw_prob",0)
    )

    away_prob = decision.get(
        "away_probability",
        decision.get("away_prob",0)
    )


    lines.append(
        "📈 *Вероятности*"
    )

    lines.append(
        f"П1 {home_prob}%  Х {draw_prob}%  П2 {away_prob}%"
    )


    lines.append(
        "──────────────"
    )


    # ===============================
    # SCORES
    # ===============================

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
                f"{medals[i]} {score.get('score','')} "
                f"({score.get('probability',0):.1f}%)"
            )


    else:

        lines.append(
            decision.get(
                "expected_score",
                "-"
            )
        )


    lines.append("")


    # ===============================
    # BTTS
    # ===============================

    lines.append(
        "🤝 *Обе забьют*"
    )

    lines.append(
        f"{'Да ✅' if btts > 0.5 else 'Нет ❌'} "
        f"({btts*100:.1f}%)"
    )


    lines.append("")


    # ===============================
    # TOTAL
    # ===============================

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


    # ===============================
    # ANALYSIS
    # ===============================

    lines.append(
        "📌 *Аналитический вывод*"
    )


    winner_probability = decision.get(
        "winner_probability",
        0
    )


    if winner_probability >= 55:

        lines.append(
            f"Преимущество: *{decision.get('winner_name','')}*"
        )


    elif winner_probability >= 45:

        lines.append(
            "Матч сбалансирован"
        )


    else:

        lines.append(
            "Высокий риск прогноза"
        )


    confidence = decision.get(
        "confidence",
        0
    )


    if confidence >= 80:

        lines.append(
            "Надёжность: *AA*"
        )

    elif confidence >=70:

        lines.append(
            "Надёжность: *A*"
        )

    else:

        lines.append(
            "Надёжность: *B*"
        )


    lines.append("")


    # ===============================
    # FACTORS
    # ===============================

    if factors:

        lines.append(
            "🧠 *Ключевые факторы*"
        )

        for factor in factors[:4]:

            lines.append(
                f"• {factor}"
            )


    return "\n".join(lines)

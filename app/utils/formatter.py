def format_prediction(home, away, league, xg, decision, top_scores, btts, over25, factors):
    lines = []
    lines.append(f"⚽ *{home} — {away}*")
    lines.append(f"🏆 *Лига:* {league}")
    lines.append("──────────────")
    lines.append(f"📊 *xG*")
    lines.append(f"FAJ: {xg['home']:.2f} — {xg['away']:.2f}")
    lines.append("")
    lines.append("📈 *Вероятности*")
    lines.append(f"П1 {decision['home_prob']}%  Х {decision['draw_prob']}%  П2 {decision['away_prob']}%")
    lines.append("──────────────")
    lines.append(f"🎯 *Наиболее вероятный счёт*")
    if top_scores:
        lines.append(f"{decision['expected_score']}  (вероятность {top_scores[0][1]*100:.1f}%)")
    else:
        lines.append(f"{decision['expected_score']}")
    lines.append("")
    lines.append("🤝 *Обе забьют*")
    lines.append(f"{'Да ✅' if btts > 0.5 else 'Нет ❌'} ({btts*100:.1f}%)")
    lines.append("")
    lines.append("⚽ *Тотал >2.5*")
    lines.append(f"{'Да ✅' if over25 > 0.5 else 'Нет ❌'} ({over25*100:.1f}%)")
    lines.append("──────────────")
    lines.append("📌 *Аналитический вывод*")
    if decision["winner_probability"] > 55 and decision["confidence"] > 65:
        lines.append(f"Преимущество {decision['winner_name']}")
        if decision["confidence"] > 75:
            lines.append("Надёжность: *AA* (очень высокая)")
        else:
            lines.append("Надёжность: *A* (высокая)")
    elif 45 <= decision["winner_probability"] <= 55:
        lines.append("Матч сбалансирован, явного фаворита нет")
        lines.append("Надёжность: *B* (средняя)")
    else:
        lines.append("Высокий риск, прогноз нестабилен")
        lines.append("Надёжность: *C* (низкая)")
    lines.append("")
    if factors:
        lines.append("🧠 *Ключевые факторы*")
        for f in factors[:4]:
            lines.append(f"• {f}")
    return "\n".join(lines)

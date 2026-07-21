import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from app.config import Config

logger = logging.getLogger(__name__)

async def run_bot(core, journal):
    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан!")
        return
    bot = Bot(token=Config.TELEGRAM_TOKEN)
    dp = Dispatcher()
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "⚽ *FAJ Platform v5.0*\n\n"
            "Просто напиши названия двух команд через пробел.\n"
            "Пример: Зенит Спартак\n"
            "Можно указать лигу: Зенит Спартак RPL\n"
            "Доступные лиги: EPL, LaLiga, Bundesliga, SerieA, Ligue1, UCL, RPL",
            parse_mode="Markdown"
        )
    
    @dp.message()
    async def handle_text(message: types.Message):
        text = message.text.strip()
        if not text:
            return
        parts = text.split()
        if len(parts) < 2:
            await message.answer("❌ Напиши две команды через пробел.\nПример: Зенит Спартак")
            return
        
        if len(parts) >= 3 and parts[2].upper() in ["EPL", "LALIGA", "BUNDESLIGA", "SERIEA", "LIGUE1", "UCL", "RPL"]:
            home = parts[0]
            away = parts[1]
            league = parts[2].upper()
        else:
            home = parts[0]
            away = parts[1]
            league = "RPL"
        
        await message.answer(f"⏳ Анализирую матч *{home} — {away}* ({league})...", parse_mode="Markdown")
        try:
            result = core.predict_match(home, away, league)
            d = result["decision"]
            xg = result["xg"]
            top_scores = result.get("top_scores", [])
            btts = result.get("btts", 0.0)
            over25 = result.get("over25", 0.0)
            recommendation = result.get("recommendation", "Нет рекомендации")
            tactical = result.get("tactical", {})
            home_standing = result.get("home_standing")
            away_standing = result.get("away_standing")
            
            if "не рекомендую" in recommendation.lower() or "нестабилен" in recommendation.lower():
                rec_color = "🔴"
            elif "нейтрально" in recommendation.lower():
                rec_color = "🟡"
            else:
                rec_color = "🟢"
            
            lines = []
            lines.append(f"⚽ *{home} — {away}*")
            lines.append(f"🏆 *Лига:* {league}")
            if home_standing and away_standing:
                lines.append(f"📊 *Место в таблице:* {home_standing['position']} ({home_standing['points']} pts) — {away_standing['position']} ({away_standing['points']} pts)")
            lines.append(f"📊 *xG:* {xg['home']:.2f} — {xg['away']:.2f}")
            lines.append("")
            lines.append("📈 *Вероятности:*")
            lines.append(f"   • П1: {d['home_prob']}%")
            lines.append(f"   • X:  {d['draw_prob']}%")
            lines.append(f"   • П2: {d['away_prob']}%")
            lines.append("")
            lines.append(f"🎯 *Прогноз:* {d['winner_name']} ({d['winner_probability']}%)")
            lines.append(f"🧮 *Ожидаемый счёт:* {d['expected_score']}")
            lines.append(f"🔒 *Уверенность:* {d['confidence']}%")
            lines.append("")
            if top_scores:
                lines.append("📌 *Топ-3 счета:*")
                for score, prob in top_scores[:3]:
                    lines.append(f"   • {score} – {prob*100:.1f}%")
                lines.append("")
            lines.append(f"🤝 *Обе забьют:* {'Да ✅' if btts > 0.5 else 'Нет ❌'} ({btts*100:.1f}%)")
            lines.append(f"⚽ *Тотал > 2.5:* {'Да ✅' if over25 > 0.5 else 'Нет ❌'} ({over25*100:.1f}%)")
            lines.append("")
            if recommendation:
                lines.append(f"{rec_color} *Рекомендация:* {recommendation}")
                lines.append("")
            if tactical:
                summary = tactical.get('summary', '')
                if summary and summary != "Тактический анализ временно отключён":
                    lines.append("🧠 *Тактический анализ:*")
                    for part in summary.split('. '):
                        if part.strip():
                            lines.append(f"   • {part.strip()}.")
                    lines.append("")
                else:
                    lines.append("🧠 *Тактика:* Информация временно недоступна.")
                    lines.append("")
            lines.append(f"⏱ *Время расчёта:* {result['processing_time']} сек")
            
            await message.answer("\n".join(lines), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка прогноза: {e}")
            await message.answer("⚠️ Ошибка. Попробуйте позже.")
    
    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        await message.answer(
            f"🔹 *FAJ Platform*\nВерсия: {core.version}\nСтатус: ✅ работает",
            parse_mode="Markdown"
        )
    
    logger.info("Бот запущен и готов к работе")
    await dp.start_polling(bot)

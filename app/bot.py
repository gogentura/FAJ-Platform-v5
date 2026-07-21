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
            
            if "не рекомендую" in recommendation.lower() or "нестабилен" in recommendation.lower():
                rec_color = "🔴"
            elif "нейтрально" in recommendation.lower():
                rec_color = "🟡"
            else:
                rec_color = "🟢"
            
            text = (
                f"⚽ *{home} — {away}*\n"
                f"🏆 *Лига:* {league}\n"
                f"📊 *xG:* {xg['home']:.2f} — {xg['away']:.2f}\n"
                f"📈 *Вероятности:*\n"
                f"   • П1: {d['home_prob']}%\n"
                f"   • X:  {d['draw_prob']}%\n"
                f"   • П2: {d['away_prob']}%\n"
                f"🎯 *Прогноз:* {d['winner_name']} ({d['winner_probability']}%)\n"
                f"🧮 *Ожидаемый счёт:* {d['expected_score']}\n"
                f"🔒 *Уверенность:* {d['confidence']}%\n"
            )
            if top_scores:
                text += "📌 *Топ-3 счета:*\n"
                for score, prob in top_scores[:3]:
                    text += f"   • {score} – {prob*100:.1f}%\n"
            text += f"🤝 *Обе забьют:* {'Да' if btts > 0.5 else 'Нет'} ({btts*100:.1f}%)\n"
            text += f"⚽ *Тотал > 2.5:* {'Да' if over25 > 0.5 else 'Нет'} ({over25*100:.1f}%)\n"
            if recommendation:
                text += f"{rec_color} *Рекомендация:* {recommendation}\n"
            if tactical:
                text += f"🧠 *Тактика:* {tactical.get('summary', 'Нет данных')}\n"
            text += f"\n⏱ *Время расчёта:* {result['processing_time']} сек"
            await message.answer(text, parse_mode="Markdown")
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

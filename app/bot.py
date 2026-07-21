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
            "Я — футбольный аналитический бот.\n"
            "Используй /predict <команда1> <команда2>\n\n"
            "Пример: /predict Зенит Спартак",
            parse_mode="Markdown"
        )
    
    @dp.message(Command("predict"))
    async def cmd_predict(message: types.Message):
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.answer("❌ Укажи две команды: /predict Арсенал Челси")
            return
        home, away = args[1], args[2]
        await message.answer(f"⏳ Анализирую матч *{home} — {away}*...", parse_mode="Markdown")
        try:
            result = core.predict_match(home, away)
            text = (
                f"⚽ *{home} — {away}*\n"
                f"📊 *xG:* {result['xg']['home']:.2f} — {result['xg']['away']:.2f}\n"
                f"📈 *Вероятности:*\n"
                f"   • П1: {result['probabilities']['home']}%\n"
                f"   • X:  {result['probabilities']['draw']}%\n"
                f"   • П2: {result['probabilities']['away']}%\n"
                f"🎯 *Прогноз:* {result['prediction']['winner_name']} ({result['prediction']['winner_probability']}%)\n"
                f"🧮 *Счёт:* {result['prediction']['expected_score']}\n"
                f"🔒 *Уверенность:* {result['confidence']}%\n"
                f"⏱ *Время:* {result['processing_time']} сек"
            )
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

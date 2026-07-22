import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from app.config import Config
from app.core.faj_core import FAJCore
from app.update_manager import UpdateManager
from app.passport_manager import load_passport
from app.status import get_full_status
from app.journal import Journal
from app.api_tracker import get_api_status

logger = logging.getLogger(__name__)

# Клавиатура с кнопками
def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="📋 Журнал")],
        [KeyboardButton(text="🔄 Обновить РПЛ"), KeyboardButton(text="📁 Паспорт")],
        [KeyboardButton(text="⚙️ Здоровье"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def run_bot(core, journal):
    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    ADMIN_ID = int(Config.ADMIN_CHAT_ID) if Config.ADMIN_CHAT_ID else None
    if not ADMIN_ID:
        logger.warning("ADMIN_CHAT_ID не задан — бот будет доступен всем!")

    bot = Bot(token=Config.TELEGRAM_TOKEN)
    dp = Dispatcher()
    update_manager = UpdateManager()

    async def check_access(message: types.Message) -> bool:
        if ADMIN_ID and message.from_user.id != ADMIN_ID:
            await message.answer("⛔ Доступ запрещён. Этот бот — личный.")
            return False
        return True

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        if not await check_access(message):
            return
        await message.answer(
            "⚽ *FAJ Platform v5.0.1 RC*\n\n"
            "Просто напиши две команды: Зенит Спартак\n"
            "Или используй кнопки ниже 👇",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    # Вызов меню по словам "FAJ" или "Прогноз"
    @dp.message(lambda msg: msg.text.lower() in ["faj", "прогноз"])
    async def cmd_show_menu(message: types.Message):
        if not await check_access(message):
            return
        await message.answer(
            "⚽ *Главное меню FAJ*\nВыбери действие 👇",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    # --- Обработка кнопок ---
    @dp.message(lambda msg: msg.text == "📊 Статус")
    async def btn_status(message: types.Message):
        if not await check_access(message):
            return
        text = get_full_status()
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    @dp.message(lambda msg: msg.text == "📋 Журнал")
    async def btn_journal(message: types.Message):
        if not await check_access(message):
            return
        entries = journal.get_all(limit=5)
        if not entries:
            await message.answer("📭 Журнал пуст", reply_markup=get_main_keyboard())
            return
        text = "📋 *Последние прогнозы:*\n"
        for e in entries:
            text += f"• {e['match']}: {e['prediction']} (факт: {e.get('actual_score', '?')})\n"
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    @dp.message(lambda msg: msg.text == "🔄 Обновить РПЛ")
    async def btn_update_rpl(message: types.Message):
        if not await check_access(message):
            return
        await message.answer("⏳ Обновляю РПЛ... (16 команд, ~5 секунд)", reply_markup=get_main_keyboard())
        result = await update_manager.update_rpl()
        updated = sum(1 for r in result["results"] if r["status"] == "ok")
        skipped = sum(1 for r in result["results"] if r["status"] == "skipped")
        await message.answer(f"✅ Обновлено: {updated}, пропущено (уже сегодня): {skipped}", reply_markup=get_main_keyboard())

    @dp.message(lambda msg: msg.text == "📁 Паспорт")
    async def btn_passport(message: types.Message):
        if not await check_access(message):
            return
        await message.answer("📋 Введи название команды, например: Спартак", reply_markup=get_main_keyboard())

    @dp.message(lambda msg: msg.text == "⚙️ Здоровье")
    async def btn_health(message: types.Message):
        if not await check_access(message):
            return
        api = get_api_status()
        await message.answer(
            f"✅ *Система работает*\n"
            f"• Бот: активен\n"
            f"• API-Football: доступен (осталось {api['remaining']} запросов)\n"
            f"• Паспорта: загружены\n"
            f"• Журнал: работает",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    @dp.message(lambda msg: msg.text == "❓ Помощь")
    async def btn_help(message: types.Message):
        if not await check_access(message):
            return
        await message.answer(
            "📖 *Доступные команды:*\n\n"
            "/start — показать меню\n"
            "/status — состояние системы\n"
            "/update_rpl — обновить РПЛ\n"
            "/update_team <команда> — обновить одну команду\n"
            "/passport <команда> — паспорт команды\n"
            "/journal — последние прогнозы\n"
            "/health — проверка системы\n\n"
            "Или просто напиши две команды через пробел: Зенит Спартак",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    # --- Обработка команд (для совместимости) ---
    @dp.message(Command("status"))
    async def cmd_status(message: types.Message):
        if not await check_access(message):
            return
        text = get_full_status()
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    @dp.message(Command("update_rpl"))
    async def cmd_update_rpl(message: types.Message):
        if not await check_access(message):
            return
        await message.answer("⏳ Обновляю РПЛ... (16 команд, ~5 секунд)", reply_markup=get_main_keyboard())
        result = await update_manager.update_rpl()
        updated = sum(1 for r in result["results"] if r["status"] == "ok")
        skipped = sum(1 for r in result["results"] if r["status"] == "skipped")
        await message.answer(f"✅ Обновлено: {updated}, пропущено (уже сегодня): {skipped}", reply_markup=get_main_keyboard())

    @dp.message(Command("update_team"))
    async def cmd_update_team(message: types.Message):
        if not await check_access(message):
            return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Укажи команду: /update_team Спартак", reply_markup=get_main_keyboard())
            return
        team = args[1]
        await message.answer(f"⏳ Обновляю {team}...", reply_markup=get_main_keyboard())
        result = await update_manager.update_team(team)
        if result["status"] == "ok":
            await message.answer(f"✅ {team} обновлён (версия паспорта: {result['version']})", reply_markup=get_main_keyboard())
        else:
            await message.answer(f"❌ {result['message']}", reply_markup=get_main_keyboard())

    @dp.message(Command("passport"))
    async def cmd_passport(message: types.Message):
        if not await check_access(message):
            return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer("❌ Укажи команду: /passport Спартак", reply_markup=get_main_keyboard())
            return
        team = args[1]
        passport = load_passport(team)
        if not passport:
            await message.answer(f"❌ Паспорт {team} не найден. Обнови: /update_team {team}", reply_markup=get_main_keyboard())
            return
        text = (
            f"📋 *{team}*\n"
            f"Passport v{passport['version']}\n"
            f"🔄 {passport['last_updated']}\n"
            f"⚔️ Атака: {passport['attack']}\n"
            f"🛡️ Защита: {passport['defense']}\n"
            f"🎮 Контроль: {passport['control']}\n"
            f"📈 Форма: {passport['form_index']}\n"
            f"📊 xG: {passport['avg_xg']:.2f}"
        )
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    @dp.message(Command("journal"))
    async def cmd_journal(message: types.Message):
        if not await check_access(message):
            return
        entries = journal.get_all(limit=5)
        if not entries:
            await message.answer("📭 Журнал пуст", reply_markup=get_main_keyboard())
            return
        text = "📋 *Последние прогнозы:*\n"
        for e in entries:
            text += f"• {e['match']}: {e['prediction']} (факт: {e.get('actual_score', '?')})\n"
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

    @dp.message(Command("health"))
    async def cmd_health(message: types.Message):
        if not await check_access(message):
            return
        api = get_api_status()
        await message.answer(
            f"✅ *Система работает*\n"
            f"• Бот: активен\n"
            f"• API-Football: доступен (осталось {api['remaining']} запросов)\n"
            f"• Паспорта: загружены\n"
            f"• Журнал: работает",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

    # --- Обработка простого текста (прогноз) ---
    @dp.message()
    async def handle_text(message: types.Message):
        if not await check_access(message):
            return
        text = message.text.strip()
        if not text or text.startswith("/"):
            return
        # Если текст — не команда и не кнопка, считаем прогнозом
        parts = text.split()
        if len(parts) < 2:
            await message.answer("❌ Напиши две команды: Зенит Спартак", reply_markup=get_main_keyboard())
            return
        home = parts[0]
        away = parts[1]
        league = parts[2].upper() if len(parts) >= 3 and parts[2].upper() in ["EPL", "RPL", "UCL"] else "RPL"
        await message.answer(f"⏳ Анализирую {home} — {away} ({league})...", reply_markup=get_main_keyboard())
        try:
            result = core.predict_match(home, away, league)
            if "error" in result:
                await message.answer(f"❌ {result['error']}", reply_markup=get_main_keyboard())
                return
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
            lines = []
            lines.append(f"⚽ *{home} — {away}*")
            lines.append(f"🏆 *Лига:* {league}")
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
            journal.save(
                match=f"{home} — {away}",
                prediction={
                    "winner": d["winner_name"],
                    "winner_probability": d["winner_probability"],
                    "xg_home": xg['home'],
                    "xg_away": xg['away'],
                    "expected_score": d["expected_score"],
                    "confidence": d["confidence"]
                }
            )
            await message.answer("\n".join(lines), reply_markup=get_main_keyboard(), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка прогноза: {e}")
            await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=get_main_keyboard())

    logger.info("Бот запущен (приватный режим, постоянная клавиатура)")
    await dp.start_polling(bot)

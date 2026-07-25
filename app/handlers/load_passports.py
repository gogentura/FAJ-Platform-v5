# =====================================================
# FAJ Platform v6.3
# app/handlers/load_passports.py
#
# RPL Expert Team Passports Loader
# PostgreSQL compatible
# =====================================================

import logging
import traceback

from aiogram import types

from app.config import Config

from app.passport_manager import (
    save_passport,
    init_default_aliases
)

from app.handlers.keyboard import (
    get_main_keyboard
)


logger = logging.getLogger(__name__)


# =====================================================
# EXPERT PASSPORTS
# FAJ v6.3
# =====================================================

EXPERT_PASSPORTS = [

    {
        "team": "Зенит",
        "league": "RPL",
        "season": "2026/27",

        "attack": 88,
        "defense": 79,
        "control": 84,

        "form": 84,

        "efficiency": 78,
        "mentality": 85,

        "discipline": 80,
        "fitness": 84,
        "predictability": 82,

        "xg_for": 1.8,
        "xg_against": 0.8,

        "transfer_index": 5,
        "injury_index": 0,
        "fatigue_index": 0
    },

    {
        "team": "Краснодар",
        "league": "RPL",
        "season": "2026/27",

        "attack": 80,
        "defense": 77,
        "control": 81,

        "form": 79,

        "efficiency": 76,
        "mentality": 79,

        "discipline": 78,
        "fitness": 80,
        "predictability": 76,

        "xg_for": 1.6,
        "xg_against": 0.9,

        "transfer_index": 4,
        "injury_index": 0,
        "fatigue_index": 0
    },

    {
        "team": "Локомотив",
        "league": "RPL",
        "season": "2026/27",

        "attack": 81,
        "defense": 78,
        "control": 82,

        "form": 87,

        "efficiency": 77,
        "mentality": 81,

        "discipline": 79,
        "fitness": 83,
        "predictability": 78,

        "xg_for": 1.7,
        "xg_against": 0.8,

        "transfer_index": 3,
        "injury_index": 0,
        "fatigue_index": 0
    },

    {
        "team": "Динамо М",
        "league": "RPL",
        "season": "2026/27",

        "attack": 80,
        "defense": 78,
        "control": 80,

        "form": 81,

        "efficiency": 75,
        "mentality": 78,

        "discipline": 77,
        "fitness": 79,
        "predictability": 75,

        "xg_for": 1.6,
        "xg_against": 0.9,

        "transfer_index": 2,
        "injury_index": 0,
        "fatigue_index": 0
    },

    {
        "team": "Спартак",
        "league": "RPL",
        "season": "2026/27",

        "attack": 80,
        "defense": 76,
        "control": 78,

        "form": 76,

        "efficiency": 74,
        "mentality": 77,

        "discipline": 75,
        "fitness": 77,
        "predictability": 73,

        "xg_for": 1.5,
        "xg_against": 1.0,

        "transfer_index": 2,
        "injury_index": 0,
        "fatigue_index": 0
    },

    {
        "team": "ЦСКА",
        "league": "RPL",
        "season": "2026/27",

        "attack": 78,
        "defense": 80,
        "control": 79,

        "form": 79,

        "efficiency": 73,
        "mentality": 76,

        "discipline": 80,
        "fitness": 78,
        "predictability": 77,

        "xg_for": 1.5,
        "xg_against": 0.9,

        "transfer_index": 3,
        "injury_index": 0,
        "fatigue_index": 0
    },

    {
        "team": "Ахмат",
        "league": "RPL",
        "season": "2026/27",
        "attack": 76,
        "defense": 75,
        "control": 77,
        "form": 78,
        "efficiency": 72,
        "mentality": 75,
        "discipline": 76,
        "fitness": 76,
        "predictability": 74,
        "xg_for": 1.4,
        "xg_against": 1.1,
        "transfer_index": 2,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Рубин",
        "league": "RPL",
        "season": "2026/27",
        "attack": 75,
        "defense": 76,
        "control": 76,
        "form": 71,
        "efficiency": 71,
        "mentality": 74,
        "discipline": 78,
        "fitness": 74,
        "predictability": 72,
        "xg_for": 1.3,
        "xg_against": 1.1,
        "transfer_index": 2,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Ростов",
        "league": "RPL",
        "season": "2026/27",
        "attack": 74,
        "defense": 74,
        "control": 74,
        "form": 74,
        "efficiency": 70,
        "mentality": 73,
        "discipline": 74,
        "fitness": 75,
        "predictability": 70,
        "xg_for": 1.3,
        "xg_against": 1.2,
        "transfer_index": 1,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Балтика",
        "league": "RPL",
        "season": "2026/27",
        "attack": 71,
        "defense": 72,
        "control": 72,
        "form": 76,
        "efficiency": 68,
        "mentality": 70,
        "discipline": 75,
        "fitness": 77,
        "predictability": 76,
        "xg_for": 1.2,
        "xg_against": 1.3,
        "transfer_index": 3,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Акрон",
        "league": "RPL",
        "season": "2026/27",
        "attack": 70,
        "defense": 71,
        "control": 71,
        "form": 75,
        "efficiency": 67,
        "mentality": 69,
        "discipline": 73,
        "fitness": 74,
        "predictability": 71,
        "xg_for": 1.1,
        "xg_against": 1.3,
        "transfer_index": 2,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Оренбург",
        "league": "RPL",
        "season": "2026/27",
        "attack": 72,
        "defense": 73,
        "control": 73,
        "form": 70,
        "efficiency": 68,
        "mentality": 71,
        "discipline": 72,
        "fitness": 71,
        "predictability": 70,
        "xg_for": 1.2,
        "xg_against": 1.2,
        "transfer_index": 1,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Факел",
        "league": "RPL",
        "season": "2026/27",
        "attack": 70,
        "defense": 72,
        "control": 70,
        "form": 68,
        "efficiency": 66,
        "mentality": 68,
        "discipline": 71,
        "fitness": 70,
        "predictability": 68,
        "xg_for": 1.0,
        "xg_against": 1.4,
        "transfer_index": 1,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Крылья Советов",
        "league": "RPL",
        "season": "2026/27",
        "attack": 69,
        "defense": 71,
        "control": 69,
        "form": 67,
        "efficiency": 65,
        "mentality": 67,
        "discipline": 70,
        "fitness": 69,
        "predictability": 67,
        "xg_for": 1.0,
        "xg_against": 1.4,
        "transfer_index": 1,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Динамо Мх",
        "league": "RPL",
        "season": "2026/27",
        "attack": 68,
        "defense": 70,
        "control": 68,
        "form": 70,
        "efficiency": 64,
        "mentality": 66,
        "discipline": 72,
        "fitness": 71,
        "predictability": 69,
        "xg_for": 0.9,
        "xg_against": 1.5,
        "transfer_index": 1,
        "injury_index": 0,
        "fatigue_index": 0
    },
    {
        "team": "Родина",
        "league": "RPL",
        "season": "2026/27",
        "attack": 67,
        "defense": 69,
        "control": 67,
        "form": 68,
        "efficiency": 63,
        "mentality": 65,
        "discipline": 68,
        "fitness": 69,
        "predictability": 65,
        "xg_for": 0.8,
        "xg_against": 1.6,
        "transfer_index": 1,
        "injury_index": 0,
        "fatigue_index": 0
    }
]

# =====================================================
# LOAD PASSPORTS HANDLER
# FAJ v6.3
# =====================================================
async def cmd_load_passports(
    message: types.Message
):
    # Проверка администратора
    if str(message.from_user.id) != str(Config.ADMIN_CHAT_ID):
        await message.answer(
            "⛔ Только для администратора.",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(
        """
⏳ FAJ загружает паспорта РПЛ...
Обновление:
• рейтинги команд
• xG модель
• форма
• физика
• дисциплина
• трансферы
        """,
        reply_markup=get_main_keyboard()
    )

    count = 0
    errors = []

    for data in EXPERT_PASSPORTS:
        team = data["team"]
        try:
            passport = {
                "team": team,
                "league": data["league"],
                "season": data["season"],
                # СИЛА КОМАНДЫ
                "attack": data["attack"],
                "defense": data["defense"],
                "control": data["control"],
                # СОСТОЯНИЕ
                "form": data["form"],
                # ДОПОЛНИТЕЛЬНЫЕ ИНДЕКСЫ
                "efficiency": data["efficiency"],
                "mentality": data["mentality"],
                "discipline": data["discipline"],
                "fitness": data["fitness"],
                "predictability": data["predictability"],
                # xG
                "xg_for": data["xg_for"],
                "xg_against": data["xg_against"],
                # СЛУЖЕБНЫЕ
                "transfer_index": data["transfer_index"],
                "injury_index": data["injury_index"],
                "fatigue_index": data["fatigue_index"]
            }
            save_passport(
                team,
                passport
            )
            count += 1
            logger.info(
                f"Passport loaded: {team}"
            )
        except Exception as e:
            error = (
                f"{team}: {str(e)}"
            )
            logger.error(
                error
            )
            logger.error(
                traceback.format_exc()
            )
            errors.append(error)

    # =================================================
    # ALIASES
    # =================================================
    try:
        init_default_aliases()
    except Exception as e:
        errors.append(
            f"Aliases error: {e}"
        )

    # =================================================
    # REPORT
    # =================================================
    if errors:
        text = f"""
⚠️ Паспорта загружены частично
✅ Загружено:
{count}
Ошибки:
"""
        for err in errors[:5]:
            text += f"""
❌ {err}
"""
    else:
        text = f"""
✅ Паспорта успешно обновлены
🏆 Лига:
RPL
📅 Сезон:
2026/27
━━━━━━━━━━━━━━
📊 Команд:
{count}
━━━━━━━━━━━━━━
Теперь FAJ готов:
🧠 рассчитывать xG
🎯 строить прогнозы
📈 считать форму команд
"""
    await message.answer(
        text,
        reply_markup=get_main_keyboard()
    )

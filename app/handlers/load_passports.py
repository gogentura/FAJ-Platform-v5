import logging
from aiogram import types
from app.database import get_db
from app.passport_manager import save_passport, init_default_aliases
from app.handlers.keyboard import get_main_keyboard

logger = logging.getLogger(__name__)

# Экспертные паспорта РПЛ (актуальны на 24.07.2026)
EXPERT_PASSPORTS = [
    {"team": "Зенит", "league": "RPL", "attack": 88, "defense": 79, "control": 84, "form_index": 84,
     "efficiency": 78, "mentality": 85, "home_rating": 93, "away_rating": 87,
     "coach_factor": 86, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.8, "source": "expert"}},
     "avg_goals": {"value": 2.0, "source": "expert"},
     "avg_goals_conceded": {"value": 0.8, "source": "expert"},
     "avg_possession": {"value": 60, "source": "expert"}},
    {"team": "Краснодар", "league": "RPL", "attack": 80, "defense": 77, "control": 81, "form_index": 79,
     "efficiency": 76, "mentality": 79, "home_rating": 86, "away_rating": 79,
     "coach_factor": 82, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.6, "source": "expert"}},
     "avg_goals": {"value": 1.7, "source": "expert"},
     "avg_goals_conceded": {"value": 0.9, "source": "expert"},
     "avg_possession": {"value": 57, "source": "expert"}},
    {"team": "Локомотив", "league": "RPL", "attack": 81, "defense": 78, "control": 82, "form_index": 87,
     "efficiency": 77, "mentality": 81, "home_rating": 87, "away_rating": 80,
     "coach_factor": 84, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.7, "source": "expert"}},
     "avg_goals": {"value": 1.8, "source": "expert"},
     "avg_goals_conceded": {"value": 0.8, "source": "expert"},
     "avg_possession": {"value": 58, "source": "expert"}},
    {"team": "Динамо М", "league": "RPL", "attack": 80, "defense": 78, "control": 80, "form_index": 81,
     "efficiency": 75, "mentality": 78, "home_rating": 88, "away_rating": 79,
     "coach_factor": 81, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.6, "source": "expert"}},
     "avg_goals": {"value": 1.7, "source": "expert"},
     "avg_goals_conceded": {"value": 0.9, "source": "expert"},
     "avg_possession": {"value": 56, "source": "expert"}},
    {"team": "Спартак", "league": "RPL", "attack": 80, "defense": 76, "control": 78, "form_index": 76,
     "efficiency": 74, "mentality": 77, "home_rating": 84, "away_rating": 74,
     "coach_factor": 82, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.5, "source": "expert"}},
     "avg_goals": {"value": 1.6, "source": "expert"},
     "avg_goals_conceded": {"value": 1.0, "source": "expert"},
     "avg_possession": {"value": 54, "source": "expert"}},
    {"team": "ЦСКА", "league": "RPL", "attack": 78, "defense": 80, "control": 79, "form_index": 79,
     "efficiency": 73, "mentality": 76, "home_rating": 85, "away_rating": 76,
     "coach_factor": 79, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.5, "source": "expert"}},
     "avg_goals": {"value": 1.5, "source": "expert"},
     "avg_goals_conceded": {"value": 0.9, "source": "expert"},
     "avg_possession": {"value": 55, "source": "expert"}},
    {"team": "Ахмат", "league": "RPL", "attack": 76, "defense": 75, "control": 77, "form_index": 78,
     "efficiency": 72, "mentality": 75, "home_rating": 80, "away_rating": 72,
     "coach_factor": 78, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.4, "source": "expert"}},
     "avg_goals": {"value": 1.4, "source": "expert"},
     "avg_goals_conceded": {"value": 1.1, "source": "expert"},
     "avg_possession": {"value": 53, "source": "expert"}},
    {"team": "Рубин", "league": "RPL", "attack": 75, "defense": 76, "control": 76, "form_index": 71,
     "efficiency": 71, "mentality": 74, "home_rating": 81, "away_rating": 73,
     "coach_factor": 77, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.3, "source": "expert"}},
     "avg_goals": {"value": 1.3, "source": "expert"},
     "avg_goals_conceded": {"value": 1.1, "source": "expert"},
     "avg_possession": {"value": 52, "source": "expert"}},
    {"team": "Ростов", "league": "RPL", "attack": 74, "defense": 74, "control": 74, "form_index": 74,
     "efficiency": 70, "mentality": 73, "home_rating": 79, "away_rating": 70,
     "coach_factor": 76, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.3, "source": "expert"}},
     "avg_goals": {"value": 1.2, "source": "expert"},
     "avg_goals_conceded": {"value": 1.2, "source": "expert"},
     "avg_possession": {"value": 51, "source": "expert"}},
    {"team": "Балтика", "league": "RPL", "attack": 71, "defense": 72, "control": 72, "form_index": 76,
     "efficiency": 68, "mentality": 70, "home_rating": 78, "away_rating": 67,
     "coach_factor": 74, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.2, "source": "expert"}},
     "avg_goals": {"value": 1.1, "source": "expert"},
     "avg_goals_conceded": {"value": 1.3, "source": "expert"},
     "avg_possession": {"value": 49, "source": "expert"}},
    {"team": "Акрон", "league": "RPL", "attack": 70, "defense": 71, "control": 71, "form_index": 75,
     "efficiency": 67, "mentality": 69, "home_rating": 76, "away_rating": 66,
     "coach_factor": 73, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.1, "source": "expert"}},
     "avg_goals": {"value": 1.0, "source": "expert"},
     "avg_goals_conceded": {"value": 1.3, "source": "expert"},
     "avg_possession": {"value": 48, "source": "expert"}},
    {"team": "Оренбург", "league": "RPL", "attack": 72, "defense": 73, "control": 73, "form_index": 70,
     "efficiency": 68, "mentality": 71, "home_rating": 77, "away_rating": 68,
     "coach_factor": 74, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.2, "source": "expert"}},
     "avg_goals": {"value": 1.2, "source": "expert"},
     "avg_goals_conceded": {"value": 1.2, "source": "expert"},
     "avg_possession": {"value": 50, "source": "expert"}},
    {"team": "Факел", "league": "RPL", "attack": 70, "defense": 72, "control": 70, "form_index": 68,
     "efficiency": 66, "mentality": 68, "home_rating": 76, "away_rating": 65,
     "coach_factor": 72, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.0, "source": "expert"}},
     "avg_goals": {"value": 0.9, "source": "expert"},
     "avg_goals_conceded": {"value": 1.4, "source": "expert"},
     "avg_possession": {"value": 47, "source": "expert"}},
    {"team": "Крылья Советов", "league": "RPL", "attack": 69, "defense": 71, "control": 69, "form_index": 67,
     "efficiency": 65, "mentality": 67, "home_rating": 74, "away_rating": 64,
     "coach_factor": 71, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.0, "source": "expert"}},
     "avg_goals": {"value": 0.9, "source": "expert"},
     "avg_goals_conceded": {"value": 1.4, "source": "expert"},
     "avg_possession": {"value": 46, "source": "expert"}},
    {"team": "Динамо Мх", "league": "RPL", "attack": 68, "defense": 70, "control": 68, "form_index": 70,
     "efficiency": 64, "mentality": 66, "home_rating": 72, "away_rating": 63,
     "coach_factor": 70, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 0.9, "source": "expert"}},
     "avg_goals": {"value": 0.8, "source": "expert"},
     "avg_goals_conceded": {"value": 1.5, "source": "expert"},
     "avg_possession": {"value": 45, "source": "expert"}},
    {"team": "Родина", "league": "RPL", "attack": 67, "defense": 69, "control": 67, "form_index": 68,
     "efficiency": 63, "mentality": 65, "home_rating": 70, "away_rating": 61,
     "coach_factor": 69, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 0.8, "source": "expert"}},
     "avg_goals": {"value": 0.7, "source": "expert"},
     "avg_goals_conceded": {"value": 1.6, "source": "expert"},
     "avg_possession": {"value": 44, "source": "expert"}},
]

async def cmd_load_passports(message: types.Message):
    # Проверка, что это админ (по chat_id из конфига)
    from app.config import Config
    if str(message.from_user.id) != Config.ADMIN_CHAT_ID:
        await message.answer("⛔ Только для администратора.", reply_markup=get_main_keyboard())
        return

    await message.answer("⏳ Загружаю паспорта РПЛ...", reply_markup=get_main_keyboard())
    count = 0
    for data in EXPERT_PASSPORTS:
        team = data["team"]
        passport = {
            "team": team,
            "league": data["league"],
            "attack": data["attack"],
            "defense": data["defense"],
            "control": data["control"],
            "form_index": data["form_index"],
            "efficiency": data["efficiency"],
            "mentality": data["mentality"],
            "home_rating": data["home_rating"],
            "away_rating": data["away_rating"],
            "coach_factor": data["coach_factor"],
            "injury_index": data["injury_index"],
            "fatigue_index": data["fatigue_index"],
            "xg": data["xg"],
            "avg_goals": data["avg_goals"],
            "avg_goals_conceded": data["avg_goals_conceded"],
            "avg_possession": data["avg_possession"],
        }
        save_passport(team, passport)
        count += 1
        logger.info(f"Загружен паспорт {team}")

    # Загружаем алиасы
    init_default_aliases()

    await message.answer(f"✅ Загружено {count} паспортов команд РПЛ.\nАлиасы (синонимы) добавлены.", reply_markup=get_main_keyboard())

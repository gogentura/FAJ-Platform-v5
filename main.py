#!/usr/bin/env python3
import os
import asyncio
import logging
from dotenv import load_dotenv
from app.bot import run_bot
from app.core.faj_core import FAJCore
from app.journal import Journal
from app.database import get_db, init_db
from app.passport_manager import save_passport, init_default_aliases

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FAJ")

# Данные паспортов команд РПЛ (актуальны на 24.07.2026)
INITIAL_PASSPORTS = [
    {"team": "Зенит", "league": "RPL", "attack": 88, "defense": 79, "control": 84, "form_index": 84,
     "efficiency": 78, "mentality": 85, "home_rating": 93, "away_rating": 87,
     "coach_factor": 86, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.8, "source": "expert"}},
     "avg_goals": {"value": 2.0, "source": "expert"},
     "avg_goals_conceded": {"value": 0.8, "source": "expert"},
     "avg_possession": {"value": 60, "source": "expert"},
     "extra": {"tempo": 76, "press": 80, "transition": 75, "tactical": 82, "depth": 85, "transfer": 91, "uncertainty": 16, "faj_rating": 91.8}
    },
    {"team": "Краснодар", "league": "RPL", "attack": 80, "defense": 77, "control": 81, "form_index": 79,
     "efficiency": 76, "mentality": 79, "home_rating": 86, "away_rating": 79,
     "coach_factor": 82, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.6, "source": "expert"}},
     "avg_goals": {"value": 1.7, "source": "expert"},
     "avg_goals_conceded": {"value": 0.9, "source": "expert"},
     "avg_possession": {"value": 57, "source": "expert"},
     "extra": {"tempo": 74, "press": 78, "transition": 73, "tactical": 79, "depth": 82, "transfer": 88, "uncertainty": 22, "faj_rating": 89.9}
    },
    {"team": "Локомотив", "league": "RPL", "attack": 81, "defense": 78, "control": 82, "form_index": 87,
     "efficiency": 77, "mentality": 81, "home_rating": 87, "away_rating": 80,
     "coach_factor": 84, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.7, "source": "expert"}},
     "avg_goals": {"value": 1.8, "source": "expert"},
     "avg_goals_conceded": {"value": 0.8, "source": "expert"},
     "avg_possession": {"value": 58, "source": "expert"},
     "extra": {"tempo": 78, "press": 76, "transition": 74, "tactical": 80, "depth": 83, "transfer": 86, "uncertainty": 20, "faj_rating": 90.2}
    },
    {"team": "Динамо М", "league": "RPL", "attack": 80, "defense": 78, "control": 80, "form_index": 81,
     "efficiency": 75, "mentality": 78, "home_rating": 88, "away_rating": 79,
     "coach_factor": 81, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.6, "source": "expert"}},
     "avg_goals": {"value": 1.7, "source": "expert"},
     "avg_goals_conceded": {"value": 0.9, "source": "expert"},
     "avg_possession": {"value": 56, "source": "expert"},
     "extra": {"tempo": 75, "press": 77, "transition": 72, "tactical": 78, "depth": 80, "transfer": 84, "uncertainty": 24, "faj_rating": 88.9}
    },
    {"team": "Спартак", "league": "RPL", "attack": 80, "defense": 76, "control": 78, "form_index": 76,
     "efficiency": 74, "mentality": 77, "home_rating": 84, "away_rating": 74,
     "coach_factor": 82, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.5, "source": "expert"}},
     "avg_goals": {"value": 1.6, "source": "expert"},
     "avg_goals_conceded": {"value": 1.0, "source": "expert"},
     "avg_possession": {"value": 54, "source": "expert"},
     "extra": {"tempo": 82, "press": 73, "transition": 70, "tactical": 77, "depth": 78, "transfer": 82, "uncertainty": 32, "faj_rating": 86.8}
    },
    {"team": "ЦСКА", "league": "RPL", "attack": 78, "defense": 80, "control": 79, "form_index": 79,
     "efficiency": 73, "mentality": 76, "home_rating": 85, "away_rating": 76,
     "coach_factor": 79, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.5, "source": "expert"}},
     "avg_goals": {"value": 1.5, "source": "expert"},
     "avg_goals_conceded": {"value": 0.9, "source": "expert"},
     "avg_possession": {"value": 55, "source": "expert"},
     "extra": {"tempo": 74, "press": 75, "transition": 71, "tactical": 76, "depth": 80, "transfer": 80, "uncertainty": 26, "faj_rating": 86.9}
    },
    {"team": "Ахмат", "league": "RPL", "attack": 76, "defense": 75, "control": 77, "form_index": 78,
     "efficiency": 72, "mentality": 75, "home_rating": 80, "away_rating": 72,
     "coach_factor": 78, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.4, "source": "expert"}},
     "avg_goals": {"value": 1.4, "source": "expert"},
     "avg_goals_conceded": {"value": 1.1, "source": "expert"},
     "avg_possession": {"value": 53, "source": "expert"},
     "extra": {"tempo": 73, "press": 74, "transition": 70, "tactical": 75, "depth": 78, "transfer": 79, "uncertainty": 28, "faj_rating": 87.1}
    },
    {"team": "Рубин", "league": "RPL", "attack": 75, "defense": 76, "control": 76, "form_index": 71,
     "efficiency": 71, "mentality": 74, "home_rating": 81, "away_rating": 73,
     "coach_factor": 77, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.3, "source": "expert"}},
     "avg_goals": {"value": 1.3, "source": "expert"},
     "avg_goals_conceded": {"value": 1.1, "source": "expert"},
     "avg_possession": {"value": 52, "source": "expert"},
     "extra": {"tempo": 75, "press": 73, "transition": 69, "tactical": 74, "depth": 76, "transfer": 77, "uncertainty": 30, "faj_rating": 85.2}
    },
    {"team": "Ростов", "league": "RPL", "attack": 74, "defense": 74, "control": 74, "form_index": 74,
     "efficiency": 70, "mentality": 73, "home_rating": 79, "away_rating": 70,
     "coach_factor": 76, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.3, "source": "expert"}},
     "avg_goals": {"value": 1.2, "source": "expert"},
     "avg_goals_conceded": {"value": 1.2, "source": "expert"},
     "avg_possession": {"value": 51, "source": "expert"},
     "extra": {"tempo": 72, "press": 72, "transition": 68, "tactical": 73, "depth": 75, "transfer": 76, "uncertainty": 28, "faj_rating": 84.3}
    },
    {"team": "Балтика", "league": "RPL", "attack": 71, "defense": 72, "control": 72, "form_index": 76,
     "efficiency": 68, "mentality": 70, "home_rating": 78, "away_rating": 67,
     "coach_factor": 74, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.2, "source": "expert"}},
     "avg_goals": {"value": 1.1, "source": "expert"},
     "avg_goals_conceded": {"value": 1.3, "source": "expert"},
     "avg_possession": {"value": 49, "source": "expert"},
     "extra": {"tempo": 70, "press": 71, "transition": 67, "tactical": 70, "depth": 73, "transfer": 75, "uncertainty": 26, "faj_rating": 84.9}
    },
    {"team": "Акрон", "league": "RPL", "attack": 70, "defense": 71, "control": 71, "form_index": 75,
     "efficiency": 67, "mentality": 69, "home_rating": 76, "away_rating": 66,
     "coach_factor": 73, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.1, "source": "expert"}},
     "avg_goals": {"value": 1.0, "source": "expert"},
     "avg_goals_conceded": {"value": 1.3, "source": "expert"},
     "avg_possession": {"value": 48, "source": "expert"},
     "extra": {"tempo": 69, "press": 70, "transition": 66, "tactical": 69, "depth": 72, "transfer": 74, "uncertainty": 30, "faj_rating": 84.8}
    },
    {"team": "Оренбург", "league": "RPL", "attack": 72, "defense": 73, "control": 73, "form_index": 70,
     "efficiency": 68, "mentality": 71, "home_rating": 77, "away_rating": 68,
     "coach_factor": 74, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.2, "source": "expert"}},
     "avg_goals": {"value": 1.2, "source": "expert"},
     "avg_goals_conceded": {"value": 1.2, "source": "expert"},
     "avg_possession": {"value": 50, "source": "expert"},
     "extra": {"tempo": 71, "press": 70, "transition": 67, "tactical": 71, "depth": 73, "transfer": 75, "uncertainty": 32, "faj_rating": 83.8}
    },
    {"team": "Факел", "league": "RPL", "attack": 70, "defense": 72, "control": 70, "form_index": 68,
     "efficiency": 66, "mentality": 68, "home_rating": 76, "away_rating": 65,
     "coach_factor": 72, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.0, "source": "expert"}},
     "avg_goals": {"value": 0.9, "source": "expert"},
     "avg_goals_conceded": {"value": 1.4, "source": "expert"},
     "avg_possession": {"value": 47, "source": "expert"},
     "extra": {"tempo": 68, "press": 69, "transition": 65, "tactical": 68, "depth": 71, "transfer": 72, "uncertainty": 34, "faj_rating": 83.3}
    },
    {"team": "Крылья Советов", "league": "RPL", "attack": 69, "defense": 71, "control": 69, "form_index": 67,
     "efficiency": 65, "mentality": 67, "home_rating": 74, "away_rating": 64,
     "coach_factor": 71, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 1.0, "source": "expert"}},
     "avg_goals": {"value": 0.9, "source": "expert"},
     "avg_goals_conceded": {"value": 1.4, "source": "expert"},
     "avg_possession": {"value": 46, "source": "expert"},
     "extra": {"tempo": 69, "press": 68, "transition": 64, "tactical": 67, "depth": 70, "transfer": 71, "uncertainty": 36, "faj_rating": 81.9}
    },
    {"team": "Динамо Мх", "league": "RPL", "attack": 68, "defense": 70, "control": 68, "form_index": 70,
     "efficiency": 64, "mentality": 66, "home_rating": 72, "away_rating": 63,
     "coach_factor": 70, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 0.9, "source": "expert"}},
     "avg_goals": {"value": 0.8, "source": "expert"},
     "avg_goals_conceded": {"value": 1.5, "source": "expert"},
     "avg_possession": {"value": 45, "source": "expert"},
     "extra": {"tempo": 67, "press": 67, "transition": 63, "tactical": 66, "depth": 69, "transfer": 70, "uncertainty": 32, "faj_rating": 82.8}
    },
    {"team": "Родина", "league": "RPL", "attack": 67, "defense": 69, "control": 67, "form_index": 68,
     "efficiency": 63, "mentality": 65, "home_rating": 70, "away_rating": 61,
     "coach_factor": 69, "injury_index": 0, "fatigue_index": 0,
     "xg": {"historical": {"value": 0.8, "source": "expert"}},
     "avg_goals": {"value": 0.7, "source": "expert"},
     "avg_goals_conceded": {"value": 1.6, "source": "expert"},
     "avg_possession": {"value": 44, "source": "expert"},
     "extra": {"tempo": 66, "press": 66, "transition": 62, "tactical": 65, "depth": 68, "transfer": 69, "uncertainty": 38, "faj_rating": 82.0}
    }
]

def load_initial_passports():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM passports").fetchone()[0]
    conn.close()
    if count > 0:
        logger.info("Паспорта уже загружены (пропускаем инициализацию)")
        return

    logger.info("Загрузка начальных паспортов РПЛ...")
    for data in INITIAL_PASSPORTS:
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
            "extra": data.get("extra", {})
        }
        save_passport(team, passport)
        logger.info(f"✅ Загружен паспорт {team}")
    logger.info("Загрузка завершена.")

async def main():
    init_db()
    init_default_aliases()
    load_initial_passports()
    logger.info("База данных инициализирована")
    core = FAJCore()
    journal = Journal()
    logger.info("Запуск FAJ Platform v5.1")
    await run_bot(core, journal)

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Passport Core — РПЛ 2026/27
FAJ Expert Initial Knowledge Pack v1.0
"""

from .passport_schema import (
    FAJ_PASSPORT_VERSION,
    FAJ_ENGINE_VERSION,
    PASSPORT_AUTHOR,
    PASSPORT_CREATED,
    validate_passport
)

TEAM_ALIASES = {
    "Динамо М": "Динамо Москва",
    "Динамо Мх": "Динамо Махачкала",
    "Динамо (М)": "Динамо Москва",
    "Динамо (Мх)": "Динамо Махачкала",
    "ЦСКА М": "ЦСКА",
    "Спартак М": "Спартак",
    "Локомотив М": "Локомотив",
    "Зенит (СПб)": "Зенит",
    "Краснодар (Кр)": "Краснодар",
    "Ростов (РнД)": "Ростов",
    "Крылья Советов (С)": "Крылья Советов",
    "Крылья": "Крылья Советов",
    "Ахмат (Гр)": "Ахмат",
    "Рубин (Кз)": "Рубин",
    "Факел (Вр)": "Факел",
    "Оренбург (Ор)": "Оренбург",
    "Балтика (Кл)": "Балтика",
    "Акрон (Тл)": "Акрон",
    "Родина (М)": "Родина"
}


def normalize_team_name(name):
    return TEAM_ALIASES.get(name, name)


RPL_PASSPORTS_2026_27 = {
    "Зенит": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 88, "defense": 84, "control": 90,
            "press": 78, "tempo": 72, "transition": 82,
            "finishing": 86, "goalkeeper": 84,
            "coach_factor": 85, "squad_quality": 90,
            "bench_quality": 88, "home_advantage": 1.05
        },
        "IDENTITY": {
            "style": "possession",
            "tempo_style": "medium",
            "pressing": "high",
            "risk": "medium"
        },
        "EXPERT": {
            "dna": "Чемпионский класс",
            "class": "Чемпионский претендент",
            "strengths": {"possession": 90, "individual_quality": 88, "mental": 85, "depth": 82},
            "weaknesses": {"leader_dependence": 75, "transition_speed": 70}
        },
        "DYNAMIC_INITIAL": {
            "form": 80, "fitness": 85, "morale": 85,
            "fatigue": 15, "injury_index": 0, "passport_confidence": 0.85
        }
    },
    "Спартак": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 86, "defense": 78, "control": 82,
            "press": 80, "tempo": 84, "transition": 85,
            "finishing": 84, "goalkeeper": 80,
            "coach_factor": 82, "squad_quality": 84,
            "bench_quality": 80, "home_advantage": 1.08
        },
        "IDENTITY": {
            "style": "direct",
            "tempo_style": "high",
            "pressing": "medium",
            "risk": "high"
        },
        "EXPERT": {
            "dna": "Эмоциональная атака",
            "class": "Большая команда",
            "strengths": {"individuality": 85, "emotions": 82, "home_factor": 80},
            "weaknesses": {"stability": 65, "defensive_errors": 60}
        },
        "DYNAMIC_INITIAL": {
            "form": 78, "fitness": 82, "morale": 80,
            "fatigue": 18, "injury_index": 0, "passport_confidence": 0.80
        }
    },
    "ЦСКА": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 82, "defense": 86, "control": 84,
            "press": 82, "tempo": 74, "transition": 84,
            "finishing": 82, "goalkeeper": 85,
            "coach_factor": 86, "squad_quality": 82,
            "bench_quality": 78, "home_advantage": 1.03
        },
        "IDENTITY": {
            "style": "organized",
            "tempo_style": "medium",
            "pressing": "medium",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Дисциплина и результат",
            "class": "Команда результата",
            "strengths": {"discipline": 88, "structure": 85, "character": 84},
            "weaknesses": {"low_block_creation": 65}
        },
        "DYNAMIC_INITIAL": {
            "form": 76, "fitness": 80, "morale": 78,
            "fatigue": 20, "injury_index": 0, "passport_confidence": 0.82
        }
    },
    "Динамо Москва": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 85, "defense": 80, "control": 84,
            "press": 86, "tempo": 88, "transition": 82,
            "finishing": 82, "goalkeeper": 80,
            "coach_factor": 82, "squad_quality": 82,
            "bench_quality": 80, "home_advantage": 1.04
        },
        "IDENTITY": {
            "style": "high_press",
            "tempo_style": "high",
            "pressing": "high",
            "risk": "medium"
        },
        "EXPERT": {
            "dna": "Темп и интенсивность",
            "class": "Команда темпа",
            "strengths": {"speed": 85, "flanks": 82, "intensity": 84},
            "weaknesses": {"space_behind": 68}
        },
        "DYNAMIC_INITIAL": {
            "form": 75, "fitness": 78, "morale": 76,
            "fatigue": 22, "injury_index": 0, "passport_confidence": 0.78
        }
    },
    "Локомотив": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 84, "defense": 78, "control": 80,
            "press": 80, "tempo": 86, "transition": 84,
            "finishing": 82, "goalkeeper": 78,
            "coach_factor": 80, "squad_quality": 80,
            "bench_quality": 78, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "direct",
            "tempo_style": "high",
            "pressing": "medium",
            "risk": "high"
        },
        "EXPERT": {
            "dna": "Молодость и скорость",
            "class": "Команда развития",
            "strengths": {"speed": 84, "transitions": 82, "energy": 80},
            "weaknesses": {"experience": 60}
        },
        "DYNAMIC_INITIAL": {
            "form": 74, "fitness": 76, "morale": 74,
            "fatigue": 20, "injury_index": 0, "passport_confidence": 0.76
        }
    },
    "Краснодар": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 84, "defense": 85, "control": 88,
            "press": 82, "tempo": 74, "transition": 80,
            "finishing": 84, "goalkeeper": 82,
            "coach_factor": 86, "squad_quality": 84,
            "bench_quality": 82, "home_advantage": 1.04
        },
        "IDENTITY": {
            "style": "possession",
            "tempo_style": "medium",
            "pressing": "medium",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Система и структура",
            "class": "Самая системная команда",
            "strengths": {"structure": 88, "organization": 86, "stability": 84},
            "weaknesses": {"aggression": 70}
        },
        "DYNAMIC_INITIAL": {
            "form": 77, "fitness": 80, "morale": 78,
            "fatigue": 18, "injury_index": 0, "passport_confidence": 0.82
        }
    },
    "Ростов": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 76, "defense": 78, "control": 74,
            "press": 76, "tempo": 70, "transition": 74,
            "finishing": 74, "goalkeeper": 76,
            "coach_factor": 80, "squad_quality": 74,
            "bench_quality": 70, "home_advantage": 1.06
        },
        "IDENTITY": {
            "style": "organized",
            "tempo_style": "low",
            "pressing": "medium",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Характер и борьба",
            "class": "Команда-сюрприз",
            "strengths": {"character": 84, "home_factor": 82},
            "weaknesses": {"squad_quality": 65}
        },
        "DYNAMIC_INITIAL": {
            "form": 72, "fitness": 74, "morale": 76,
            "fatigue": 22, "injury_index": 0, "passport_confidence": 0.72
        }
    },
    "Ахмат": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 74, "defense": 80, "control": 70,
            "press": 78, "tempo": 72, "transition": 72,
            "finishing": 72, "goalkeeper": 78,
            "coach_factor": 76, "squad_quality": 72,
            "bench_quality": 68, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "physical",
            "tempo_style": "medium",
            "pressing": "high",
            "risk": "medium"
        },
        "EXPERT": {
            "dna": "Мощь и единоборства",
            "class": "Сложный соперник",
            "strengths": {"physical": 84, "duels": 82},
            "weaknesses": {"creation": 62}
        },
        "DYNAMIC_INITIAL": {
            "form": 70, "fitness": 72, "morale": 74,
            "fatigue": 24, "injury_index": 0, "passport_confidence": 0.70
        }
    },
    "Рубин": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 72, "defense": 80, "control": 74,
            "press": 72, "tempo": 68, "transition": 72,
            "finishing": 72, "goalkeeper": 78,
            "coach_factor": 78, "squad_quality": 72,
            "bench_quality": 68, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "organized",
            "tempo_style": "low",
            "pressing": "medium",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Рациональность и дисциплина",
            "class": "Рациональная команда",
            "strengths": {"organization": 80, "discipline": 78},
            "weaknesses": {"creativity": 62}
        },
        "DYNAMIC_INITIAL": {
            "form": 68, "fitness": 70, "morale": 72,
            "fatigue": 24, "injury_index": 0, "passport_confidence": 0.68
        }
    },
    "Крылья Советов": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 76, "defense": 70, "control": 70,
            "press": 76, "tempo": 84, "transition": 78,
            "finishing": 74, "goalkeeper": 72,
            "coach_factor": 74, "squad_quality": 70,
            "bench_quality": 66, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "direct",
            "tempo_style": "high",
            "pressing": "medium",
            "risk": "high"
        },
        "EXPERT": {
            "dna": "Скорость и энергия",
            "class": "Команда скорости",
            "strengths": {"transitions": 80, "energy": 78},
            "weaknesses": {"stability": 60}
        },
        "DYNAMIC_INITIAL": {
            "form": 66, "fitness": 68, "morale": 70,
            "fatigue": 26, "injury_index": 0, "passport_confidence": 0.66
        }
    },
    "Факел": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 64, "defense": 74, "control": 64,
            "press": 70, "tempo": 62, "transition": 64,
            "finishing": 62, "goalkeeper": 72,
            "coach_factor": 72, "squad_quality": 64,
            "bench_quality": 60, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "defensive",
            "tempo_style": "low",
            "pressing": "low",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Оборона и борьба",
            "class": "Оборонительная команда",
            "strengths": {"fighting": 74, "discipline": 72},
            "weaknesses": {"attack": 55}
        },
        "DYNAMIC_INITIAL": {
            "form": 62, "fitness": 64, "morale": 68,
            "fatigue": 28, "injury_index": 0, "passport_confidence": 0.62
        }
    },
    "Оренбург": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 76, "defense": 64, "control": 70,
            "press": 74, "tempo": 80, "transition": 74,
            "finishing": 72, "goalkeeper": 68,
            "coach_factor": 72, "squad_quality": 68,
            "bench_quality": 64, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "direct",
            "tempo_style": "high",
            "pressing": "medium",
            "risk": "high"
        },
        "EXPERT": {
            "dna": "Смелость и атака",
            "class": "Атакующий новичок",
            "strengths": {"attack": 78, "courage": 76},
            "weaknesses": {"defense": 58}
        },
        "DYNAMIC_INITIAL": {
            "form": 64, "fitness": 66, "morale": 68,
            "fatigue": 26, "injury_index": 0, "passport_confidence": 0.64
        }
    },
    "Балтика": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 68, "defense": 76, "control": 70,
            "press": 72, "tempo": 66, "transition": 68,
            "finishing": 66, "goalkeeper": 74,
            "coach_factor": 74, "squad_quality": 68,
            "bench_quality": 64, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "organized",
            "tempo_style": "low",
            "pressing": "medium",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Структура и дисциплина",
            "class": "Организованная команда",
            "strengths": {"structure": 76, "discipline": 74},
            "weaknesses": {"attack": 60}
        },
        "DYNAMIC_INITIAL": {
            "form": 64, "fitness": 66, "morale": 68,
            "fatigue": 26, "injury_index": 0, "passport_confidence": 0.64
        }
    },
    "Акрон": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 64, "defense": 68, "control": 62,
            "press": 70, "tempo": 72, "transition": 66,
            "finishing": 62, "goalkeeper": 66,
            "coach_factor": 68, "squad_quality": 62,
            "bench_quality": 58, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "direct",
            "tempo_style": "medium",
            "pressing": "medium",
            "risk": "medium"
        },
        "EXPERT": {
            "dna": "Энергия новичка",
            "class": "Новичок с энергией",
            "strengths": {"motivation": 78},
            "weaknesses": {"depth": 55}
        },
        "DYNAMIC_INITIAL": {
            "form": 60, "fitness": 62, "morale": 72,
            "fatigue": 30, "injury_index": 0, "passport_confidence": 0.60
        }
    },
    "Динамо Махачкала": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 64, "defense": 76, "control": 66,
            "press": 70, "tempo": 62, "transition": 64,
            "finishing": 62, "goalkeeper": 72,
            "coach_factor": 72, "squad_quality": 64,
            "bench_quality": 60, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "defensive",
            "tempo_style": "low",
            "pressing": "medium",
            "risk": "low"
        },
        "EXPERT": {
            "dna": "Оборона и характер",
            "class": "Оборонительная команда",
            "strengths": {"organization": 74},
            "weaknesses": {"attack": 58}
        },
        "DYNAMIC_INITIAL": {
            "form": 60, "fitness": 62, "morale": 68,
            "fatigue": 28, "injury_index": 0, "passport_confidence": 0.60
        }
    },
    "Родина": {
        "version": FAJ_PASSPORT_VERSION,
        "created": PASSPORT_CREATED,
        "author": PASSPORT_AUTHOR,
        "BASE": {
            "attack": 62, "defense": 66, "control": 64,
            "press": 68, "tempo": 74, "transition": 64,
            "finishing": 60, "goalkeeper": 64,
            "coach_factor": 66, "squad_quality": 60,
            "bench_quality": 56, "home_advantage": 1.02
        },
        "IDENTITY": {
            "style": "direct",
            "tempo_style": "medium",
            "pressing": "medium",
            "risk": "medium"
        },
        "EXPERT": {
            "dna": "Потенциал и молодость",
            "class": "Команда развития",
            "strengths": {"potential": 76},
            "weaknesses": {"experience": 52}
        },
        "DYNAMIC_INITIAL": {
            "form": 58, "fitness": 60, "morale": 66,
            "fatigue": 30, "injury_index": 0, "passport_confidence": 0.58
        }
    }
}


if __name__ == "__main__":
    print("🔍 Валидация паспортов РПЛ 2026/27...")
    all_valid = True
    for team_name, passport in RPL_PASSPORTS_2026_27.items():
        if not validate_passport(passport, team_name):
            all_valid = False
    if all_valid:
        print("✅ Все паспорта РПЛ 2026/27 валидны")
    else:
        print("❌ Обнаружены ошибки в паспортах")

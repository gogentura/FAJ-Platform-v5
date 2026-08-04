#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Passport Schema v1.0
Определяет обязательную структуру паспорта команды
"""

from typing import Dict, Any

FAJ_PASSPORT_VERSION = "RPL-2026-27-v1.0"
FAJ_ENGINE_VERSION = "10.0"
PASSPORT_AUTHOR = "FAJ Expert Layer"
PASSPORT_CREATED = "2026-07-01"

PASSPORT_SCHEMA = {
    "version": str,
    "created": str,
    "author": str,
    "BASE": {
        "attack": (int, float),
        "defense": (int, float),
        "control": (int, float),
        "press": (int, float),
        "tempo": (int, float),
        "transition": (int, float),
        "finishing": (int, float),
        "goalkeeper": (int, float),
        "coach_factor": (int, float),
        "squad_quality": (int, float),
        "bench_quality": (int, float),
        "home_advantage": (int, float)
    },
    "IDENTITY": {
        "style": str,
        "tempo_style": str,
        "pressing": str,
        "risk": str
    },
    "EXPERT": {
        "dna": str,
        "class": str,
        "strengths": dict,
        "weaknesses": dict
    },
    "DYNAMIC_INITIAL": {
        "form": (int, float),
        "fitness": (int, float),
        "morale": (int, float),
        "fatigue": (int, float),
        "injury_index": int,
        "passport_confidence": (int, float)
    }
}


def validate_passport(passport: Dict[str, Any], team_name: str) -> bool:
    try:
        for section in ["BASE", "IDENTITY", "EXPERT", "DYNAMIC_INITIAL"]:
            if section not in passport:
                print(f"❌ {team_name}: отсутствует секция {section}")
                return False

        for field, field_type in PASSPORT_SCHEMA["BASE"].items():
            if field not in passport["BASE"]:
                print(f"❌ {team_name}: отсутствует BASE.{field}")
                return False
            if not isinstance(passport["BASE"][field], field_type):
                print(f"❌ {team_name}: BASE.{field} должен быть {field_type}")
                return False

        for field in PASSPORT_SCHEMA["IDENTITY"].keys():
            if field not in passport["IDENTITY"]:
                print(f"❌ {team_name}: отсутствует IDENTITY.{field}")
                return False

        if "strengths" not in passport["EXPERT"] or not isinstance(passport["EXPERT"]["strengths"], dict):
            print(f"❌ {team_name}: EXPERT.strengths должен быть объектом (dict)")
            return False
        if "weaknesses" not in passport["EXPERT"] or not isinstance(passport["EXPERT"]["weaknesses"], dict):
            print(f"❌ {team_name}: EXPERT.weaknesses должен быть объектом (dict)")
            return False

        for field in PASSPORT_SCHEMA["DYNAMIC_INITIAL"].keys():
            if field not in passport["DYNAMIC_INITIAL"]:
                print(f"❌ {team_name}: отсутствует DYNAMIC_INITIAL.{field}")
                return False

        print(f"✅ {team_name}: паспорт валиден")
        return True

    except Exception as e:
        print(f"❌ {team_name}: ошибка валидации - {e}")
        return False

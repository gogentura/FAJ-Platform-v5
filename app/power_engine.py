#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Power Engine v2.0
Рассчитывает полный профиль команды: Attack, Defense, Control, Keeper

Вход: team_id, season_id
Выход: {
    "attack_power": float,
    "defense_power": float,
    "control_power": float,
    "goalkeeper_power": float,
    "passport_confidence": float,
    "model_confidence": float,
    "explanation": {...},
    "components": {...}
}
"""

from app.database import FAJDatabase
from app.style_matrix import STYLE_MATRIX, get_style_bonus_vector
import json
import math


class PowerEngine:
    """
    Движок расчёта профиля команды
    """

    def __init__(self):
        self.db = FAJDatabase()
        self._load_weights()

    # ============================================================
    # ЗАГРУЗКА ВЕСОВ ИЗ БД
    # ============================================================

    def _load_weights(self):
        """Загружает веса из model_parameters или использует значения по умолчанию"""
        default = {
            "base_weights": {
                "attack": {"attack": 0.50, "transition": 0.25, "finishing": 0.25},
                "defense": {"defense": 0.50, "transition": 0.20, "goalkeeper": 0.30},
                "control": {"control": 0.60, "press": 0.40},
                "goalkeeper": {"goalkeeper": 1.0},
            },
            "synergy_threshold": 80,
            "synergy_bonus": 0.7,
            "dynamic_weights": {
                "form": {"attack": 0.40, "defense": 0.20, "control": 0.30, "keeper": 0.10},
                "fitness": {"attack": 0.25, "defense": 0.30, "control": 0.25, "keeper": 0.20},
                "morale": {"attack": 0.30, "defense": 0.20, "control": 0.30, "keeper": 0.20},
                "fatigue": {"attack": 0.20, "defense": 0.35, "control": 0.25, "keeper": 0.20},
            },
            "home_advantage": {
                "attack": 0.04,
                "defense": 0.02,
                "control": 0.03,
                "keeper": 0.01,
            },
            "learning_weight": 0.30,
            "learning_window": 5,
            "expert_weights": {
                "champion_dna": 0.10,
                "big_match": 0.08,
                "comeback": 0.05,
                "discipline": 0.08,
                "pressure": 0.06,
            },
            "model_confidence_weight": 0.50,
        }

        try:
            params = self.db.get_model_parameters(model_version="power_engine")
            if params:
                for p in params:
                    if p['parameter'] == 'config':
                        loaded = json.loads(p['value'])
                        self.base_weights = loaded.get("base_weights", default["base_weights"])
                        self.synergy_threshold = loaded.get("synergy_threshold", default["synergy_threshold"])
                        self.synergy_bonus = loaded.get("synergy_bonus", default["synergy_bonus"])
                        self.dynamic_weights = loaded.get("dynamic_weights", default["dynamic_weights"])
                        self.home_advantage = loaded.get("home_advantage", default["home_advantage"])
                        self.learning_weight = loaded.get("learning_weight", default["learning_weight"])
                        self.learning_window = loaded.get("learning_window", default["learning_window"])
                        self.expert_weights = loaded.get("expert_weights", default["expert_weights"])
                        self.model_confidence_weight = loaded.get("model_confidence_weight", default["model_confidence_weight"])
                        return
        except:
            pass

        self.base_weights = default["base_weights"]
        self.synergy_threshold = default["synergy_threshold"]
        self.synergy_bonus = default["synergy_bonus"]
        self.dynamic_weights = default["dynamic_weights"]
        self.home_advantage = default["home_advantage"]
        self.learning_weight = default["learning_weight"]
        self.learning_window = default["learning_window"]
        self.expert_weights = default["expert_weights"]
        self.model_confidence_weight = default["model_confidence_weight"]

    # ============================================================
    # ОСНОВНОЙ МЕТОД
    # ============================================================

    def calculate(self, team_id: int, season_id: int) -> dict:
        """
        Рассчитывает полный профиль команды
        """
        explanation = {
            "base": {},
            "synergy": {},
            "dynamic": {},
            "identity": {},
            "expert": {},
            "learning": {},
            "home": {},
            "final": {},
        }
        components = {}

        # 1. Получаем паспортные данные
        base = self.db.get_base(team_id, season_id)
        identity = self.db.get_identity(team_id, season_id)
        dynamic = self.db.get_dynamic(team_id, season_id)
        meta = self._get_passport_meta(team_id, season_id)

        if not base or not identity:
            return {"error": "Паспорт команды не найден"}

        # 2. CONFIDENCE
        passport_confidence = dynamic.get("passport_confidence", 0.7)
        model_confidence = self._calculate_model_confidence(team_id)

        # 3. БАЗОВЫЕ ПОКАЗАТЕЛИ
        attack_base = self._calculate_attack(base)
        defense_base = self._calculate_defense(base)
        control_base = self._calculate_control(base)
        keeper_base = self._calculate_goalkeeper(base)

        explanation["base"] = {
            "attack": attack_base,
            "defense": defense_base,
            "control": control_base,
            "goalkeeper": keeper_base,
        }

        # 4. СИНЕРГИЯ (НЕЛИНЕЙНЫЕ ЭФФЕКТЫ)
        synergy_bonus = self._calculate_synergy(base)
        explanation["synergy"] = synergy_bonus

        # 5. ДИНАМИКА
        dynamic_corr = self._calculate_dynamic(dynamic)
        explanation["dynamic"] = dynamic_corr

        # 6. СТИЛЬ (ПОКОМПОНЕНТНО)
        identity_corr = self._calculate_identity(identity)
        explanation["identity"] = identity_corr

        # 7. ЭКСПЕРТ (ПОКОМПОНЕНТНО)
        expert_corr = self._calculate_expert(meta)
        explanation["expert"] = expert_corr

        # 8. ОБУЧЕНИЕ (ПОКОМПОНЕНТНО)
        learning_corr = self._calculate_learning(team_id, season_id)
        explanation["learning"] = learning_corr

        # 9. ДОМАШНЕЕ ПРЕИМУЩЕСТВО
        home_corr = self._calculate_home()
        explanation["home"] = home_corr

        # 10. ИТОГОВЫЕ ПОКАЗАТЕЛИ (С УЧЁТОМ CONFIDENCE)
        confidence = passport_confidence * (0.5 + 0.5 * model_confidence)

        attack_final = (
            attack_base
            + synergy_bonus["attack"]
            + confidence * (
                dynamic_corr["attack"]
                + identity_corr["attack"]
                + expert_corr["attack"]
                + learning_corr["attack"]
                + home_corr["attack"]
            )
        )
        defense_final = (
            defense_base
            + synergy_bonus["defense"]
            + confidence * (
                dynamic_corr["defense"]
                + identity_corr["defense"]
                + expert_corr["defense"]
                + learning_corr["defense"]
                + home_corr["defense"]
            )
        )
        control_final = (
            control_base
            + synergy_bonus["control"]
            + confidence * (
                dynamic_corr["control"]
                + identity_corr["control"]
                + expert_corr["control"]
                + learning_corr["control"]
                + home_corr["control"]
            )
        )
        keeper_final = (
            keeper_base
            + confidence * (
                dynamic_corr["keeper"]
                + identity_corr["keeper"]
                + expert_corr["keeper"]
                + learning_corr["keeper"]
                + home_corr["keeper"]
            )
        )

        explanation["final"] = {
            "attack": attack_final,
            "defense": defense_final,
            "control": control_final,
            "goalkeeper": keeper_final,
        }

        return {
            "attack_power": round(attack_final, 2),
            "defense_power": round(defense_final, 2),
            "control_power": round(control_final, 2),
            "goalkeeper_power": round(keeper_final, 2),
            "passport_confidence": round(passport_confidence, 3),
            "model_confidence": round(model_confidence, 3),
            "explanation": explanation,
            "components": {
                "base": base,
                "identity": identity,
                "dynamic": dynamic,
                "meta": meta,
            }
        }

    # ============================================================
    # BASE
    # ============================================================

    def _calculate_attack(self, base) -> float:
        attack = base.get("attack", 50)
        transition = base.get("transition", 50)
        finishing = base.get("finishing", 50)
        return (
            attack * self.base_weights["attack"]["attack"]
            + transition * self.base_weights["attack"]["transition"]
            + finishing * self.base_weights["attack"]["finishing"]
        )

    def _calculate_defense(self, base) -> float:
        defense = base.get("defense", 50)
        transition = base.get("transition", 50)
        goalkeeper = base.get("goalkeeper", 50)
        return (
            defense * self.base_weights["defense"]["defense"]
            + transition * self.base_weights["defense"]["transition"]
            + goalkeeper * self.base_weights["defense"]["goalkeeper"]
        )

    def _calculate_control(self, base) -> float:
        control = base.get("control", 50)
        press = base.get("press", 50)
        return (
            control * self.base_weights["control"]["control"]
            + press * self.base_weights["control"]["press"]
        )

    def _calculate_goalkeeper(self, base) -> float:
        return base.get("goalkeeper", 50)

    # ============================================================
    # SYNERGY (НЕЛИНЕЙНЫЕ ЭФФЕКТЫ)
    # ============================================================

    def _calculate_synergy(self, base) -> dict:
        attack = base.get("attack", 50)
        transition = base.get("transition", 50)
        threshold = self.synergy_threshold
        bonus = self.synergy_bonus

        result = {"attack": 0.0, "defense": 0.0, "control": 0.0, "keeper": 0.0}

        # attack + transition synergy
        if attack > threshold and transition > threshold:
            result["attack"] += bonus
            result["control"] += bonus * 0.5

        # defense + goalkeeper synergy
        defense = base.get("defense", 50)
        goalkeeper = base.get("goalkeeper", 50)
        if defense > threshold and goalkeeper > threshold:
            result["defense"] += bonus * 0.7
            result["keeper"] += bonus * 0.3

        # control + press synergy
        control = base.get("control", 50)
        press = base.get("press", 50)
        if control > threshold and press > threshold:
            result["control"] += bonus * 0.6
            result["defense"] += bonus * 0.4

        return result

    # ============================================================
    # DYNAMIC
    # ============================================================

    def _calculate_dynamic(self, dynamic) -> dict:
        form = (dynamic.get("form", 50) - 50) / 10
        fitness = (dynamic.get("fitness", 50) - 50) / 10
        morale = (dynamic.get("morale", 50) - 50) / 10
        fatigue = (dynamic.get("fatigue", 50) - 50) / 10

        return {
            "attack": (
                form * self.dynamic_weights["form"]["attack"]
                + fitness * self.dynamic_weights["fitness"]["attack"]
                + morale * self.dynamic_weights["morale"]["attack"]
                - fatigue * self.dynamic_weights["fatigue"]["attack"]
            ),
            "defense": (
                form * self.dynamic_weights["form"]["defense"]
                + fitness * self.dynamic_weights["fitness"]["defense"]
                + morale * self.dynamic_weights["morale"]["defense"]
                - fatigue * self.dynamic_weights["fatigue"]["defense"]
            ),
            "control": (
                form * self.dynamic_weights["form"]["control"]
                + fitness * self.dynamic_weights["fitness"]["control"]
                + morale * self.dynamic_weights["morale"]["control"]
                - fatigue * self.dynamic_weights["fatigue"]["control"]
            ),
            "keeper": (
                form * self.dynamic_weights["form"]["keeper"]
                + fitness * self.dynamic_weights["fitness"]["keeper"]
                + morale * self.dynamic_weights["morale"]["keeper"]
                - fatigue * self.dynamic_weights["fatigue"]["keeper"]
            ),
        }

    # ============================================================
    # IDENTITY
    # ============================================================

    def _calculate_identity(self, identity) -> dict:
        style = identity.get("style", "mixed")
        return get_style_bonus_vector(style)

    # ============================================================
    # EXPERT (С ВЕСАМИ ИЗ КОНФИГА)
    # ============================================================

    def _calculate_expert(self, meta) -> dict:
        result = {"attack": 0.0, "defense": 0.0, "control": 0.0, "keeper": 0.0}

        if not meta:
            return result

        expert = meta.get("expert", {})

        w = self.expert_weights
        result["attack"] += expert.get("champion_dna", 0.0) * w.get("champion_dna", 0.10)
        result["attack"] += expert.get("big_match", 0.0) * w.get("big_match", 0.08)

        result["defense"] += expert.get("discipline", 0.0) * w.get("discipline", 0.08)
        result["defense"] += expert.get("pressure", 0.0) * w.get("pressure", 0.06)

        result["control"] += expert.get("comeback", 0.0) * w.get("comeback", 0.05)
        result["control"] += expert.get("pressure", 0.0) * w.get("pressure", 0.05)

        result["keeper"] += expert.get("big_match", 0.0) * 0.04

        return result

    # ============================================================
    # LEARNING (НЕЗАВИСИМО)
    # ============================================================

    def _calculate_learning(self, team_id: int, season_id: int) -> dict:
        result = {"attack": 0.0, "defense": 0.0, "control": 0.0, "keeper": 0.0}

        # Получаем последние N записей из learning_records
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT error_xg, error_score, cause_type
            FROM learning_records
            WHERE gold_id IN (
                SELECT id FROM gold_dataset
                WHERE match_id IN (
                    SELECT id FROM matches
                    WHERE home_team_id = ? OR away_team_id = ?
                )
            )
            ORDER BY created_at DESC
            LIMIT ?
        """, (team_id, team_id, self.learning_window))

        records = cursor.fetchall()
        conn.close()

        if not records:
            return result

        attack_errors = []
        defense_errors = []
        control_errors = []

        for r in records:
            error_xg = r['error_xg'] or 0
            cause = r['cause_type'] or ""

            if "attack" in cause.lower() or "xg" in cause.lower():
                attack_errors.append(error_xg)
            elif "defense" in cause.lower():
                defense_errors.append(error_xg)
            else:
                control_errors.append(error_xg)

        if attack_errors:
            avg = sum(attack_errors) / len(attack_errors)
            result["attack"] = (0.5 - avg) * self.learning_weight

        if defense_errors:
            avg = sum(defense_errors) / len(defense_errors)
            result["defense"] = (0.5 - avg) * self.learning_weight

        if control_errors:
            avg = sum(control_errors) / len(control_errors)
            result["control"] = (0.5 - avg) * self.learning_weight

        return result

    # ============================================================
    # HOME
    # ============================================================

    def _calculate_home(self) -> dict:
        return {
            "attack": self.home_advantage.get("attack", 0.04),
            "defense": self.home_advantage.get("defense", 0.02),
            "control": self.home_advantage.get("control", 0.03),
            "keeper": self.home_advantage.get("keeper", 0.01),
        }

    # ============================================================
    # MODEL CONFIDENCE
    # ============================================================

    def _calculate_model_confidence(self, team_id: int) -> float:
        """
        Рассчитывает доверие модели к прогнозам для этой команды
        на основе исторической точности
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN error_score = 0 THEN 1 ELSE 0 END) as correct
            FROM learning_records
            WHERE match_id IN (
                SELECT id FROM matches
                WHERE home_team_id = ? OR away_team_id = ?
            )
        """, (team_id, team_id))

        row = cursor.fetchone()
        conn.close()

        if not row or row['total'] == 0:
            return 0.5

        accuracy = row['correct'] / row['total']
        return 0.5 + 0.5 * accuracy

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ
    # ============================================================

    def _get_passport_meta(self, team_id: int, season_id: int):
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM team_passport_meta
            WHERE team_id = ? AND season_id = ?
        """, (team_id, season_id))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "style": row.get("style", ""),
                "dna": row.get("dna", ""),
                "strengths": row.get("strengths", {}),
                "weaknesses": row.get("weaknesses", {}),
                "class": row.get("class", ""),
                "version": row.get("version", "1.0"),
                "source": row.get("source", "FAJ Expert Layer"),
                "expert": row.get("expert", {}),
            }

        return None


if __name__ == "__main__":
    engine = PowerEngine()

    seasons = engine.db.get_seasons()
    season_id = None
    for s in seasons:
        if s['league'] == "РПЛ":
            season_id = s['id']
            break

    if season_id:
        teams = engine.db.get_teams(league="РПЛ")
        for team in teams:
            if team['name'] == "Зенит":
                result = engine.calculate(team['id'], season_id)

                print(f"\n🏆 Зенит — Power Profile")
                print("=" * 50)
                print(f"ATTACK:  {result['attack_power']}")
                print(f"DEFENSE: {result['defense_power']}")
                print(f"CONTROL: {result['control_power']}")
                print(f"KEEPER:  {result['goalkeeper_power']}")
                print(f"PASSPORT CONFIDENCE: {result['passport_confidence']}")
                print(f"MODEL CONFIDENCE:    {result['model_confidence']}")
                print("\n📊 Компоненты:")
                for key, value in result['explanation'].items():
                    if isinstance(value, dict):
                        print(f"  {key}: {value}")
                    else:
                        print(f"  {key}: {value}")

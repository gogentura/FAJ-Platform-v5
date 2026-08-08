#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ XG Model v1.4
=====================================================

Расчёт ожидаемых голов (xG) на основе Team Passport.

Поддерживаемые структуры паспорта:

1. ПЛОСКАЯ структура из SQLite team_passports:

{
    "attack": 82,
    "defense": 78,
    "control": 80,
    "goalkeeper": 75,
    "tempo": 70,
    "press": 65,
    "transition": 72,
    "finishing": 74,
    "mental": 80,
    "faj_rating": 85.5,
    ...
}

2. ВЛОЖЕННАЯ структура:

{
    "BASE": {
        "attack": 82,
        "defense": 78,
        "control": 80,
        "goalkeeper": 75,
        ...
    },
    "DYNAMIC_INITIAL": {
        "form": 50,
        ...
    }
}

Главный принцип:

xG = League Mean
     × Attack
     × Opponent Defense
     × Opponent Goalkeeper
     × Control
     × Home Advantage
     × Form

ВАЖНО:

- модель НЕ использует букмекерские коэффициенты;
- модель НЕ подменяет FAJ Rating;
- home_rating / away_rating пока используются
  только для диагностики и объяснения;
- паспорт является основным источником силы команды;
- отсутствующие динамические параметры НЕ должны
  искусственно усиливать команду.

=====================================================
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any


logger = logging.getLogger(__name__)


class FAJXGModel:
    """
    FAJ Expected Goals Model.

    Версия 1.4.

    Основная задача:
        Получить два паспорта команд
        → извлечь Power Profile
        → рассчитать xG хозяев и гостей.
    """

    # ============================================================
    # CONFIGURATION
    # ============================================================

    MODEL_VERSION = "FAJ_XG_v1.4"

    # Среднее количество голов одной команды
    LEAGUE_MEAN_XG = 1.35

    # Домашнее преимущество
    HOME_ADVANTAGE = 1.12

    # Нейтральная сила
    POWER_BASE = 70.0

    # Ограничения xG
    MIN_XG = 0.15
    MAX_XG = 4.00

    # ============================================================
    # CONTROL
    # ============================================================

    CONTROL_WEIGHT = 0.50

    MIN_CONTROL_FACTOR = 0.85
    MAX_CONTROL_FACTOR = 1.15

    # ============================================================
    # GOALKEEPER
    # ============================================================

    MIN_KEEPER_FACTOR = 0.85
    MAX_KEEPER_FACTOR = 1.15

    # ============================================================
    # DEFENSE
    # ============================================================

    MIN_DEFENSE_FACTOR = 0.70
    MAX_DEFENSE_FACTOR = 1.40

    # ============================================================
    # FORM
    # ============================================================

    # Форма НЕ должна полностью ломать базовый xG.
    MIN_FORM_FACTOR = 0.90
    MAX_FORM_FACTOR = 1.10

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float = 70.0,
        away_rating: float = 70.0
    ) -> Dict[str, Any]:
        """
        Рассчитать xG матча.

        Args:
            home_passport:
                Паспорт хозяев.

            away_passport:
                Паспорт гостей.

            home_rating:
                FAJ Rating хозяев.

            away_rating:
                FAJ Rating гостей.

        Returns:
            {
                "home_xg": float,
                "away_xg": float,
                "components": {...},
                "explanation": [...],
                "model_version": "...",
                "timestamp": "..."
            }
        """

        # ========================================================
        # 1. VALIDATION
        # ========================================================

        if not isinstance(home_passport, dict):
            raise TypeError(
                "home_passport must be dict"
            )

        if not isinstance(away_passport, dict):
            raise TypeError(
                "away_passport must be dict"
            )

        # ========================================================
        # 2. EXTRACT HOME PASSPORT
        # ========================================================

        home = self._extract_passport(
            home_passport,
            side="HOME"
        )

        # ========================================================
        # 3. EXTRACT AWAY PASSPORT
        # ========================================================

        away = self._extract_passport(
            away_passport,
            side="AWAY"
        )

        # ========================================================
        # 4. LOG INPUT
        # ========================================================

        logger.info(
            "📊 XG INPUT HOME | "
            "attack=%.1f defense=%.1f control=%.1f "
            "keeper=%.1f form=%.3f",
            home["attack"],
            home["defense"],
            home["control"],
            home["goalkeeper"],
            home["form"]
        )

        logger.info(
            "📊 XG INPUT AWAY | "
            "attack=%.1f defense=%.1f control=%.1f "
            "keeper=%.1f form=%.3f",
            away["attack"],
            away["defense"],
            away["control"],
            away["goalkeeper"],
            away["form"]
        )

        # ========================================================
        # 5. FACTORS
        # ========================================================

        # Атака
        home_attack_factor = (
            self._attack_factor(home["attack"])
            * home["form"]
        )

        away_attack_factor = (
            self._attack_factor(away["attack"])
            * away["form"]
        )

        # Защита соперника
        #
        # ВАЖНО:
        # сильная защита соперника уменьшает наш xG.
        #
        # Поэтому:
        #
        # home_xG использует away_defense_factor
        # away_xG использует home_defense_factor

        home_defense_factor = self._defense_factor(
            home["defense"]
        )

        away_defense_factor = self._defense_factor(
            away["defense"]
        )

        # Вратари
        home_keeper_factor = self._keeper_factor(
            home["goalkeeper"]
        )

        away_keeper_factor = self._keeper_factor(
            away["goalkeeper"]
        )

        # ========================================================
        # 6. CONTROL
        # ========================================================

        control_factor = self._control_factor(
            home["control"],
            away["control"]
        )

        # ========================================================
        # 7. HOME ADVANTAGE
        # ========================================================

        home_bonus = self.HOME_ADVANTAGE

        # ========================================================
        # 8. RAW XG
        # ========================================================

        home_xg_raw = (
            self.LEAGUE_MEAN_XG

            * home_attack_factor

            * away_defense_factor

            * away_keeper_factor

            * control_factor

            * home_bonus
        )

        away_xg_raw = (
            self.LEAGUE_MEAN_XG

            * away_attack_factor

            * home_defense_factor

            * home_keeper_factor

            * control_factor
        )

        # ========================================================
        # 9. CLAMP
        # ========================================================

        home_xg = self._clamp_xg(home_xg_raw)
        away_xg = self._clamp_xg(away_xg_raw)

        # ========================================================
        # 10. COMPONENTS
        # ========================================================

        components = {

            # Input
            "home_attack": round(home["attack"], 2),
            "away_attack": round(away["attack"], 2),

            "home_defense": round(home["defense"], 2),
            "away_defense": round(away["defense"], 2),

            "home_control": round(home["control"], 2),
            "away_control": round(away["control"], 2),

            "home_goalkeeper": round(home["goalkeeper"], 2),
            "away_goalkeeper": round(away["goalkeeper"], 2),

            # Factors
            "home_attack_factor": round(
                home_attack_factor, 3
            ),

            "away_attack_factor": round(
                away_attack_factor, 3
            ),

            "home_defense_factor": round(
                home_defense_factor, 3
            ),

            "away_defense_factor": round(
                away_defense_factor, 3
            ),

            "home_keeper_factor": round(
                home_keeper_factor, 3
            ),

            "away_keeper_factor": round(
                away_keeper_factor, 3
            ),

            "control_factor": round(
                control_factor, 3
            ),

            "home_bonus": round(
                home_bonus, 3
            ),

            "home_form": round(
                home["form"], 3
            ),

            "away_form": round(
                away["form"], 3
            ),

            # Ratings для диагностики
            "home_rating": round(
                float(home_rating), 2
            ),

            "away_rating": round(
                float(away_rating), 2
            ),

            # Raw
            "home_xg_raw": round(
                home_xg_raw, 4
            ),

            "away_xg_raw": round(
                away_xg_raw, 4
            )
        }

        # ========================================================
        # 11. EXPLANATION
        # ========================================================

        explanation = self._build_explanation(
            home=home,
            away=away,
            home_attack_factor=home_attack_factor,
            away_attack_factor=away_attack_factor,
            home_defense_factor=home_defense_factor,
            away_defense_factor=away_defense_factor,
            home_keeper_factor=home_keeper_factor,
            away_keeper_factor=away_keeper_factor,
            control_factor=control_factor,
            home_xg=home_xg,
            away_xg=away_xg
        )

        # ========================================================
        # 12. RESULT
        # ========================================================

        result = {
            "home_xg": round(home_xg, 3),
            "away_xg": round(away_xg, 3),

            "components": components,

            "explanation": explanation,

            "model_version": self.MODEL_VERSION,

            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(
            "⚽ XG RESULT | HOME %.3f : %.3f AWAY",
            home_xg,
            away_xg
        )

        return result

    # ============================================================
    # PASSPORT EXTRACTION
    # ============================================================

    def _extract_passport(
        self,
        passport: Dict[str, Any],
        side: str = ""
    ) -> Dict[str, float]:
        """
        Универсальное извлечение параметров паспорта.

        Поддерживает:

        A) BASE / DYNAMIC_INITIAL

        B) Плоский SQLite team_passports
        """

        # ========================================================
        # NESTED PASSPORT
        # ========================================================

        if isinstance(passport.get("BASE"), dict):

            base = passport.get(
                "BASE",
                {}
            )

            dynamic = passport.get(
                "DYNAMIC_INITIAL",
                {}
            )

            attack = self._safe_number(
                base.get("attack"),
                70.0
            )

            defense = self._safe_number(
                base.get("defense"),
                70.0
            )

            control = self._safe_number(
                base.get("control"),
                70.0
            )

            goalkeeper = self._safe_number(
                base.get("goalkeeper"),
                70.0
            )

            raw_form = dynamic.get(
                "form",
                None
            )

        # ========================================================
        # FLAT DATABASE PASSPORT
        # ========================================================

        else:

            attack = self._safe_number(
                passport.get("attack"),
                70.0
            )

            defense = self._safe_number(
                passport.get("defense"),
                70.0
            )

            control = self._safe_number(
                passport.get("control"),
                70.0
            )

            goalkeeper = self._safe_number(
                passport.get("goalkeeper"),
                70.0
            )

            # ----------------------------------------------------
            # Форма
            # ----------------------------------------------------
            #
            # В team_passports формы сейчас НЕТ.
            #
            # Поэтому отсутствие form = нейтральная форма.
            #
            # НЕ делаем:
            #
            # form = 70 / 50 = 1.40
            #
            # потому что это искусственно увеличивает xG на 40%.

            raw_form = passport.get(
                "form",
                None
            )

        # ========================================================
        # NORMALIZE
        # ========================================================

        attack = self._clamp_value(
            attack,
            40.0,
            100.0
        )

        defense = self._clamp_value(
            defense,
            40.0,
            100.0
        )

        control = self._clamp_value(
            control,
            40.0,
            100.0
        )

        goalkeeper = self._clamp_value(
            goalkeeper,
            40.0,
            100.0
        )

        # ========================================================
        # FORM
        # ========================================================

        form = self._normalize_form(
            raw_form
        )

        return {
            "attack": attack,
            "defense": defense,
            "control": control,
            "goalkeeper": goalkeeper,
            "form": form
        }

    # ============================================================
    # FORM NORMALIZATION
    # ============================================================

    def _normalize_form(
        self,
        value: Any
    ) -> float:
        """
        Нормализация формы.

        Возможные входы:

        None
            → 1.0

        50
            → 1.0

        60
            → 1.10

        40
            → 0.90

        0.95
            → 0.95

        Значение ограничивается:
            0.90 – 1.10
        """

        if value is None:
            return 1.0

        try:
            value = float(value)
        except (
            TypeError,
            ValueError
        ):
            return 1.0

        # Если форма уже коэффициент
        if 0.5 <= value <= 1.5:
            factor = value

        # Если форма 0-100
        else:
            factor = value / 50.0

        return max(
            self.MIN_FORM_FACTOR,
            min(
                self.MAX_FORM_FACTOR,
                factor
            )
        )

    # ============================================================
    # ATTACK
    # ============================================================

    def _attack_factor(
        self,
        attack_power: float
    ) -> float:
        """
        Фактор атаки.

        70 = 1.00
        84 = 1.20
        56 = 0.80
        """

        if attack_power <= 0:
            return 1.0

        return attack_power / self.POWER_BASE

    # ============================================================
    # DEFENSE
    # ============================================================

    def _defense_factor(
        self,
        defense_power: float
    ) -> float:
        """
        Фактор защиты.

        Чем сильнее защита команды,
        тем меньше xG соперника.

        70 → 1.00
        80 → 0.875
        90 → 0.778
        60 → 1.167
        """

        if defense_power <= 0:
            return 1.0

        factor = (
            self.POWER_BASE
            / defense_power
        )

        return max(
            self.MIN_DEFENSE_FACTOR,
            min(
                self.MAX_DEFENSE_FACTOR,
                factor
            )
        )

    # ============================================================
    # GOALKEEPER
    # ============================================================

    def _keeper_factor(
        self,
        goalkeeper_power: float
    ) -> float:
        """
        Фактор вратаря.

        70 → 1.00
        80 → 0.875
        90 → 0.85
        60 → 1.15
        """

        if goalkeeper_power <= 0:
            return 1.0

        factor = (
            self.POWER_BASE
            / goalkeeper_power
        )

        return max(
            self.MIN_KEEPER_FACTOR,
            min(
                self.MAX_KEEPER_FACTOR,
                factor
            )
        )

    # ============================================================
    # CONTROL
    # ============================================================

    def _control_factor(
        self,
        home_control: float,
        away_control: float
    ) -> float:
        """
        Контроль матча.

        Разница между командами влияет
        на общий xG темпа/создания моментов.

        Например:

        HOME 80
        AWAY 70

        diff = +10

        factor = 1.05
        """

        diff = (
            home_control
            - away_control
        )

        factor = (
            1.0
            + (diff / 100.0)
            * self.CONTROL_WEIGHT
        )

        return max(
            self.MIN_CONTROL_FACTOR,
            min(
                self.MAX_CONTROL_FACTOR,
                factor
            )
        )

    # ============================================================
    # XG CLAMP
    # ============================================================

    def _clamp_xg(
        self,
        value: float
    ) -> float:
        """
        Ограничение xG.
        """

        try:
            value = float(value)
        except (
            TypeError,
            ValueError
        ):
            value = self.LEAGUE_MEAN_XG

        return max(
            self.MIN_XG,
            min(
                self.MAX_XG,
                value
            )
        )

    # ============================================================
    # VALUE CLAMP
    # ============================================================

    def _clamp_value(
        self,
        value: Any,
        minimum: float,
        maximum: float
    ) -> float:
        """
        Безопасное ограничение значения.
        """

        try:
            value = float(value)
        except (
            TypeError,
            ValueError
        ):
            value = (
                minimum + maximum
            ) / 2.0

        return max(
            minimum,
            min(
                maximum,
                value
            )
        )

    # ============================================================
    # SAFE NUMBER
    # ============================================================

    def _safe_number(
        self,
        value: Any,
        default: float
    ) -> float:
        """
        Безопасное преобразование числа.
        """

        if value is None:
            return default

        try:
            return float(value)
        except (
            TypeError,
            ValueError
        ):
            return default

    # ============================================================
    # EXPLANATION
    # ============================================================

    def _build_explanation(
        self,
        home: Dict[str, float],
        away: Dict[str, float],
        home_attack_factor: float,
        away_attack_factor: float,
        home_defense_factor: float,
        away_defense_factor: float,
        home_keeper_factor: float,
        away_keeper_factor: float,
        control_factor: float,
        home_xg: float,
        away_xg: float
    ) -> List[str]:
        """
        Человеческое объяснение расчёта.
        """

        explanation: List[str] = []

        # ========================================================
        # FORM
        # ========================================================

        if home["form"] > 1.05:

            explanation.append(
                "Форма хозяев повышает атакующий потенциал "
                f"({home['form']:.2f}x)"
            )

        elif home["form"] < 0.95:

            explanation.append(
                "Форма хозяев снижает атакующий потенциал "
                f"({home['form']:.2f}x)"
            )

        if away["form"] > 1.05:

            explanation.append(
                "Форма гостей повышает атакующий потенциал "
                f"({away['form']:.2f}x)"
            )

        elif away["form"] < 0.95:

            explanation.append(
                "Форма гостей снижает атакующий потенциал "
                f"({away['form']:.2f}x)"
            )

        # ========================================================
        # ATTACK
        # ========================================================

        if home_attack_factor > 1.10:

            explanation.append(
                "Атака хозяев выше среднего "
                f"({home_attack_factor:.2f}x)"
            )

        elif home_attack_factor < 0.90:

            explanation.append(
                "Атака хозяев ниже среднего "
                f"({home_attack_factor:.2f}x)"
            )

        if away_attack_factor > 1.10:

            explanation.append(
                "Атака гостей выше среднего "
                f"({away_attack_factor:.2f}x)"
            )

        elif away_attack_factor < 0.90:

            explanation.append(
                "Атака гостей ниже среднего "
                f"({away_attack_factor:.2f}x)"
            )

        # ========================================================
        # DEFENSE
        # ========================================================

        if away_defense_factor < 0.85:

            explanation.append(
                "Сильная защита гостей снижает "
                "xG хозяев "
                f"({away_defense_factor:.2f}x)"
            )

        elif away_defense_factor > 1.15:

            explanation.append(
                "Слабая защита гостей повышает "
                "xG хозяев "
                f"({away_defense_factor:.2f}x)"
            )

        if home_defense_factor < 0.85:

            explanation.append(
                "Сильная защита хозяев снижает "
                "xG гостей "
                f"({home_defense_factor:.2f}x)"
            )

        elif home_defense_factor > 1.15:

            explanation.append(
                "Слабая защита хозяев повышает "
                "xG гостей "
                f"({home_defense_factor:.2f}x)"
            )

        # ========================================================
        # GOALKEEPER
        # ========================================================

        if away_keeper_factor < 0.90:

            explanation.append(
                "Сильный вратарь гостей снижает "
                "xG хозяев "
                f"({away_keeper_factor:.2f}x)"
            )

        elif away_keeper_factor > 1.10:

            explanation.append(
                "Слабый вратарь гостей повышает "
                "xG хозяев "
                f"({away_keeper_factor:.2f}x)"
            )

        if home_keeper_factor < 0.90:

            explanation.append(
                "Сильный вратарь хозяев снижает "
                "xG гостей "
                f"({home_keeper_factor:.2f}x)"
            )

        elif home_keeper_factor > 1.10:

            explanation.append(
                "Слабый вратарь хозяев повышает "
                "xG гостей "
                f"({home_keeper_factor:.2f}x)"
            )

        # ========================================================
        # CONTROL
        # ========================================================

        if control_factor > 1.08:

            explanation.append(
                "Контроль матча заметно повышает "
                "создание моментов "
                f"({control_factor:.2f}x)"
            )

        elif control_factor > 1.02:

            explanation.append(
                "Контроль матча даёт небольшое "
                f"преимущество ({control_factor:.2f}x)"
            )

        elif control_factor < 0.95:

            explanation.append(
                "Контроль матча снижает "
                f"эффективность ({control_factor:.2f}x)"
            )

        # ========================================================
        # HOME ADVANTAGE
        # ========================================================

        explanation.append(
            "Домашнее преимущество: "
            f"{self.HOME_ADVANTAGE:.2f}x"
        )

        # ========================================================
        # FINAL
        # ========================================================

        explanation.append(
            f"Ожидаемые голы: "
            f"{home_xg:.2f} : {away_xg:.2f}"
        )

        return explanation


# ================================================================
# COMPATIBILITY ALIAS
# ================================================================

XGModel = FAJXGModel


# ================================================================
# SINGLETON
# ================================================================

_xg_model_instance: Optional[FAJXGModel] = None


def get_xg_model() -> FAJXGModel:
    """
    Получить singleton экземпляр XG Model.
    """

    global _xg_model_instance

    if _xg_model_instance is None:
        _xg_model_instance = FAJXGModel()

    return _xg_model_instance


# ================================================================
# LOCAL TEST
# ================================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s"
    )

    model = FAJXGModel()

    # ============================================================
    # TEST 1 — ПЛОСКИЙ ПАСПОРТ
    # ============================================================

    home_passport = {
        "id": 1,
        "team_id": 1,
        "season_id": 1,

        "attack": 82,
        "defense": 78,
        "control": 80,
        "tempo": 70,
        "press": 65,
        "transition": 72,
        "finishing": 74,
        "goalkeeper": 75,

        "discipline": 80,
        "squad_quality": 85,
        "bench_quality": 80,
        "coach_factor": 82,
        "mental": 78,

        "home_strength": 85,
        "away_strength": 75,

        "injury_factor": 50,
        "key_player_loss": 50,

        "league_adaptation": 85,
        "passport_confidence": 0.70,

        "faj_rating": 82.5,
        "version": "v1.0"
    }

    away_passport = {
        "id": 2,
        "team_id": 2,
        "season_id": 1,

        "attack": 74,
        "defense": 81,
        "control": 76,
        "tempo": 65,
        "press": 70,
        "transition": 68,
        "finishing": 70,
        "goalkeeper": 79,

        "discipline": 78,
        "squad_quality": 76,
        "bench_quality": 70,
        "coach_factor": 75,
        "mental": 74,

        "home_strength": 70,
        "away_strength": 80,

        "injury_factor": 50,
        "key_player_loss": 50,

        "league_adaptation": 82,
        "passport_confidence": 0.70,

        "faj_rating": 78.5,
        "version": "v1.0"
    }

    result = model.calculate(
        home_passport,
        away_passport,
        home_rating=82.5,
        away_rating=78.5
    )

    print()
    print("=" * 70)
    print("⚽ FAJ XG MODEL v1.4")
    print("=" * 70)

    print(
        f"xG HOME: {result['home_xg']}"
    )

    print(
        f"xG AWAY: {result['away_xg']}"
    )

    print(
        f"MODEL: {result['model_version']}"
    )

    print()
    print("📊 COMPONENTS")
    print("-" * 70)

    for key, value in result["components"].items():
        print(
            f"{key}: {value}"
        )

    print()
    print("📝 EXPLANATION")
    print("-" * 70)

    for line in result["explanation"]:
        print(
            f"• {line}"
        )

    # ============================================================
    # TEST 2 — ВЛОЖЕННЫЙ ПАСПОРТ
    # ============================================================

    nested_home = {
        "BASE": {
            "attack": 82,
            "defense": 78,
            "control": 80,
            "goalkeeper": 75
        },
        "DYNAMIC_INITIAL": {
            "form": 50
        }
    }

    nested_away = {
        "BASE": {
            "attack": 74,
            "defense": 81,
            "control": 76,
            "goalkeeper": 79
        },
        "DYNAMIC_INITIAL": {
            "form": 50
        }
    }

    nested_result = model.calculate(
        nested_home,
        nested_away
    )

    print()
    print("=" * 70)
    print("🧪 NESTED PASSPORT TEST")
    print("=" * 70)

    print(
        f"xG HOME: {nested_result['home_xg']}"
    )

    print(
        f"xG AWAY: {nested_result['away_xg']}"
    )

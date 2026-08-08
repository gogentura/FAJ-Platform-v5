#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================
FAJ Platform v12.0
FAJ XG Model v1.4
РОЛЬ:
    Расчёт ожидаемых голов (xG) на основе Team Passport.
ПОДДЕРЖИВАЕТ:
    1. Вложенный паспорт:
       {
           "BASE": {...},
           "DYNAMIC_INITIAL": {...}
       }
    2. Плоский паспорт из SQLite:
       {
           "attack": 82,
           "defense": 78,
           "control": 80,
           "goalkeeper": 75,
           "faj_rating": 85.5,
           ...
       }
ВАЖНО:
    Модель НЕ использует bookmaker odds.
    Модель использует:
        - attack
        - defense
        - control
        - goalkeeper
        - form
        - home advantage
Вход:
    home_passport
    away_passport
    home_rating
    away_rating
Выход:
    {
        "home_xg": float,
        "away_xg": float,
        "components": {...},
        "explanation": [...],
        "model_version": "FAJ_XG_v1.4",
        "timestamp": "..."
    }
=====================================================
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class FAJXGModel:
    """
    FAJ Expected Goals Model.
    Версия 1.4:
        - поддержка плоских паспортов SQLite
        - поддержка вложенных паспортов
        - безопасная обработка form
        - подробное логирование входных данных
        - защита от одинаковых/default значений
        - Home Advantage применяется ТОЛЬКО внутри XG Model
        - Rating НЕ вмешивается в xG (только диагностика)
        - Контроль разделён на home/away факторы (будет калиброваться)
    """

    # ============================================================
    # CONFIGURATION
    # ============================================================

    MODEL_VERSION = "FAJ_XG_v1.4"

    # Среднее количество голов одной команды
    LEAGUE_MEAN_XG = 1.35

    # Домашнее преимущество (применяется ТОЛЬКО здесь)
    HOME_ADVANTAGE = 1.12

    # Базовая сила
    POWER_BASE = 70.0

    # Ограничения xG
    MIN_XG = 0.15
    MAX_XG = 4.0

    # Контроль (будет калиброваться)
    CONTROL_WEIGHT = 0.50
    MIN_CONTROL_FACTOR = 0.85
    MAX_CONTROL_FACTOR = 1.15

    # Вратарь
    MIN_KEEPER_FACTOR = 0.85
    MAX_KEEPER_FACTOR = 1.15

    # Защита
    MIN_DEFENSE_FACTOR = 0.70
    MAX_DEFENSE_FACTOR = 1.40

    # Форма
    FORM_BASE = 50.0
    MIN_FORM_FACTOR = 0.85
    MAX_FORM_FACTOR = 1.15

    # Диапазоны паспортных значений
    MIN_POWER = 40.0
    MAX_POWER = 100.0

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

        Поддерживает как вложенную структуру паспорта,
        так и плоскую структуру из SQLite.

        ВАЖНО:
        home_rating / away_rating логируются и возвращаются
        в components, но напрямую НЕ вмешиваются в xG.
        """
        try:
            # ====================================================
            # 1. ПРОВЕРКА ВХОДНЫХ ДАННЫХ
            # ====================================================
            if not isinstance(home_passport, dict):
                raise TypeError(
                    f"home_passport must be dict, got "
                    f"{type(home_passport).__name__}"
                )
            if not isinstance(away_passport, dict):
                raise TypeError(
                    f"away_passport must be dict, got "
                    f"{type(away_passport).__name__}"
                )

            # ====================================================
            # 2. ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ
            # ====================================================
            home = self._extract_team_parameters(
                home_passport,
                side="HOME"
            )
            away = self._extract_team_parameters(
                away_passport,
                side="AWAY"
            )

            # ====================================================
            # 3. ЛОГИРОВАНИЕ
            # ====================================================
            logger.info(
                "XG INPUT HOME | "
                "attack=%.2f defense=%.2f control=%.2f "
                "keeper=%.2f form=%.3f",
                home["attack"],
                home["defense"],
                home["control"],
                home["goalkeeper"],
                home["form"]
            )
            logger.info(
                "XG INPUT AWAY | "
                "attack=%.2f defense=%.2f control=%.2f "
                "keeper=%.2f form=%.3f",
                away["attack"],
                away["defense"],
                away["control"],
                away["goalkeeper"],
                away["form"]
            )
            logger.info(
                "XG RATINGS (diagnostic only) | HOME=%.2f AWAY=%.2f",
                home_rating,
                away_rating
            )

            # ====================================================
            # 4. FACTORS
            # ====================================================
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
            away_defense_factor = self._defense_factor(
                away["defense"]
            )
            home_defense_factor = self._defense_factor(
                home["defense"]
            )

            # Вратари
            away_keeper_factor = self._keeper_factor(
                away["goalkeeper"]
            )
            home_keeper_factor = self._keeper_factor(
                home["goalkeeper"]
            )

            # Контроль (будет калиброваться)
            home_control_factor, away_control_factor = (
                self._control_factors(
                    home["control"],
                    away["control"]
                )
            )

            # ====================================================
            # 5. HOME ADVANTAGE (ПРИМЕНЯЕТСЯ ТОЛЬКО ЗДЕСЬ)
            # ====================================================
            home_bonus = self.HOME_ADVANTAGE

            # ====================================================
            # 6. RAW xG
            # ====================================================
            home_xg_raw = (
                self.LEAGUE_MEAN_XG
                * home_attack_factor
                * away_defense_factor
                * away_keeper_factor
                * home_control_factor
                * home_bonus
            )

            away_xg_raw = (
                self.LEAGUE_MEAN_XG
                * away_attack_factor
                * home_defense_factor
                * home_keeper_factor
                * away_control_factor
            )

            # ====================================================
            # 7. CLAMP
            # ====================================================
            home_xg = self._clamp_xg(home_xg_raw)
            away_xg = self._clamp_xg(away_xg_raw)

            # ====================================================
            # 8. COMPONENTS
            # ====================================================
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

                # Form
                "home_form_factor": round(home["form"], 3),
                "away_form_factor": round(away["form"], 3),

                # Factors
                "home_attack_factor": round(home_attack_factor, 3),
                "away_attack_factor": round(away_attack_factor, 3),
                "home_defense_factor": round(home_defense_factor, 3),
                "away_defense_factor": round(away_defense_factor, 3),
                "home_keeper_factor": round(home_keeper_factor, 3),
                "away_keeper_factor": round(away_keeper_factor, 3),
                "home_control_factor": round(home_control_factor, 3),
                "away_control_factor": round(away_control_factor, 3),

                # Home Advantage (диагностика)
                "home_bonus": round(home_bonus, 3),

                # Ratings (диагностика, НЕ влияют на xG)
                "home_rating": round(float(home_rating), 2),
                "away_rating": round(float(away_rating), 2),

                # Raw
                "home_xg_raw": round(home_xg_raw, 4),
                "away_xg_raw": round(away_xg_raw, 4)
            }

            # ====================================================
            # 9. EXPLANATION
            # ====================================================
            explanation = self._build_explanation(
                home=home,
                away=away,
                home_attack_factor=home_attack_factor,
                away_attack_factor=away_attack_factor,
                home_defense_factor=home_defense_factor,
                away_defense_factor=away_defense_factor,
                home_keeper_factor=home_keeper_factor,
                away_keeper_factor=away_keeper_factor,
                home_control_factor=home_control_factor,
                away_control_factor=away_control_factor,
                home_xg=home_xg,
                away_xg=away_xg
            )

            # ====================================================
            # 10. RESULT
            # ====================================================
            result = {
                "status": "success",
                "home_xg": round(home_xg, 3),
                "away_xg": round(away_xg, 3),
                "components": components,
                "explanation": explanation,
                "model_version": self.MODEL_VERSION,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(
                "XG RESULT | %.3f : %.3f",
                home_xg,
                away_xg
            )

            return result

        except Exception as e:
            logger.exception("FAJ XG calculation error")
            return {
                "status": "error",
                "message": str(e),
                "home_xg": 0.0,
                "away_xg": 0.0,
                "model_version": self.MODEL_VERSION,
                "timestamp": datetime.utcnow().isoformat()
            }

    # ============================================================
    # PASSPORT EXTRACTION
    # ============================================================

    def _extract_team_parameters(
        self,
        passport: Dict[str, Any],
        side: str = "TEAM"
    ) -> Dict[str, float]:
        """
        Универсальное извлечение параметров.

        Поддержка:
        A:
            {
                "BASE": {...},
                "DYNAMIC_INITIAL": {...}
            }
        B:
            {
                "attack": 82,
                "defense": 78,
                ...
            }

        ВАЖНО:
        отсутствие form НЕ означает form=70.
        При отсутствии формы используется нейтральный
        фактор 1.0.
        """
        # --------------------------------------------------------
        # Вложенный паспорт
        # --------------------------------------------------------
        if isinstance(passport.get("BASE"), dict):
            base = passport.get("BASE", {})
            dynamic = passport.get("DYNAMIC_INITIAL", {})

            if not isinstance(dynamic, dict):
                dynamic = {}

            attack = base.get("attack", 70)
            defense = base.get("defense", 70)
            control = base.get("control", 70)
            goalkeeper = base.get("goalkeeper", 70)
            raw_form = dynamic.get("form", self.FORM_BASE)
            form_factor = self._form_factor(raw_form)
            source = "nested"

        # --------------------------------------------------------
        # Плоский паспорт SQLite
        # --------------------------------------------------------
        else:
            attack = passport.get("attack", 70)
            defense = passport.get("defense", 70)
            control = passport.get("control", 70)
            goalkeeper = passport.get("goalkeeper", 70)

            # ----------------------------------------------------
            # Форма
            # ----------------------------------------------------
            #
            # В team_passports её сейчас может не быть.
            #
            # Поэтому:
            # отсутствует -> 1.0
            #
            # Если есть form -> используем её.
            #
            if "form" in passport:
                raw_form = passport.get("form", self.FORM_BASE)
                form_factor = self._form_factor(raw_form)
            else:
                form_factor = 1.0

            source = "flat"

        # --------------------------------------------------------
        # Clamp
        # --------------------------------------------------------
        attack = self._clamp_value(attack, self.MIN_POWER, self.MAX_POWER)
        defense = self._clamp_value(defense, self.MIN_POWER, self.MAX_POWER)
        control = self._clamp_value(control, self.MIN_POWER, self.MAX_POWER)
        goalkeeper = self._clamp_value(goalkeeper, self.MIN_POWER, self.MAX_POWER)

        logger.debug(
            "XG PASSPORT %s | source=%s "
            "attack=%.2f defense=%.2f "
            "control=%.2f goalkeeper=%.2f form=%.3f",
            side,
            source,
            attack,
            defense,
            control,
            goalkeeper,
            form_factor
        )

        return {
            "attack": attack,
            "defense": defense,
            "control": control,
            "goalkeeper": goalkeeper,
            "form": form_factor
        }

    # ============================================================
    # FACTORS
    # ============================================================

    def _attack_factor(self, attack_power: float) -> float:
        """Сила атаки относительно базового уровня 70."""
        return attack_power / self.POWER_BASE

    # ------------------------------------------------------------

    def _defense_factor(self, defense_power: float) -> float:
        """
        Сильная защита соперника снижает xG.
        70 defense -> 1.00
        80 defense -> 0.875
        90 defense -> 0.778
        60 defense -> 1.167
        """
        if defense_power <= 0:
            return 1.0
        factor = self.POWER_BASE / defense_power
        return max(self.MIN_DEFENSE_FACTOR, min(self.MAX_DEFENSE_FACTOR, factor))

    # ------------------------------------------------------------

    def _keeper_factor(self, goalkeeper_power: float) -> float:
        """
        Сильный вратарь снижает xG соперника.
        70 -> 1.00
        80 -> 0.875
        90 -> 0.85 (clamp)
        60 -> 1.15 (clamp)
        """
        if goalkeeper_power <= 0:
            return 1.0
        factor = self.POWER_BASE / goalkeeper_power
        return max(self.MIN_KEEPER_FACTOR, min(self.MAX_KEEPER_FACTOR, factor))

    # ------------------------------------------------------------

    def _form_factor(self, form: Any) -> float:
        """
        Преобразование формы 0-100 в коэффициент влияния.
        50 -> 1.00
        60 -> 1.15
        40 -> 0.85

        Ограничение: 0.85 - 1.15

        Неверное/отсутствующее значение: 1.00
        """
        try:
            value = float(form)
        except (TypeError, ValueError):
            return 1.0

        if value <= 0:
            return 1.0

        factor = value / self.FORM_BASE
        return max(self.MIN_FORM_FACTOR, min(self.MAX_FORM_FACTOR, factor))

    # ------------------------------------------------------------

    def _control_factors(self, home_control: float, away_control: float) -> tuple:
        """
        Контроль распределяется между командами.

        Это важное изменение относительно старой версии.
        Раньше один control_factor умножал xG ОБЕИХ команд.

        Теперь преимущество контроля должно
        работать относительно сторон.

        Например:
            Home 80, Away 60
        Home получает небольшой плюс,
        Away получает небольшой минус.

        ВНИМАНИЕ: этот коэффициент будет калиброваться
        после первых тестов.
        """
        diff = home_control - away_control

        home_factor = 1.0 + (diff / 100.0) * self.CONTROL_WEIGHT
        away_factor = 1.0 - (diff / 100.0) * self.CONTROL_WEIGHT

        home_factor = max(self.MIN_CONTROL_FACTOR, min(self.MAX_CONTROL_FACTOR, home_factor))
        away_factor = max(self.MIN_CONTROL_FACTOR, min(self.MAX_CONTROL_FACTOR, away_factor))

        return (home_factor, away_factor)

    # ============================================================
    # CLAMP
    # ============================================================

    def _clamp_value(self, value: Any, min_val: float, max_val: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = (min_val + max_val) / 2.0
        return max(min_val, min(max_val, value))

    # ------------------------------------------------------------

    def _clamp_xg(self, value: float) -> float:
        return max(self.MIN_XG, min(self.MAX_XG, value))

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
        home_control_factor: float,
        away_control_factor: float,
        home_xg: float,
        away_xg: float
    ) -> List[str]:
        explanation = []

        # --------------------------------------------------------
        # Атака
        # --------------------------------------------------------
        if home_attack_factor >= 1.10:
            explanation.append(
                f"Атака хозяев выше средней ({home_attack_factor:.2f}x)"
            )
        elif home_attack_factor <= 0.90:
            explanation.append(
                f"Атака хозяев ниже средней ({home_attack_factor:.2f}x)"
            )

        if away_attack_factor >= 1.10:
            explanation.append(
                f"Атака гостей выше средней ({away_attack_factor:.2f}x)"
            )
        elif away_attack_factor <= 0.90:
            explanation.append(
                f"Атака гостей ниже средней ({away_attack_factor:.2f}x)"
            )

        # --------------------------------------------------------
        # Защита
        # --------------------------------------------------------
        if away_defense_factor < 0.90:
            explanation.append("Сильная защита гостей снижает xG хозяев")
        elif away_defense_factor > 1.10:
            explanation.append("Слабая защита гостей повышает xG хозяев")

        if home_defense_factor < 0.90:
            explanation.append("Сильная защита хозяев снижает xG гостей")
        elif home_defense_factor > 1.10:
            explanation.append("Слабая защита хозяев повышает xG гостей")

        # --------------------------------------------------------
        # Вратари
        # --------------------------------------------------------
        if away_keeper_factor < 0.90:
            explanation.append("Сильный вратарь гостей снижает xG хозяев")
        elif away_keeper_factor > 1.10:
            explanation.append("Слабый вратарь гостей повышает xG хозяев")

        if home_keeper_factor < 0.90:
            explanation.append("Сильный вратарь хозяев снижает xG гостей")
        elif home_keeper_factor > 1.10:
            explanation.append("Слабый вратарь хозяев повышает xG гостей")

        # --------------------------------------------------------
        # Контроль
        # --------------------------------------------------------
        if home_control_factor > 1.05:
            explanation.append(
                f"Контроль даёт преимущество хозяев ({home_control_factor:.2f}x)"
            )
        elif away_control_factor > 1.05:
            explanation.append(
                f"Контроль даёт преимущество гостей ({away_control_factor:.2f}x)"
            )

        # --------------------------------------------------------
        # Форма
        # --------------------------------------------------------
        if home["form"] > 1.05:
            explanation.append(
                f"Форма хозяев повышает атакующий потенциал ({home['form']:.2f}x)"
            )
        elif home["form"] < 0.95:
            explanation.append(
                f"Форма хозяев снижает атакующий потенциал ({home['form']:.2f}x)"
            )

        if away["form"] > 1.05:
            explanation.append(
                f"Форма гостей повышает атакующий потенциал ({away['form']:.2f}x)"
            )
        elif away["form"] < 0.95:
            explanation.append(
                f"Форма гостей снижает атакующий потенциал ({away['form']:.2f}x)"
            )

        # --------------------------------------------------------
        # Home Advantage (диагностика)
        # --------------------------------------------------------
        explanation.append(
            f"Домашнее преимущество: {self.HOME_ADVANTAGE:.2f}x"
        )

        # --------------------------------------------------------
        # Итог
        # --------------------------------------------------------
        explanation.append(
            f"Ожидаемые голы: {home_xg:.2f} : {away_xg:.2f}"
        )

        return explanation


# ================================================================
# ALIAS ДЛЯ СОВМЕСТИМОСТИ С PIPELINE
# ================================================================

XGModel = FAJXGModel


# ================================================================
# SINGLETON
# ================================================================

_xg_model_instance: Optional[FAJXGModel] = None


def get_xg_model() -> FAJXGModel:
    global _xg_model_instance
    if _xg_model_instance is None:
        _xg_model_instance = FAJXGModel()
    return _xg_model_instance


# ================================================================
# LOCAL TEST
# ================================================================

if __name__ == "__main__":
    model = FAJXGModel()

    # ------------------------------------------------------------
    # TEST 1 — ПЛОСКИЙ ПАСПОРТ
    # ------------------------------------------------------------
    home_passport = {
        "attack": 82,
        "defense": 78,
        "control": 80,
        "goalkeeper": 75,
        "faj_rating": 82.5
    }

    away_passport = {
        "attack": 74,
        "defense": 81,
        "control": 76,
        "goalkeeper": 79,
        "faj_rating": 76.5
    }

    result = model.calculate(
        home_passport,
        away_passport,
        home_rating=82.5,
        away_rating=76.5
    )

    print()
    print("=" * 70)
    print("FAJ XG MODEL v1.4")
    print("=" * 70)
    print(f"xG: {result['home_xg']:.3f} : {result['away_xg']:.3f}")
    print()
    print("COMPONENTS")
    print("-" * 70)
    for key, value in result["components"].items():
        print(f"{key}: {value}")
    print()
    print("EXPLANATION")
    print("-" * 70)
    for line in result["explanation"]:
        print(f"• {line}")
    print()
    print(f"MODEL: {result['model_version']}")

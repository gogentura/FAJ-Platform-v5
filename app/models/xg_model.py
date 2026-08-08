#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ XG Model v1.4
FAJ Platform v12.0

РОЛЬ:
    Расчёт ожидаемых голов (xG).

ПРИНЦИП:
    XG Model НЕ работает с БД напрямую.
    На вход получает уже загруженные паспорта команд.

ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ ПАСПОРТА:

1. Вложенный:
    {
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

2. Плоский (из SQLite):
    {
        "attack": 82,
        "defense": 78,
        "control": 80,
        "goalkeeper": 75,
        "form": 50,
        ...
    }

ВЫХОД:
    {
        "home_xg": float,
        "away_xg": float,
        "components": {...},
        "explanation": [...],
        "model_version": str,
        "timestamp": str
    }

ВАЖНО:
    Model не знает о БД.
    Model не загружает паспорта.
    Model не изменяет паспорта.
=====================================================
"""

from datetime import datetime
from typing import Dict, List, Any
import logging


logger = logging.getLogger(__name__)


class FAJXGModel:
    """
    FAJ Expected Goals Model.

    Рассчитывает xG на основе:
        - attack
        - defense
        - control
        - goalkeeper
        - form
        - home advantage
    """

    # ============================================================
    # ОСНОВНЫЕ ПАРАМЕТРЫ
    # ============================================================

    MODEL_VERSION = "FAJ_XG_v1.4"

    # Среднее количество голов команды в лиге
    LEAGUE_MEAN_XG = 1.35

    # Домашнее преимущество
    HOME_ADVANTAGE = 1.12

    # Базовая сила FAJ
    POWER_BASE = 70.0

    # Ограничения xG
    MIN_XG = 0.15
    MAX_XG = 4.00

    # ============================================================
    # CONTROL
    # ============================================================

    CONTROL_WEIGHT = 0.50

    MIN_CONTROL_FACTOR = 0.85
    MAX_CONTROL_FACTOR = 1.30

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
    # PASSPORT VALUES
    # ============================================================

    MIN_POWER = 40.0
    MAX_POWER = 100.0

    DEFAULT_POWER = 70.0

    # Form хранится в диапазоне 40-100.
    # 50 = нейтральная форма.
    FORM_BASE = 50.0

    MIN_FORM = 40.0
    MAX_FORM = 100.0

    # Защита от слишком сильного влияния формы
    MIN_FORM_FACTOR = 0.80
    MAX_FORM_FACTOR = 1.20

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self):
        logger.info(
            "FAJ XG Model v%s initialized",
            self.MODEL_VERSION
        )

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
        Основной расчёт xG.

        Parameters
        ----------
        home_passport:
            Паспорт хозяев.

        away_passport:
            Паспорт гостей.

        home_rating:
            FAJ Rating хозяев.

        away_rating:
            FAJ Rating гостей.

        Returns
        -------
        Dict
            Результат расчёта xG.
        """

        try:

            # ====================================================
            # 1. VALIDATION
            # ====================================================

            if not isinstance(home_passport, dict):
                raise TypeError(
                    "home_passport должен быть Dict"
                )

            if not isinstance(away_passport, dict):
                raise TypeError(
                    "away_passport должен быть Dict"
                )

            # ====================================================
            # 2. EXTRACT HOME
            # ====================================================

            home = self._extract_passport(
                home_passport,
                side="home"
            )

            # ====================================================
            # 3. EXTRACT AWAY
            # ====================================================

            away = self._extract_passport(
                away_passport,
                side="away"
            )

            # ====================================================
            # 4. COMPONENT FACTORS
            # ====================================================

            home_attack_factor = (
                self._attack_factor(home["attack"])
                * home["form_factor"]
            )

            away_attack_factor = (
                self._attack_factor(away["attack"])
                * away["form_factor"]
            )

            # Сильная защита = меньше xG соперника.
            #
            # Форма используется симметрично:
            # плохая форма ухудшает защитную эффективность,
            # хорошая — повышает.
            home_defense_factor = (
                self._defense_factor(home["defense"])
                / home["form_factor"]
            )

            away_defense_factor = (
                self._defense_factor(away["defense"])
                / away["form_factor"]
            )

            home_keeper_factor = self._keeper_factor(
                home["goalkeeper"]
            )

            away_keeper_factor = self._keeper_factor(
                away["goalkeeper"]
            )

            control_factor = self._control_factor(
                home["control"],
                away["control"]
            )

            home_bonus = self.HOME_ADVANTAGE

            # ====================================================
            # 5. HOME xG
            # ====================================================

            home_xg_raw = (
                self.LEAGUE_MEAN_XG
                * home_attack_factor
                * away_defense_factor
                * away_keeper_factor
                * control_factor
                * home_bonus
            )

            # ====================================================
            # 6. AWAY xG
            # ====================================================

            away_xg_raw = (
                self.LEAGUE_MEAN_XG
                * away_attack_factor
                * home_defense_factor
                * home_keeper_factor
                * control_factor
            )

            # ====================================================
            # 7. CLAMP
            # ====================================================

            home_xg = self._clamp_xg(home_xg_raw)
            away_xg = self._clamp_xg(away_xg_raw)

            # ====================================================
            # 8. DIAGNOSTIC COMPONENTS
            # ====================================================

            components = {

                # Attack
                "home_attack_factor": round(
                    home_attack_factor,
                    3
                ),

                "away_attack_factor": round(
                    away_attack_factor,
                    3
                ),

                # Defense
                "home_defense_factor": round(
                    home_defense_factor,
                    3
                ),

                "away_defense_factor": round(
                    away_defense_factor,
                    3
                ),

                # Goalkeeper
                "home_keeper_factor": round(
                    home_keeper_factor,
                    3
                ),

                "away_keeper_factor": round(
                    away_keeper_factor,
                    3
                ),

                # Control
                "control_factor": round(
                    control_factor,
                    3
                ),

                # Home advantage
                "home_bonus": round(
                    home_bonus,
                    3
                ),

                # Form
                "home_form": round(
                    home["form_factor"],
                    3
                ),

                "away_form": round(
                    away["form_factor"],
                    3
                ),

                # Raw passport values
                "home_attack": round(
                    home["attack"],
                    2
                ),

                "away_attack": round(
                    away["attack"],
                    2
                ),

                "home_defense": round(
                    home["defense"],
                    2
                ),

                "away_defense": round(
                    away["defense"],
                    2
                ),

                "home_control": round(
                    home["control"],
                    2
                ),

                "away_control": round(
                    away["control"],
                    2
                ),

                "home_goalkeeper": round(
                    home["goalkeeper"],
                    2
                ),

                "away_goalkeeper": round(
                    away["goalkeeper"],
                    2
                ),

                # Ratings
                "home_rating": round(
                    float(home_rating),
                    2
                ),

                "away_rating": round(
                    float(away_rating),
                    2
                ),

                # Raw xG before clamp
                "home_xg_raw": round(
                    home_xg_raw,
                    4
                ),

                "away_xg_raw": round(
                    away_xg_raw,
                    4
                )
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
                control_factor=control_factor,
                home_xg=home_xg,
                away_xg=away_xg
            )

            # ====================================================
            # 10. LOGGING
            # ====================================================

            logger.info(
                "XG calculation: "
                "HOME attack=%.1f defense=%.1f control=%.1f "
                "keeper=%.1f form=%.2f | "
                "AWAY attack=%.1f defense=%.1f control=%.1f "
                "keeper=%.1f form=%.2f",
                home["attack"],
                home["defense"],
                home["control"],
                home["goalkeeper"],
                home["form_factor"],
                away["attack"],
                away["defense"],
                away["control"],
                away["goalkeeper"],
                away["form_factor"]
            )

            logger.info(
                "XG result: %.3f - %.3f",
                home_xg,
                away_xg
            )

            # ====================================================
            # 11. RETURN
            # ====================================================

            return {
                "home_xg": round(home_xg, 3),
                "away_xg": round(away_xg, 3),
                "components": components,
                "explanation": explanation,
                "model_version": self.MODEL_VERSION,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as exc:

            logger.error(
                "FAJ XG calculation error: %s",
                exc,
                exc_info=True
            )

            raise

    # ============================================================
    # PASSPORT EXTRACTION
    # ============================================================

    def _extract_passport(
        self,
        passport: Dict[str, Any],
        side: str
    ) -> Dict[str, float]:
        """
        Универсальный адаптер паспорта.

        Поддерживает:

            BASE + DYNAMIC_INITIAL

        и:

            плоский словарь из SQLite.
        """

        # ========================================================
        # ВЛОЖЕННЫЙ ПАСПОРТ
        # ========================================================

        if isinstance(
            passport.get("BASE"),
            dict
        ):

            base = passport.get(
                "BASE",
                {}
            )

            dynamic = passport.get(
                "DYNAMIC_INITIAL",
                {}
            )

            attack = base.get(
                "attack",
                self.DEFAULT_POWER
            )

            defense = base.get(
                "defense",
                self.DEFAULT_POWER
            )

            control = base.get(
                "control",
                self.DEFAULT_POWER
            )

            goalkeeper = base.get(
                "goalkeeper",
                self.DEFAULT_POWER
            )

            form = dynamic.get(
                "form",
                self.FORM_BASE
            )

            passport_type = "nested"

        # ========================================================
        # ПЛОСКИЙ ПАСПОРТ
        # ========================================================

        else:

            attack = passport.get(
                "attack",
                self.DEFAULT_POWER
            )

            defense = passport.get(
                "defense",
                self.DEFAULT_POWER
            )

            control = passport.get(
                "control",
                self.DEFAULT_POWER
            )

            goalkeeper = passport.get(
                "goalkeeper",
                self.DEFAULT_POWER
            )

            form = passport.get(
                "form",
                self.FORM_BASE
            )

            passport_type = "flat"

        # ========================================================
        # SANITIZE
        # ========================================================

        attack = self._safe_number(
            attack,
            self.DEFAULT_POWER
        )

        defense = self._safe_number(
            defense,
            self.DEFAULT_POWER
        )

        control = self._safe_number(
            control,
            self.DEFAULT_POWER
        )

        goalkeeper = self._safe_number(
            goalkeeper,
            self.DEFAULT_POWER
        )

        form = self._safe_number(
            form,
            self.FORM_BASE
        )

        # ========================================================
        # CLAMP
        # ========================================================

        attack = self._clamp_value(
            attack,
            self.MIN_POWER,
            self.MAX_POWER
        )

        defense = self._clamp_value(
            defense,
            self.MIN_POWER,
            self.MAX_POWER
        )

        control = self._clamp_value(
            control,
            self.MIN_POWER,
            self.MAX_POWER
        )

        goalkeeper = self._clamp_value(
            goalkeeper,
            self.MIN_POWER,
            self.MAX_POWER
        )

        form = self._clamp_value(
            form,
            self.MIN_FORM,
            self.MAX_FORM
        )

        # ========================================================
        # FORM FACTOR
        # ========================================================

        form_factor = form / self.FORM_BASE

        form_factor = max(
            self.MIN_FORM_FACTOR,
            min(
                self.MAX_FORM_FACTOR,
                form_factor
            )
        )

        logger.debug(
            "%s passport detected: %s",
            side,
            passport_type
        )

        return {
            "attack": attack,
            "defense": defense,
            "control": control,
            "goalkeeper": goalkeeper,
            "form": form,
            "form_factor": form_factor
        }

    # ============================================================
    # ATTACK
    # ============================================================

    def _attack_factor(
        self,
        attack_power: float
    ) -> float:
        """
        Сила атаки относительно FAJ базовой силы.

        70 = 1.00
        84 = 1.20
        56 = 0.80
        """

        return attack_power / self.POWER_BASE

    # ============================================================
    # DEFENSE
    # ============================================================

    def _defense_factor(
        self,
        defense_power: float
    ) -> float:
        """
        Сильная защита уменьшает xG соперника.

        70 = 1.00
        80 = 0.875
        90 = 0.778
        50 = 1.40
        """

        if defense_power <= 0:
            return 1.0

        factor = (
            self.POWER_BASE /
            defense_power
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
        Сильный вратарь уменьшает xG соперника.

        Ограничение:
            0.85 - 1.15
        """

        if goalkeeper_power <= 0:
            return 1.0

        factor = (
            self.POWER_BASE /
            goalkeeper_power
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

        diff = home_control - away_control

        При равном контроле:
            1.00

        Преимущество хозяев:
            > 1.00

        Преимущество гостей:
            < 1.00
        """

        diff = (
            home_control -
            away_control
        )

        factor = (
            1.0 +
            (diff / 100.0)
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
        Ограничение итогового xG.
        """

        return max(
            self.MIN_XG,
            min(
                self.MAX_XG,
                value
            )
        )

    # ============================================================
    # GENERIC CLAMP
    # ============================================================

    def _clamp_value(
        self,
        value: float,
        min_val: float,
        max_val: float
    ) -> float:

        return max(
            min_val,
            min(
                max_val,
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
        Безопасное преобразование значения.

        Защищает модель от:
            None
            ""
            NaN
            строковых чисел
        """

        try:

            if value is None:
                return default

            if isinstance(value, str):

                value = value.strip()

                if not value:
                    return default

            number = float(value)

            if number != number:
                return default

            return number

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
        Человеческое объяснение результата.
        """

        explanation = []

        # ========================================================
        # FORM
        # ========================================================

        if home["form_factor"] >= 1.10:

            explanation.append(
                "Хозяева находятся в хорошей форме"
            )

        elif home["form_factor"] <= 0.90:

            explanation.append(
                "Хозяева находятся в плохой форме"
            )

        if away["form_factor"] >= 1.10:

            explanation.append(
                "Гости находятся в хорошей форме"
            )

        elif away["form_factor"] <= 0.90:

            explanation.append(
                "Гости находятся в плохой форме"
            )

        # ========================================================
        # ATTACK
        # ========================================================

        if home_attack_factor >= 1.15:

            explanation.append(
                f"Атака хозяев значительно выше средней "
                f"({home_attack_factor:.2f}x)"
            )

        elif home_attack_factor <= 0.85:

            explanation.append(
                f"Атака хозяев ниже средней "
                f"({home_attack_factor:.2f}x)"
            )

        if away_attack_factor >= 1.15:

            explanation.append(
                f"Атака гостей значительно выше средней "
                f"({away_attack_factor:.2f}x)"
            )

        elif away_attack_factor <= 0.85:

            explanation.append(
                f"Атака гостей ниже средней "
                f"({away_attack_factor:.2f}x)"
            )

        # ========================================================
        # DEFENSE
        # ========================================================

        if home_defense_factor <= 0.85:

            explanation.append(
                f"Сильная защита хозяев снижает xG гостей "
                f"({home_defense_factor:.2f}x)"
            )

        elif home_defense_factor >= 1.15:

            explanation.append(
                f"Слабая защита хозяев повышает xG гостей "
                f"({home_defense_factor:.2f}x)"
            )

        if away_defense_factor <= 0.85:

            explanation.append(
                f"Сильная защита гостей снижает xG хозяев "
                f"({away_defense_factor:.2f}x)"
            )

        elif away_defense_factor >= 1.15:

            explanation.append(
                f"Слабая защита гостей повышает xG хозяев "
                f"({away_defense_factor:.2f}x)"
            )

        # ========================================================
        # GOALKEEPER
        # ========================================================

        if home_keeper_factor <= 0.90:

            explanation.append(
                f"Сильный вратарь хозяев снижает xG гостей "
                f"({home_keeper_factor:.2f}x)"
            )

        elif home_keeper_factor >= 1.10:

            explanation.append(
                f"Вратарь хозяев повышает ожидаемый xG гостей "
                f"({home_keeper_factor:.2f}x)"
            )

        if away_keeper_factor <= 0.90:

            explanation.append(
                f"Сильный вратарь гостей снижает xG хозяев "
                f"({away_keeper_factor:.2f}x)"
            )

        elif away_keeper_factor >= 1.10:

            explanation.append(
                f"Вратарь гостей повышает ожидаемый xG хозяев "
                f"({away_keeper_factor:.2f}x)"
            )

        # ========================================================
        # CONTROL
        # ========================================================

        if control_factor >= 1.08:

            explanation.append(
                f"Контроль матча даёт преимущество хозяев "
                f"({control_factor:.2f}x)"
            )

        elif control_factor <= 0.92:

            explanation.append(
                f"Контроль матча даёт преимущество гостям "
                f"({control_factor:.2f}x)"
            )

        elif control_factor > 1.02:

            explanation.append(
                f"Небольшое преимущество хозяев "
                f"по контролю ({control_factor:.2f}x)"
            )

        elif control_factor < 0.98:

            explanation.append(
                f"Небольшое преимущество гостей "
                f"по контролю ({control_factor:.2f}x)"
            )

        # ========================================================
        # HOME ADVANTAGE
        # ========================================================

        explanation.append(
            f"Домашнее преимущество: "
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
# ALIAS
# ================================================================

# PredictionPipeline импортирует XGModel.
XGModel = FAJXGModel


# ================================================================
# SINGLETON
# ================================================================

_xg_model_instance = None


def get_xg_model() -> FAJXGModel:
    """
    Возвращает singleton экземпляр XG Model.
    """

    global _xg_model_instance

    if _xg_model_instance is None:

        _xg_model_instance = FAJXGModel()

    return _xg_model_instance


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":

    model = FAJXGModel()

    # ============================================================
    # TEST 1 — NESTED PASSPORT
    # ============================================================

    home_passport_nested = {

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

    away_passport_nested = {

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

    result_nested = model.calculate(
        home_passport_nested,
        away_passport_nested,
        home_rating=75.0,
        away_rating=70.0
    )

    print()
    print("=" * 70)
    print("FAJ XG MODEL v1.4")
    print("TEST 1 — NESTED PASSPORT")
    print("=" * 70)

    print(
        f"xG: "
        f"{result_nested['home_xg']} : "
        f"{result_nested['away_xg']}"
    )

    print(
        f"Version: "
        f"{result_nested['model_version']}"
    )

    # ============================================================
    # TEST 2 — FLAT PASSPORT
    # ============================================================

    home_passport_flat = {

        "attack": 82,
        "defense": 78,
        "control": 80,
        "goalkeeper": 75,
        "form": 50,

        "faj_rating": 75.0
    }

    away_passport_flat = {

        "attack": 74,
        "defense": 81,
        "control": 76,
        "goalkeeper": 79,
        "form": 50,

        "faj_rating": 70.0
    }

    result_flat = model.calculate(
        home_passport_flat,
        away_passport_flat,
        home_rating=75.0,
        away_rating=70.0
    )

    print()
    print("=" * 70)
    print("TEST 2 — FLAT SQLITE PASSPORT")
    print("=" * 70)

    print(
        f"xG: "
        f"{result_flat['home_xg']} : "
        f"{result_flat['away_xg']}"
    )

    print(
        f"Version: "
        f"{result_flat['model_version']}"
    )

    print()
    print("Components:")

    for key, value in result_flat["components"].items():

        print(
            f"  {key}: {value}"
        )

    print()
    print("Explanation:")

    for line in result_flat["explanation"]:

        print(
            f"  • {line}"
        )

    print()
    print("=" * 70)

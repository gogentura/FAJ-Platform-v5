#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ XG Model v1.5
=====================================================

РОЛЬ:
    Расчёт ожидаемых голов (xG) на основе Team Passport.

ЦЕПОЧКА:
    Team Passport
        ↓
    FAJ XG Model
        ↓
    home_xg / away_xg
        ↓
    Poisson / Monte Carlo

ПОДДЕРЖИВАЕТ:

    1. Вложенный паспорт:

    {
        "BASE": {...},
        "DYNAMIC_INITIAL": {...}
    }

    2. Плоский паспорт SQLite:

    {
        "attack": 82,
        "defense": 78,
        "control": 80,
        "goalkeeper": 75,
        "form": 55,
        "faj_rating": 85.5
    }

ВАЖНЫЕ ПРИНЦИПЫ:

    - bookmaker odds НЕ используются
    - FAJ Rating НЕ используется напрямую для xG
    - Home Advantage применяется ТОЛЬКО здесь
    - форма влияет на атакующий потенциал
    - защита соперника снижает xG
    - вратарь соперника снижает xG
    - контроль распределяется между командами
    - отсутствующая форма = нейтральный фактор 1.0
    - обязательные паспортные параметры не заменяются
      молча нейтральным значением
    - xG ограничивается единым диапазоном
    - результат совместим с Poisson / Monte Carlo

=====================================================
MODEL CONTRACT
=====================================================

INPUT:

    home_passport: Dict
    away_passport: Dict

    home_rating: float
    away_rating: float

OUTPUT:

    {
        "status": "success",

        "home_xg": float,
        "away_xg": float,

        "components": {...},

        "explanation": [...],

        "model_version": "FAJ_XG_v1.5",

        "timestamp": "..."
    }

=====================================================
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


logger = logging.getLogger(__name__)


class FAJXGModel:
    """
    FAJ Expected Goals Model v1.5

    Центральная задача модели:

        Team Passport → xG

    FAJ Rating здесь используется только
    для диагностики и НЕ является множителем xG.
    """

    VERSION = "1.5"
    MODEL_VERSION = "FAJ_XG_v1.5"

    # ============================================================
    # BASE MODEL
    # ============================================================

    # Среднее количество голов одной команды
    LEAGUE_MEAN_XG = 1.35

    # Базовый уровень силы команды
    POWER_BASE = 70.0

    # ============================================================
    # HOME ADVANTAGE
    # ============================================================

    # Home Advantage применяется ТОЛЬКО здесь.
    #
    # В Passport Manager Home Advantage
    # НЕ должен попадать в FAJ Rating.
    #
    HOME_ADVANTAGE = 1.12

    # ============================================================
    # XG LIMITS
    # ============================================================

    # Эти значения должны совпадать с Poisson Model.
    MIN_XG = 0.10
    MAX_XG = 4.00

    # ============================================================
    # PASSPORT LIMITS
    # ============================================================

    MIN_POWER = 40.0
    MAX_POWER = 100.0

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

    FORM_BASE = 50.0

    MIN_FORM_FACTOR = 0.85
    MAX_FORM_FACTOR = 1.15

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

        home_rating / away_rating:

            только диагностические значения.

        Они НЕ участвуют непосредственно
        в математическом расчёте xG.
        """

        timestamp = datetime.utcnow().isoformat()

        try:

            # ====================================================
            # 1. INPUT VALIDATION
            # ====================================================

            if not isinstance(home_passport, dict):
                raise TypeError(
                    "home_passport must be dict, "
                    f"got {type(home_passport).__name__}"
                )

            if not isinstance(away_passport, dict):
                raise TypeError(
                    "away_passport must be dict, "
                    f"got {type(away_passport).__name__}"
                )

            # ====================================================
            # 2. EXTRACT PASSPORTS
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
            # 3. RATINGS
            # ====================================================

            home_rating = self._safe_float(
                home_rating,
                70.0
            )

            away_rating = self._safe_float(
                away_rating,
                70.0
            )

            home_rating = self._clamp(
                home_rating,
                0.0,
                100.0
            )

            away_rating = self._clamp(
                away_rating,
                0.0,
                100.0
            )

            # ====================================================
            # 4. LOG INPUT
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
                "XG RATINGS DIAGNOSTIC ONLY | "
                "HOME=%.2f AWAY=%.2f",
                home_rating,
                away_rating
            )

            # ====================================================
            # 5. ATTACK FACTORS
            # ====================================================

            home_attack_base = self._attack_factor(
                home["attack"]
            )

            away_attack_base = self._attack_factor(
                away["attack"]
            )

            home_attack_factor = (
                home_attack_base
                * home["form"]
            )

            away_attack_factor = (
                away_attack_base
                * away["form"]
            )

            # ====================================================
            # 6. OPPONENT DEFENSE
            # ====================================================

            away_defense_factor = self._defense_factor(
                away["defense"]
            )

            home_defense_factor = self._defense_factor(
                home["defense"]
            )

            # ====================================================
            # 7. OPPONENT GOALKEEPER
            # ====================================================

            away_keeper_factor = self._keeper_factor(
                away["goalkeeper"]
            )

            home_keeper_factor = self._keeper_factor(
                home["goalkeeper"]
            )

            # ====================================================
            # 8. CONTROL
            # ====================================================

            (
                home_control_factor,
                away_control_factor
            ) = self._control_factors(
                home["control"],
                away["control"]
            )

            # ====================================================
            # 9. HOME ADVANTAGE
            # ====================================================

            home_bonus = self.HOME_ADVANTAGE

            # ====================================================
            # 10. RAW XG
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
            # 11. CLAMP XG
            # ====================================================

            home_xg = self._clamp_xg(
                home_xg_raw
            )

            away_xg = self._clamp_xg(
                away_xg_raw
            )

            # ====================================================
            # 12. COMPONENTS
            # ====================================================

            components = {

                # -----------------------------
                # Passport input
                # -----------------------------

                "home_attack": round(
                    home["attack"], 2
                ),

                "away_attack": round(
                    away["attack"], 2
                ),

                "home_defense": round(
                    home["defense"], 2
                ),

                "away_defense": round(
                    away["defense"], 2
                ),

                "home_control": round(
                    home["control"], 2
                ),

                "away_control": round(
                    away["control"], 2
                ),

                "home_goalkeeper": round(
                    home["goalkeeper"], 2
                ),

                "away_goalkeeper": round(
                    away["goalkeeper"], 2
                ),

                # -----------------------------
                # Form
                # -----------------------------

                "home_form": round(
                    home["form_raw"], 2
                ),

                "away_form": round(
                    away["form_raw"], 2
                ),

                "home_form_factor": round(
                    home["form"], 3
                ),

                "away_form_factor": round(
                    away["form"], 3
                ),

                # -----------------------------
                # Attack
                # -----------------------------

                "home_attack_base_factor": round(
                    home_attack_base, 3
                ),

                "away_attack_base_factor": round(
                    away_attack_base, 3
                ),

                "home_attack_factor": round(
                    home_attack_factor, 3
                ),

                "away_attack_factor": round(
                    away_attack_factor, 3
                ),

                # -----------------------------
                # Defense
                # -----------------------------

                "home_defense_factor": round(
                    home_defense_factor, 3
                ),

                "away_defense_factor": round(
                    away_defense_factor, 3
                ),

                # -----------------------------
                # Goalkeeper
                # -----------------------------

                "home_keeper_factor": round(
                    home_keeper_factor, 3
                ),

                "away_keeper_factor": round(
                    away_keeper_factor, 3
                ),

                # -----------------------------
                # Control
                # -----------------------------

                "home_control_factor": round(
                    home_control_factor, 3
                ),

                "away_control_factor": round(
                    away_control_factor, 3
                ),

                # -----------------------------
                # Home Advantage
                # -----------------------------

                "home_advantage": round(
                    home_bonus,
                    3
                ),

                # Compatibility alias
                "home_bonus": round(
                    home_bonus,
                    3
                ),

                # -----------------------------
                # Ratings
                # -----------------------------

                "home_rating": round(
                    home_rating,
                    2
                ),

                "away_rating": round(
                    away_rating,
                    2
                ),

                "rating_used_for_xg": False,

                # -----------------------------
                # Base
                # -----------------------------

                "league_mean_xg": round(
                    self.LEAGUE_MEAN_XG,
                    3
                ),

                "power_base": round(
                    self.POWER_BASE,
                    2
                ),

                # -----------------------------
                # Raw
                # -----------------------------

                "home_xg_raw": round(
                    home_xg_raw,
                    5
                ),

                "away_xg_raw": round(
                    away_xg_raw,
                    5
                ),

                # -----------------------------
                # Final
                # -----------------------------

                "home_xg": round(
                    home_xg,
                    3
                ),

                "away_xg": round(
                    away_xg,
                    3
                )
            }

            # ====================================================
            # 13. EXPLANATION
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
            # 14. RESULT
            # ====================================================

            result = {

                "status": "success",

                "home_xg": round(
                    home_xg,
                    3
                ),

                "away_xg": round(
                    away_xg,
                    3
                ),

                "components": components,

                "explanation": explanation,

                "model_version": self.MODEL_VERSION,

                "timestamp": timestamp
            }

            logger.info(
                "XG RESULT | %.3f : %.3f",
                home_xg,
                away_xg
            )

            return result

        except Exception as exc:

            logger.exception(
                "FAJ XG calculation error"
            )

            return {

                "status": "error",

                "message": str(exc),

                "home_xg": 0.0,

                "away_xg": 0.0,

                "components": {},

                "explanation": [],

                "model_version": self.MODEL_VERSION,

                "timestamp": timestamp
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

        Приоритет:

            BASE
            ↓
            верхний уровень
            ↓
            DYNAMIC

        Поддерживает:

            BASE
            base
            team_base

            DYNAMIC_INITIAL
            dynamic_initial
            DYNAMIC
            dynamic
            team_dynamic

        Обязательные поля:

            attack
            defense
            control
            goalkeeper

        Form:

            необязательная.

        Если form отсутствует:

            form factor = 1.0
        """

        if not isinstance(
            passport,
            dict
        ):
            raise TypeError(
                f"{side} passport must be dict"
            )

        # ========================================================
        # BASE
        # ========================================================

        base = None

        for key in (
            "BASE",
            "base",
            "team_base"
        ):

            value = passport.get(
                key
            )

            if isinstance(
                value,
                dict
            ):

                base = value
                break

        # ========================================================
        # DYNAMIC
        # ========================================================

        dynamic = {}

        for key in (
            "DYNAMIC_INITIAL",
            "dynamic_initial",
            "DYNAMIC",
            "dynamic",
            "team_dynamic"
        ):

            value = passport.get(
                key
            )

            if isinstance(
                value,
                dict
            ):

                dynamic = value
                break

        # ========================================================
        # FIND VALUE
        # ========================================================

        def find_value(
            field: str,
            default=None
        ):

            if (
                base is not None
                and field in base
            ):

                return base[field]

            if field in passport:
                return passport[field]

            if field in dynamic:
                return dynamic[field]

            return default

        # ========================================================
        # REQUIRED
        # ========================================================

        attack = find_value(
            "attack"
        )

        defense = find_value(
            "defense"
        )

        control = find_value(
            "control"
        )

        goalkeeper = find_value(
            "goalkeeper"
        )

        if goalkeeper is None:

            goalkeeper = find_value(
                "keeper"
            )

        # ========================================================
        # VALIDATION
        # ========================================================

        missing = []

        if attack is None:
            missing.append(
                "attack"
            )

        if defense is None:
            missing.append(
                "defense"
            )

        if control is None:
            missing.append(
                "control"
            )

        if goalkeeper is None:
            missing.append(
                "goalkeeper"
            )

        if missing:

            logger.error(
                "XG PASSPORT ERROR | "
                "%s | missing=%s | keys=%s",
                side,
                ",".join(missing),
                list(passport.keys())
            )

            raise ValueError(
                f"{side} passport missing "
                f"required fields: "
                f"{', '.join(missing)}"
            )

        # ========================================================
        # FORM
        # ========================================================

        raw_form = find_value(
            "form",
            None
        )

        if raw_form is None:

            form_raw = 50.0
            form_factor = 1.0

        else:

            try:

                form_raw = float(
                    raw_form
                )

            except (
                TypeError,
                ValueError
            ):

                form_raw = 50.0

            form_raw = self._clamp(
                form_raw,
                0.0,
                100.0
            )

            form_factor = self._form_factor(
                form_raw
            )

        # ========================================================
        # CLAMP PASSPORT PARAMETERS
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

        # ========================================================
        # LOG
        # ========================================================

        logger.info(
            "XG PASSPORT %s | "
            "attack=%.2f "
            "defense=%.2f "
            "control=%.2f "
            "goalkeeper=%.2f "
            "form=%.2f "
            "form_factor=%.3f",
            side,
            attack,
            defense,
            control,
            goalkeeper,
            form_raw,
            form_factor
        )

        # ========================================================
        # RETURN
        # ========================================================

        return {

            "attack": attack,

            "defense": defense,

            "control": control,

            "goalkeeper": goalkeeper,

            "form_raw": form_raw,

            "form": form_factor
        }

    # ============================================================
    # ATTACK
    # ============================================================

    def _attack_factor(
        self,
        attack_power: float
    ) -> float:
        """
        Атака относительно POWER_BASE.

        70 → 1.00
        80 → 1.143
        60 → 0.857
        """

        return (
            attack_power
            / self.POWER_BASE
        )

    # ============================================================
    # DEFENSE
    # ============================================================

    def _defense_factor(
        self,
        defense_power: float
    ) -> float:
        """
        Сильная защита соперника
        снижает xG.

        70 → 1.000
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
        Сильный вратарь соперника
        снижает xG.

        70 → 1.000
        80 → 0.875
        90 → 0.850
        60 → 1.150
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
    # FORM
    # ============================================================

    def _form_factor(
        self,
        form: Any
    ) -> float:
        """
        Форма 0–100 → коэффициент.

        50 → 1.00
        60 → 1.15
        40 → 0.85

        Ограничение:

            0.85 – 1.15
        """

        try:

            value = float(
                form
            )

        except (
            TypeError,
            ValueError
        ):

            return 1.0

        if value <= 0:
            return 1.0

        factor = (
            value
            / self.FORM_BASE
        )

        return max(
            self.MIN_FORM_FACTOR,
            min(
                self.MAX_FORM_FACTOR,
                factor
            )
        )

    # ============================================================
    # CONTROL
    # ============================================================

    def _control_factors(
        self,
        home_control: float,
        away_control: float
    ) -> Tuple[float, float]:
        """
        Контроль распределяется
        между командами.

        Например:

            Home = 80
            Away = 60

        Home получает небольшой плюс.
        Away получает небольшой минус.

        CONTROL_WEIGHT пока является
        калибруемым параметром.
        """

        diff = (
            home_control
            - away_control
        )

        home_factor = (
            1.0
            + (
                diff / 100.0
            )
            * self.CONTROL_WEIGHT
        )

        away_factor = (
            1.0
            - (
                diff / 100.0
            )
            * self.CONTROL_WEIGHT
        )

        home_factor = max(
            self.MIN_CONTROL_FACTOR,
            min(
                self.MAX_CONTROL_FACTOR,
                home_factor
            )
        )

        away_factor = max(
            self.MIN_CONTROL_FACTOR,
            min(
                self.MAX_CONTROL_FACTOR,
                away_factor
            )
        )

        return (
            home_factor,
            away_factor
        )

    # ============================================================
    # SAFE FLOAT
    # ============================================================

    def _safe_float(
        self,
        value: Any,
        default: float
    ) -> float:

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            return default

    # ============================================================
    # CLAMP VALUE
    # ============================================================

    def _clamp_value(
        self,
        value: Any,
        min_val: float,
        max_val: float
    ) -> float:

        try:

            value = float(
                value
            )

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                f"Invalid passport value: "
                f"{value}"
            )

        return max(
            min_val,
            min(
                max_val,
                value
            )
        )

    # ============================================================
    # GENERIC CLAMP
    # ============================================================

    def _clamp(
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
    # XG CLAMP
    # ============================================================

    def _clamp_xg(
        self,
        value: float
    ) -> float:

        return self._clamp(
            value,
            self.MIN_XG,
            self.MAX_XG
        )

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

        # ========================================================
        # ATTACK
        # ========================================================

        if home_attack_factor >= 1.10:

            explanation.append(
                "Атака хозяев выше средней "
                f"({home_attack_factor:.2f}x)"
            )

        elif home_attack_factor <= 0.90:

            explanation.append(
                "Атака хозяев ниже средней "
                f"({home_attack_factor:.2f}x)"
            )

        if away_attack_factor >= 1.10:

            explanation.append(
                "Атака гостей выше средней "
                f"({away_attack_factor:.2f}x)"
            )

        elif away_attack_factor <= 0.90:

            explanation.append(
                "Атака гостей ниже средней "
                f"({away_attack_factor:.2f}x)"
            )

        # ========================================================
        # DEFENSE
        # ========================================================

        if away_defense_factor < 0.90:

            explanation.append(
                "Сильная защита гостей "
                "снижает xG хозяев"
            )

        elif away_defense_factor > 1.10:

            explanation.append(
                "Слабая защита гостей "
                "повышает xG хозяев"
            )

        if home_defense_factor < 0.90:

            explanation.append(
                "Сильная защита хозяев "
                "снижает xG гостей"
            )

        elif home_defense_factor > 1.10:

            explanation.append(
                "Слабая защита хозяев "
                "повышает xG гостей"
            )

        # ========================================================
        # GOALKEEPER
        # ========================================================

        if away_keeper_factor < 0.90:

            explanation.append(
                "Сильный вратарь гостей "
                "снижает xG хозяев"
            )

        elif away_keeper_factor > 1.10:

            explanation.append(
                "Слабый вратарь гостей "
                "повышает xG хозяев"
            )

        if home_keeper_factor < 0.90:

            explanation.append(
                "Сильный вратарь хозяев "
                "снижает xG гостей"
            )

        elif home_keeper_factor > 1.10:

            explanation.append(
                "Слабый вратарь хозяев "
                "повышает xG гостей"
            )

        # ========================================================
        # CONTROL
        # ========================================================

        if home_control_factor > 1.05:

            explanation.append(
                "Контроль даёт преимущество "
                f"хозяев ({home_control_factor:.2f}x)"
            )

        elif away_control_factor > 1.05:

            explanation.append(
                "Контроль даёт преимущество "
                f"гостей ({away_control_factor:.2f}x)"
            )

        # ========================================================
        # FORM
        # ========================================================

        if home["form"] > 1.05:

            explanation.append(
                "Форма хозяев повышает "
                "атакующий потенциал "
                f"({home['form']:.2f}x)"
            )

        elif home["form"] < 0.95:

            explanation.append(
                "Форма хозяев снижает "
                "атакующий потенциал "
                f"({home['form']:.2f}x)"
            )

        if away["form"] > 1.05:

            explanation.append(
                "Форма гостей повышает "
                "атакующий потенциал "
                f"({away['form']:.2f}x)"
            )

        elif away["form"] < 0.95:

            explanation.append(
                "Форма гостей снижает "
                "атакующий потенциал "
                f"({away['form']:.2f}x)"
            )

        # ========================================================
        # HOME ADVANTAGE
        # ========================================================

        explanation.append(
            "Домашнее преимущество: "
            f"{self.HOME_ADVANTAGE:.2f}x"
        )

        # ========================================================
        # RATING
        # ========================================================

        explanation.append(
            "FAJ Rating используется "
            "только для диагностики и "
            "не является множителем xG"
        )

        # ========================================================
        # FINAL
        # ========================================================

        explanation.append(
            f"Ожидаемые голы: "
            f"{home_xg:.2f} : {away_xg:.2f}"
        )

        return explanation

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:

        return {

            "model": "FAJ XG Model",

            "version": self.VERSION,

            "model_version": self.MODEL_VERSION,

            "league_mean_xg": self.LEAGUE_MEAN_XG,

            "home_advantage": self.HOME_ADVANTAGE,

            "xg_range": [
                self.MIN_XG,
                self.MAX_XG
            ],

            "power_base": self.POWER_BASE,

            "control_weight": self.CONTROL_WEIGHT,

            "rating_used_for_xg": False,

            "status": "READY"
        }

    # ============================================================
    # TEST
    # ============================================================

    def test(self) -> Dict[str, Any]:

        home_passport = {

            "attack": 82,

            "defense": 78,

            "control": 80,

            "goalkeeper": 75,

            "form": 55,

            "faj_rating": 82.5
        }

        away_passport = {

            "attack": 74,

            "defense": 81,

            "control": 76,

            "goalkeeper": 79,

            "form": 48,

            "faj_rating": 76.5
        }

        return self.calculate(

            home_passport,

            away_passport,

            home_rating=82.5,

            away_rating=76.5
        )


# ================================================================
# COMPATIBILITY ALIAS
# ================================================================

XGModel = FAJXGModel


# ================================================================
# SINGLETON
# ================================================================

_xg_model_instance: Optional[
    FAJXGModel
] = None


def get_xg_model() -> FAJXGModel:

    global _xg_model_instance

    if _xg_model_instance is None:

        _xg_model_instance = (
            FAJXGModel()
        )

    return _xg_model_instance


# ================================================================
# LOCAL TEST
# ================================================================

if __name__ == "__main__":

    model = FAJXGModel()

    print()
    print("=" * 70)
    print("FAJ XG MODEL v1.5")
    print("=" * 70)

    print()
    print("STATUS")
    print("-" * 70)

    print(
        model.status()
    )

    print()
    print("TEST")
    print("-" * 70)

    result = model.test()

    print(
        f"xG: "
        f"{result['home_xg']:.3f} : "
        f"{result['away_xg']:.3f}"
    )

    print()
    print("COMPONENTS")
    print("-" * 70)

    for key, value in result[
        "components"
    ].items():

        print(
            f"{key}: {value}"
        )

    print()
    print("EXPLANATION")
    print("-" * 70)

    for line in result[
        "explanation"
    ]:

        print(
            f"• {line}"
        )

    print()
    print(
        f"MODEL: "
        f"{result['model_version']}"
    )

    print()
    print("=" * 70)
    print("XG MODEL TEST COMPLETED")
    print("=" * 70)

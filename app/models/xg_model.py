#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ XG Model v2.0
============================================================

ФАЙЛ:
    app/models/xg_model.py

РОЛЬ:
    Расчёт ожидаемых голов (xG) для предматчевого прогноза.

АРХИТЕКТУРА:

    TEAM PASSPORT
         │
         ├── attack
         ├── defense
         ├── goalkeeper
         ├── control
         └── form
         │
         ▼
    FAJ XG MODEL
         │
         ├── home_xg
         └── away_xg
         │
         ▼
    POISSON
         │
         ▼
    FINAL PROBABILITIES

============================================================
ПРИНЦИП
============================================================

FAJ Rating НЕ является отдельным множителем xG.

xG строится из игровых компонентов паспорта:

    ATTACK
    DEFENSE
    GOALKEEPER
    CONTROL
    FORM

Home Advantage применяется только к хозяевам.

============================================================
ОСНОВНАЯ ФОРМУЛА
============================================================

Home xG = League Mean
        × Home Attack
        × Away Defense
        × Away Goalkeeper
        × Home Control
        × Home Form
        × Home Advantage

Away xG = League Mean
        × Away Attack
        × Home Defense
        × Home Goalkeeper
        × Away Control
        × Away Form

============================================================
ВАЖНО
============================================================

1. FAJ Rating не участвует напрямую в xG.
2. Prediction xG отделён от Observed xG.
3. Модель не использует результаты будущего матча.
4. Модель детерминирована.
5. Нет JSON-конфигурации.
6. Параметры берутся из Config там, где это возможно.
7. Некорректный паспорт не должен приводить к crash.
8. Ограничение xG применяется только после расчёта.
9. Факторы не должны искусственно схлопывать команды
   в диапазон 0.85–1.15.
10. Модель не занимается Poisson / Monte Carlo.
============================================================
"""

from __future__ import annotations

import logging
import math

from typing import Any, Dict, Optional, Tuple

from app.config import config


logger = logging.getLogger(__name__)


class XGModel:
    """
    FAJ XG Model v2.0

    Рассчитывает предматчевый xG на основе Team Passport.

    Ответственность модели:
        passport -> xG

    Не входит в ответственность:
        xG -> Poisson
        xG -> Monte Carlo
        xG -> learning
        xG -> rating
    """

    VERSION = "2.0"
    MODEL_VERSION = "FAJ_XG_v2.0"

    # ============================================================
    # BASE MODEL
    # ============================================================

    LEAGUE_MEAN_XG = config.XG_LEAGUE_MEAN
    HOME_ADVANTAGE = config.HOME_ADVANTAGE

    XG_MIN = config.XG_MIN
    XG_MAX = config.XG_MAX

    # ============================================================
    # PASSPORT SCALE
    # ============================================================

    PASSPORT_MIN = 0.0
    PASSPORT_MAX = 100.0

    # ============================================================
    # COMPONENT CENTERS
    # ============================================================

    # Значение 50 = нейтральный уровень.
    #
    # 50 -> фактор 1.00
    #
    # Значения выше 50:
    #     усиливают компонент
    #
    # Значения ниже 50:
    #     ослабляют компонент

    CENTER = 50.0

    # ============================================================
    # FACTOR SENSITIVITY
    # ============================================================

    # Сила влияния компонента.
    #
    # Это НЕ жёсткий диапазон факторов.
    #
    # Формула:
    #
    #     factor = exp((value - 50) * sensitivity / 50)
    #
    # После этого применяется безопасный диапазон.

    ATTACK_SENSITIVITY = 0.28
    DEFENSE_SENSITIVITY = 0.24
    GOALKEEPER_SENSITIVITY = 0.14
    CONTROL_SENSITIVITY = 0.12
    FORM_SENSITIVITY = 0.12

    # ============================================================
    # FACTOR SAFETY LIMITS
    # ============================================================

    FACTOR_MIN = 0.70
    FACTOR_MAX = 1.30

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self) -> None:

        self.version = self.VERSION
        self.model_version = self.MODEL_VERSION

        logger.info(
            "FAJ XG Model v%s initialized | "
            "league_mean=%.3f | "
            "home_advantage=%.3f | "
            "xg_range=%.2f-%.2f",
            self.VERSION,
            self.LEAGUE_MEAN_XG,
            self.HOME_ADVANTAGE,
            self.XG_MIN,
            self.XG_MAX,
        )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float = 50.0,
        away_rating: float = 50.0,
    ) -> Dict[str, Any]:
        """
        Рассчитывает предматчевый xG.

        home_rating / away_rating сохраняются только
        для диагностической совместимости.

        Rating НЕ участвует в математике xG.
        """

        try:

            # ====================================================
            # 1. EXTRACT PASSPORT
            # ====================================================

            home = self._extract_team_parameters(
                home_passport
            )

            away = self._extract_team_parameters(
                away_passport
            )

            # ====================================================
            # 2. COMPONENT VALUES
            # ====================================================

            home_attack = home["attack"]
            home_defense = home["defense"]
            home_control = home["control"]
            home_goalkeeper = home["goalkeeper"]
            home_form = home["form"]

            away_attack = away["attack"]
            away_defense = away["defense"]
            away_control = away["control"]
            away_goalkeeper = away["goalkeeper"]
            away_form = away["form"]

            # ====================================================
            # 3. COMPONENT FACTORS
            # ====================================================

            home_attack_factor = self._attack_factor(
                home_attack
            )

            away_attack_factor = self._attack_factor(
                away_attack
            )

            home_defense_factor = self._defense_factor(
                home_defense
            )

            away_defense_factor = self._defense_factor(
                away_defense
            )

            home_keeper_factor = self._goalkeeper_factor(
                home_goalkeeper
            )

            away_keeper_factor = self._goalkeeper_factor(
                away_goalkeeper
            )

            # ====================================================
            # CONTROL
            # ====================================================

            (
                home_control_factor,
                away_control_factor,
            ) = self._control_factors(
                home_control,
                away_control,
            )

            # ====================================================
            # FORM
            # ====================================================

            home_form_factor = self._form_factor(
                home_form
            )

            away_form_factor = self._form_factor(
                away_form
            )

            # ====================================================
            # 4. RAW XG
            # ====================================================

            home_xg_raw = (
                self.LEAGUE_MEAN_XG
                * home_attack_factor
                * away_defense_factor
                * away_keeper_factor
                * home_control_factor
                * home_form_factor
                * self.HOME_ADVANTAGE
            )

            away_xg_raw = (
                self.LEAGUE_MEAN_XG
                * away_attack_factor
                * home_defense_factor
                * home_keeper_factor
                * away_control_factor
                * away_form_factor
            )

            # ====================================================
            # 5. SANITIZE
            # ====================================================

            home_xg = self._clamp_xg(
                home_xg_raw
            )

            away_xg = self._clamp_xg(
                away_xg_raw
            )

            # ====================================================
            # 6. DIAGNOSTICS
            # ====================================================

            components = {
                "home_attack_factor": round(
                    home_attack_factor,
                    4,
                ),
                "away_attack_factor": round(
                    away_attack_factor,
                    4,
                ),

                "home_defense_factor": round(
                    home_defense_factor,
                    4,
                ),
                "away_defense_factor": round(
                    away_defense_factor,
                    4,
                ),

                "home_keeper_factor": round(
                    home_keeper_factor,
                    4,
                ),
                "away_keeper_factor": round(
                    away_keeper_factor,
                    4,
                ),

                "home_control_factor": round(
                    home_control_factor,
                    4,
                ),
                "away_control_factor": round(
                    away_control_factor,
                    4,
                ),

                "home_form_factor": round(
                    home_form_factor,
                    4,
                ),
                "away_form_factor": round(
                    away_form_factor,
                    4,
                ),

                "home_advantage": round(
                    self.HOME_ADVANTAGE,
                    4,
                ),

                "home_rating": self._safe_rating(
                    home_rating
                ),

                "away_rating": self._safe_rating(
                    away_rating
                ),

                "rating_used_for_xg": False,
            }

            diagnostic = {
                "home_attack": round(
                    home_attack,
                    2,
                ),
                "home_defense": round(
                    home_defense,
                    2,
                ),
                "home_control": round(
                    home_control,
                    2,
                ),
                "home_goalkeeper": round(
                    home_goalkeeper,
                    2,
                ),
                "home_form": round(
                    home_form,
                    2,
                ),

                "away_attack": round(
                    away_attack,
                    2,
                ),
                "away_defense": round(
                    away_defense,
                    2,
                ),
                "away_control": round(
                    away_control,
                    2,
                ),
                "away_goalkeeper": round(
                    away_goalkeeper,
                    2,
                ),
                "away_form": round(
                    away_form,
                    2,
                ),

                "home_xg_raw": round(
                    home_xg_raw,
                    4,
                ),
                "away_xg_raw": round(
                    away_xg_raw,
                    4,
                ),

                "home_xg": round(
                    home_xg,
                    3,
                ),
                "away_xg": round(
                    away_xg,
                    3,
                ),
            }

            logger.debug(
                "FAJ XG calculated | "
                "home_xg=%.3f | away_xg=%.3f | "
                "raw_home=%.3f | raw_away=%.3f",
                home_xg,
                away_xg,
                home_xg_raw,
                away_xg_raw,
            )

            # ====================================================
            # 7. RESULT
            # ====================================================

            return {
                "status": "success",

                "home_xg": round(
                    home_xg,
                    3,
                ),

                "away_xg": round(
                    away_xg,
                    3,
                ),

                "components": components,

                "diagnostic": diagnostic,

                "model_version": self.MODEL_VERSION,
            }

        except Exception as exc:

            logger.error(
                "XG calculation error: %s",
                exc,
                exc_info=True,
            )

            return {
                "status": "error",
                "message": str(exc),

                "home_xg": self.LEAGUE_MEAN_XG,
                "away_xg": self.LEAGUE_MEAN_XG,

                "components": {},

                "diagnostic": {},

                "model_version": self.MODEL_VERSION,
            }

    # ============================================================
    # PASSPORT EXTRACTION
    # ============================================================

    def _extract_team_parameters(
        self,
        passport: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Извлекает параметры из плоского Team Passport.

        Ожидается:

            attack
            defense
            control
            goalkeeper
            form

        Отсутствующие значения получают нейтральный уровень 50.

        Это важно:
        отсутствие данных НЕ превращается в сильную команду
        или слабую команду.
        """

        params = {
            "attack": self.CENTER,
            "defense": self.CENTER,
            "control": self.CENTER,
            "goalkeeper": self.CENTER,
            "form": self.CENTER,
        }

        if not isinstance(
            passport,
            dict,
        ):

            logger.warning(
                "Passport is not dict: %s",
                type(passport),
            )

            return params

        for key in params:

            value = passport.get(
                key
            )

            if value is None:
                continue

            try:

                value = float(value)

                if not math.isfinite(
                    value
                ):
                    raise ValueError(
                        "non-finite value"
                    )

                params[key] = self._clamp_passport_value(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):

                logger.warning(
                    "Invalid passport value | "
                    "field=%s | value=%r",
                    key,
                    value,
                )

        return params

    # ============================================================
    # PASSPORT CLAMP
    # ============================================================

    def _clamp_passport_value(
        self,
        value: float,
    ) -> float:

        return max(
            self.PASSPORT_MIN,
            min(
                self.PASSPORT_MAX,
                value,
            ),
        )

    # ============================================================
    # GENERIC FACTOR
    # ============================================================

    def _factor(
        self,
        value: float,
        sensitivity: float,
    ) -> float:
        """
        Преобразование значения паспорта 0–100
        в multiplicative factor.

        50 -> 1.00

        В отличие от старой модели:

            attack / 70
            70 / defense

        здесь все компоненты имеют общий нейтральный центр.

        Это делает модель математически более стабильной.
        """

        value = self._clamp_passport_value(
            value
        )

        delta = (
            value - self.CENTER
        ) / self.CENTER

        factor = math.exp(
            delta * sensitivity
        )

        return self._clamp_factor(
            factor
        )

    # ============================================================
    # ATTACK
    # ============================================================

    def _attack_factor(
        self,
        attack: float,
    ) -> float:

        return self._factor(
            attack,
            self.ATTACK_SENSITIVITY,
        )

    # ============================================================
    # DEFENSE
    # ============================================================

    def _defense_factor(
        self,
        defense: float,
    ) -> float:
        """
        Сильная защита соперника должна уменьшать xG.

        Поэтому для противостоящей защиты
        используется обратное направление:

            defense = 50 -> 1.00
            defense > 50 -> factor < 1
            defense < 50 -> factor > 1
        """

        value = self._clamp_passport_value(
            defense
        )

        delta = (
            self.CENTER - value
        ) / self.CENTER

        factor = math.exp(
            delta * self.DEFENSE_SENSITIVITY
        )

        return self._clamp_factor(
            factor
        )

    # ============================================================
    # GOALKEEPER
    # ============================================================

    def _goalkeeper_factor(
        self,
        goalkeeper: float,
    ) -> float:
        """
        Сильный вратарь соперника уменьшает xG.
        """

        value = self._clamp_passport_value(
            goalkeeper
        )

        delta = (
            self.CENTER - value
        ) / self.CENTER

        factor = math.exp(
            delta * self.GOALKEEPER_SENSITIVITY
        )

        return self._clamp_factor(
            factor
        )

    # ============================================================
    # FORM
    # ============================================================

    def _form_factor(
        self,
        form: float,
    ) -> float:

        return self._factor(
            form,
            self.FORM_SENSITIVITY,
        )

    # ============================================================
    # CONTROL
    # ============================================================

    def _control_factors(
        self,
        home_control: float,
        away_control: float,
    ) -> Tuple[float, float]:
        """
        Контроль рассчитывается относительно соперника.

        Разница:

            home_control - away_control

        влияет на распределение xG.

        Важно:
        контроль не должен самостоятельно создавать голы.
        Поэтому влияние ограничено.
        """

        home_control = self._clamp_passport_value(
            home_control
        )

        away_control = self._clamp_passport_value(
            away_control
        )

        diff = (
            home_control
            - away_control
        )

        normalized_diff = (
            diff / self.PASSPORT_MAX
        )

        home_factor = math.exp(
            normalized_diff
            * self.CONTROL_SENSITIVITY
        )

        away_factor = math.exp(
            -normalized_diff
            * self.CONTROL_SENSITIVITY
        )

        return (
            self._clamp_factor(
                home_factor
            ),
            self._clamp_factor(
                away_factor
            ),
        )

    # ============================================================
    # FACTOR CLAMP
    # ============================================================

    def _clamp_factor(
        self,
        factor: float,
    ) -> float:

        if not math.isfinite(
            factor
        ):

            return 1.0

        return max(
            self.FACTOR_MIN,
            min(
                self.FACTOR_MAX,
                factor,
            ),
        )

    # ============================================================
    # XG CLAMP
    # ============================================================

    def _clamp_xg(
        self,
        value: float,
    ) -> float:

        if not math.isfinite(
            value
        ):

            return self.LEAGUE_MEAN_XG

        return max(
            self.XG_MIN,
            min(
                self.XG_MAX,
                value,
            ),
        )

    # ============================================================
    # RATING — DIAGNOSTIC ONLY
    # ============================================================

    def _safe_rating(
        self,
        value: Any,
    ) -> float:

        try:

            value = float(value)

            if not math.isfinite(
                value
            ):
                return 50.0

            return round(
                value,
                2,
            )

        except (
            TypeError,
            ValueError,
        ):

            return 50.0

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:

        return {
            "model": self.MODEL_VERSION,
            "version": self.VERSION,

            "league_mean_xg": self.LEAGUE_MEAN_XG,

            "home_advantage": self.HOME_ADVANTAGE,

            "xg_range": [
                self.XG_MIN,
                self.XG_MAX,
            ],

            "factor_range": [
                self.FACTOR_MIN,
                self.FACTOR_MAX,
            ],

            "passport_scale": [
                self.PASSPORT_MIN,
                self.PASSPORT_MAX,
            ],

            "rating_used_for_xg": False,

            "status": "READY",
        }


# ================================================================
# SINGLETON
# ================================================================

_xg_model_instance: Optional[XGModel] = None


def get_xg_model() -> XGModel:

    global _xg_model_instance

    if _xg_model_instance is None:

        _xg_model_instance = XGModel()

    return _xg_model_instance

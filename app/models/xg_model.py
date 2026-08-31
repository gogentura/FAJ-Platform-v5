#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ XG Model v2.2
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

FAJ Rating УЧАСТВУЕТ в математике xG (начиная с v2.2).

xG строится из игровых компонентов паспорта + рейтинга:

    ATTACK
    DEFENSE
    GOALKEEPER
    CONTROL
    FORM
    RATING

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
        × Home Rating Factor

Away xG = League Mean
        × Away Attack
        × Home Defense
        × Home Goalkeeper
        × Away Control
        × Away Form
        × Away Rating Factor

============================================================
ИСПРАВЛЕНИЯ v2.2
============================================================

1. Добавлен RATING как математический фактор xG
2. Добавлен параметр rating_sensitivity
3. rating_used_for_xg = True
4. Обновлён список learnable_parameters

ИСПРАВЛЕНИЯ v2.1
============================================================

1. Добавлен параметр parameters в calculate()
2. Динамическая attack_sensitivity (с fallback на ATTACK_SENSITIVITY)
3. Динамическая defense_sensitivity (с fallback на DEFENSE_SENSITIVITY)
4. Динамическая control_sensitivity (с fallback на CONTROL_SENSITIVITY)
5. Динамическая form_sensitivity (с fallback на FORM_SENSITIVITY)
6. Добавлен parameters_used в результат
7. Сохранена обратная совместимость (sensitivity=None → static)
8. Goalkeeper пока остаётся статическим (не обучаем)

ВАЖНО
============================================================

1. Prediction xG отделён от Observed xG.
2. Модель не использует результаты будущего матча.
3. Модель детерминирована.
4. Нет JSON-конфигурации.
5. Параметры берутся из Config там, где это возможно.
6. Некорректный паспорт не должен приводить к crash.
7. Ограничение xG применяется только после расчёта.
8. Факторы не должны искусственно схлопывать команды
   в диапазон 0.85–1.15.
9. Модель не занимается Poisson / Monte Carlo.
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
    FAJ XG Model v2.2

    Рассчитывает предматчевый xG на основе Team Passport и Rating.

    Ответственность модели:
        passport + rating -> xG

    Не входит в ответственность:
        xG -> Poisson
        xG -> Monte Carlo
        xG -> learning
    """

    VERSION = "2.2"
    MODEL_VERSION = "FAJ_XG_v2.2"

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
    # FACTOR SENSITIVITY (STATIC DEFAULTS)
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
    # RATING SENSITIVITY (НОВОЕ v2.2)
    # ============================================================

    RATING_BASELINE = 1500.0  # нейтральный уровень рейтинга
    RATING_SENSITIVITY = 0.15  # ±100 рейтинга → ±15% xG

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
            "xg_range=%.2f-%.2f | "
            "rating_baseline=%.1f | "
            "rating_sensitivity=%.3f",
            self.VERSION,
            self.LEAGUE_MEAN_XG,
            self.HOME_ADVANTAGE,
            self.XG_MIN,
            self.XG_MAX,
            self.RATING_BASELINE,
            self.RATING_SENSITIVITY,
        )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float = 1500.0,
        away_rating: float = 1500.0,
        parameters: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Рассчитывает предматчевый xG.

        home_rating / away_rating УЧАСТВУЮТ в математике xG (v2.2).

        Args:
            parameters: словарь с параметрами модели
                - attack_sensitivity: float (default 0.28)
                - defense_sensitivity: float (default 0.24)
                - control_sensitivity: float (default 0.12)
                - form_sensitivity: float (default 0.12)
                - rating_sensitivity: float (default 0.15)  # НОВОЕ v2.2
        """

        # ============================================================
        # НОРМАЛИЗАЦИЯ ПАРАМЕТРОВ
        # ============================================================

        parameters = parameters or {}

        attack_sensitivity = float(
            parameters.get(
                "attack_sensitivity",
                self.ATTACK_SENSITIVITY,
            )
        )

        defense_sensitivity = float(
            parameters.get(
                "defense_sensitivity",
                self.DEFENSE_SENSITIVITY,
            )
        )

        control_sensitivity = float(
            parameters.get(
                "control_sensitivity",
                self.CONTROL_SENSITIVITY,
            )
        )

        form_sensitivity = float(
            parameters.get(
                "form_sensitivity",
                self.FORM_SENSITIVITY,
            )
        )

        rating_sensitivity = float(
            parameters.get(
                "rating_sensitivity",
                self.RATING_SENSITIVITY,
            )
        )

        # Goalkeeper пока статический (не обучаем)
        goalkeeper_sensitivity = self.GOALKEEPER_SENSITIVITY

        parameters_used = {
            "attack_sensitivity": round(attack_sensitivity, 6),
            "defense_sensitivity": round(defense_sensitivity, 6),
            "control_sensitivity": round(control_sensitivity, 6),
            "form_sensitivity": round(form_sensitivity, 6),
            "rating_sensitivity": round(rating_sensitivity, 6),  # НОВОЕ v2.2
            "goalkeeper_sensitivity": round(goalkeeper_sensitivity, 6),
        }

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
                home_attack,
                sensitivity=attack_sensitivity,
            )

            away_attack_factor = self._attack_factor(
                away_attack,
                sensitivity=attack_sensitivity,
            )

            home_defense_factor = self._defense_factor(
                home_defense,
                sensitivity=defense_sensitivity,
            )

            away_defense_factor = self._defense_factor(
                away_defense,
                sensitivity=defense_sensitivity,
            )

            home_keeper_factor = self._goalkeeper_factor(
                home_goalkeeper,
                sensitivity=goalkeeper_sensitivity,
            )

            away_keeper_factor = self._goalkeeper_factor(
                away_goalkeeper,
                sensitivity=goalkeeper_sensitivity,
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
                sensitivity=control_sensitivity,
            )

            # ====================================================
            # FORM
            # ====================================================

            home_form_factor = self._form_factor(
                home_form,
                sensitivity=form_sensitivity,
            )

            away_form_factor = self._form_factor(
                away_form,
                sensitivity=form_sensitivity,
            )

            # ====================================================
            # RATING FACTOR (НОВОЕ v2.2)
            # ====================================================

            rating_factor = self._rating_factor(
                home_rating,
                away_rating,
                sensitivity=rating_sensitivity,
            )

            home_rating_factor = rating_factor["home"]
            away_rating_factor = rating_factor["away"]

            # ====================================================
            # 4. RAW XG (С УЧЁТОМ РЕЙТИНГА)
            # ====================================================

            home_xg_raw = (
                self.LEAGUE_MEAN_XG
                * home_attack_factor
                * away_defense_factor
                * away_keeper_factor
                * home_control_factor
                * home_form_factor
                * self.HOME_ADVANTAGE
                * home_rating_factor  # НОВОЕ v2.2
            )

            away_xg_raw = (
                self.LEAGUE_MEAN_XG
                * away_attack_factor
                * home_defense_factor
                * home_keeper_factor
                * away_control_factor
                * away_form_factor
                * away_rating_factor  # НОВОЕ v2.2
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

                "home_rating_factor": round(
                    home_rating_factor,
                    4,
                ),
                "away_rating_factor": round(
                    away_rating_factor,
                    4,
                ),
                "rating_sensitivity_used": round(
                    rating_sensitivity,
                    6,
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

                "rating_used_for_xg": True,  # ИЗМЕНЕНО v2.2
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
                "raw_home=%.3f | raw_away=%.3f | "
                "rating_home=%.1f | rating_away=%.1f | "
                "parameters_used=%s",
                home_xg,
                away_xg,
                home_xg_raw,
                away_xg_raw,
                home_rating,
                away_rating,
                parameters_used,
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

                "parameters_used": parameters_used,
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

                "parameters_used": parameters_used,
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
    # RATING FACTOR (НОВОЕ v2.2)
    # ============================================================

    def _rating_factor(
        self,
        home_rating: float,
        away_rating: float,
        sensitivity: float,
    ) -> Dict[str, float]:
        """
        Вычисляет фактор рейтинга для xG.

        Формула:
            factor = 1 + (rating - RATING_BASELINE) / RATING_BASELINE * sensitivity

        Пример:
            rating=1650 → factor ≈ 1.15
            rating=1500 → factor = 1.00
            rating=1350 → factor ≈ 0.85

        Args:
            home_rating: рейтинг хозяев
            away_rating: рейтинг гостей
            sensitivity: чувствительность рейтинга

        Returns:
            Dict с home_factor и away_factor
        """
        # Защита от некорректных значений
        try:
            home_rating = float(home_rating)
        except (TypeError, ValueError):
            home_rating = self.RATING_BASELINE

        try:
            away_rating = float(away_rating)
        except (TypeError, ValueError):
            away_rating = self.RATING_BASELINE

        if not math.isfinite(home_rating):
            home_rating = self.RATING_BASELINE

        if not math.isfinite(away_rating):
            away_rating = self.RATING_BASELINE

        # Расчёт факторов
        home_factor = 1.0 + (home_rating - self.RATING_BASELINE) / self.RATING_BASELINE * sensitivity
        away_factor = 1.0 + (away_rating - self.RATING_BASELINE) / self.RATING_BASELINE * sensitivity

        # Безопасное ограничение
        return {
            "home": self._clamp_factor(home_factor),
            "away": self._clamp_factor(away_factor),
        }

    # ============================================================
    # ATTACK
    # ============================================================

    def _attack_factor(
        self,
        attack: float,
        sensitivity: Optional[float] = None,
    ) -> float:
        """
        Вычисляет фактор атаки.

        Args:
            attack: значение атаки из паспорта (0-100)
            sensitivity: чувствительность (если None — статическая)

        Returns:
            float: множитель для xG
        """
        if sensitivity is None:
            sensitivity = self.ATTACK_SENSITIVITY

        return self._factor(
            attack,
            sensitivity,
        )

    # ============================================================
    # DEFENSE
    # ============================================================

    def _defense_factor(
        self,
        defense: float,
        sensitivity: Optional[float] = None,
    ) -> float:
        """
        Вычисляет фактор защиты.

        Сильная защита соперника должна уменьшать xG.

        Поэтому для противостоящей защиты
        используется обратное направление:

            defense = 50 -> 1.00
            defense > 50 -> factor < 1
            defense < 50 -> factor > 1

        Args:
            defense: значение защиты из паспорта (0-100)
            sensitivity: чувствительность (если None — статическая)

        Returns:
            float: множитель для xG
        """
        if sensitivity is None:
            sensitivity = self.DEFENSE_SENSITIVITY

        value = self._clamp_passport_value(
            defense
        )

        delta = (
            self.CENTER - value
        ) / self.CENTER

        factor = math.exp(
            delta * sensitivity
        )

        return self._clamp_factor(
            factor
        )

    # ============================================================
    # GOALKEEPER (ПОКА СТАТИЧЕСКИЙ)
    # ============================================================

    def _goalkeeper_factor(
        self,
        goalkeeper: float,
        sensitivity: Optional[float] = None,
    ) -> float:
        """
        Вычисляет фактор вратаря.

        Сильный вратарь соперника уменьшает xG.

        Args:
            goalkeeper: значение вратаря из паспорта (0-100)
            sensitivity: чувствительность (если None — статическая)

        Returns:
            float: множитель для xG
        """
        if sensitivity is None:
            sensitivity = self.GOALKEEPER_SENSITIVITY

        value = self._clamp_passport_value(
            goalkeeper
        )

        delta = (
            self.CENTER - value
        ) / self.CENTER

        factor = math.exp(
            delta * sensitivity
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
        sensitivity: Optional[float] = None,
    ) -> float:
        """
        Вычисляет фактор формы.

        Args:
            form: значение формы из паспорта (0-100)
            sensitivity: чувствительность (если None — статическая)

        Returns:
            float: множитель для xG
        """
        if sensitivity is None:
            sensitivity = self.FORM_SENSITIVITY

        return self._factor(
            form,
            sensitivity,
        )

    # ============================================================
    # CONTROL
    # ============================================================

    def _control_factors(
        self,
        home_control: float,
        away_control: float,
        sensitivity: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Вычисляет факторы контроля для обеих команд.

        Контроль рассчитывается относительно соперника.

        Разница:

            home_control - away_control

        влияет на распределение xG.

        Важно:
        контроль не должен самостоятельно создавать голы.
        Поэтому влияние ограничено.

        Args:
            home_control: контроль хозяев (0-100)
            away_control: контроль гостей (0-100)
            sensitivity: чувствительность (если None — статическая)

        Returns:
            Tuple[float, float]: (home_factor, away_factor)
        """
        if sensitivity is None:
            sensitivity = self.CONTROL_SENSITIVITY

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
            * sensitivity
        )

        away_factor = math.exp(
            -normalized_diff
            * sensitivity
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
    # RATING — SAFE
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
                return self.RATING_BASELINE

            return round(
                value,
                2,
            )

        except (
            TypeError,
            ValueError,
        ):

            return self.RATING_BASELINE

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

            "rating_baseline": self.RATING_BASELINE,
            "rating_sensitivity_default": self.RATING_SENSITIVITY,
            "rating_used_for_xg": True,  # ИЗМЕНЕНО v2.2

            "parameters_supported": True,
            "learnable_parameters": [  # ОБНОВЛЕНО v2.2
                "attack_sensitivity",
                "defense_sensitivity",
                "control_sensitivity",
                "form_sensitivity",
                "rating_sensitivity",
            ],

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

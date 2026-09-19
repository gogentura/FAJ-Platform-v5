#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
WINNER STATE v1.0
============================================================

НАЗНАЧЕНИЕ
----------

WinnerState — display-only слой поверх уже посчитанных данных.

Он НЕ:

    - рассчитывает вероятности (это делает ProbabilityModel);
    - изменяет λ, 1X2, BTTS, totals, score (это неприкосновенное
      ядро Brain);
    - применяет Winner Override;
    - использует bookmaker odds, будущий результат, обучение.

Он ТОЛЬКО:

    1. классифицирует уже посчитанный 1X2 по "равности"
       (closeness) — насколько близки вероятности исходов;
    2. агрегирует уже посчитанные relative-сигналы существующих
       evidence-органов (FormWin.compare, Defence.compare,
       FormControl compare_control, FormSpecial.compare,
       разница anomaly_signal) в единый "evidence lean" —
       медианой, без фиксированных весов, по той же схеме,
       что уже используется в special_form.aggregate_signals;
    3. отдаёт готовую метку фаворита для UI.

evidence_lean НЕ является вероятностью и НЕ участвует в
прогнозе. Это тот же принцип, что уже применяется во всех
diagnostic-органах проекта (FormWin, Defence, FormControl,
FormAnomaly, FormSpecial): evidence описывает, но не решает.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from statistics import median
from typing import Any, Dict, List, Mapping, Optional


# ============================================================
# VERSION / THRESHOLDS
# ============================================================

WINNER_STATE_VERSION = "1.0"

# Closeness — насколько разошлись top-1 и top-2 исходы 1X2.
# Это чисто дескриптивные пороги для ярлыка, не коэффициенты
# в математике.
CLOSENESS_WIDE_THRESHOLD = 0.20
CLOSENESS_MODERATE_THRESHOLD = 0.10

# Порог для evidence lean — ниже него матч считается
# BALANCED (перевес слишком мал, чтобы что-то отображать).
EVIDENCE_LEAN_THRESHOLD = 0.15


# ============================================================
# HELPERS
# ============================================================

def _num(value: Any) -> Optional[float]:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result != result:  # NaN guard
        return None

    return result


def _get(obj: Any, *names: str) -> Any:

    if obj is None:
        return None

    for name in names:

        if isinstance(obj, Mapping):
            if name in obj:
                return obj[name]

        try:
            if name in obj.keys():
                return obj[name]
        except (AttributeError, TypeError):
            pass

        try:
            return getattr(obj, name)
        except AttributeError:
            pass

    return None


# ============================================================
# CLOSENESS
# ============================================================

def _match_closeness(
    home_win: Optional[float],
    draw: Optional[float],
    away_win: Optional[float],
) -> tuple[Optional[float], str, Optional[str]]:
    """
    Возвращает (margin, label, favorite_side).

    favorite_side ∈ {"HOME", "DRAW", "AWAY", None}

    margin = разрыв между top-1 и top-2 вероятностями исхода.

    Ничего не пересчитывает — работает только с уже готовыми
    home_win/draw/away_win от ProbabilityModel.
    """

    labeled = [
        ("HOME", _num(home_win)),
        ("DRAW", _num(draw)),
        ("AWAY", _num(away_win)),
    ]

    available = [(name, value) for name, value in labeled if value is not None]

    if len(available) < 2:
        return None, "неизвестно", None

    available.sort(key=lambda item: item[1], reverse=True)

    top_name, top_value = available[0]
    _, second_value = available[1]

    margin = top_value - second_value

    if margin >= CLOSENESS_WIDE_THRESHOLD:
        label = "явный фаворит"
    elif margin >= CLOSENESS_MODERATE_THRESHOLD:
        label = "фаворит"
    else:
        label = "равный матч"

    return margin, label, top_name


# ============================================================
# EVIDENCE LEAN
# ============================================================

def _evidence_lean(
    components: Mapping[str, Optional[float]],
) -> tuple[Optional[float], str, List[str]]:
    """
    Медианa доступных relative-сигналов (HOME - AWAY, каждый
    в диапазоне примерно [-1, +1]).

    Медиана, а не среднее с фиксированными весами — тот же
    метод, что special_form.aggregate_signals уже использует,
    чтобы ни один источник не стал скрытым коэффициентом.

    Возвращает (lean, direction, sources_used).
    direction ∈ {"HOME", "AWAY", "BALANCED", "unknown"}
    """

    available = {
        name: value
        for name, value in components.items()
        if value is not None
    }

    if len(available) < 2:
        return None, "unknown", list(available.keys())

    lean = median(list(available.values()))

    if lean > EVIDENCE_LEAN_THRESHOLD:
        direction = "HOME"
    elif lean < -EVIDENCE_LEAN_THRESHOLD:
        direction = "AWAY"
    else:
        direction = "BALANCED"

    return lean, direction, list(available.keys())


# ============================================================
# RESULT
# ============================================================

@dataclass
class WinnerState:

    version: str = WINNER_STATE_VERSION

    closeness_margin: Optional[float] = None
    closeness_label: str = "неизвестно"

    favorite: Optional[str] = None

    evidence_lean: Optional[float] = None
    evidence_lean_direction: str = "unknown"
    evidence_lean_team: Optional[str] = None

    evidence_sources_used: List[str] = field(default_factory=list)

    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# BUILDER
# ============================================================

class WinnerStateBuilder:
    """
    Строит WinnerState ИСКЛЮЧИТЕЛЬНО из уже посчитанных данных:

        - вероятностей ProbabilityModel (closeness)
        - relative evidence уже существующих compare()-методов
          FormWin / Defence / FormControl / FormSpecial и
          разницы anomaly_signal

    Ничего не пересчитывает. Ничего не пишет обратно в Core.
    """

    VERSION = WINNER_STATE_VERSION

    def build(
        self,
        *,
        home_win_probability: Optional[float],
        draw_probability: Optional[float],
        away_win_probability: Optional[float],
        home_team: Optional[str],
        away_team: Optional[str],
        relative_form_win: Optional[float] = None,
        relative_defence: Optional[float] = None,
        relative_control: Optional[float] = None,
        special_differential: Optional[float] = None,
        anomaly_differential: Optional[float] = None,
    ) -> WinnerState:

        margin, closeness_label, favorite_side = _match_closeness(
            home_win_probability,
            draw_probability,
            away_win_probability,
        )

        favorite_name: Optional[str] = None

        if favorite_side == "HOME":
            favorite_name = home_team
        elif favorite_side == "AWAY":
            favorite_name = away_team
        elif favorite_side == "DRAW":
            favorite_name = "Ничья"

        lean, direction, sources = _evidence_lean(
            {
                "form_win": relative_form_win,
                "defence": relative_defence,
                "control": relative_control,
                "special_form": special_differential,
                "anomaly": anomaly_differential,
            }
        )

        lean_team: Optional[str] = None

        if direction == "HOME":
            lean_team = home_team
        elif direction == "AWAY":
            lean_team = away_team

        diagnostics = {
            "version": self.VERSION,
            "model_role": "display_only_winner_synthesis",

            # ------------------------------------------------
            # Жёсткие архитектурные гарантии — по аналогии с
            # тем, как остальные органы самодокументируются.
            # ------------------------------------------------

            "is_probability": False,
            "affects_core": False,
            "affects_goal_model": False,
            "affects_probability_model": False,
            "affects_score_predictor": False,
            "winner_override": False,
            "future_result_used": False,
            "bookmaker_odds_used": False,
            "learning_performed": False,

            "closeness_thresholds": {
                "wide": CLOSENESS_WIDE_THRESHOLD,
                "moderate": CLOSENESS_MODERATE_THRESHOLD,
            },

            "evidence_lean_threshold": EVIDENCE_LEAN_THRESHOLD,

            "aggregation_method": "median_of_available_relative_evidence",

            "evidence_sources_available": sources,

            "evidence_sources_possible": [
                "form_win",
                "defence",
                "control",
                "special_form",
                "anomaly",
            ],
        }

        return WinnerState(
            version=self.VERSION,
            closeness_margin=margin,
            closeness_label=closeness_label,
            favorite=favorite_name,
            evidence_lean=lean,
            evidence_lean_direction=direction,
            evidence_lean_team=lean_team,
            evidence_sources_used=sources,
            diagnostics=diagnostics,
        )


# ============================================================
# PUBLIC API
# ============================================================

def build_winner_state(
    *,
    home_win_probability: Optional[float],
    draw_probability: Optional[float],
    away_win_probability: Optional[float],
    home_team: Optional[str],
    away_team: Optional[str],
    relative_form_win: Optional[float] = None,
    relative_defence: Optional[float] = None,
    relative_control: Optional[float] = None,
    special_differential: Optional[float] = None,
    anomaly_differential: Optional[float] = None,
) -> WinnerState:

    return WinnerStateBuilder().build(
        home_win_probability=home_win_probability,
        draw_probability=draw_probability,
        away_win_probability=away_win_probability,
        home_team=home_team,
        away_team=away_team,
        relative_form_win=relative_form_win,
        relative_defence=relative_defence,
        relative_control=relative_control,
        special_differential=special_differential,
        anomaly_differential=anomaly_differential,
    )


__all__ = [
    "WINNER_STATE_VERSION",
    "WinnerState",
    "WinnerStateBuilder",
    "build_winner_state",
]


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    state = build_winner_state(
        home_win_probability=0.286,
        draw_probability=0.294,
        away_win_probability=0.424,
        home_team="Акрон",
        away_team="Ахмат",
        relative_form_win=0.22,
        relative_defence=0.05,
        relative_control=None,
        special_differential=0.10,
        anomaly_differential=-0.02,
    )

    print("WINNER STATE v1.0")
    print("Closeness:", state.closeness_label, state.closeness_margin)
    print("Favorite:", state.favorite)
    print("Evidence lean:", state.evidence_lean_direction, state.evidence_lean)

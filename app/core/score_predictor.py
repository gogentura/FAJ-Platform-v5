#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SCORE PREDICTOR v1.2
============================================================

ROLE
----

ScorePredictor формирует Score State из уже рассчитанного
ProbabilityModel распределения точных счетов.

ARCHITECTURE

    GoalModel
        │
        ▼
    home_lambda / away_lambda
        │
        ▼
    ProbabilityModel
        │
        ▼
    score_distribution
        │
        ▼
    ScorePredictor
        │
        ├── predicted_score          (argmax raw probability)
        ├── second_score
        ├── third_score
        ├── top_scores               (top-N)
        ├── upper_tail_state
        ├── separation_state
        ├── top_scores_identity
        └── distribution_state

MATHEMATICAL CONTRACT
---------------------

    predicted_score = argmax P(score)

ProbabilityModel является единственным владельцем
вероятностей точных счетов.

ScorePredictor:

    НЕ пересчитывает Poisson
    НЕ пересчитывает P(score)
    НЕ нормализует распределение
    НЕ меняет P(score)
    НЕ применяет бонусы
    НЕ применяет штрафы
    НЕ использует FormWin
    НЕ использует Defence
    НЕ использует Control
    НЕ использует Anomaly
    НЕ использует SpecialForm
    НЕ использует WinnerState
    НЕ использует Confidence
    НЕ использует Risk
    НЕ использует ScoreUtility

ScorePredictor является ranking/state layer.

LOW-SCORE CORRECTION
--------------------

Архитектурно зарезервирована, но в v1.2 НЕ применяется.

Важно:

    Score State ≠ Probability State
    Score State ≠ Winner State
    Score State ≠ Confidence State
    Score State ≠ Risk State

Все значения вероятности берутся непосредственно
из ProbabilityModel.

None != 0.
============================================================
CHANGES IN V1.2
============================================================

Расширение Score State без изменения контракта:

    - добавлен upper_tail_mass и upper_tail_state
    - добавлен top1_top2_gap / top1_top3_gap
      и separation_state
    - добавлен top_scores_identity
    - добавлен distribution_entropy
      (Shannon H по нормированной копии
       распределения; raw_probability
       не изменяется)
    - добавлен distribution_state

Все новые поля являются metadata / state.

predicted_score остаётся строгим
argmax raw probability.

Никаких бонусов, штрафов или корректировок
в ranking не добавлено.

top_scores не обрезается по вероятности,
берётся первые TOP_SCORES_COUNT элементов
отсортированного списка.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import math


# ============================================================
# VERSION
# ============================================================

VERSION = "1.2"
FORMULA_STATUS = "CONTRACT_V1"

TOP_SCORES_COUNT = 10

# ------------------------------------------------------------
# Thresholds for Score State (v1.2)
#
# ВНИМАНИЕ:
#   Это пороги отображения / классификации, а НЕ
#   пороги, изменяющие predicted_score.
# ------------------------------------------------------------

UPPER_TAIL_LOW = 0.10
UPPER_TAIL_HIGH = 0.25

SEPARATION_SHARP = 0.03
SEPARATION_FLAT = 0.01

DISTRIBUTION_CONCENTRATED = 2.0
DISTRIBUTION_DIFFUSE = 3.0

UPPER_TAIL_MIN_TOTAL_GOALS = 4


# ============================================================
# SCORE PREDICTION
# ============================================================

@dataclass
class ScorePrediction:
    """
    Score State v1.2.

    Основные результаты:

        predicted_score
        probability_score
        top_scores

    ProbabilityScore является RAW P(score), полученной
    от ProbabilityModel.

    Старые поля сохранены как compatibility API.
    """

    version: str

    likely_score: Optional[str]
    predicted_score: Optional[str]

    second_score: Optional[str]
    third_score: Optional[str]

    primary_score_value: Optional[float]
    second_score_value: Optional[float]
    third_score_value: Optional[float]

    probability_score: Optional[float]

    # Полное ранжированное распределение.
    top_scores: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # Compatibility / diagnostic metadata.
    home_lambda: Optional[float] = None
    away_lambda: Optional[float] = None

    home_xg: Optional[float] = None
    away_xg: Optional[float] = None

    # Explicit Score State metadata.
    low_score_state: Optional[str] = None
    score_data_quality: Optional[float] = None
    sample_size: Optional[int] = None

    # --------------------------------------------------------
    # v1.2 — Score State extensions
    # --------------------------------------------------------

    upper_tail_mass: Optional[float] = None
    upper_tail_state: Optional[str] = None

    top1_top2_gap: Optional[float] = None
    top1_top3_gap: Optional[float] = None
    separation_state: Optional[str] = None

    top_scores_identity: Optional[str] = None

    distribution_entropy: Optional[float] = None
    distribution_state: Optional[str] = None

    # --------------------------------------------------------
    # Старые compatibility fields.
    # --------------------------------------------------------

    outcome_fit_score: Optional[float] = None
    margin_fit_score: Optional[float] = None
    btts_fit_score: Optional[float] = None
    total_fit_score: Optional[float] = None
    scenario_fit_score: Optional[float] = None
    state_advantage: Optional[float] = None

    probability_summary: Dict[str, Any] = field(
        default_factory=dict
    )

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# SCORE PREDICTOR
# ============================================================

class ScorePredictor:
    """
    Pure Score State layer.

    Источник P(score):

        ProbabilityModel.score_distribution

    Никакой собственной probability mathematics здесь нет.
    """

    def predict(
        self,
        score_probabilities: Any,
        home_lambda: Optional[float] = None,
        away_lambda: Optional[float] = None,
        probability_result: Any = None,
        *,
        home_xg: Optional[float] = None,
        away_xg: Optional[float] = None,
    ) -> ScorePrediction:
        """
        Rank scores directly from ProbabilityModel.

        ВАЖНО:

        home_lambda / away_lambda НЕ являются обязательными
        для ranking уже существующего score_distribution.

        Они используются только как metadata.

        Если distribution отсутствует или не содержит
        валидных score probabilities — Score State unavailable.
        """

        # ----------------------------------------------------
        # Compatibility input resolution
        # ----------------------------------------------------

        if home_lambda is None:
            home_lambda = home_xg

        if away_lambda is None:
            away_lambda = away_xg

        home_lambda = self._safe_float(
            home_lambda
        )

        away_lambda = self._safe_float(
            away_lambda
        )

        # ----------------------------------------------------
        # Read ProbabilityModel distribution
        # ----------------------------------------------------

        candidates = self._read_score_distribution(
            score_probabilities
        )

        if not candidates:
            return self._unavailable_prediction(
                home_lambda=home_lambda,
                away_lambda=away_lambda,
                reason="EMPTY_SCORE_DISTRIBUTION",
            )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # NO normalization.
        # NO Poisson.
        # NO probability modification.
        #
        # ProbabilityModel owns P(score).
        # ----------------------------------------------------

        ranked = sorted(
            candidates,
            key=lambda item: (
                -item["raw_probability"],
                item["home_goals"],
                item["away_goals"],
            ),
        )

        # ----------------------------------------------------
        # Top N
        # ----------------------------------------------------

        top_scores = ranked[
            :TOP_SCORES_COUNT
        ]

        primary = (
            top_scores[0]
            if top_scores
            else None
        )

        second = (
            top_scores[1]
            if len(top_scores) >= 2
            else None
        )

        third = (
            top_scores[2]
            if len(top_scores) >= 3
            else None
        )

        likely_score = (
            primary["score"]
            if primary
            else None
        )

        predicted_score = likely_score

        second_score = (
            second["score"]
            if second
            else None
        )

        third_score = (
            third["score"]
            if third
            else None
        )

        primary_probability = (
            primary["raw_probability"]
            if primary
            else None
        )

        second_probability = (
            second["raw_probability"]
            if second
            else None
        )

        third_probability = (
            third["raw_probability"]
            if third
            else None
        )

        # ----------------------------------------------------
        # v1.2 — Score State extensions
        #
        # Все эти поля — metadata.
        # Они НЕ меняют predicted_score.
        # ----------------------------------------------------

        upper_tail_mass = (
            self._compute_upper_tail_mass(
                ranked
            )
        )

        upper_tail_state = (
            self._classify_upper_tail(
                upper_tail_mass
            )
        )

        (
            top1_top2_gap,
            top1_top3_gap,
        ) = self._compute_separation(
            primary_probability,
            second_probability,
            third_probability,
        )

        separation_state = (
            self._classify_separation(
                top1_top2_gap
            )
        )

        top_scores_identity = (
            self._classify_top_scores_identity(
                top_scores
            )
        )

        distribution_entropy = (
            self._compute_entropy(
                ranked
            )
        )

        distribution_state = (
            self._classify_distribution(
                distribution_entropy
            )
        )

        # ----------------------------------------------------
        # Probability summary
        #
        # Diagnostic only.
        # NEVER affects score ranking.
        # ----------------------------------------------------

        probability_summary = (
            self._extract_probability_summary(
                probability_result
            )
        )

        # ----------------------------------------------------
        # Score data quality
        # ----------------------------------------------------

        score_data_quality = 1.0

        diagnostics = {
            "version": VERSION,
            "formula_status": FORMULA_STATUS,

            "home_lambda": home_lambda,
            "away_lambda": away_lambda,

            "home_xg": home_lambda,
            "away_xg": away_lambda,

            "candidate_count": len(candidates),
            "top_scores_count": len(top_scores),

            "predicted_score": predicted_score,
            "predicted_probability": primary_probability,

            "second_score": second_score,
            "second_probability": second_probability,

            "third_score": third_score,
            "third_probability": third_probability,

            "selection_method": (
                "ARGMAX_RAW_SCORE_PROBABILITY"
            ),

            "distribution_source": (
                "ProbabilityModel"
            ),

            # ------------------------------------------------
            # Probability ownership
            # ------------------------------------------------

            "probability_recalculated": False,
            "probability_modified": False,
            "probability_normalized": False,

            "poisson_recalculated": False,

            # ------------------------------------------------
            # v1.2 extensions
            # ------------------------------------------------

            "upper_tail_mass": upper_tail_mass,
            "upper_tail_state": upper_tail_state,
            "upper_tail_thresholds": (
                UPPER_TAIL_LOW,
                UPPER_TAIL_HIGH,
            ),
            "upper_tail_min_total_goals": (
                UPPER_TAIL_MIN_TOTAL_GOALS
            ),

            "top1_top2_gap": top1_top2_gap,
            "top1_top3_gap": top1_top3_gap,
            "separation_state": separation_state,
            "separation_thresholds": (
                SEPARATION_FLAT,
                SEPARATION_SHARP,
            ),

            "top_scores_identity": (
                top_scores_identity
            ),

            "distribution_entropy": (
                distribution_entropy
            ),
            "distribution_state": (
                distribution_state
            ),
            "distribution_thresholds": (
                DISTRIBUTION_CONCENTRATED,
                DISTRIBUTION_DIFFUSE,
            ),

            # ------------------------------------------------
            # Reserved correction
            # ------------------------------------------------

            "low_score_correction_available": True,
            "low_score_correction_used": False,

            # ------------------------------------------------
            # Secondary evidence
            # ------------------------------------------------

            "secondary_signals_used": False,

            "winner_state_used": False,

            "form_win_used": False,
            "defence_used": False,
            "control_used": False,
            "anomaly_used": False,
            "special_used": False,

            "confidence_used": False,
            "risk_used": False,

            "outcome_fit_used": False,
            "margin_fit_used": False,
            "btts_fit_used": False,
            "total_fit_used": False,
            "scenario_fit_used": False,
            "score_utility_used": False,

            # ------------------------------------------------
            # Contract
            # ------------------------------------------------

            "ranking_is_probability_argmax": True,
            "raw_probability_preserved": True,
            "score_state_only": True,
        }

        return ScorePrediction(
            version=VERSION,

            likely_score=likely_score,
            predicted_score=predicted_score,

            second_score=second_score,
            third_score=third_score,

            primary_score_value=primary_probability,
            second_score_value=second_probability,
            third_score_value=third_probability,

            probability_score=primary_probability,

            top_scores=top_scores,

            home_lambda=home_lambda,
            away_lambda=away_lambda,

            home_xg=home_lambda,
            away_xg=away_lambda,

            low_score_state="NOT_APPLIED",
            score_data_quality=score_data_quality,
            sample_size=len(candidates),

            # ------------------------------------------------
            # v1.2 Score State extensions
            # ------------------------------------------------

            upper_tail_mass=upper_tail_mass,
            upper_tail_state=upper_tail_state,

            top1_top2_gap=top1_top2_gap,
            top1_top3_gap=top1_top3_gap,
            separation_state=separation_state,

            top_scores_identity=top_scores_identity,

            distribution_entropy=distribution_entropy,
            distribution_state=distribution_state,

            # ------------------------------------------------
            # Compatibility fields.
            # ------------------------------------------------

            outcome_fit_score=None,
            margin_fit_score=None,
            btts_fit_score=None,
            total_fit_score=None,
            scenario_fit_score=None,

            state_advantage=None,

            probability_summary=probability_summary,

            diagnostics=diagnostics,
        )

    # ========================================================
    # v1.2 — UPPER TAIL
    # ========================================================

    @staticmethod
    def _compute_upper_tail_mass(
        ranked: List[Dict[str, Any]],
    ) -> Optional[float]:
        """
        Сумма P(score) для счетов с total_goals >= threshold.

        Использует raw_probability как есть.
        Не нормирует.
        """

        if not ranked:
            return None

        total = 0.0

        for item in ranked:

            total_goals = (
                item.get("total_goals")
            )

            if total_goals is None:
                continue

            if total_goals >= (
                UPPER_TAIL_MIN_TOTAL_GOALS
            ):

                probability = (
                    item.get("raw_probability")
                )

                if probability is None:
                    continue

                total += float(probability)

        return total

    @staticmethod
    def _classify_upper_tail(
        upper_tail_mass: Optional[float],
    ) -> Optional[str]:

        if upper_tail_mass is None:
            return None

        if upper_tail_mass < UPPER_TAIL_LOW:
            return "LOW"

        if upper_tail_mass > UPPER_TAIL_HIGH:
            return "HIGH"

        return "MEDIUM"

    # ========================================================
    # v1.2 — SEPARATION
    # ========================================================

    @staticmethod
    def _compute_separation(
        primary: Optional[float],
        second: Optional[float],
        third: Optional[float],
    ) -> tuple[
        Optional[float],
        Optional[float],
    ]:

        if primary is None:
            return None, None

        top1_top2_gap = None
        top1_top3_gap = None

        if second is not None:
            top1_top2_gap = primary - second

        if third is not None:
            top1_top3_gap = primary - third

        return top1_top2_gap, top1_top3_gap

    @staticmethod
    def _classify_separation(
        top1_top2_gap: Optional[float],
    ) -> Optional[str]:

        if top1_top2_gap is None:
            return None

        if top1_top2_gap >= SEPARATION_SHARP:
            return "SHARP"

        if top1_top2_gap <= SEPARATION_FLAT:
            return "FLAT"

        return "MODERATE"

    # ========================================================
    # v1.2 — TOP SCORES IDENTITY
    # ========================================================

    @staticmethod
    def _classify_top_scores_identity(
        top_scores: List[Dict[str, Any]],
    ) -> Optional[str]:

        if not top_scores:
            return None

        # ----------------------------------------------------
        # Анализируем первые три (или сколько есть).
        # ----------------------------------------------------

        sample = top_scores[:3]

        winners = set()
        btts_states = set()

        for item in sample:

            winner = item.get("winner")

            if winner:
                winners.add(winner)

            btts = item.get("btts")

            if btts:
                btts_states.add(btts)

        # ----------------------------------------------------
        # Определяем характер Top-3
        # ----------------------------------------------------

        single_winner = (
            len(winners) == 1
        )

        single_btts = (
            len(btts_states) == 1
        )

        if single_winner and single_btts:

            winner = next(iter(winners))
            btts = next(iter(btts_states))

            return (
                f"CONSISTENT_{winner}_"
                f"BTTS_{btts}"
            )

        if single_winner:

            winner = next(iter(winners))

            return f"CONSISTENT_{winner}"

        if single_btts:

            btts = next(iter(btts_states))

            return f"BTTS_{btts}"

        return "MIXED"

    # ========================================================
    # v1.2 — DISTRIBUTION ENTROPY
    # ========================================================

    @staticmethod
    def _compute_entropy(
        ranked: List[Dict[str, Any]],
    ) -> Optional[float]:
        """
        Shannon entropy по нормированной копии
        raw_probability.

        ВАЖНО:

            raw_probability НЕ изменяется.

            Нормировка выполняется только
            локально для расчёта энтропии.
        """

        if not ranked:
            return None

        values: List[float] = []

        for item in ranked:

            probability = item.get(
                "raw_probability"
            )

            if probability is None:
                continue

            value = float(probability)

            if value <= 0.0:
                continue

            values.append(value)

        if not values:
            return None

        total = sum(values)

        if total <= 0.0:
            return None

        entropy = 0.0

        for value in values:

            p = value / total

            if p <= 0.0:
                continue

            entropy -= p * math.log(p)

        return entropy

    @staticmethod
    def _classify_distribution(
        entropy: Optional[float],
    ) -> Optional[str]:

        if entropy is None:
            return None

        if entropy < DISTRIBUTION_CONCENTRATED:
            return "CONCENTRATED"

        if entropy > DISTRIBUTION_DIFFUSE:
            return "DIFFUSE"

        return "BALANCED"

    # ========================================================
    # READ SCORE DISTRIBUTION
    # ========================================================

    def _read_score_distribution(
        self,
        score_probabilities: Any,
    ) -> List[Dict[str, Any]]:
        """
        Convert ProbabilityModel score distribution into
        Score State records.

        IMPORTANT:

        Probability values are NOT normalized
        and NOT recalculated.

        Supplied P(score) is preserved exactly
        apart from numeric conversion to float.
        """

        if score_probabilities is None:
            return []

        candidates: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # Dict
        # ----------------------------------------------------

        if isinstance(
            score_probabilities,
            dict,
        ):
            for score, probability in (
                score_probabilities.items()
            ):
                self._append_candidate(
                    candidates,
                    score,
                    probability,
                )

        # ----------------------------------------------------
        # List / tuple
        # ----------------------------------------------------

        elif isinstance(
            score_probabilities,
            (list, tuple),
        ):
            for item in score_probabilities:

                score = None
                probability = None

                if isinstance(
                    item,
                    (list, tuple),
                ):
                    if len(item) >= 2:
                        score = item[0]
                        probability = item[1]

                elif isinstance(
                    item,
                    dict,
                ):
                    score = (
                        item.get("score")
                        or item.get("exact_score")
                        or item.get("result")
                    )

                    probability = (
                        item.get("raw_probability")
                        if "raw_probability" in item
                        else item.get("probability")
                    )

                    if probability is None:
                        probability = item.get(
                            "prob"
                        )

                else:
                    score = (
                        self._get_value(
                            item,
                            "score",
                        )
                        or self._get_value(
                            item,
                            "exact_score",
                        )
                        or self._get_value(
                            item,
                            "result",
                        )
                    )

                    probability = (
                        self._get_value(
                            item,
                            "raw_probability",
                        )
                    )

                    if probability is None:
                        probability = (
                            self._get_value(
                                item,
                                "probability",
                            )
                        )

                    if probability is None:
                        probability = (
                            self._get_value(
                                item,
                                "prob",
                            )
                        )

                self._append_candidate(
                    candidates,
                    score,
                    probability,
                )

        # ----------------------------------------------------
        # Object / wrapper
        # ----------------------------------------------------

        else:

            nested = self._get_value(
                score_probabilities,
                "score_distribution",
            )

            if nested is not None:
                return self._read_score_distribution(
                    nested
                )

            nested = self._get_value(
                score_probabilities,
                "score_probabilities",
            )

            if nested is not None:
                return self._read_score_distribution(
                    nested
                )

            nested = self._get_value(
                score_probabilities,
                "distribution",
            )

            if nested is not None:
                return self._read_score_distribution(
                    nested
                )

        # ----------------------------------------------------
        # Merge duplicate scores.
        #
        # Если один и тот же счёт встречается более одного
        # раза, вероятности складываются, так как относятся
        # к одному и тому же состоянию.
        #
        # Нормализация не выполняется.
        # ----------------------------------------------------

        merged: Dict[
            str,
            float,
        ] = {}

        for item in candidates:

            score = item["score"]
            probability = item["raw_probability"]

            merged[score] = (
                merged.get(score, 0.0)
                + probability
            )

        return [
            self._build_score_state(
                score,
                probability,
            )
            for score, probability
            in merged.items()
        ]

    # ========================================================
    # APPEND CANDIDATE
    # ========================================================

    def _append_candidate(
        self,
        candidates: List[Dict[str, Any]],
        score: Any,
        probability: Any,
    ) -> None:

        score_text = self._parse_score(
            score
        )

        probability_value = (
            self._safe_float(
                probability
            )
        )

        if (
            score_text is None
            or probability_value is None
            or probability_value < 0.0
            or probability_value > 1.0
        ):
            return

        home_goals, away_goals = (
            self._score_parts(
                score_text
            )
        )

        if (
            home_goals is None
            or away_goals is None
        ):
            return

        candidates.append(
            {
                "score": score_text,
                "raw_probability": probability_value,
                "home_goals": home_goals,
                "away_goals": away_goals,
            }
        )

    # ========================================================
    # BUILD SCORE STATE
    # ========================================================

    @staticmethod
    def _build_score_state(
        score: str,
        probability: float,
    ) -> Dict[str, Any]:
        """
        Add descriptive scenario metadata.

        Probability is not changed.
        """

        home_goals, away_goals = (
            ScorePredictor._score_parts(
                score
            )
        )

        if (
            home_goals is None
            or away_goals is None
        ):
            raise ValueError(
                f"Invalid score: {score}"
            )

        if home_goals > away_goals:
            winner = "HOME"
        elif away_goals > home_goals:
            winner = "AWAY"
        else:
            winner = "DRAW"

        total_goals = (
            home_goals
            + away_goals
        )

        btts = (
            "YES"
            if home_goals > 0
            and away_goals > 0
            else "NO"
        )

        return {
            "score": score,

            # Contract name.
            "raw_probability": probability,

            # Compatibility name.
            "probability": probability,

            "home_goals": home_goals,
            "away_goals": away_goals,

            "winner": winner,

            "total_goals": total_goals,

            "btts": btts,
        }

    # ========================================================
    # SCORE PARSER
    # ========================================================

    @staticmethod
    def _parse_score(
        score: Any,
    ) -> Optional[str]:

        if score is None:
            return None

        if isinstance(
            score,
            str,
        ):
            value = score.strip()

            if not value:
                return None

            value = value.replace(
                " ",
                "",
            )

            if ":" in value:
                parts = value.split(
                    ":",
                    1,
                )
            elif "-" in value:
                parts = value.split(
                    "-",
                    1,
                )
            else:
                return None

            if len(parts) != 2:
                return None

            try:
                home = int(parts[0])
                away = int(parts[1])
            except (
                TypeError,
                ValueError,
            ):
                return None

            if home < 0 or away < 0:
                return None

            return f"{home}:{away}"

        if isinstance(
            score,
            (tuple, list),
        ):
            if len(score) < 2:
                return None

            try:
                home = int(score[0])
                away = int(score[1])
            except (
                TypeError,
                ValueError,
            ):
                return None

            if home < 0 or away < 0:
                return None

            return f"{home}:{away}"

        if isinstance(
            score,
            dict,
        ):
            home = (
                score.get("home")
                if "home" in score
                else score.get("home_goals")
            )

            away = (
                score.get("away")
                if "away" in score
                else score.get("away_goals")
            )

            try:
                home = int(home)
                away = int(away)
            except (
                TypeError,
                ValueError,
            ):
                return None

            if home < 0 or away < 0:
                return None

            return f"{home}:{away}"

        return None

    # ========================================================
    # SCORE PARTS
    # ========================================================

    @staticmethod
    def _score_parts(
        score: str,
    ) -> tuple[
        Optional[int],
        Optional[int],
    ]:

        if not isinstance(
            score,
            str,
        ):
            return None, None

        parts = score.split(
            ":",
            1,
        )

        if len(parts) != 2:
            return None, None

        try:
            home = int(parts[0])
            away = int(parts[1])
        except (
            TypeError,
            ValueError,
        ):
            return None, None

        if home < 0 or away < 0:
            return None, None

        return home, away

    # ========================================================
    # PROBABILITY SUMMARY
    # ========================================================

    def _extract_probability_summary(
        self,
        probability_result: Any,
    ) -> Dict[str, Any]:

        if probability_result is None:
            return {}

        summary = self._get_value(
            probability_result,
            "probability_summary",
        )

        if isinstance(
            summary,
            dict,
        ):
            return dict(summary)

        fields = (
            "home_win",
            "draw",
            "away_win",

            "btts_yes",
            "btts_no",

            "over_15",
            "under_15",

            "over_25",
            "under_25",

            "over_35",
            "under_35",
        )

        result: Dict[str, Any] = {}

        for field_name in fields:

            value = self._safe_float(
                self._get_value(
                    probability_result,
                    field_name,
                )
            )

            if value is not None:
                result[field_name] = value

        return result

    # ========================================================
    # UNAVAILABLE
    # ========================================================

    def _unavailable_prediction(
        self,
        *,
        home_lambda: Optional[float],
        away_lambda: Optional[float],
        reason: str,
    ) -> ScorePrediction:

        diagnostics = {
            "version": VERSION,
            "formula_status": FORMULA_STATUS,

            "home_lambda": home_lambda,
            "away_lambda": away_lambda,

            "candidate_count": 0,

            "predicted_score": None,
            "predicted_probability": None,

            "selection_method": (
                "ARGMAX_RAW_SCORE_PROBABILITY"
            ),

            "distribution_source": (
                "ProbabilityModel"
            ),

            "probability_recalculated": False,
            "probability_modified": False,
            "probability_normalized": False,

            "poisson_recalculated": False,

            # ------------------------------------------------
            # v1.2 extensions
            # ------------------------------------------------

            "upper_tail_mass": None,
            "upper_tail_state": None,
            "upper_tail_thresholds": (
                UPPER_TAIL_LOW,
                UPPER_TAIL_HIGH,
            ),
            "upper_tail_min_total_goals": (
                UPPER_TAIL_MIN_TOTAL_GOALS
            ),

            "top1_top2_gap": None,
            "top1_top3_gap": None,
            "separation_state": None,
            "separation_thresholds": (
                SEPARATION_FLAT,
                SEPARATION_SHARP,
            ),

            "top_scores_identity": None,

            "distribution_entropy": None,
            "distribution_state": None,
            "distribution_thresholds": (
                DISTRIBUTION_CONCENTRATED,
                DISTRIBUTION_DIFFUSE,
            ),

            "low_score_correction_available": True,
            "low_score_correction_used": False,

            "secondary_signals_used": False,

            "winner_state_used": False,

            "form_win_used": False,
            "defence_used": False,
            "control_used": False,
            "anomaly_used": False,
            "special_used": False,

            "confidence_used": False,
            "risk_used": False,

            "outcome_fit_used": False,
            "margin_fit_used": False,
            "btts_fit_used": False,
            "total_fit_used": False,
            "scenario_fit_used": False,
            "score_utility_used": False,

            "ranking_is_probability_argmax": True,
            "raw_probability_preserved": True,
            "score_state_only": True,

            "error": reason,
        }

        return ScorePrediction(
            version=VERSION,

            likely_score=None,
            predicted_score=None,

            second_score=None,
            third_score=None,

            primary_score_value=None,
            second_score_value=None,
            third_score_value=None,

            probability_score=None,

            top_scores=[],

            home_lambda=home_lambda,
            away_lambda=away_lambda,

            home_xg=home_lambda,
            away_xg=away_lambda,

            low_score_state=None,
            score_data_quality=None,
            sample_size=None,

            # ------------------------------------------------
            # v1.2 Score State extensions
            # ------------------------------------------------

            upper_tail_mass=None,
            upper_tail_state=None,

            top1_top2_gap=None,
            top1_top3_gap=None,
            separation_state=None,

            top_scores_identity=None,

            distribution_entropy=None,
            distribution_state=None,

            # ------------------------------------------------
            # Compatibility fields.
            # ------------------------------------------------

            outcome_fit_score=None,
            margin_fit_score=None,
            btts_fit_score=None,
            total_fit_score=None,
            scenario_fit_score=None,

            state_advantage=None,

            probability_summary={},

            diagnostics=diagnostics,
        )

    # ========================================================
    # SAFE FLOAT
    # ========================================================

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:

        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return None

        try:
            result = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not math.isfinite(result):
            return None

        return result

    # ========================================================
    # GET VALUE
    # ========================================================

    @staticmethod
    def _get_value(
        source: Any,
        field: str,
        default: Any = None,
    ) -> Any:

        if source is None:
            return default

        if isinstance(
            source,
            dict,
        ):
            return source.get(
                field,
                default,
            )

        return getattr(
            source,
            field,
            default,
        )

    # ========================================================
    # COMPATIBILITY API
    # ========================================================

    def predict_score(
        self,
        score_probabilities: Any,
        home_xg: Optional[float],
        away_xg: Optional[float],
        probability_result: Any = None,
    ) -> ScorePrediction:
        """
        Compatibility wrapper for old FAJ callers.
        """

        return self.predict(
            score_probabilities=score_probabilities,
            home_xg=home_xg,
            away_xg=away_xg,
            probability_result=probability_result,
        )


# ============================================================
# MODULE-LEVEL CONVENIENCE
# ============================================================

def predict_score(
    score_probabilities: Any,
    home_xg: Optional[float],
    away_xg: Optional[float],
    probability_result: Any = None,
) -> ScorePrediction:

    return ScorePredictor().predict(
        score_probabilities=score_probabilities,
        home_xg=home_xg,
        away_xg=away_xg,
        probability_result=probability_result,
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "VERSION",
    "FORMULA_STATUS",
    "TOP_SCORES_COUNT",
    "UPPER_TAIL_LOW",
    "UPPER_TAIL_HIGH",
    "SEPARATION_SHARP",
    "SEPARATION_FLAT",
    "DISTRIBUTION_CONCENTRATED",
    "DISTRIBUTION_DIFFUSE",
    "UPPER_TAIL_MIN_TOTAL_GOALS",
    "ScorePrediction",
    "ScorePredictor",
    "predict_score",
]

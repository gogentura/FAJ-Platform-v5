#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SCORE PREDICTOR v1.0
============================================================

Назначение
----------
ScorePredictor формирует Score State из уже рассчитанного
ProbabilityModel распределения точных счетов.

Архитектура:

    GoalModel
        │
        ▼
    home_lambda
    away_lambda
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
        ├── predicted_score
        ├── second_score
        ├── third_score
        └── ranked_scores

КРИТИЧЕСКИЙ ПРИНЦИП
-------------------

ProbabilityModel является единственным владельцем
вероятностей точных счетов.

ScorePredictor:

    НЕ пересчитывает Poisson
    НЕ меняет P(score)
    НЕ применяет бонусы
    НЕ применяет штрафы
    НЕ использует FormWin
    НЕ использует Defence
    НЕ использует Control
    НЕ использует Anomaly
    НЕ использует SpecialForm
    НЕ использует WinnerState
    НЕ использует ScoreUtility

Математика:

    predicted_score = argmax P(score)

ScorePredictor является ranking / state layer,
а не второй probability model.
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import math


# ============================================================
# VERSION
# ============================================================

VERSION = "1.0"
FORMULA_STATUS = "CONTRACT_V1"

TOP_SCORES_COUNT = 10


# ============================================================
# SCORE PREDICTION
# ============================================================

@dataclass
class ScorePrediction:
    """
    Score State v1.

    Основной математический результат:

        predicted_score
        probability_score
        ranked_scores

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

    # Compatibility.
    home_lambda: Optional[float] = None
    away_lambda: Optional[float] = None

    # Старые имена API.
    home_xg: Optional[float] = None
    away_xg: Optional[float] = None

    # Старые compatibility fields.
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

    Источник вероятности:

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

        Compatibility:
            home_xg / away_xg могут быть переданы вместо
            home_lambda / away_lambda.

        Внутри используются именно lambda.
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
        # Lambda validation
        # ----------------------------------------------------

        if (
            home_lambda is None
            or away_lambda is None
            or home_lambda < 0.0
            or away_lambda < 0.0
        ):
            return self._unavailable_prediction(
                home_lambda=home_lambda,
                away_lambda=away_lambda,
                reason="INVALID_LAMBDA",
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
        # No normalization.
        # No probability modification.
        #
        # ProbabilityModel owns P(score).
        # ----------------------------------------------------

        ranked = sorted(
            candidates,
            key=lambda item: (
                -item["probability"],
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
            primary["probability"]
            if primary
            else None
        )

        second_probability = (
            second["probability"]
            if second
            else None
        )

        third_probability = (
            third["probability"]
            if third
            else None
        )

        # ----------------------------------------------------
        # Diagnostic probability summary only.
        #
        # Never used to modify score ranking.
        # ----------------------------------------------------

        probability_summary = (
            self._extract_probability_summary(
                probability_result
            )
        )

        diagnostics = {
            "version": VERSION,
            "formula_status": FORMULA_STATUS,

            "home_lambda": home_lambda,
            "away_lambda": away_lambda,

            # Compatibility names.
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
            # Explicit architectural contract.
            # ------------------------------------------------

            "probability_recalculated": False,
            "probability_modified": False,

            "poisson_recalculated": False,
            "low_score_correction_used": False,

            "secondary_signals_used": False,

            "winner_state_used": False,

            "form_win_used": False,
            "defence_used": False,
            "control_used": False,
            "anomaly_used": False,
            "special_used": False,

            "outcome_fit_used": False,
            "margin_fit_used": False,
            "btts_fit_used": False,
            "total_fit_used": False,
            "scenario_fit_used": False,
            "score_utility_used": False,
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

        Probabilities are NOT normalized and NOT recalculated.

        The numeric P(score) received from ProbabilityModel
        is preserved.
        """

        if score_probabilities is None:
            return []

        candidates: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # Dict:
        #
        # {
        #     "1:0": 0.18,
        #     "1:1": 0.14
        # }
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
                        item.get("probability")
                        if "probability" in item
                        else item.get("prob")
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
        # ProbabilityResult / object wrapper
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
        # Merge duplicates WITHOUT changing total probability
        #
        # Duplicate score records represent the same state.
        # Their supplied probabilities are summed.
        # ----------------------------------------------------

        merged: Dict[
            str,
            float,
        ] = {}

        for item in candidates:

            score = item["score"]
            probability = item["probability"]

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
                "probability": probability_value,
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

        No probability modification occurs here.
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

            "poisson_recalculated": False,
            "low_score_correction_used": False,

            "secondary_signals_used": False,

            "winner_state_used": False,

            "form_win_used": False,
            "defence_used": False,
            "control_used": False,
            "anomaly_used": False,
            "special_used": False,

            "outcome_fit_used": False,
            "margin_fit_used": False,
            "btts_fit_used": False,
            "total_fit_used": False,
            "scenario_fit_used": False,
            "score_utility_used": False,

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

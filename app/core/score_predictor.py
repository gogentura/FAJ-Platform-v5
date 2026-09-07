#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SCORE PREDICTOR v2.2
============================================================

Назначение
----------
ScorePredictor выбирает наиболее вероятные точные счета
из уже рассчитанного ProbabilityModel распределения.

Архитектура:

    GoalModel v2
          │
          ▼
       λ Home
       λ Away
          │
          ▼
    ProbabilityModel
          │
          ▼
    Score Distribution
          │
          ▼
    ScorePredictor v2.2
          │
          ├── likely_score
          ├── predicted_score
          ├── second_score
          ├── third_score
          └── top_scores

ВАЖНЫЙ ПРИНЦИП
---------------

ScorePredictor НЕ является второй probability model.

Он НЕ пересчитывает:

- OutcomeFit
- MarginFit
- BTTSFit
- TotalFit
- ScenarioFit
- ScoreUtility
- FormWin
- Defence
- Control
- Anomaly
- Special signals

Главный и единственный источник вероятности
точного счёта:

    P(score)

из ProbabilityModel.

Следовательно:

    predicted_score = argmax(P(score))

Top-N также строится непосредственно
по P(score).

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math


# ============================================================
# VERSION
# ============================================================

VERSION = "2.2"
FORMULA_STATUS = "RESEARCH_FORMULA"

TOP_SCORES_COUNT = 10


# ============================================================
# SCORE PREDICTION RESULT
# ============================================================

@dataclass
class ScorePrediction:
    """
    Результат ScorePredictor.

    Старые поля сохраняются ради совместимости
    с остальным FAJ.

    В v2.2:

        likely_score
            чистый argmax P(score)

        predicted_score
            основной выбранный счёт.
            В v2.2 равен likely_score.

        second_score
            второй по вероятности.

        third_score
            третий по вероятности.

        primary_score_value
            P(primary_score)

        second_score_value
            P(second_score)

        third_score_value
            P(third_score)

        probability_score
            P(predicted_score)

    Старые secondary-fit поля оставлены,
    но математически не используются.
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

    top_scores: List[Dict[str, Any]] = field(
        default_factory=list
    )

    home_xg: Optional[float] = None
    away_xg: Optional[float] = None

    # --------------------------------------------------------
    # Compatibility fields
    # --------------------------------------------------------

    outcome_fit_score: Optional[float] = None
    margin_fit_score: Optional[float] = None
    btts_fit_score: Optional[float] = None
    total_fit_score: Optional[float] = None
    scenario_fit_score: Optional[float] = None

    state_advantage: Optional[float] = None

    # --------------------------------------------------------
    # Probability summary
    # --------------------------------------------------------

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
    Score ranking layer.

    Input:

        ProbabilityModel score distribution.

    Output:

        mathematically highest-probability exact scores.

    No secondary scenario model.
    """

    def __init__(self) -> None:
        pass

    # ========================================================
    # PUBLIC API
    # ========================================================

    def predict(
        self,
        score_probabilities: Any,
        home_xg: Optional[float],
        away_xg: Optional[float],
        probability_result: Any = None,
    ) -> ScorePrediction:
        """
        Select exact scores directly from ProbabilityModel.

        Parameters
        ----------
        score_probabilities:
            Score probability distribution.

            Supported examples:

                {
                    "1:0": 0.18,
                    "1:1": 0.14,
                    "2:0": 0.11,
                }

            or a list of score records.

        home_xg:
            GoalModel home lambda.

        away_xg:
            GoalModel away lambda.

        probability_result:
            Optional ProbabilityModel result.
            Used only for diagnostics / summary.

        Returns
        -------
        ScorePrediction
        """

        home_xg = self._safe_float(home_xg)
        away_xg = self._safe_float(away_xg)

        # ----------------------------------------------------
        # Validate xG
        # ----------------------------------------------------

        if home_xg is None or away_xg is None:
            return self._unavailable_prediction(
                home_xg=home_xg,
                away_xg=away_xg,
                reason="INVALID_XG",
            )

        # ----------------------------------------------------
        # Normalize score distribution
        # ----------------------------------------------------

        candidates = self._normalize_score_probabilities(
            score_probabilities
        )

        if not candidates:
            return self._unavailable_prediction(
                home_xg=home_xg,
                away_xg=away_xg,
                reason="EMPTY_SCORE_DISTRIBUTION",
            )

        # ----------------------------------------------------
        # Pure mathematical ranking
        # ----------------------------------------------------

        evaluated = sorted(
            candidates,
            key=lambda item: item["probability"],
            reverse=True,
        )

        # ----------------------------------------------------
        # Top N
        # ----------------------------------------------------

        top_scores = evaluated[
            :TOP_SCORES_COUNT
        ]

        # ----------------------------------------------------
        # Primary / secondary / tertiary
        # ----------------------------------------------------

        primary = (
            top_scores[0]
            if len(top_scores) >= 1
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
            if primary is not None
            else None
        )

        predicted_score = likely_score

        second_score = (
            second["score"]
            if second is not None
            else None
        )

        third_score = (
            third["score"]
            if third is not None
            else None
        )

        primary_probability = (
            primary["probability"]
            if primary is not None
            else None
        )

        second_probability = (
            second["probability"]
            if second is not None
            else None
        )

        third_probability = (
            third["probability"]
            if third is not None
            else None
        )

        # ----------------------------------------------------
        # Probability summary
        # ----------------------------------------------------

        probability_summary = (
            self._extract_probability_summary(
                probability_result
            )
        )

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        diagnostics = {
            "version": VERSION,
            "formula_status": FORMULA_STATUS,

            "home_xg": home_xg,
            "away_xg": away_xg,

            "candidate_count": len(
                candidates
            ),

            "top_scores_count": len(
                top_scores
            ),

            "likely_score": likely_score,
            "likely_probability": primary_probability,

            "predicted_score": predicted_score,
            "predicted_probability": primary_probability,

            "second_score": second_score,
            "second_probability": second_probability,

            "third_score": third_score,
            "third_probability": third_probability,

            "selection_method": (
                "PURE_SCORE_PROBABILITY"
            ),

            "distribution_source": (
                "ProbabilityModel"
            ),

            # ------------------------------------------------
            # Explicitly document what is NOT used.
            # ------------------------------------------------

            "secondary_signals_used": False,

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

            home_xg=home_xg,
            away_xg=away_xg,

            # ------------------------------------------------
            # Compatibility fields.
            # No secondary mathematical scoring.
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
    # NORMALIZE SCORE PROBABILITIES
    # ========================================================

    def _normalize_score_probabilities(
        self,
        score_probabilities: Any,
    ) -> List[Dict[str, Any]]:
        """
        Normalize different ProbabilityModel output shapes
        into:

            [
                {
                    "score": "1:2",
                    "probability": 0.148
                },
                ...
            ]

        Missing/invalid probabilities are ignored.

        No probability is invented.
        """

        if score_probabilities is None:
            return []

        candidates: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # Dictionary:
        #
        # {
        #     "1:0": 0.15,
        #     "1:1": 0.12
        # }
        # ----------------------------------------------------

        if isinstance(
            score_probabilities,
            dict,
        ):
            for score, probability in (
                score_probabilities.items()
            ):
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
                    or probability_value < 0
                ):
                    continue

                candidates.append(
                    {
                        "score": score_text,
                        "probability": probability_value,
                    }
                )

        # ----------------------------------------------------
        # List / tuple
        # ----------------------------------------------------

        elif isinstance(
            score_probabilities,
            (
                list,
                tuple,
            ),
        ):
            for item in score_probabilities:

                score = None
                probability = None

                # --------------------------------------------
                # Tuple:
                #
                # ("1:2", 0.14)
                # --------------------------------------------

                if isinstance(
                    item,
                    (list, tuple),
                ):
                    if len(item) >= 2:
                        score = item[0]
                        probability = item[1]

                # --------------------------------------------
                # Dict record
                # --------------------------------------------

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

                # --------------------------------------------
                # Object
                # --------------------------------------------

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
                    or probability_value < 0
                ):
                    continue

                candidates.append(
                    {
                        "score": score_text,
                        "probability": probability_value,
                    }
                )

        # ----------------------------------------------------
        # Object containing score_probabilities
        # ----------------------------------------------------

        else:
            nested = self._get_value(
                score_probabilities,
                "score_probabilities",
            )

            if nested is not None:
                return self._normalize_score_probabilities(
                    nested
                )

            nested = self._get_value(
                score_probabilities,
                "scores",
            )

            if nested is not None:
                return self._normalize_score_probabilities(
                    nested
                )

            nested = self._get_value(
                score_probabilities,
                "distribution",
            )

            if nested is not None:
                return self._normalize_score_probabilities(
                    nested
                )

        # ----------------------------------------------------
        # Merge duplicate scores
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

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        total = sum(
            merged.values()
        )

        if total <= 0.0:
            return []

        normalized = [
            {
                "score": score,
                "probability": (
                    probability / total
                ),
            }
            for score, probability
            in merged.items()
        ]

        return normalized

    # ========================================================
    # SCORE PARSER
    # ========================================================

    @staticmethod
    def _parse_score(
        score: Any,
    ) -> Optional[str]:
        """
        Normalize score representation.

        Accepted examples:

            "1:2"
            "1-2"
            "1 : 2"
            (1, 2)
            [1, 2]
            {"home": 1, "away": 2}
        """

        if score is None:
            return None

        # ----------------------------------------------------
        # String
        # ----------------------------------------------------

        if isinstance(score, str):

            value = score.strip()

            if not value:
                return None

            value = value.replace(
                " ",
                "",
            )

            if "-" in value:
                parts = value.split(
                    "-",
                    1,
                )

            elif ":" in value:
                parts = value.split(
                    ":",
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

        # ----------------------------------------------------
        # Tuple / list
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Dict
        # ----------------------------------------------------

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
    # PROBABILITY SUMMARY
    # ========================================================

    def _extract_probability_summary(
        self,
        probability_result: Any,
    ) -> Dict[str, Any]:
        """
        Extract ProbabilityModel summary.

        IMPORTANT:

        This data is diagnostic only.

        It is NOT used to modify exact-score ranking.
        """

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

        return self._derive_probability_summary(
            probability_result
        )

    # ========================================================
    # DERIVE PROBABILITY SUMMARY
    # ========================================================

    def _derive_probability_summary(
        self,
        probability_result: Any,
    ) -> Dict[str, Any]:
        """
        Best-effort extraction of common
        ProbabilityModel aggregate values.

        These values are diagnostic only.
        """

        fields = (
            "home_win",
            "draw",
            "away_win",
            "btts_yes",
            "btts_no",
            "over_25",
            "under_25",
            "over_15",
            "under_15",
            "over_35",
            "under_35",
        )

        result: Dict[str, Any] = {}

        for field_name in fields:

            value = self._get_value(
                probability_result,
                field_name,
            )

            value = self._safe_float(
                value
            )

            if value is not None:
                result[field_name] = value

        # ----------------------------------------------------
        # Common alternate names
        # ----------------------------------------------------

        aliases = {
            "home_win_probability": "home_win",
            "draw_probability": "draw",
            "away_win_probability": "away_win",
            "btts_yes_probability": "btts_yes",
            "btts_no_probability": "btts_no",
            "over_25_probability": "over_25",
            "under_25_probability": "under_25",
        }

        for source_name, target_name in (
            aliases.items()
        ):

            if target_name in result:
                continue

            value = self._get_value(
                probability_result,
                source_name,
            )

            value = self._safe_float(
                value
            )

            if value is not None:
                result[target_name] = value

        return result

    # ========================================================
    # UNAVAILABLE RESULT
    # ========================================================

    def _unavailable_prediction(
        self,
        *,
        home_xg: Optional[float],
        away_xg: Optional[float],
        reason: str,
    ) -> ScorePrediction:
        """
        Return safe empty result when prediction
        cannot be calculated.

        No artificial score is created.
        """

        diagnostics = {
            "version": VERSION,
            "formula_status": FORMULA_STATUS,

            "home_xg": home_xg,
            "away_xg": away_xg,

            "candidate_count": 0,

            "likely_score": None,
            "likely_probability": None,

            "predicted_score": None,
            "predicted_probability": None,

            "selection_method": (
                "PURE_SCORE_PROBABILITY"
            ),

            "distribution_source": (
                "ProbabilityModel"
            ),

            "error": reason,

            "secondary_signals_used": False,

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

            likely_score=None,
            predicted_score=None,

            second_score=None,
            third_score=None,

            primary_score_value=None,
            second_score_value=None,
            third_score_value=None,

            probability_score=None,

            top_scores=[],

            home_xg=home_xg,
            away_xg=away_xg,

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
        """
        Convert value to finite float.

        None stays None.
        Invalid values stay None.
        """

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
        """
        Read field from dict or object.
        """

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
    # CLAMP
    # ========================================================

    @staticmethod
    def _clamp(
        value: Optional[float],
        minimum: float = 0.0,
        maximum: float = 1.0,
    ) -> Optional[float]:
        """
        Generic numeric clamp.

        Kept as a technical helper for compatibility.
        """

        if value is None:
            return None

        return max(
            minimum,
            min(
                maximum,
                value,
            ),
        )

    # ========================================================
    # LOG SAFE
    # ========================================================

    @staticmethod
    def _log_safe(
        value: Optional[float],
        floor: float = 1e-12,
    ) -> Optional[float]:
        """
        Safe natural logarithm.

        Kept as a technical compatibility helper.

        v2.2 does NOT use logarithmic ScoreUtility.
        """

        if value is None:
            return None

        value = max(
            value,
            floor,
        )

        return math.log(value)

    # ========================================================
    # COMPATIBILITY PUBLIC METHOD
    # ========================================================

    def predict_score(
        self,
        score_probabilities: Any,
        home_xg: Optional[float],
        away_xg: Optional[float],
        probability_result: Any = None,
    ) -> ScorePrediction:
        """
        Compatibility wrapper.

        Delegates directly to predict().
        """

        return self.predict(
            score_probabilities=score_probabilities,
            home_xg=home_xg,
            away_xg=away_xg,
            probability_result=probability_result,
        )


# ============================================================
# MODULE-LEVEL CONVENIENCE FUNCTION
# ============================================================

def predict_score(
    score_probabilities: Any,
    home_xg: Optional[float],
    away_xg: Optional[float],
    probability_result: Any = None,
) -> ScorePrediction:
    """
    Module-level convenience API.
    """

    predictor = ScorePredictor()

    return predictor.predict(
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
    "ScorePrediction",
    "ScorePredictor",
    "predict_score",
]

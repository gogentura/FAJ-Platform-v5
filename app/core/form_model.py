from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Optional, Sequence, Tuple

from .brain_contract import (
    FormContext, FormModelResult, PatternState,
    HISTORY_MATCHES, RESULT_WIN, RESULT_DRAW, RESULT_LOSS,
    DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD,
    result_to_points, validate_form_context, validate_pattern_state,
)

MODEL_VERSION = "1.0.0"

CONTRACT_CONSTANT = "CONTRACT_CONSTANT"
RESEARCH_PARAMETER = "RESEARCH_PARAMETER"
CALIBRATED_PARAMETER = "CALIBRATED_PARAMETER"


@dataclass(frozen=True)
class FormModelConfig:
    # RESEARCH_PARAMETER — transparent baseline; not calibrated truth.
    recency_slope: float = 1.0
    dark_horse_xg_max: float = 1.0
    dark_horse_finishing_delta_min: float = 0.35
    lukaku_xg_min: float = 1.5
    lukaku_finishing_delta_max: float = -0.35
    gladiator_min_wins: int = 5
    fortress_min_unbeaten: int = 4
    fortress_window_matches: int = 5
    leicester_min_away_wins: int = 4
    leicester_window_matches: int = 5
    kepa_goals_against_high: float = 1.8
    haaland_goals_for_high: float = 1.8
    god_kiss_min_away_streak: int = 3

    def __post_init__(self):
        for name in (
            "recency_slope", "dark_horse_xg_max",
            "dark_horse_finishing_delta_min", "lukaku_xg_min",
            "kepa_goals_against_high", "haaland_goals_for_high",
        ):
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        if not isfinite(self.lukaku_finishing_delta_max):
            raise ValueError("lukaku_finishing_delta_max must be finite")


@dataclass(frozen=True)
class EffectSignal:
    signal: Optional[float]
    evidence: Tuple[str, ...] = ()
    confidence: Optional[float] = None


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _clamp(value, lo=0.0, hi=1.0):
    if value is None:
        return None
    return max(lo, min(hi, float(value)))


def _result_value(result: str) -> float:
    return result_to_points(result) / 3.0


def _recency_weights(n: int, slope: float):
    return tuple(1.0 + slope * i for i in range(n))


def _weighted_mean(values, weights):
    pairs = [(float(v), float(w)) for v, w in zip(values, weights)
             if v is not None and w > 0]
    if not pairs:
        return None
    return sum(v*w for v, w in pairs) / sum(w for _, w in pairs)


def _trend(results: Sequence[str]) -> Optional[float]:
    if len(results) < 2:
        return None
    y = [_result_value(r) for r in results]
    x = list(range(len(y)))
    xm, ym = _mean(x), _mean(y)
    den = sum((v-xm)**2 for v in x)
    if not den:
        return 0.0
    slope = sum((a-xm)*(b-ym) for a,b in zip(x,y)) / den
    return _clamp(slope / 0.5, -1.0, 1.0)


def _consistency(results: Sequence[str]) -> Optional[float]:
    if not results:
        return None
    if len(results) == 1:
        return 1.0
    changes = sum(a != b for a,b in zip(results, results[1:]))
    return _clamp(1.0 - changes/(len(results)-1))


def _bucket_score(results, difficulties, bucket):
    values = [_result_value(r) for r,d in zip(results,difficulties) if d == bucket]
    return _mean(values)


def _difficulty_adjusted(results, difficulties):
    # Structural descriptor only: easy=1, medium=1.5, hard=2.
    # NOT opponent strength and NOT a calibrated rating.
    weights = {
        DIFFICULTY_EASY: 1.0,
        DIFFICULTY_MEDIUM: 1.5,
        DIFFICULTY_HARD: 2.0,
    }
    pairs = [(_result_value(r), weights[d]) for r,d in zip(results,difficulties)
             if d in weights]
    if not pairs:
        return None
    return _clamp(sum(v*w for v,w in pairs) / (len(pairs)*2.0))


def _venue_strength(matches, wins, draws):
    if not matches:
        return None
    return _clamp((wins*3 + draws)/(3*matches))


def _symmetric_delta(delta, scale=1.0):
    if delta is None:
        return None
    return delta/(abs(delta)+scale)


class EffectDetectors:
    """Pure detectors. Signals never modify xG, score or probabilities."""

    def __init__(self, config: FormModelConfig):
        self.c = config

    def dark_horse(self, ctx):
        if ctx.xg_avg is None or ctx.goals_for_avg is None:
            return EffectSignal(None, (), None)
        delta = ctx.goals_for_avg - ctx.xg_avg
        detected = ctx.xg_avg <= self.c.dark_horse_xg_max and delta >= self.c.dark_horse_finishing_delta_min
        signal = _clamp(delta / self.c.dark_horse_finishing_delta_min)
        return EffectSignal(signal if detected else 0.0,
                            (f"xg_avg={ctx.xg_avg}", f"finishing_delta={delta}"), 1.0)

    def lukaku(self, ctx):
        if ctx.xg_avg is None or ctx.goals_for_avg is None:
            return EffectSignal(None, (), None)
        delta = ctx.goals_for_avg - ctx.xg_avg
        detected = ctx.xg_avg >= self.c.lukaku_xg_min and delta <= self.c.lukaku_finishing_delta_max
        signal = _clamp(abs(delta) / abs(self.c.lukaku_finishing_delta_max))
        return EffectSignal(signal if detected else 0.0,
                            (f"xg_avg={ctx.xg_avg}", f"finishing_delta={delta}"), 1.0)

    def gladiator(self, ctx, pat):
        streak = max(ctx.consecutive_wins, pat.consecutive_wins)
        return EffectSignal(
            _clamp(streak/max(self.c.gladiator_min_wins,1))
            if streak >= self.c.gladiator_min_wins else 0.0,
            (f"consecutive_wins={streak}",), 1.0)

    def fortress(self, ctx, pat):
        unbeaten = max(ctx.home_unbeaten_count, pat.home_unbeaten_count)
        matches = max(ctx.home_matches, pat.home_matches)
        ok = matches >= self.c.fortress_window_matches and unbeaten >= self.c.fortress_min_unbeaten
        return EffectSignal(
            _clamp(unbeaten/max(self.c.fortress_window_matches,1)) if ok else 0.0,
            (f"home_matches={matches}", f"home_unbeaten_count={unbeaten}"), 1.0)

    def leicester(self, ctx, pat):
        wins = max(ctx.away_wins_recent, pat.away_wins)
        matches = max(ctx.away_matches, pat.away_matches)
        ok = matches >= self.c.leicester_window_matches and wins >= self.c.leicester_min_away_wins
        return EffectSignal(
            _clamp(wins/max(self.c.leicester_window_matches,1)) if ok else 0.0,
            (f"away_matches={matches}", f"away_wins={wins}"), 1.0)

    def kepa(self, ctx):
        if ctx.goals_against_avg is None:
            return EffectSignal(None, (), None)
        signal = _clamp(ctx.goals_against_avg/self.c.kepa_goals_against_high)
        return EffectSignal(
            signal if ctx.goals_against_avg >= self.c.kepa_goals_against_high else 0.0,
            (f"goals_against_avg={ctx.goals_against_avg}",), 1.0)

    def haaland(self, ctx):
        if ctx.goals_for_avg is None:
            return EffectSignal(None, (), None)
        signal = _clamp(ctx.goals_for_avg/self.c.haaland_goals_for_high)
        return EffectSignal(
            signal if ctx.goals_for_avg >= self.c.haaland_goals_for_high else 0.0,
            (f"goals_for_avg={ctx.goals_for_avg}",), 1.0)

    def god_kiss(self, ctx, pat):
        streak = max(ctx.consecutive_away_matches, pat.consecutive_away_matches)
        ok = streak >= self.c.god_kiss_min_away_streak
        return EffectSignal(
            _clamp(streak/max(self.c.god_kiss_min_away_streak,1)) if ok else 0.0,
            (f"consecutive_away_matches={streak}",
             "next_match_home_required_for_activation=True"), 1.0)


class FormModel:
    """Deterministic interpreter of FormContext + PatternState."""

    def __init__(self, config: Optional[FormModelConfig] = None):
        self.config = config or FormModelConfig()
        self.effects = EffectDetectors(self.config)

    def calculate(self, context: FormContext, patterns: PatternState) -> FormModelResult:
        validate_form_context(context)
        validate_pattern_state(patterns)

        if context.matches_count != HISTORY_MATCHES or patterns.matches_count != HISTORY_MATCHES:
            raise ValueError(f"FormModel requires exactly {HISTORY_MATCHES} matches")

        results = tuple(context.results)
        if len(results) != HISTORY_MATCHES:
            raise ValueError(f"FormContext.results must contain exactly {HISTORY_MATCHES} items")

        difficulties = tuple(context.difficulty)
        if difficulties and len(difficulties) != len(results):
            raise ValueError("difficulty and results must have equal length")

        weights = _recency_weights(len(results), self.config.recency_slope)
        values = tuple(_result_value(r) for r in results)

        points_rate = context.points/(3*context.matches_count)
        recent_points_rate = _weighted_mean(values, weights)
        difficulty_form = _difficulty_adjusted(results, difficulties) if difficulties else recent_points_rate

        trend_score = _trend(results)
        if trend_score is None:
            trend = None
        elif trend_score > 0.10:
            trend = "improving"
        elif trend_score < -0.10:
            trend = "declining"
        else:
            trend = "stable"

        consistency = _consistency(results)

        goal_attack = _clamp(context.goals_for_avg/3.0) if context.goals_for_avg is not None else None
        goal_defense = _clamp(1.0-context.goals_against_avg/3.0) if context.goals_against_avg is not None else None
        xg_attack = _clamp(context.xg_avg/3.0) if context.xg_avg is not None else None
        xg_defense = _clamp(1.0-context.xga_avg/3.0) if context.xga_avg is not None else None

        finishing_delta = context.goals_for_avg-context.xg_avg if context.goals_for_avg is not None and context.xg_avg is not None else None
        defensive_delta = context.goals_against_avg-context.xga_avg if context.goals_against_avg is not None and context.xga_avg is not None else None

        # Goals and xG remain separate; geometric mean only produces a descriptive
        # joint-strength state when both observations exist.
        attack_strength = ((goal_attack*xg_attack)**0.5
                           if goal_attack is not None and xg_attack is not None
                           else goal_attack if goal_attack is not None else xg_attack)
        defense_strength = ((goal_defense*xg_defense)**0.5
                            if goal_defense is not None and xg_defense is not None
                            else goal_defense if goal_defense is not None else xg_defense)

        hard = _bucket_score(results, difficulties, DIFFICULTY_HARD) if difficulties else None
        medium = _bucket_score(results, difficulties, DIFFICULTY_MEDIUM) if difficulties else None
        easy = _bucket_score(results, difficulties, DIFFICULTY_EASY) if difficulties else None

        e1 = self.effects.dark_horse(context)
        e2 = self.effects.lukaku(context)
        e3 = self.effects.gladiator(context, patterns)
        e4 = self.effects.fortress(context, patterns)
        e5 = self.effects.leicester(context, patterns)
        e6 = self.effects.kepa(context)
        e7 = self.effects.haaland(context)
        e8 = self.effects.god_kiss(context, patterns)

        # Effects are intentionally excluded from form_score.
        form_score = _weighted_mean(
            [recent_points_rate, difficulty_form],
            [1.0, 1.0],
        )

        return FormModelResult(
            form_score=form_score,
            attack_strength=attack_strength,
            defense_strength=defense_strength,
            home_strength=_venue_strength(context.home_matches, context.home_wins, context.home_draws),
            away_strength=_venue_strength(context.away_matches, context.away_wins, context.away_draws),
            trend=trend,
            consistency=consistency,
            hard_match_strength=hard,
            medium_match_strength=medium,
            easy_match_strength=easy,
            difficulty_adjustment=(difficulty_form-recent_points_rate
                                   if difficulty_form is not None and recent_points_rate is not None else None),
            goal_strength=goal_attack,
            xg_strength=xg_attack,
            realization_strength=_symmetric_delta(finishing_delta),
            defensive_xg_strength=_symmetric_delta(defensive_delta),
            dark_horse_effect=e1.signal,
            lukaku_effect=e2.signal,
            gladiator_effect=e3.signal,
            fortress_effect=e4.signal,
            leicester_effect=e5.signal,
            kepa_effect=e6.signal,
            haaland_effect=e7.signal,
            god_kiss_effect=e8.signal,
        )


def calculate_form(context: FormContext, patterns: PatternState,
                   config: Optional[FormModelConfig] = None) -> FormModelResult:
    return FormModel(config).calculate(context, patterns)

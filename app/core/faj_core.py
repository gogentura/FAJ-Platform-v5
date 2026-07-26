# =====================================================
# FAJ Platform v6.7.1
# FAJ Core Engine
# =====================================================
import time
import hashlib
import numpy as np
from math import exp
from math import factorial
from datetime import datetime
from app.database import get_db
from app.passport_manager import (
    load_passport,
    get_team_by_alias,
    calculate_faj_rating
)

class FAJCore:
    VERSION = "6.7.1"
    LEAGUE_MEAN = 1.35
    HOME_ADVANTAGE = 1.08
    MAX_GOALS = 8
    SIMULATIONS = 10000
    MIN_XG = 0.10
    MAX_XG = 4.00

    # Сезонные коэффициенты
    SEASON_PHASE = {
        "start": 0.90,
        "early": 0.95,
        "mid": 1.00,
        "end": 1.05
    }

    def __init__(self):
        self.version = self.VERSION

    # =====================================================
    # PUBLIC API
    # =====================================================
    def predict(
        self,
        home_team,
        away_team,
        league="RPL"
    ):
        return self.predict_match(
            home_team,
            away_team,
            league
        )

    # =====================================================
    # LOAD TEAM
    # =====================================================
    def load_team(
        self,
        team
    ):
        alias = get_team_by_alias(team)
        if alias:
            team = alias
        passport = load_passport(team)
        if passport:
            return passport
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM team_passports
            WHERE LOWER(team)=LOWER(%s)
            LIMIT 1
            """,
            (team,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    # =====================================================
    # FIND FIXTURE
    # =====================================================
    def find_fixture(
        self,
        home,
        away,
        league
    ):
        try:
            conn = get_db()
            cur = conn.cursor()
            today = datetime.now().date().isoformat()
            cur.execute(
                """
                SELECT id
                FROM fixtures
                WHERE
                    LOWER(home_team)=LOWER(%s)
                AND
                    LOWER(away_team)=LOWER(%s)
                AND
                    league=%s
                AND
                    match_date>=%s
                AND
                    status='scheduled'
                ORDER BY match_date
                LIMIT 1
                """,
                (
                    home,
                    away,
                    league,
                    today
                )
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return row["id"]
        except Exception:
            pass
        return None

    # =====================================================
    # SAFE FLOAT
    # =====================================================
    def safe(
        self,
        value,
        default=0
    ):
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    # =====================================================
    # SEASON PHASE
    # =====================================================
    def get_season_phase(
        self,
        season="2026/27"
    ):
        today = datetime.now()
        start_date = datetime(
            2026,
            7,
            25
        )
        days = (
            today - start_date
        ).days
        if days < 30:
            return "start"
        elif days < 90:
            return "early"
        elif days < 210:
            return "mid"
        else:
            return "end"

    # =====================================================
    # PASSPORT QUALITY
    # =====================================================
    def passport_quality(
        self,
        team
    ):
        fields = [
            "attack",
            "defense",
            "control",
            "form",
            "xg_for",
            "xg_against"
        ]
        filled = 0
        for f in fields:
            if team.get(f) is not None:
                filled += 1
        return round(
            filled / len(fields),
            2
        )

    # =====================================================
    # VOLATILITY
    # =====================================================
    def calculate_volatility(
        self,
        simulation
    ):
        probs = [
            simulation["home_win_prob"],
            simulation["draw_prob"],
            simulation["away_win_prob"]
        ]
        return round(
            max(probs) - min(probs),
            3
        )

    # =====================================================
    # XG MODEL
    # =====================================================
    def calculate_xg(
        self,
        team,
        opponent,
        home=True
    ):
        attack = self.safe(team.get("attack"), 70)
        defense = self.safe(opponent.get("defense"), 70)
        control = self.safe(team.get("control"), 70)
        form = self.safe(team.get("form"), 70)
        efficiency = self.safe(team.get("efficiency"), 70)
        mentality = self.safe(team.get("mentality"), 70)
        fitness = self.safe(team.get("fitness"), 70)
        injuries = self.safe(team.get("injury_index"), 0)
        fatigue = self.safe(team.get("fatigue_index"), 0)
        transfers = self.safe(team.get("transfer_index"), 0)
        historical = self.safe(
            team.get("xg_for", team.get("historical_xg_value")),
            self.LEAGUE_MEAN
        )
        xg = historical
        xg *= (1 + (attack - 70) / 180)
        xg *= (1 + (70 - defense) / 220)
        xg *= (1 + (control - 70) / 450)
        xg *= (1 + (form - 70) / 280)
        xg *= (1 + (efficiency - 70) / 320)
        xg *= (1 + (mentality - 70) / 600)
        xg *= (1 + (fitness - 70) / 500)
        xg *= (1 - injuries / 450)
        xg *= (1 - fatigue / 450)
        xg *= (1 + transfers / 900)
        if home:
            xg *= self.HOME_ADVANTAGE

        # ---- Сезонный модификатор ----
        phase = self.get_season_phase()
        modifier = self.SEASON_PHASE.get(
            phase,
            1.0
        )
        xg *= modifier

        return round(
            max(
                self.MIN_XG,
                min(
                    self.MAX_XG,
                    xg
                )
            ),
            3
        )

    # =====================================================
    # DETERMINISTIC RANDOM
    # =====================================================
    def build_seed(
        self,
        home,
        away,
        league
    ):
        key = f"{home}|{away}|{league}"
        value = hashlib.md5(
            key.encode()
        ).hexdigest()
        return int(
            value[:8],
            16
        )

    # =====================================================
    # POISSON
    # =====================================================
    def poisson(
        self,
        goals,
        xg
    ):
        return exp(-xg) * (xg ** goals) / factorial(goals)

    # =====================================================
    # MONTE CARLO
    # =====================================================
    def simulate(
        self,
        home,
        away,
        league,
        home_xg,
        away_xg
    ):
        seed = self.build_seed(
            home,
            away,
            league
        )
        rng = np.random.default_rng(seed)
        home_goals = rng.poisson(
            home_xg,
            self.SIMULATIONS
        )
        away_goals = rng.poisson(
            away_xg,
            self.SIMULATIONS
        )
        scores = {}
        home_win = 0
        draw = 0
        away_win = 0
        for h, a in zip(
            home_goals,
            away_goals
        ):
            h = min(
                int(h),
                self.MAX_GOALS
            )
            a = min(
                int(a),
                self.MAX_GOALS
            )
            scores[(h, a)] = scores.get(
                (h, a),
                0
            ) + 1
            if h > a:
                home_win += 1
            elif h == a:
                draw += 1
            else:
                away_win += 1
        top_scores = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return {
            "home_win_prob": round(home_win / self.SIMULATIONS, 4),
            "draw_prob": round(draw / self.SIMULATIONS, 4),
            "away_win_prob": round(away_win / self.SIMULATIONS, 4),
            "scores": scores,
            "top_scores": top_scores
        }

    # =====================================================
    # STABILITY INDEX
    # =====================================================
    def calculate_stability(
        self,
        simulation
    ):
        top_scores = simulation["top_scores"]
        if not top_scores:
            return 0
        best = top_scores[0][1]
        second = top_scores[1][1] if len(top_scores) > 1 else 0
        stability = (best - second) / self.SIMULATIONS * 100
        return round(
            max(
                0,
                min(
                    100,
                    stability * 8
                )
            ),
            1
        )

    # =====================================================
    # CONFIDENCE (улучшенный с учётом качества паспортов)
    # =====================================================
    def calculate_confidence(
        self,
        home_rating,
        away_rating,
        home_xg,
        away_xg,
        winner_probability,
        stability,
        home_quality,
        away_quality
    ):
        rating_gap = abs(
            home_rating - away_rating
        )
        xg_gap = abs(
            home_xg - away_xg
        )
        confidence = (
            winner_probability * 0.55 +
            rating_gap * 0.30 +
            xg_gap * 25 * 0.15 +
            stability * 0.20
        )
        # ---- Корректировка на качество данных ----
        quality_modifier = (
            home_quality +
            away_quality
        ) / 2
        confidence *= quality_modifier

        confidence = max(
            35,
            min(
                98,
                confidence
            )
        )
        return round(
            confidence,
            1
        )

    # =====================================================
    # DECISION ENGINE
    # =====================================================
    def make_decision(
        self,
        simulation,
        home_xg,
        away_xg
    ):
        home = simulation["home_win_prob"]
        draw = simulation["draw_prob"]
        away = simulation["away_win_prob"]
        stability = self.calculate_stability(
            simulation
        )
        if home >= draw and home >= away:
            winner = "home"
            winner_name = "Хозяева"
            target = lambda s: int(s[0]) > int(s[1])
        elif away >= draw and away >= home:
            winner = "away"
            winner_name = "Гости"
            target = lambda s: int(s[0]) < int(s[1])
        else:
            winner = "draw"
            winner_name = "Ничья"
            target = lambda s: int(s[0]) == int(s[1])
        expected_score = None
        for score, count in simulation["top_scores"]:
            if target(score):
                expected_score = score
                break
        if expected_score is None:
            expected_score = simulation["top_scores"][0][0]
        expected_score = f"{expected_score[0]}-{expected_score[1]}"
        winner_probability = round(
            max(
                home,
                draw,
                away
            ) * 100,
            1
        )
        return {
            "winner": winner,
            "winner_name": winner_name,
            "winner_probability": winner_probability,
            "home_probability": round(home * 100, 1),
            "draw_probability": round(draw * 100, 1),
            "away_probability": round(away * 100, 1),
            "expected_score": expected_score,
            "stability": stability
        }

    # =====================================================
    # BTTS
    # =====================================================
    def btts_probability(
        self,
        home_xg,
        away_xg
    ):
        p0h = exp(-home_xg)
        p0a = exp(-away_xg)
        return round(
            1 - p0h - p0a + p0h * p0a,
            3
        )

    # =====================================================
    # OVER / UNDER
    # =====================================================
    def total_probability(
        self,
        home_xg,
        away_xg,
        limit
    ):
        prob = 0
        for h in range(self.MAX_GOALS + 1):
            for a in range(self.MAX_GOALS + 1):
                value = self.poisson(
                    h,
                    home_xg
                ) * self.poisson(
                    a,
                    away_xg
                )
                if h + a > limit:
                    prob += value
        return round(
            prob,
            3
        )

    # =====================================================
    # MAIN PREDICTION
    # =====================================================
    def predict_match(
        self,
        home_team,
        away_team,
        league="RPL"
    ):
        started = time.time()
        home = self.load_team(home_team)
        away = self.load_team(away_team)
        if home is None:
            raise Exception(
                f"Паспорт не найден: {home_team}"
            )
        if away is None:
            raise Exception(
                f"Паспорт не найден: {away_team}"
            )
        fixture_id = self.find_fixture(
            home_team,
            away_team,
            league
        )
        home_rating = calculate_faj_rating(home)
        away_rating = calculate_faj_rating(away)
        home_xg = self.calculate_xg(
            home,
            away,
            True
        )
        away_xg = self.calculate_xg(
            away,
            home,
            False
        )
        simulation = self.simulate(
            home_team,
            away_team,
            league,
            home_xg,
            away_xg
        )
        decision = self.make_decision(
            simulation,
            home_xg,
            away_xg
        )

        # ---- Новые показатели ----
        home_quality = self.passport_quality(home)
        away_quality = self.passport_quality(away)
        volatility = self.calculate_volatility(simulation)
        season_phase = self.get_season_phase()

        confidence = self.calculate_confidence(
            home_rating,
            away_rating,
            home_xg,
            away_xg,
            decision["winner_probability"],
            decision["stability"],
            home_quality,
            away_quality
        )
        decision["confidence"] = confidence

        over15 = self.total_probability(
            home_xg,
            away_xg,
            1
        )
        over25 = self.total_probability(
            home_xg,
            away_xg,
            2
        )
        over35 = self.total_probability(
            home_xg,
            away_xg,
            3
        )

        result = {
            "version": self.VERSION,
            "fixture_id": fixture_id,
            "league": league,
            "home_team": home_team,
            "away_team": away_team,
            "home_rating": round(home_rating, 1),
            "away_rating": round(away_rating, 1),
            "season_phase": season_phase,
            "passport_quality": {
                "home": home_quality,
                "away": away_quality
            },
            "volatility": volatility,
            "xg": {
                "predicted": {
                    "home": round(home_xg, 2),
                    "away": round(away_xg, 2)
                }
            },
            "simulation": {
                "top_scores": [
                    {
                        "score": f"{s[0]}-{s[1]}",
                        "probability": round(
                            c / self.SIMULATIONS * 100,
                            2
                        )
                    }
                    for s, c in simulation["top_scores"][:10]
                ]
            },
            "decision": decision,
            "btts": self.btts_probability(
                home_xg,
                away_xg
            ),
            "over15": over15,
            "over25": over25,
            "under25": round(
                1 - over25,
                3
            ),
            "over35": over35,
            "processing_time": round(
                time.time() - started,
                3
            )
        }
        return result

    # =====================================================
    # INFO
    # =====================================================
    def info(self):
        return {
            "engine": "FAJ Engine",
            "version": self.VERSION,
            "simulations": self.SIMULATIONS,
            "league_mean": self.LEAGUE_MEAN,
            "home_advantage": self.HOME_ADVANTAGE
        }

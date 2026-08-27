#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Match Context Service v1.0
============================================================

НАЗНАЧЕНИЕ:
    Получение дополнительного статистического контекста
    для конкретного матча.

АРХИТЕКТУРА:

    Predict Round
          ↓
    MatchContextService
          ↓
    DataFootballAPI
          ↓
    внешний API

ВАЖНО:

    Этот сервис НЕ:
        - пишет в SQLite;
        - изменяет facts;
        - изменяет passports;
        - изменяет FAJ ratings;
        - изменяет PredictionManager;
        - обучает ETC.

Он является READ-ONLY Scout Layer.

Запускается только по запросу пользователя.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.parsers.data_football_api import (
    DataFootballAPI,
    DataFootballAPIError,
    get_data_football_api,
)


logger = logging.getLogger(__name__)


class MatchContextError(Exception):
    """Ошибка получения контекста матча."""


class MatchContextService:
    """
    Read-only сервис статистического контекста.

    Не имеет доступа к FAJDatabase.
    """

    VERSION = "1.0"

    def __init__(
        self,
        api: Optional[DataFootballAPI] = None,
    ):
        self.api = api or get_data_football_api()

    # ========================================================
    # MAIN
    # ========================================================

    def get_match_context(
        self,
        home_team_id: int,
        away_team_id: int,
        *,
        h2h_last: int = 10,
        form_last: int = 5,
    ) -> Dict[str, Any]:
        """
        Получает полный контекст конкретного матча.

        Один вызов запускается только тогда, когда пользователь
        запросил дополнительную статистику.
        """

        if not self.api.available:
            raise MatchContextError(
                "Data Football API не настроен. "
                "Установите API_FOOTBALL_KEY."
            )

        try:
            h2h = self.api.get_h2h(
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                last=h2h_last,
            )

            home_last = self.api.get_team_last_matches(
                team_id=home_team_id,
                last=form_last,
            )

            away_last = self.api.get_team_last_matches(
                team_id=away_team_id,
                last=form_last,
            )

            home_matches = self.api.get_team_home_matches(
                team_id=home_team_id,
                last=form_last,
            )

            away_matches = self.api.get_team_away_matches(
                team_id=away_team_id,
                last=form_last,
            )

            return {
                "status": "ok",
                "version": self.VERSION,
                "home_team_id": int(home_team_id),
                "away_team_id": int(away_team_id),

                "h2h": h2h,

                "home": {
                    "last_matches": home_last,
                    "home_matches": home_matches,
                    "last_summary": self._summarize_matches(
                        home_last,
                        home_team_id,
                    ),
                    "home_summary": self._summarize_matches(
                        home_matches,
                        home_team_id,
                    ),
                },

                "away": {
                    "last_matches": away_last,
                    "away_matches": away_matches,
                    "last_summary": self._summarize_matches(
                        away_last,
                        away_team_id,
                    ),
                    "away_summary": self._summarize_matches(
                        away_matches,
                        away_team_id,
                    ),
                },

                "h2h_summary": self._summarize_h2h(
                    h2h,
                    home_team_id,
                    away_team_id,
                ),
            }

        except DataFootballAPIError as exc:
            logger.warning(
                "Match context API error: %s",
                exc,
            )

            raise MatchContextError(
                str(exc)
            ) from exc

        except Exception as exc:
            logger.exception(
                "Unexpected MatchContext error"
            )

            raise MatchContextError(
                f"Ошибка получения статистического контекста: {exc}"
            ) from exc

    # ========================================================
    # H2H SUMMARY
    # ========================================================

    @staticmethod
    def _summarize_h2h(
        matches: List[Dict[str, Any]],
        home_team_id: int,
        away_team_id: int,
    ) -> Dict[str, Any]:

        summary = {
            "matches": 0,
            "home_wins": 0,
            "draws": 0,
            "away_wins": 0,
            "home_goals": 0,
            "away_goals": 0,
        }

        for match in matches:
            teams = match.get("teams", {})
            goals = match.get("goals", {})

            home = teams.get("home", {})
            away = teams.get("away", {})

            home_id = home.get("id")
            away_id = away.get("id")

            home_goals = goals.get("home")
            away_goals = goals.get("away")

            if (
                home_id is None
                or away_id is None
                or home_goals is None
                or away_goals is None
            ):
                continue

            try:
                home_goals = int(home_goals)
                away_goals = int(away_goals)
            except (TypeError, ValueError):
                continue

            summary["matches"] += 1

            # Приводим результат к перспективе
            # выбранных home_team / away_team.
            if home_id == home_team_id:
                selected_home_goals = home_goals
                selected_away_goals = away_goals

            elif home_id == away_team_id:
                selected_home_goals = away_goals
                selected_away_goals = home_goals

            else:
                continue

            summary["home_goals"] += selected_home_goals
            summary["away_goals"] += selected_away_goals

            if selected_home_goals > selected_away_goals:
                summary["home_wins"] += 1

            elif selected_home_goals < selected_away_goals:
                summary["away_wins"] += 1

            else:
                summary["draws"] += 1

        if summary["matches"]:
            summary["home_goals_avg"] = round(
                summary["home_goals"]
                / summary["matches"],
                2,
            )

            summary["away_goals_avg"] = round(
                summary["away_goals"]
                / summary["matches"],
                2,
            )

        else:
            summary["home_goals_avg"] = 0.0
            summary["away_goals_avg"] = 0.0

        return summary

    # ========================================================
    # TEAM SUMMARY
    # ========================================================

    @staticmethod
    def _summarize_matches(
        matches: List[Dict[str, Any]],
        team_id: int,
    ) -> Dict[str, Any]:

        summary = {
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "goals_for_avg": 0.0,
            "goals_against_avg": 0.0,
            "points_avg": 0.0,
        }

        for match in matches:
            teams = match.get("teams", {})
            goals = match.get("goals", {})

            home = teams.get("home", {})
            away = teams.get("away", {})

            home_id = home.get("id")
            away_id = away.get("id")

            home_goals = goals.get("home")
            away_goals = goals.get("away")

            if (
                home_id is None
                or away_id is None
                or home_goals is None
                or away_goals is None
            ):
                continue

            try:
                home_goals = int(home_goals)
                away_goals = int(away_goals)
            except (TypeError, ValueError):
                continue

            if home_id == team_id:
                scored = home_goals
                conceded = away_goals

            elif away_id == team_id:
                scored = away_goals
                conceded = home_goals

            else:
                continue

            summary["matches"] += 1
            summary["goals_for"] += scored
            summary["goals_against"] += conceded

            if scored > conceded:
                summary["wins"] += 1
                summary["points"] += 3

            elif scored == conceded:
                summary["draws"] += 1
                summary["points"] += 1

            else:
                summary["losses"] += 1

        if summary["matches"]:
            summary["goals_for_avg"] = round(
                summary["goals_for"]
                / summary["matches"],
                2,
            )

            summary["goals_against_avg"] = round(
                summary["goals_against"]
                / summary["matches"],
                2,
            )

            summary["points_avg"] = round(
                summary["points"]
                / summary["matches"],
                2,
            )

        return summary

    # ========================================================
    # HUMAN READABLE FORM
    # ========================================================

    @staticmethod
    def form_string(
        summary: Dict[str, Any],
    ) -> str:
        """
        Возвращает компактную форму:

            W W D L W

        Используется UI.
        """

        return (
            " ".join(
                ["W"] * int(summary.get("wins", 0))
                + ["D"] * int(summary.get("draws", 0))
                + ["L"] * int(summary.get("losses", 0))
            )
            or "—"
        )

    # ========================================================
    # SHORT SUMMARY
    # ========================================================

    @staticmethod
    def build_director_summary(
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Формирует компактный набор показателей
        для отображения Директору.

        Никаких прогнозных коэффициентов здесь нет.
        """

        h2h = context.get(
            "h2h_summary",
            {},
        )

        home = context.get(
            "home",
            {},
        )

        away = context.get(
            "away",
            {},
        )

        return {
            "h2h": h2h,

            "home_form": home.get(
                "last_summary",
                {},
            ),

            "home_at_home": home.get(
                "home_summary",
                {},
            ),

            "away_form": away.get(
                "last_summary",
                {},
            ),

            "away_away": away.get(
                "away_summary",
                {},
            ),
        }


# ============================================================
# FACTORY
# ============================================================

_default_service: Optional[MatchContextService] = None


def get_match_context_service() -> MatchContextService:
    global _default_service

    if _default_service is None:
        _default_service = MatchContextService()

    return _default_service

# app/api/football_data.py
from __future__ import annotations

from typing import Any, Optional
import requests
import streamlit as st


BASE_URL = "https://api.football-data.org/v4"
DEFAULT_COMPETITION = "PD"
DEFAULT_LIMIT = 6
TIMEOUT = 20

# football-data.org team IDs
TEAM_IDS = {
    "Barcelona": 81,
    "FC Barcelona": 81,
    "Барселона": 81,
    "Valencia": 95,
    "Valencia CF": 95,
    "Валенсия": 95,
}


def _get_token() -> Optional[str]:
    """Read token from Streamlit Secrets. Token is never stored in source code."""
    for key in (
        "FOOTBALL_DATA_API_TOKEN",
        "FOOTBALL_DATA_TOKEN",
        "FOOTBALL_DATA_API_KEY",
    ):
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
        if value:
            return str(value).strip()
    return None


def _request(path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    token = _get_token()
    if not token:
        raise RuntimeError(
            "Не найден token football-data.org в Streamlit Secrets. "
            "Ожидается FOOTBALL_DATA_API_TOKEN "
            "(также поддерживаются FOOTBALL_DATA_TOKEN и FOOTBALL_DATA_API_KEY)."
        )

    response = requests.get(
        f"{BASE_URL}{path}",
        headers={"X-Auth-Token": token},
        params=params or {},
        timeout=TIMEOUT,
    )

    if response.status_code == 401:
        raise RuntimeError("football-data.org: неверный или недоступный API token.")
    if response.status_code == 403:
        raise RuntimeError(
            "football-data.org: доступ запрещён. Проверь доступ Free-подписки "
            "к соревнованию PD."
        )
    if response.status_code == 429:
        raise RuntimeError("football-data.org: превышен лимит запросов (429).")

    response.raise_for_status()
    return response.json()


def resolve_team_id(team_name: str) -> Optional[int]:
    name = str(team_name or "").strip()
    return TEAM_IDS.get(name)


def get_team_matches(
    team_name: str,
    limit: int = DEFAULT_LIMIT,
    competition: str = DEFAULT_COMPETITION,
) -> list[dict[str, Any]]:
    """
    Получить последние завершённые матчи команды.

    Это отдельный Scout/API слой:
    - не пишет в database.py;
    - не меняет Soccer365 историю;
    - не передаёт данные в GoalModel;
    - не используется ETC.
    """
    team_id = resolve_team_id(team_name)
    if team_id is None:
        raise ValueError(
            f"Неизвестная команда для football-data.org: {team_name}. "
            f"Добавь её ID в TEAM_IDS."
        )

    data = _request(
        f"/teams/{team_id}/matches",
        params={
            "competitions": competition,
            "status": "FINISHED",
            "limit": int(limit),
        },
    )

    matches = data.get("matches") or []

    # API обычно возвращает матчи от новых к старым.
    # Для FAJ показываем oldest -> newest, как и текущую историю.
    rows: list[dict[str, Any]] = []

    for match in matches:
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        score = match.get("score") or {}
        full_time = score.get("fullTime") or {}

        rows.append(
            {
                "source": "football-data.org",
                "competition": (match.get("competition") or {}).get("name"),
                "competition_code": (match.get("competition") or {}).get("code"),
                "date": str(match.get("utcDate") or "")[:10],
                "home": home.get("name"),
                "away": away.get("name"),
                "home_score": full_time.get("home"),
                "away_score": full_time.get("away"),
                "status": match.get("status"),
                "match_id": match.get("id"),
                "venue": "HOME" if int(home.get("id") or -1) == team_id else "AWAY",
            }
        )

    rows.sort(key=lambda row: row.get("date") or "")
    return rows[-int(limit):]


def get_team_pair_matches(
    home_team: str,
    away_team: str,
    limit: int = DEFAULT_LIMIT,
    competition: str = DEFAULT_COMPETITION,
) -> dict[str, Any]:
    return {
        "home": get_team_matches(home_team, limit=limit, competition=competition),
        "away": get_team_matches(away_team, limit=limit, competition=competition),
    }

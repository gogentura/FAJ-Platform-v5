#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Data Football API Client v1.0
============================================================

НАЗНАЧЕНИЕ:
    Внешний источник дополнительного футбольного контекста.

ВАЖНО:
    Этот модуль НЕ:
        - изменяет SQLite;
        - изменяет FAJ рейтинги;
        - изменяет паспорта;
        - изменяет факты;
        - запускает обучение;
        - изменяет PredictionManager;
        - автоматически вызывается при прогнозе.

Он работает ТОЛЬКО ПО ЗАПРОСУ.

Основные данные:
    1. H2H
    2. Последние матчи команды
    3. Домашняя форма
    4. Выездная форма
    5. Статистика отдельного матча

Источник:
    API-Football / API-Sports

Документация:
    https://www.api-football.com/documentation-v3

Конфигурация:
    API_FOOTBALL_KEY

Опционально:
    API_FOOTBALL_BASE_URL
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)


class DataFootballAPIError(Exception):
    """Ошибка Data Football API."""


class DataFootballAPI:
    """
    Минимальный клиент внешнего футбольного API.

    Клиент не имеет никакого доступа к FAJDatabase.
    """

    DEFAULT_BASE_URL = "https://v3.football.api-sports.io"
    DEFAULT_TIMEOUT = 15

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.api_key = (
            api_key
            or os.getenv("API_FOOTBALL_KEY")
            or os.getenv("DATA_FOOTBALL_API_KEY")
        )

        self.base_url = (
            base_url
            or os.getenv(
                "API_FOOTBALL_BASE_URL",
                self.DEFAULT_BASE_URL,
            )
        ).rstrip("/")

        self.timeout = timeout

        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update(
                {
                    "x-apisports-key": self.api_key,
                    "Accept": "application/json",
                }
            )

    # ========================================================
    # CONFIGURATION
    # ========================================================

    @property
    def available(self) -> bool:
        """API настроен и готов к запросам."""
        return bool(self.api_key)

    def status(self) -> Dict[str, Any]:
        """Информация о состоянии клиента."""
        return {
            "available": self.available,
            "base_url": self.base_url,
        }

    def _require_key(self) -> None:
        if not self.api_key:
            raise DataFootballAPIError(
                "Не задан API ключ. "
                "Укажите переменную окружения API_FOOTBALL_KEY."
            )

    # ========================================================
    # LOW LEVEL REQUEST
    # ========================================================

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        self._require_key()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        logger.info(
            "DATA FOOTBALL API | GET %s | params=%s",
            endpoint,
            params,
        )

        try:
            response = self.session.get(
                url,
                params=params or {},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DataFootballAPIError(
                f"Ошибка соединения с Data Football API: {exc}"
            ) from exc

        if response.status_code != 200:
            raise DataFootballAPIError(
                f"Data Football API HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise DataFootballAPIError(
                "Data Football API вернул некорректный JSON."
            ) from exc

        errors = payload.get("errors")

        if errors:
            if isinstance(errors, dict):
                error_text = "; ".join(
                    f"{key}: {value}"
                    for key, value in errors.items()
                )
            else:
                error_text = str(errors)

            raise DataFootballAPIError(
                f"Data Football API error: {error_text}"
            )

        return payload

    # ========================================================
    # GENERIC HELPERS
    # ========================================================

    @staticmethod
    def _response_list(
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        response = payload.get("response", [])

        if not isinstance(response, list):
            return []

        return [
            item
            for item in response
            if isinstance(item, dict)
        ]

    # ========================================================
    # TEAM SEARCH
    # ========================================================

    def search_team(
        self,
        name: str,
        country: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ищет команду во внешнем API.

        Используется верхним слоем для получения
        внешнего team_id.
        """

        params: Dict[str, Any] = {
            "search": name,
        }

        if country:
            params["country"] = country

        payload = self._request(
            "teams",
            params,
        )

        return self._response_list(payload)

    # ========================================================
    # TEAM BY ID
    # ========================================================

    def get_team(
        self,
        team_id: int,
    ) -> Optional[Dict[str, Any]]:
        payload = self._request(
            "teams",
            {
                "id": int(team_id),
            },
        )

        teams = self._response_list(payload)

        return teams[0] if teams else None

    # ========================================================
    # H2H
    # ========================================================

    def get_h2h(
        self,
        home_team_id: int,
        away_team_id: int,
        last: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        История очных встреч.

        Возвращает последние H2H матчи двух команд.
        """

        last = max(1, min(int(last), 20))

        payload = self._request(
            "fixtures/headtohead",
            {
                "h2h": f"{int(home_team_id)}-{int(away_team_id)}",
                "last": last,
            },
        )

        return self._response_list(payload)

    # ========================================================
    # TEAM LAST MATCHES
    # ========================================================

    def get_team_last_matches(
        self,
        team_id: int,
        last: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Последние сыгранные матчи команды.

        Используется для оценки текущей формы.
        """

        last = max(1, min(int(last), 20))

        payload = self._request(
            "fixtures",
            {
                "team": int(team_id),
                "last": last,
            },
        )

        return self._response_list(payload)

    # ========================================================
    # HOME MATCHES
    # ========================================================

    def get_team_home_matches(
        self,
        team_id: int,
        last: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Последние матчи команды, где она была хозяином.

        Фильтрация выполняется локально после получения
        последних матчей.
        """

        matches = self.get_team_last_matches(
            team_id=team_id,
            last=max(int(last) * 3, 10),
        )

        result = []

        for match in matches:
            teams = match.get("teams", {})

            home = teams.get("home", {})

            if home.get("id") == int(team_id):
                result.append(match)

            if len(result) >= int(last):
                break

        return result

    # ========================================================
    # AWAY MATCHES
    # ========================================================

    def get_team_away_matches(
        self,
        team_id: int,
        last: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Последние матчи команды, где она была гостем.
        """

        matches = self.get_team_last_matches(
            team_id=team_id,
            last=max(int(last) * 3, 10),
        )

        result = []

        for match in matches:
            teams = match.get("teams", {})

            away = teams.get("away", {})

            if away.get("id") == int(team_id):
                result.append(match)

            if len(result) >= int(last):
                break

        return result

    # ========================================================
    # FIXTURE STATISTICS
    # ========================================================

    def get_fixture_statistics(
        self,
        fixture_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Статистика конкретного сыгранного матча.

        Это дополнительный источник.
        Он не является Import Facts.
        """

        payload = self._request(
            "fixtures/statistics",
            {
                "fixture": int(fixture_id),
            },
        )

        return self._response_list(payload)

    # ========================================================
    # FIXTURE
    # ========================================================

    def get_fixture(
        self,
        fixture_id: int,
    ) -> Optional[Dict[str, Any]]:
        payload = self._request(
            "fixtures",
            {
                "id": int(fixture_id),
            },
        )

        fixtures = self._response_list(payload)

        return fixtures[0] if fixtures else None

    # ========================================================
    # LEAGUE STANDINGS
    # ========================================================

    def get_standings(
        self,
        league_id: int,
        season: int,
    ) -> List[Dict[str, Any]]:
        """
        Получает таблицу турнира.

        Пока не используется Tour Manager.
        Оставляем здесь для дальнейшего Scout-контекста.
        """

        payload = self._request(
            "standings",
            {
                "league": int(league_id),
                "season": int(season),
            },
        )

        return self._response_list(payload)

    # ========================================================
    # COMPETITION FIXTURES
    # ========================================================

    def get_matches(
        self,
        competition_code: Optional[int] = None,
        season: Optional[int] = None,
        team_id: Optional[int] = None,
        last: Optional[int] = None,
        next_matches: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Универсальный получение матчей.

        Оставлен для будущего использования.

        competition_code:
            league ID внешнего API.

        season:
            год сезона.

        team_id:
            внешний ID команды.

        last:
            последние матчи.

        next_matches:
            ближайшие матчи.
        """

        params: Dict[str, Any] = {}

        if competition_code is not None:
            params["league"] = int(competition_code)

        if season is not None:
            params["season"] = int(season)

        if team_id is not None:
            params["team"] = int(team_id)

        if last is not None:
            params["last"] = max(1, min(int(last), 100))

        if next_matches is not None:
            params["next"] = max(1, min(int(next_matches), 100))

        payload = self._request(
            "fixtures",
            params,
        )

        return self._response_list(payload)


# ============================================================
# FACTORY
# ============================================================

_default_api: Optional[DataFootballAPI] = None


def get_data_football_api() -> DataFootballAPI:
    """
    Singleton клиента.

    Сам по себе API-запрос не выполняется.
    """

    global _default_api

    if _default_api is None:
        _default_api = DataFootballAPI()

    return _default_api


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
    )

    api = get_data_football_api()

    print("=" * 60)
    print("DATA FOOTBALL API")
    print("=" * 60)

    print(
        f"Available: {api.available}"
    )

    if not api.available:
        print(
            "\nAPI ключ не установлен."
        )
        print(
            "Укажите переменную окружения:"
        )
        print(
            "API_FOOTBALL_KEY=..."
        )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
NB-BET Stats Parser v5.1
============================================================

РОЛЬ:
    Только получение статистики сыгранного матча с NB-BET.

НЕ ОТВЕЧАЕТ ЗА:
    - счёт матча;
    - ввод счёта;
    - определение победителя;
    - FAJ Prediction;
    - Expert Prediction;
    - Validation;
    - Gold;
    - запись в SQLite.

ИСТОЧНИК:
    NB-BET
    pageSoccerEvent
    match["17"][0]

КОНТРАКТ IMPORT FACTS:

    parser = NbBetStatsParser()
    result = parser.parse_stats(url)

Результат:

    {
        "success": bool,
        "stats": dict,
        "data_quality": float,
        "source": "nb-bet",
        "parser_version": "5.1-nb-bet"
    }

СТАТИСТИКА:

    1  = possession
    5  = corners
    7  = shots
    8  = shots on target
    21 = xG
    22 = total passes
    23 = pass accuracy
    39 = accurate passes
    46 = tackles

ПРИНЦИП:

    NB-BET
       ↓
    Parser
       ↓
    statistics
       ↓
    Import Facts

Счёт НЕ извлекается parser'ом.

SQLite НЕ изменяется parser'ом.

None != 0.

Если значение невозможно безопасно определить —
возвращается None.

============================================================
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class NbBetStatsParser:
    """
    Парсер статистики матчей NB-BET.

    Публичный интерфейс:

        parse_stats(url)

    Совместимый legacy-интерфейс:

        parse_match_page(url)
    """

    VERSION = "5.1-nb-bet"
    SOURCE = "nb-bet"

    DEFAULT_TIMEOUT = 20
    MAX_RETRIES = 3
    RETRY_DELAY = 1.5

    # ========================================================
    # STATISTICS MAP
    # ========================================================

    STAT_MAP = {
        1: "possession",
        5: "corners",
        7: "shots",
        8: "shots_on_target",
        21: "xg",
        22: "total_passes",
        23: "pass_accuracy",
        39: "accurate_passes",
        46: "tackles",
    }

    # ========================================================
    # RESULT KEYS
    # ========================================================

    RESULT_KEYS = {
        "possession": (
            "home_possession",
            "away_possession",
        ),
        "corners": (
            "home_corners",
            "away_corners",
        ),
        "shots": (
            "home_shots",
            "away_shots",
        ),
        "shots_on_target": (
            "home_shots_on_target",
            "away_shots_on_target",
        ),
        "xg": (
            "home_xg",
            "away_xg",
        ),
        "total_passes": (
            "home_total_passes",
            "away_total_passes",
        ),
        "pass_accuracy": (
            "home_pass_accuracy",
            "away_pass_accuracy",
        ),
        "accurate_passes": (
            "home_accurate_passes",
            "away_accurate_passes",
        ),
        "tackles": (
            "home_tackles",
            "away_tackles",
        ),
    }

    # ========================================================
    # SAFE LIMITS
    # ========================================================

    LIMITS = {
        "possession": (0, 100),
        "corners": (0, 30),
        "shots": (0, 80),
        "shots_on_target": (0, 50),
        "xg": (0.0, 10.0),
        "total_passes": (0, 1500),
        "pass_accuracy": (0, 100),
        "accurate_passes": (0, 1500),
        "tackles": (0, 100),
    }

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "image/avif,image/webp,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": (
                    "ru-RU,ru;q=0.9,"
                    "en-US;q=0.8,"
                    "en;q=0.7"
                ),
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": "https://nb-bet.com/",
                "Connection": "keep-alive",
            }
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse_stats(
        self,
        url: str,
    ) -> Dict[str, Any]:
        """
        Основной публичный метод.

        Используется Import Facts:

            parser.parse_stats(url)

        ВАЖНО:

            Метод не извлекает счёт.
            Метод не изменяет SQLite.
            Метод возвращает только статистику.
        """

        return self.parse_match_page(url)

    # ========================================================
    # PARSE MATCH PAGE
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:
        """
        Реальный основной парсер страницы NB-BET.

        ВАЖНО:

            Это единственная реализация parse_match_page().

            НЕ вызывает parse_stats().

        Поэтому:

            parse_stats()
                ↓
            parse_match_page()
                ↓
            реальные методы parser

        и рекурсии нет.
        """

        result: Dict[str, Any] = {
            "success": False,
            "stats": {},
            "data_quality": 0.0,
            "source": self.SOURCE,
            "parser_version": self.VERSION,
        }

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        if not url or not str(url).strip():
            logger.warning(
                "NB-BET: пустой URL."
            )
            return result

        url = str(url).strip()

        if "nb-bet.com" not in url.lower():
            logger.warning(
                "NB-BET parser получил чужой URL: %s",
                url,
            )
            return result

        # ----------------------------------------------------
        # HTTP
        # ----------------------------------------------------

        response = self._request_page(url)

        if response is None:
            logger.error(
                "NB-BET: страницу получить не удалось."
            )
            return result

        html = response.text

        if not html:
            logger.error(
                "NB-BET: сервер вернул пустой HTML."
            )
            return result

        # ----------------------------------------------------
        # SOUP
        # ----------------------------------------------------

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # ----------------------------------------------------
        # EVENT JSON
        # ----------------------------------------------------

        event_data = self._extract_event_data(
            soup
        )

        if event_data is None:
            logger.warning(
                "NB-BET: pageSoccerEvent "
                "не разобран."
            )
            return result

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        stats = self._extract_nb_bet_stats(
            event_data
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        validated_stats = self._validate_stats(
            stats
        )

        result["stats"] = validated_stats

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------

        result["data_quality"] = (
            self._calculate_quality(
                validated_stats
            )
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        result["success"] = bool(
            validated_stats
        )

        if result["success"]:
            logger.info(
                "NB-BET статистика загружена: "
                "%s показателей, quality=%s",
                len(validated_stats),
                result["data_quality"],
            )
        else:
            logger.warning(
                "NB-BET статистика не получена."
            )

        return result

    # ========================================================
    # HTTP — ИСПРАВЛЕНА ВЕРСИЯ
    # ========================================================

    def _request_page(
        self,
        url: str,
    ) -> Optional[requests.Response]:
        """
        Надёжное получение HTML страницы NB-BET.

        ВАЖНО:
            - SQLite здесь НЕ используется.
            - Статистика здесь НЕ разбирается.
            - При HTTP 500 выполняются повторные попытки.
            - Используются разные User-Agent.
            - Оригинальный URL не изменяется.
        """
        user_agents = [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.5 Safari/605.1.15"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
        ]

        last_error: Optional[str] = None

        for attempt in range(
            1,
            self.MAX_RETRIES + 1,
        ):
            try:
                # ------------------------------------------------
                # Меняем User-Agent между попытками
                # ------------------------------------------------
                user_agent = user_agents[
                    (attempt - 1) % len(user_agents)
                ]

                headers = {
                    "User-Agent": user_agent,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,"
                        "image/avif,image/webp,"
                        "*/*;q=0.8"
                    ),
                    "Accept-Language": (
                        "ru-RU,ru;q=0.9,"
                        "en-US;q=0.8,"
                        "en;q=0.7"
                    ),
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Referer": "https://nb-bet.com/",
                    "Connection": "keep-alive",
                }

                logger.info(
                    "NB-BET HTTP request %s/%s: %s",
                    attempt,
                    self.MAX_RETRIES,
                    url,
                )

                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                logger.info(
                    "NB-BET HTTP response: "
                    "status=%s, final_url=%s, "
                    "content_type=%s, bytes=%s",
                    response.status_code,
                    response.url,
                    response.headers.get(
                        "Content-Type",
                        "",
                    ),
                    len(response.content),
                )

                # ------------------------------------------------
                # УСПЕХ
                # ------------------------------------------------
                if response.status_code == 200:
                    if not response.content:
                        last_error = (
                            "HTTP 200, но пустой ответ"
                        )
                        logger.warning(
                            "NB-BET: пустой ответ "
                            "(attempt %s/%s)",
                            attempt,
                            self.MAX_RETRIES,
                        )
                    else:
                        logger.info(
                            "NB-BET HTTP 200: %s bytes",
                            len(response.content),
                        )
                        return response

                # ------------------------------------------------
                # HTTP 500
                # ------------------------------------------------
                elif response.status_code == 500:
                    last_error = "HTTP 500"

                    # Сервер часто возвращает очень короткий
                    # технический ответ. Сохраняем его в лог.
                    try:
                        body = response.text.strip()
                        if body:
                            logger.debug(
                                "NB-BET HTTP 500 body: %s",
                                body[:500],
                            )
                    except Exception:
                        pass

                    logger.warning(
                        "NB-BET HTTP 500 "
                        "(attempt %s/%s)",
                        attempt,
                        self.MAX_RETRIES,
                    )

                # ------------------------------------------------
                # ДРУГИЕ HTTP ОШИБКИ
                # ------------------------------------------------
                else:
                    last_error = (
                        f"HTTP {response.status_code}"
                    )
                    logger.warning(
                        "NB-BET HTTP %s "
                        "(attempt %s/%s)",
                        response.status_code,
                        attempt,
                        self.MAX_RETRIES,
                    )

            except requests.RequestException as exc:
                last_error = str(exc)
                logger.warning(
                    "NB-BET request error "
                    "(attempt %s/%s): %s",
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )

            # ----------------------------------------------------
            # PAUSE BEFORE RETRY
            # ----------------------------------------------------
            if attempt < self.MAX_RETRIES:
                delay = (
                    self.RETRY_DELAY * attempt
                )
                logger.info(
                    "NB-BET: повтор через %.1f сек.",
                    delay,
                )
                time.sleep(delay)

        # ========================================================
        # FINAL FAILURE
        # ========================================================
        logger.error(
            "NB-BET HTTP failed after %s attempts: %s",
            self.MAX_RETRIES,
            last_error,
        )

        return None

    # ========================================================
    # EVENT DATA
    # ========================================================

    def _extract_event_data(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Dict[str, Any]]:
        """
        Ищет pageSoccerEvent внутри script-блоков.
        """

        scripts = soup.find_all(
            "script"
        )

        for index, script in enumerate(
            scripts
        ):
            text = (
                script.string
                or script.get_text()
            )

            if not text:
                continue

            if "pageSoccerEvent" not in text:
                continue

            logger.info(
                "NB-BET: pageSoccerEvent найден "
                "в script #%s",
                index,
            )

            data = (
                self._parse_page_soccer_event(
                    text
                )
            )

            if data is not None:
                logger.info(
                    "NB-BET: pageSoccerEvent "
                    "успешно разобран"
                )

                return data

        logger.warning(
            "NB-BET: pageSoccerEvent не найден "
            "или не удалось разобрать."
        )

        return None

    # ========================================================
    # PAGE SOCCER EVENT
    # ========================================================

    def _parse_page_soccer_event(
        self,
        text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Извлекает JSON-объект pageSoccerEvent.
        """

        marker = "pageSoccerEvent"

        position = text.find(
            marker
        )

        if position < 0:
            return None

        # ----------------------------------------------------
        # ВАРИАНТ 1
        # "pageSoccerEvent": { ... }
        # ----------------------------------------------------

        colon = text.find(
            ":",
            position,
        )

        if colon >= 0:
            start = text.find(
                "{",
                colon,
            )

            if start >= 0:
                json_text = (
                    self._extract_balanced_object(
                        text,
                        start,
                    )
                )

                if json_text:
                    try:
                        data = json.loads(
                            json_text
                        )

                        if isinstance(
                            data,
                            dict,
                        ):
                            return data

                    except json.JSONDecodeError:
                        pass

        # ----------------------------------------------------
        # ВАРИАНТ 2
        # pageSoccerEvent ... { ... }
        # ----------------------------------------------------

        start = text.find(
            "{",
            position,
        )

        if start >= 0:
            json_text = (
                self._extract_balanced_object(
                    text,
                    start,
                )
            )

            if json_text:
                try:
                    data = json.loads(
                        json_text
                    )

                    if isinstance(
                        data,
                        dict,
                    ):
                        return data

                except json.JSONDecodeError:
                    pass

        # ----------------------------------------------------
        # ВАРИАНТ 3
        # match отдельно
        # ----------------------------------------------------

        match_position = text.find(
            '"match"',
            position,
        )

        if match_position < 0:
            match_position = text.find(
                "'match'",
                position,
            )

        if match_position < 0:
            match_position = text.find(
                "match",
                position,
            )

        if match_position >= 0:
            match_start = text.find(
                "{",
                match_position,
            )

            if match_start >= 0:
                match_text = (
                    self._extract_balanced_object(
                        text,
                        match_start,
                    )
                )

                if match_text:
                    try:
                        match_data = json.loads(
                            match_text
                        )

                        if isinstance(
                            match_data,
                            dict,
                        ):
                            return {
                                "match": match_data
                            }

                    except json.JSONDecodeError:
                        pass

        return None

    # ========================================================
    # BALANCED JSON OBJECT
    # ========================================================

    def _extract_balanced_object(
        self,
        text: str,
        start: int,
    ) -> Optional[str]:
        """
        Безопасно извлекает сбалансированный
        JSON object из текста.

        Учитывает строки и escaped quotes.
        """

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):
            char = text[index]

            if in_string:

                if escaped:
                    escaped = False
                    continue

                if char == "\\":
                    escaped = True
                    continue

                if char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True

            elif char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    return text[
                        start:index + 1
                    ]

        return None

    # ========================================================
    # NB-BET STATS
    # ========================================================

    def _extract_nb_bet_stats(
        self,
        event_data: Optional[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:
        """
        Извлекает match["17"][0].
        """

        if not event_data:
            return {}

        match = event_data.get(
            "match"
        )

        if not isinstance(
            match,
            dict,
        ):
            return {}

        stats_block = match.get(
            "17"
        )

        if stats_block is None:
            stats_block = match.get(
                17
            )

        if not isinstance(
            stats_block,
            list,
        ):
            return {}

        if not stats_block:
            return {}

        first = stats_block[0]

        if not isinstance(
            first,
            dict,
        ):
            return {}

        result: Dict[str, Any] = {}

        for raw_key, raw_value in (
            first.items()
        ):
            try:
                key = int(
                    raw_key
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            stat_name = (
                self.STAT_MAP.get(
                    key
                )
            )

            if not stat_name:
                continue

            pair = self._extract_pair(
                raw_value
            )

            if pair is None:
                continue

            home, away = pair

            home_key, away_key = (
                self.RESULT_KEYS[
                    stat_name
                ]
            )

            result[
                home_key
            ] = home

            result[
                away_key
            ] = away

        return result

    # ========================================================
    # STAT PAIR
    # ========================================================

    def _extract_pair(
        self,
        value: Any,
    ) -> Optional[
        Tuple[Any, Any]
    ]:
        """
        Ожидает:

            [home, away]

        """

        if not isinstance(
            value,
            (list, tuple),
        ):
            return None

        if len(value) < 2:
            return None

        return (
            value[0],
            value[1],
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_stats(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Проверяет значения статистики
        и отношения между показателями.
        """

        result: Dict[str, Any] = {}

        for key, value in stats.items():

            stat_type: Optional[str] = None

            for name, keys in (
                self.RESULT_KEYS.items()
            ):
                if key in keys:
                    stat_type = name
                    break

            if stat_type is None:
                continue

            result[key] = (
                self._validate_value(
                    stat_type,
                    value,
                )
            )

        # ----------------------------------------------------
        # shots on target <= shots
        # ----------------------------------------------------

        self._invalidate_relation(
            result,
            "home_shots_on_target",
            "home_shots",
        )

        self._invalidate_relation(
            result,
            "away_shots_on_target",
            "away_shots",
        )

        # ----------------------------------------------------
        # possession
        # ----------------------------------------------------

        home_possession = result.get(
            "home_possession"
        )

        away_possession = result.get(
            "away_possession"
        )

        if (
            home_possession is not None
            and away_possession is not None
        ):
            total = (
                home_possession
                + away_possession
            )

            if not 98 <= total <= 102:
                logger.warning(
                    "NB-BET: invalid possession "
                    "%s + %s",
                    home_possession,
                    away_possession,
                )

                result[
                    "home_possession"
                ] = None

                result[
                    "away_possession"
                ] = None

        # ----------------------------------------------------
        # accurate passes <= total passes
        # ----------------------------------------------------

        for side in (
            "home",
            "away",
        ):
            total_key = (
                f"{side}_total_passes"
            )

            accurate_key = (
                f"{side}_accurate_passes"
            )

            total = result.get(
                total_key
            )

            accurate = result.get(
                accurate_key
            )

            if (
                total is not None
                and accurate is not None
                and accurate > total
            ):
                logger.warning(
                    "NB-BET: accurate passes "
                    "greater than total passes "
                    "(%s: %s > %s)",
                    side,
                    accurate,
                    total,
                )

                result[
                    total_key
                ] = None

                result[
                    accurate_key
                ] = None

        return result

    # ========================================================
    # VALIDATE VALUE
    # ========================================================

    def _validate_value(
        self,
        stat_type: str,
        value: Any,
    ) -> Optional[Any]:
        """
        Преобразует и проверяет одно значение.
        """

        try:
            if stat_type == "xg":
                value = float(
                    value
                )
            else:
                value = int(
                    value
                )

        except (
            TypeError,
            ValueError,
        ):
            return None

        limits = self.LIMITS.get(
            stat_type
        )

        if limits:
            minimum, maximum = limits

            if not (
                minimum
                <= value
                <= maximum
            ):
                logger.warning(
                    "NB-BET: значение %s "
                    "вне диапазона %s: %s",
                    stat_type,
                    limits,
                    value,
                )

                return None

        return value

    # ========================================================
    # RELATION VALIDATION
    # ========================================================

    def _invalidate_relation(
        self,
        stats: Dict[str, Any],
        smaller_key: str,
        larger_key: str,
    ) -> None:
        """
        Проверяет:

            smaller <= larger

        Например:

            shots_on_target <= shots
        """

        smaller = stats.get(
            smaller_key
        )

        larger = stats.get(
            larger_key
        )

        if (
            smaller is None
            or larger is None
        ):
            return

        if smaller > larger:
            logger.warning(
                "NB-BET: invalid relation "
                "%s=%s > %s=%s",
                smaller_key,
                smaller,
                larger_key,
                larger,
            )

            stats[
                smaller_key
            ] = None

            stats[
                larger_key
            ] = None

    # ========================================================
    # QUALITY
    # ========================================================

    def _calculate_quality(
        self,
        stats: Dict[str, Any],
    ) -> float:
        """
        Качество = доля присутствующих
        валидных значений.

        Максимум = 1.0.
        """

        if not stats:
            return 0.0

        total = len(stats)

        if total == 0:
            return 0.0

        present = sum(
            1
            for value in stats.values()
            if value is not None
        )

        return round(
            present / total,
            2,
        )

    # ========================================================
    # CLEAN
    # ========================================================

    def _clean(
        self,
        text: str,
    ) -> str:
        """
        Универсальная очистка текста.
        """

        if not text:
            return ""

        text = text.replace(
            "\xa0",
            " ",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def parse_match_stats(
    url: str,
) -> Dict[str, Any]:
    """
    Удобная функция для внешних вызовов.
    """

    return (
        NbBetStatsParser()
        .parse_stats(
            url
        )
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    if len(sys.argv) < 2:
        print(
            "Usage:"
        )

        print(
            "python "
            "app/parsers/nb_bet_stats_parser.py "
            "<NB-BET URL>"
        )

        raise SystemExit(1)

    parser = NbBetStatsParser()

    result = parser.parse_stats(
        sys.argv[1]
    )

    print("=" * 70)
    print(
        "FAJ NB-BET STATS PARSER "
        f"v{parser.VERSION}"
    )
    print("=" * 70)

    print(
        "Success:",
        result["success"],
    )

    print(
        "Source:",
        result["source"],
    )

    print(
        "Parser version:",
        result["parser_version"],
    )

    print(
        "Quality:",
        result["data_quality"],
    )

    print(
        "\nStats:"
    )

    for key, value in (
        result["stats"].items()
    ):
        print(
            f"  {key}: {value}"
        )

    print("=" * 70)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
NB-BET Stats Parser v4.3
============================================================

ИСТОЧНИК:
    NB-BET

ОСНОВНОЙ ИСТОЧНИК:
    pageSoccerEvent.match

СТРУКТУРА NB-BET:

    match["7"]
        "1" = домашняя команда
        "4" = голы хозяев
        "5" = вторичное поле

    match["8"]
        "1" = гостевая команда
        "4" = голы гостей
        "5" = вторичное поле

    match["17"][0]
        "1"  = possession
        "5"  = corners
        "7"  = shots
        "8"  = shots on target
        "21" = xG
        "22" = total passes
        "23" = pass accuracy
        "39" = accurate passes
        "46" = tackles

ПРИНЦИП:
    Parser только читает источник.
    SQLite не изменяет.
    Прогнозы не изменяет.
    Данные не угадывает.

Если значение невозможно безопасно определить:
    None

ВАЖНО:
    0:0 является валидным результатом.

    Отсутствие счёта НЕ означает отсутствие статистики.
    Если HTTP или SCORE недоступны, уже полученные stats
    не уничтожаются.

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

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class NbBetStatsParser:

    VERSION = "4.3-nb-bet"
    SOURCE = "nb-bet"

    DEFAULT_TIMEOUT = 20
    MAX_RETRIES = 3
    RETRY_DELAY = 1.5

    # ========================================================
    # STATISTICS
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
    # GENERIC FALLBACKS
    # ========================================================

    SCORE_PAIRS = (
        ("homeGoals", "awayGoals"),
        ("home_goals", "away_goals"),
        ("homeScore", "awayScore"),
        ("awayScore", "homeScore"),
        ("home_score", "away_score"),
        ("homeResult", "awayResult"),
        ("home_result", "away_result"),
        ("homeGoalsFullTime", "awayGoalsFullTime"),
        ("home_score_full_time", "away_score_full_time"),
    )

    SCORE_FIELDS = (
        "score",
        "result",
        "finalScore",
        "final_score",
        "matchScore",
        "match_score",
        "fullTimeScore",
        "full_time_score",
    )

    TEAM_PAIRS = (
        ("homeTeam", "awayTeam"),
        ("home_team", "away_team"),
        ("homeTeamName", "awayTeamName"),
        ("home_team_name", "away_team_name"),
        ("homeName", "awayName"),
        ("home_name", "away_name"),
    )

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
                    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
                ),
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": "https://nb-bet.com/",
                "Connection": "keep-alive",
            }
        )

    # ========================================================
    # PUBLIC PARSE
    # ========================================================

    def parse(
        self,
        url: str,
    ) -> Dict[str, Any]:

        result = {
            "success": False,

            "home_team": None,
            "away_team": None,

            "home_goals": None,
            "away_goals": None,

            "stats": {},

            "source": self.SOURCE,
            "parser_version": self.VERSION,

            "data_quality": 0.0,
        }

        if not url:
            return result

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
                "NB-BET: pageSoccerEvent не разобран."
            )

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        home_team, away_team = (
            self._extract_teams(
                soup=soup,
                url=url,
                event_data=event_data,
            )
        )

        result["home_team"] = home_team
        result["away_team"] = away_team

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = self._extract_score(
            soup=soup,
            html=html,
            event_data=event_data,
        )

        if score is not None:

            result["home_goals"] = score[0]
            result["away_goals"] = score[1]

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        stats = self._extract_nb_bet_stats(
            event_data
        )

        result["stats"] = self._validate_stats(
            stats
        )

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------

        result["data_quality"] = (
            self._calculate_quality(
                result
            )
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        result["success"] = (
            result["home_team"] is not None
            and result["away_team"] is not None
            and result["home_goals"] is not None
            and result["away_goals"] is not None
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        if result["success"]:

            logger.info(
                "NB-BET факт успешно разобран: "
                "%s %s:%s %s | stats=%s | quality=%s",
                result["home_team"],
                result["home_goals"],
                result["away_goals"],
                result["away_team"],
                len(result["stats"]),
                result["data_quality"],
            )

        else:

            logger.warning(
                "NB-BET неполный результат: "
                "teams=%s/%s score=%s:%s stats=%s quality=%s",
                result["home_team"],
                result["away_team"],
                result["home_goals"],
                result["away_goals"],
                len(result["stats"]),
                result["data_quality"],
            )

        return result

    # ========================================================
    # HTTP
    # ========================================================

    def _request_page(
        self,
        url: str,
    ) -> Optional[requests.Response]:
        """
        Получение страницы с повторными попытками.

        Важно:
            HTTP 500 = проблема получения страницы,
            а не проблема SCORE parser.

        Не смешиваем эти два случая.
        """

        last_error = None

        for attempt in range(
            1,
            self.MAX_RETRIES + 1,
        ):

            try:

                logger.info(
                    "NB-BET HTTP request %s/%s: %s",
                    attempt,
                    self.MAX_RETRIES,
                    url,
                )

                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                if response.status_code == 200:

                    logger.info(
                        "NB-BET HTTP 200: %s bytes",
                        len(response.content),
                    )

                    return response

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

            if attempt < self.MAX_RETRIES:

                time.sleep(
                    self.RETRY_DELAY * attempt
                )

        logger.error(
            "NB-BET HTTP failed after %s attempts: %s",
            self.MAX_RETRIES,
            last_error,
        )

        return None

    # ========================================================
    # EVENT JSON
    # ========================================================

    def _extract_event_data(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Dict[str, Any]]:

        scripts = soup.find_all("script")

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

            data = self._parse_page_soccer_event(
                text
            )

            if data is not None:

                logger.info(
                    "NB-BET: pageSoccerEvent успешно разобран"
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

        marker = "pageSoccerEvent"

        position = text.find(
            marker
        )

        if position < 0:
            return None

        # ----------------------------------------------------
        # ВАРИАНТ 1
        #
        # "pageSoccerEvent": {
        #     ...
        # }
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
        #
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
        #
        # Ищем объект match отдельно.
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
    # TEAMS
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
        url: str,
        event_data: Optional[Dict[str, Any]],
    ) -> Tuple[
        Optional[str],
        Optional[str],
    ]:

        # ----------------------------------------------------
        # 1. ОСНОВНОЙ NB-BET JSON
        #
        # match["7"]["1"]
        # match["8"]["1"]
        # ----------------------------------------------------

        pair = self._find_nb_bet_teams(
            event_data
        )

        if pair:

            normalized = (
                self._normalize_pair(
                    pair[0],
                    pair[1],
                )
            )

            if normalized:
                return normalized

        # ----------------------------------------------------
        # 2. Общий JSON
        # ----------------------------------------------------

        pair = self._find_teams_in_json(
            event_data
        )

        if pair:

            normalized = (
                self._normalize_pair(
                    pair[0],
                    pair[1],
                )
            )

            if normalized:
                return normalized

        # ----------------------------------------------------
        # 3. HTML headings/title
        # ----------------------------------------------------

        candidates = []

        for element in soup.find_all(
            ["h1", "h2", "h3"]
        ):

            text = self._clean(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                candidates.append(text)

        if soup.title:

            candidates.append(
                self._clean(
                    soup.title.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

        separators = (
            " — ",
            " – ",
            " - ",
            " vs ",
            " VS ",
            " против ",
        )

        for text in candidates:

            # Если title содержит счёт:
            # Динамо Москва - Крылья Советов 0-0
            text = re.sub(
                r"\s+\d{1,2}\s*[:\-]\s*\d{1,2}\s*$",
                "",
                text,
            ).strip()

            for separator in separators:

                if separator not in text:
                    continue

                parts = text.split(
                    separator,
                    1,
                )

                if len(parts) != 2:
                    continue

                pair = self._normalize_pair(
                    parts[0],
                    parts[1],
                )

                if pair:
                    return pair

        # ----------------------------------------------------
        # 4. URL
        # ----------------------------------------------------

        match = re.search(
            r"/Events/\d+-([^/?#]+)",
            url,
            re.IGNORECASE,
        )

        if match:

            slug = match.group(1)

            slug = re.sub(
                r"-prognoz-na-match.*$",
                "",
                slug,
                flags=re.IGNORECASE,
            )

            # NB-BET RPL URL обычно:
            # dinamo-moskva-krylya-sovetov
            #
            # Поэтому URL используем только как
            # последний fallback.
            #
            # Нормализатор должен определить границу
            # команд.

            normalized_slug = (
                slug.replace(
                    "-",
                    " ",
                )
            )

            pair = self._split_known_teams(
                normalized_slug
            )

            if pair:
                normalized = (
                    self._normalize_pair(
                        pair[0],
                        pair[1],
                    )
                )

                if normalized:
                    return normalized

        return None, None

    # ========================================================
    # NB-BET TEAMS
    # ========================================================

    def _find_nb_bet_teams(
        self,
        data: Any,
    ) -> Optional[
        Tuple[str, str]
    ]:

        if not isinstance(
            data,
            dict,
        ):
            return None

        match = data.get(
            "match"
        )

        if not isinstance(
            match,
            dict,
        ):
            return None

        home = match.get("7")

        if home is None:
            home = match.get(7)

        away = match.get("8")

        if away is None:
            away = match.get(8)

        if not isinstance(
            home,
            dict,
        ):
            return None

        if not isinstance(
            away,
            dict,
        ):
            return None

        home_name = (
            home.get("1")
            if "1" in home
            else home.get(1)
        )

        away_name = (
            away.get("1")
            if "1" in away
            else away.get(1)
        )

        if not home_name or not away_name:
            return None

        return (
            str(home_name),
            str(away_name),
        )

    # ========================================================
    # GENERIC TEAM SEARCH
    # ========================================================

    def _find_teams_in_json(
        self,
        data: Any,
    ) -> Optional[
        Tuple[str, str]
    ]:

        if isinstance(
            data,
            dict,
        ):

            for home_key, away_key in (
                self.TEAM_PAIRS
            ):

                if (
                    home_key in data
                    and away_key in data
                ):

                    home = self._team_value(
                        data[home_key]
                    )

                    away = self._team_value(
                        data[away_key]
                    )

                    if home and away:
                        return home, away

            for value in data.values():

                pair = (
                    self._find_teams_in_json(
                        value
                    )
                )

                if pair:
                    return pair

        elif isinstance(
            data,
            list,
        ):

            for value in data:

                pair = (
                    self._find_teams_in_json(
                        value
                    )
                )

                if pair:
                    return pair

        return None

    # ========================================================
    # TEAM VALUE
    # ========================================================

    def _team_value(
        self,
        value: Any,
    ) -> Optional[str]:

        if isinstance(
            value,
            str,
        ):
            return self._clean(value)

        if isinstance(
            value,
            dict,
        ):

            for key in (
                "name",
                "teamName",
                "team_name",
                "title",
            ):

                if key in value:

                    candidate = (
                        self._team_value(
                            value[key]
                        )
                    )

                    if candidate:
                        return candidate

        return None

    # ========================================================
    # URL TEAM SPLIT
    # ========================================================

    def _split_known_teams(
        self,
        text: str,
    ) -> Optional[
        Tuple[str, str]
    ]:

        # NB-BET URL fallback.
        #
        # Сначала пытаемся использовать
        # известные RPL названия.

        known_pairs = (
            (
                "dinamo moskva",
                "krylya sovetov",
            ),
            (
                "динамо москва",
                "крылья советов",
            ),
        )

        lowered = text.lower()

        for home, away in known_pairs:

            separator = " "

            candidate = (
                f"{home}{separator}{away}"
            )

            if candidate in lowered:

                index = lowered.find(
                    away
                )

                return (
                    text[:index].strip(),
                    text[index:].strip(),
                )

        return None

    # ========================================================
    # NORMALIZE TEAM PAIR
    # ========================================================

    def _normalize_pair(
        self,
        home: Any,
        away: Any,
    ) -> Optional[
        Tuple[str, str]
    ]:

        home = self._clean(
            str(home)
        )

        away = self._clean(
            str(away)
        )

        if not home or not away:
            return None

        try:

            normalized_home, normalized_away = (
                normalize_team_names(
                    home,
                    away,
                    strict=True,
                )
            )

            if (
                normalized_home
                and normalized_away
            ):
                return (
                    normalized_home,
                    normalized_away,
                )

        except Exception as exc:

            logger.debug(
                "NB-BET team normalizer failed: %s",
                exc,
            )

        return None

    # ========================================================
    # STATS
    # ========================================================

    def _extract_nb_bet_stats(
        self,
        event_data: Optional[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

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

        result = {}

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
    # SCORE
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
        html: str,
        event_data: Optional[
            Dict[str, Any]
        ],
    ) -> Optional[
        Tuple[int, int]
    ]:

        # ----------------------------------------------------
        # 1. ОСНОВНОЙ ИСТОЧНИК
        #
        # match["7"]["4"]
        # match["8"]["4"]
        # ----------------------------------------------------

        score = (
            self._find_nb_bet_match_score(
                event_data
            )
        )

        if score is not None:

            logger.info(
                "NB-BET SCORE: "
                "pageSoccerEvent.match[7/8][4] "
                "%s:%s",
                score[0],
                score[1],
            )

            return score

        # ----------------------------------------------------
        # 2. Общий JSON fallback
        # ----------------------------------------------------

        score = (
            self._find_score_in_json(
                event_data
            )
        )

        if score is not None:

            logger.info(
                "NB-BET SCORE: "
                "generic JSON %s:%s",
                score[0],
                score[1],
            )

            return score

        # ----------------------------------------------------
        # 3. HTML score blocks
        # ----------------------------------------------------

        selectors = (
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
        )

        for selector in selectors:

            try:

                elements = soup.select(
                    selector
                )

            except Exception:

                elements = []

            for element in elements:

                text = self._clean(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                score = (
                    self._parse_score(
                        text
                    )
                )

                if score is not None:

                    logger.info(
                        "NB-BET SCORE: "
                        "HTML %s:%s",
                        score[0],
                        score[1],
                    )

                    return score

        # ----------------------------------------------------
        # 4. TITLE
        # ----------------------------------------------------

        if soup.title:

            title = self._clean(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

            score = (
                self._parse_score(
                    title
                )
            )

            if score is not None:

                logger.info(
                    "NB-BET SCORE: "
                    "title %s:%s",
                    score[0],
                    score[1],
                )

                return score

        logger.warning(
            "NB-BET SCORE: не найден."
        )

        return None

    # ========================================================
    # NB-BET SCORE
    # ========================================================

    def _find_nb_bet_match_score(
        self,
        data: Any,
    ) -> Optional[
        Tuple[int, int]
    ]:

        if not isinstance(
            data,
            dict,
        ):
            return None

        match = data.get(
            "match"
        )

        if not isinstance(
            match,
            dict,
        ):
            return None

        home = match.get(
            "7"
        )

        if home is None:
            home = match.get(
                7
            )

        away = match.get(
            "8"
        )

        if away is None:
            away = match.get(
                8
            )

        if not isinstance(
            home,
            dict,
        ):
            return None

        if not isinstance(
            away,
            dict,
        ):
            return None

        home_goals = (
            home.get("4")
            if "4" in home
            else home.get(4)
        )

        away_goals = (
            away.get("4")
            if "4" in away
            else away.get(4)
        )

        home_goals = (
            self._safe_nb_bet_goal(
                home_goals
            )
        )

        away_goals = (
            self._safe_nb_bet_goal(
                away_goals
            )
        )

        if (
            home_goals is None
            or away_goals is None
        ):
            return None

        return (
            home_goals,
            away_goals,
        )

    # ========================================================
    # SAFE GOAL
    # ========================================================

    def _safe_nb_bet_goal(
        self,
        value: Any,
    ) -> Optional[int]:

        if value is None:
            return None

        try:

            value = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if not 0 <= value <= 15:
            return None

        return value

    # ========================================================
    # GENERIC SCORE JSON
    # ========================================================

    def _find_score_in_json(
        self,
        data: Any,
    ) -> Optional[
        Tuple[int, int]
    ]:

        if data is None:
            return None

        if isinstance(
            data,
            dict,
        ):

            for home_key, away_key in (
                self.SCORE_PAIRS
            ):

                if (
                    home_key in data
                    and away_key in data
                ):

                    score = (
                        self._make_score(
                            data[
                                home_key
                            ],
                            data[
                                away_key
                            ],
                        )
                    )

                    if score is not None:
                        return score

            for key in (
                self.SCORE_FIELDS
            ):

                if key not in data:
                    continue

                score = (
                    self._score_from_value(
                        data[key]
                    )
                )

                if score is not None:
                    return score

            for value in data.values():

                score = (
                    self._find_score_in_json(
                        value
                    )
                )

                if score is not None:
                    return score

            return None

        if isinstance(
            data,
            list,
        ):

            for value in data:

                score = (
                    self._find_score_in_json(
                        value
                    )
                )

                if score is not None:
                    return score

            return None

        if isinstance(
            data,
            str,
        ):

            return self._parse_score(
                data
            )

        return None

    # ========================================================
    # SCORE VALUE
    # ========================================================

    def _score_from_value(
        self,
        value: Any,
    ) -> Optional[
        Tuple[int, int]
    ]:

        if isinstance(
            value,
            str,
        ):

            return self._parse_score(
                value
            )

        if isinstance(
            value,
            (list, tuple),
        ):

            if len(value) >= 2:

                return self._make_score(
                    value[0],
                    value[1],
                )

        if isinstance(
            value,
            dict,
        ):

            return self._find_score_in_json(
                value
            )

        return None

    # ========================================================
    # MAKE SCORE
    # ========================================================

    def _make_score(
        self,
        home: Any,
        away: Any,
    ) -> Optional[
        Tuple[int, int]
    ]:

        try:

            home = int(
                home
            )

            away = int(
                away
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if not (
            0 <= home <= 15
            and 0 <= away <= 15
        ):
            return None

        return (
            home,
            away,
        )

    # ========================================================
    # PARSE SCORE STRING
    # ========================================================

    def _parse_score(
        self,
        text: str,
    ) -> Optional[
        Tuple[int, int]
    ]:

        if not text:
            return None

        matches = re.findall(
            r"\b(\d{1,2})\s*[:\-]\s*(\d{1,2})\b",
            text,
        )

        if len(matches) != 1:
            return None

        return self._make_score(
            matches[0][0],
            matches[0][1],
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_stats(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:

        result = {}

        for key, value in stats.items():

            stat_type = None

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

        hp = result.get(
            "home_possession"
        )

        ap = result.get(
            "away_possession"
        )

        if (
            hp is not None
            and ap is not None
        ):

            if not 98 <= hp + ap <= 102:

                logger.warning(
                    "NB-BET: invalid possession "
                    "%s + %s",
                    hp,
                    ap,
                )

                result[
                    "home_possession"
                ] = None

                result[
                    "away_possession"
                ] = None

        # ----------------------------------------------------
        # passes
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
    ):

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
        result: Dict[str, Any],
    ) -> float:

        quality = 0.0

        # Команды
        if (
            result.get("home_team")
            and result.get("away_team")
        ):

            quality += 0.25

        # Итоговый счёт
        #
        # 0:0 тоже считается полностью
        # определённым счётом.
        if (
            result.get("home_goals")
            is not None
            and
            result.get("away_goals")
            is not None
        ):

            quality += 0.50

        # Статистика
        if result.get(
            "stats"
        ):

            quality += 0.25

        return round(
            quality,
            2,
        )

    # ========================================================
    # CLEAN
    # ========================================================

    def _clean(
        self,
        text: str,
    ) -> str:

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

    # ========================================================
    # COMPATIBILITY
    # ========================================================

    def parse_match_page(
        self,
        url: str,
    ) -> Dict[str, Any]:

        return self.parse(
            url
        )

    def parse_score(
        self,
        url: str,
    ) -> Optional[
        Tuple[int, int]
    ]:

        parsed = self.parse(
            url
        )

        home = parsed.get(
            "home_goals"
        )

        away = parsed.get(
            "away_goals"
        )

        if (
            home is None
            or away is None
        ):

            return None

        return (
            home,
            away,
        )


# ============================================================
# CONVENIENCE
# ============================================================

def parse_match_stats(
    url: str,
) -> Dict[str, Any]:

    return (
        NbBetStatsParser()
        .parse_match_page(
            url
        )
    )


def parse_match_score(
    url: str,
) -> Optional[
    Tuple[int, int]
]:

    return (
        NbBetStatsParser()
        .parse_score(
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

    result = parser.parse(
        sys.argv[1]
    )

    print("=" * 70)

    print(
        "FAJ NB-BET PARSER "
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
        "Home:",
        result["home_team"],
    )

    print(
        "Away:",
        result["away_team"],
    )

    print(
        "Score:",
        result["home_goals"],
        ":",
        result["away_goals"],
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

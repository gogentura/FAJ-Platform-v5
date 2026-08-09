#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Soccerland Parser v12.1.1
=====================================================

Источник:
    https://soccerland.ru/russia/premier-liga/2026-2027/calendar

Назначение:
    - загрузка календаря РПЛ 2026/27
    - определение тура непосредственно со страницы
    - определение даты/времени
    - определение хозяев/гостей
    - определение счёта
    - загрузка матчей в SQLite
    - автоматическое создание season / round
    - получение матчей конкретного тура
    - анализ завершённых матчей

ВАЖНО:
    Тур НЕ определяется по позиции матча.

    Источник сам содержит:

        Тур 1
        матч
        матч
        ...
        Тур 2
        матч
        ...

    Поэтому parser сохраняет реальный round_number.
=====================================================
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from app.database import FAJDatabase
from app.core.prediction_manager import get_prediction_manager
from app.passports.passport_manager import get_passport_manager


logger = logging.getLogger(__name__)


class SoccerlandParser:
    """
    Парсер календаря и результатов РПЛ с soccerland.ru.
    """

    VERSION = "12.1.1"

    BASE_URL = (
        "https://soccerland.ru/russia/"
        "premier-liga/2026-2027"
    )

    CALENDAR_URL = (
        "https://soccerland.ru/russia/"
        "premier-liga/2026-2027/calendar"
    )

    LEAGUE = "RPL"
    SEASON_YEAR = "2026-27"

    EXPECTED_TEAMS = 16
    MATCHES_PER_ROUND = 8
    MAX_ROUNDS = 30

    def __init__(
        self,
        db: Optional[FAJDatabase] = None
    ):
        self.db = db or FAJDatabase()

        self.pm = get_prediction_manager()
        self.passport_manager = get_passport_manager()

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 "
                "Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        logger.info(
            "SoccerlandParser v%s initialized",
            self.VERSION
        )

    # =========================================================
    # HTTP
    # =========================================================

    def _get_calendar_soup(self) -> BeautifulSoup:
        """
        Получение календаря soccerland.ru.
        """

        response = self.session.get(
            self.CALENDAR_URL,
            timeout=20
        )

        response.raise_for_status()

        if not response.text:
            raise RuntimeError(
                "soccerland.ru returned empty response"
            )

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    # =========================================================
    # TEXT NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize_text(value: str) -> str:
        """
        Нормализация пробелов и NBSP.
        """

        if value is None:
            return ""

        value = value.replace("\xa0", " ")
        value = value.replace("\u2009", " ")
        value = value.replace("\u202f", " ")

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        return value.strip()

    # =========================================================
    # ROUND PARSING
    # =========================================================

    @staticmethod
    def _extract_round_number(text: str) -> Optional[int]:
        """
        Извлекает номер тура:

            Тур 1
            Тур 2
            ...
        """

        text = SoccerlandParser._normalize_text(text)

        match = re.search(
            r"\bТур\s+(\d{1,2})\b",
            text,
            flags=re.IGNORECASE
        )

        if not match:
            return None

        round_number = int(
            match.group(1)
        )

        if not (
            1 <= round_number <= 30
        ):
            return None

        return round_number

    # =========================================================
    # SCORE
    # =========================================================

    @staticmethod
    def _parse_score(
        score_text: str
    ) -> Dict[str, Any]:
        """
        Разбирает:

            2 : 1
            0 : 0
            – : –
        """

        score_text = (
            SoccerlandParser
            ._normalize_text(score_text)
        )

        # Разные варианты тире
        score_text = (
            score_text
            .replace("−", "-")
            .replace("–", "-")
            .replace("—", "-")
        )

        match = re.search(
            r"(\d+)\s*:\s*(\d+)",
            score_text
        )

        if match:

            return {
                "score": (
                    f"{match.group(1)}:"
                    f"{match.group(2)}"
                ),
                "actual_home": int(
                    match.group(1)
                ),
                "actual_away": int(
                    match.group(2)
                ),
                "status": "finished"
            }

        return {
            "score": "",
            "actual_home": None,
            "actual_away": None,
            "status": "scheduled"
        }

    # =========================================================
    # MATCH LINE PARSING
    # =========================================================

    def _parse_match_text(
        self,
        text: str,
        round_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Разбирает одну строку матча.

        Реальная структура soccerland:

            24.07 20:00 |
            ЦСКА |
            2 : 1 |
            Балтика

        После нормализации:

            24.07 20:00 | ЦСКА | 2 : 1 | Балтика
        """

        text = self._normalize_text(text)

        if not text:
            return None

        # -----------------------------------------------------
        # Дата + время
        # -----------------------------------------------------

        date_match = re.search(
            r"(\d{2}\.\d{2})\s+(\d{2}:\d{2})",
            text
        )

        if not date_match:
            return None

        date_text = date_match.group(1)
        time_text = date_match.group(2)

        # -----------------------------------------------------
        # Извлекаем части через |
        # -----------------------------------------------------

        parts = [
            self._normalize_text(part)
            for part in text.split("|")
        ]

        parts = [
            part
            for part in parts
            if part
        ]

        if len(parts) < 4:
            return None

        # -----------------------------------------------------
        # На soccerland:
        #
        # 0 = дата/время
        # 1 = home
        # 2 = score
        # 3 = away
        # -----------------------------------------------------

        home_team = parts[1]
        score_text = parts[2]
        away_team = parts[3]

        # -----------------------------------------------------
        # Защита от мусора
        # -----------------------------------------------------

        if not home_team or not away_team:
            return None

        if (
            home_team.lower() == "команда"
            or away_team.lower() == "команда"
        ):
            return None

        if home_team == away_team:
            return None

        # -----------------------------------------------------
        # Проверяем, что score действительно счёт
        # -----------------------------------------------------

        if ":" not in score_text:
            return None

        score_data = self._parse_score(
            score_text
        )

        # -----------------------------------------------------
        # Год.
        #
        # До января календарный год 2026.
        # После января — 2027.
        # -----------------------------------------------------

        day = int(
            date_text.split(".")[0]
        )

        month = int(
            date_text.split(".")[1]
        )

        year = (
            2026
            if month >= 7
            else 2027
        )

        iso_date = (
            f"{year:04d}-"
            f"{month:02d}-"
            f"{day:02d}"
        )

        return {
            "round": round_number,
            "date": iso_date,
            "date_display": date_text,
            "time": time_text,
            "home": home_team,
            "away": away_team,
            "score": score_data["score"],
            "status": score_data["status"],
            "actual_home": score_data[
                "actual_home"
            ],
            "actual_away": score_data[
                "actual_away"
            ],
            "source": "soccerland",
        }

    # =========================================================
    # GET ALL MATCHES
    # =========================================================

    def get_all_matches(
        self
    ) -> List[Dict[str, Any]]:
        """
        Получает все матчи сезона.

        Тур определяется по заголовку
        "Тур N", а не по позиции матча.
        """

        try:

            soup = self._get_calendar_soup()

            matches = []

            current_round = None

            # -------------------------------------------------
            # Идём по текстовым узлам страницы.
            #
            # Используем строки, которые реально содержат
            # разделители календаря.
            # -------------------------------------------------

            text_nodes = soup.find_all(
                string=re.compile(r"\|")
            )

            for node in text_nodes:

                parent = node.parent

                if not parent:
                    continue

                text = self._normalize_text(
                    parent.get_text(
                        " ",
                        strip=True
                    )
                )

                # ---------------------------------------------
                # Иногда строка матча находится выше.
                # ---------------------------------------------

                if "|" not in text:
                    continue

                # ---------------------------------------------
                # Ищем ближайший контекст с "Тур N".
                # ---------------------------------------------

                context_text = ""

                # Родитель
                if parent.parent:
                    context_text = self._normalize_text(
                        parent.parent.get_text(
                            " ",
                            strip=True
                        )
                    )

                # Если родитель слишком большой,
                # используем предыдущие элементы.
                if len(context_text) > 500:
                    context_text = text

                # ---------------------------------------------
                # Сначала пытаемся найти тур непосредственно
                # в строке / родителе.
                # ---------------------------------------------

                detected_round = (
                    self._extract_round_number(
                        text
                    )
                )

                if detected_round is not None:
                    current_round = detected_round
                    continue

                # ---------------------------------------------
                # Если текущий round ещё неизвестен,
                # пропускаем.
                # ---------------------------------------------

                if current_round is None:
                    continue

                # ---------------------------------------------
                # Проверяем дату.
                # ---------------------------------------------

                if not re.search(
                    r"\d{2}\.\d{2}\s+\d{2}:\d{2}",
                    text
                ):
                    continue

                # ---------------------------------------------
                # Парсим матч.
                # ---------------------------------------------

                parsed = self._parse_match_text(
                    text=text,
                    round_number=current_round
                )

                if not parsed:
                    continue

                matches.append(parsed)

            # =================================================
            # FALLBACK
            # =================================================
            #
            # На случай, если BeautifulSoup разбил строку
            # календаря на несколько текстовых узлов.
            #
            # Тогда используем родительские контейнеры.
            # =================================================

            if len(matches) < 20:

                logger.warning(
                    "Primary parser found only %s matches. "
                    "Running fallback parser.",
                    len(matches)
                )

                matches = self._fallback_parse(
                    soup
                )

            # =================================================
            # DEDUPLICATION
            # =================================================

            unique = []

            seen = set()

            for match in matches:

                key = (
                    match["round"],
                    match["date"],
                    match["time"],
                    match["home"],
                    match["away"]
                )

                if key in seen:
                    continue

                seen.add(key)

                unique.append(match)

            unique.sort(
                key=lambda item: (
                    item["round"],
                    item["date"],
                    item["time"],
                    item["home"],
                    item["away"]
                )
            )

            logger.info(
                "Soccerland parser found %s unique matches",
                len(unique)
            )

            # -------------------------------------------------
            # Диагностика туров
            # -------------------------------------------------

            rounds = {}

            for match in unique:

                round_number = match["round"]

                rounds[round_number] = (
                    rounds.get(
                        round_number,
                        0
                    )
                    + 1
                )

            logger.info(
                "Parsed rounds: %s",
                rounds
            )

            return unique

        except Exception as exc:

            logger.exception(
                "Soccerland get_all_matches error"
            )

            return []

    # =========================================================
    # FALLBACK PARSER
    # =========================================================

    def _fallback_parse(
        self,
        soup: BeautifulSoup
    ) -> List[Dict[str, Any]]:
        """
        Резервный парсер.

        Используется, если основной parser не смог
        собрать достаточное количество матчей.
        """

        matches = []

        current_round = None

        # Все элементы, содержащие "Тур"
        # и календарные данные.
        elements = soup.find_all(
            ["div", "li", "tr", "p", "a", "span"]
        )

        for element in elements:

            text = self._normalize_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if not text:
                continue

            # ---------------------------------------------
            # Тур
            # ---------------------------------------------

            detected_round = (
                self._extract_round_number(
                    text
                )
            )

            if (
                detected_round is not None
                and len(text) < 100
            ):
                current_round = detected_round
                continue

            if current_round is None:
                continue

            # ---------------------------------------------
            # Матч
            # ---------------------------------------------

            if "|" not in text:
                continue

            if not re.search(
                r"\d{2}\.\d{2}\s+\d{2}:\d{2}",
                text
            ):
                continue

            parsed = self._parse_match_text(
                text=text,
                round_number=current_round
            )

            if parsed:
                matches.append(parsed)

        return matches

    # =========================================================
    # GET MATCHES BY TOUR
    # =========================================================

    def get_matches_by_tour(
        self,
        tour_number: int
    ) -> List[Dict[str, Any]]:
        """
        Возвращает матчи конкретного тура.

        ВАЖНО:
            Никаких индексов.
            Тур берётся из поля match["round"].
        """

        try:
            tour_number = int(
                tour_number
            )
        except (
            TypeError,
            ValueError
        ):
            return []

        if not (
            1 <= tour_number <= self.MAX_ROUNDS
        ):
            logger.warning(
                "Invalid round number: %s",
                tour_number
            )
            return []

        all_matches = self.get_all_matches()

        tour_matches = [
            match
            for match in all_matches
            if match.get("round")
            == tour_number
        ]

        logger.info(
            "Soccerland round %s: %s matches",
            tour_number,
            len(tour_matches)
        )

        return tour_matches

    # =========================================================
    # TEAM
    # =========================================================

    def _get_or_create_team(
        self,
        name: str
    ) -> int:
        """
        Получить команду или создать её.
        """

        name = self._normalize_text(
            name
        )

        if not name:
            raise ValueError(
                "Team name cannot be empty"
            )

        team_id = self.db.get_team_id(
            name,
            self.LEAGUE
        )

        if team_id:
            return team_id

        # ---------------------------------------------
        # Создаём команду
        # ---------------------------------------------

        team_id = self.db.add_team(
            name=name,
            league=self.LEAGUE,
            country="Russia",
            team_type="club"
        )

        if not team_id:
            raise RuntimeError(
                f"Failed to create team: {name}"
            )

        # ---------------------------------------------
        # Season
        # ---------------------------------------------

        season_id = self.db.get_season_id(
            self.LEAGUE,
            self.SEASON_YEAR
        )

        if not season_id:

            season_id = self.db.create_season(
                name=(
                    f"{self.LEAGUE} "
                    f"{self.SEASON_YEAR}"
                ),
                league=self.LEAGUE,
                year=self.SEASON_YEAR,
                competition_type="league"
            )

        # ---------------------------------------------
        # Default passport
        # ---------------------------------------------

        default_passport = {
            "attack": 50,
            "defense": 50,
            "control": 50,
            "goalkeeper": 50,
            "form": 50,
            "fitness": 50,
            "morale": 50,
            "home_advantage": 1.12,
            "source": "parser"
        }

        try:

            self.passport_manager.create_passport(
                team_id=team_id,
                season_id=season_id,
                data=default_passport,
                source="parser_auto"
            )

        except Exception as exc:

            logger.warning(
                "Could not create default passport "
                "for %s: %s",
                name,
                exc
            )

        logger.info(
            "Created team: %s | id=%s",
            name,
            team_id
        )

        return team_id

    # =========================================================
    # SEASON
    # =========================================================

    def _ensure_season(self) -> int:
        """
        Гарантирует наличие сезона.
        """

        season_id = self.db.get_season_id(
            self.LEAGUE,
            self.SEASON_YEAR
        )

        if season_id:
            return season_id

        season_id = self.db.create_season(
            name=(
                f"{self.LEAGUE} "
                f"{self.SEASON_YEAR}"
            ),
            league=self.LEAGUE,
            year=self.SEASON_YEAR,
            competition_type="league"
        )

        if not season_id:
            raise RuntimeError(
                "Failed to create season "
                f"{self.LEAGUE} {self.SEASON_YEAR}"
            )

        logger.info(
            "Created season: %s",
            season_id
        )

        return season_id

    # =========================================================
    # ROUND
    # =========================================================

    def _ensure_round(
        self,
        season_id: int,
        round_number: int
    ) -> int:
        """
        Гарантирует наличие тура.

        Это основная защита от:
            Round not found
        """

        round_number = int(
            round_number
        )

        # ---------------------------------------------
        # Сначала пытаемся найти существующий тур.
        # ---------------------------------------------

        existing = self._get_round_id(
            round_number
        )

        if existing:
            return existing

        # ---------------------------------------------
        # Создаём.
        # ---------------------------------------------

        round_id = self.db.create_round(
            season_id,
            round_number
        )

        if round_id:
            # Повторно проверяем БД.
            verified = self._get_round_id(
                round_number
            )

            if verified:
                return verified

        # ---------------------------------------------
        # Если create_round ничего не вернул,
        # всё равно пытаемся найти запись.
        # ---------------------------------------------

        existing = self._get_round_id(
            round_number
        )

        if existing:
            return existing

        raise RuntimeError(
            f"Round {round_number} "
            f"could not be created/found "
            f"for season {season_id}"
        )

    # =========================================================
    # LOAD MATCHES
    # =========================================================

    def load_matches_to_db(
        self,
        matches: List[Dict[str, Any]],
        round_number: int
    ) -> int:
        """
        Загружает матчи конкретного тура.

        Перед загрузкой гарантирует:
            season
            round
        """

        if not matches:
            logger.warning(
                "No matches to load for round %s",
                round_number
            )
            return 0

        season_id = self._ensure_season()

        round_id = self._ensure_round(
            season_id,
            round_number
        )

        added_count = 0

        for match in matches:

            try:

                home_team = self._normalize_text(
                    match.get("home", "")
                )

                away_team = self._normalize_text(
                    match.get("away", "")
                )

                if not home_team or not away_team:
                    continue

                # -----------------------------------------
                # Teams
                # -----------------------------------------

                home_id = self._get_or_create_team(
                    home_team
                )

                away_id = self._get_or_create_team(
                    away_team
                )

                # -----------------------------------------
                # Score
                # -----------------------------------------

                actual_home = match.get(
                    "actual_home"
                )

                actual_away = match.get(
                    "actual_away"
                )

                status = match.get(
                    "status",
                    "scheduled"
                )

                # -----------------------------------------
                # UUID
                # -----------------------------------------

                raw_uuid = (
                    f"{self.LEAGUE}|"
                    f"{self.SEASON_YEAR}|"
                    f"{round_number}|"
                    f"{match.get('date', '')}|"
                    f"{match.get('time', '')}|"
                    f"{home_team}|"
                    f"{away_team}"
                )

                match_uuid = hashlib.md5(
                    raw_uuid.encode(
                        "utf-8"
                    )
                ).hexdigest()[:16]

                # -----------------------------------------
                # Existing match
                # -----------------------------------------

                existing = self.db.get_match_by_uuid(
                    match_uuid
                )

                if existing:

                    logger.debug(
                        "Match already exists: "
                        "%s vs %s",
                        home_team,
                        away_team
                    )

                    continue

                # -----------------------------------------
                # Match data
                # -----------------------------------------

                match_data = {
                    "round_id": round_id,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "match_uuid": match_uuid,

                    "date": match.get(
                        "date",
                        ""
                    ),

                    "competition": self.LEAGUE,

                    "status": status,

                    "actual_home": actual_home,
                    "actual_away": actual_away,

                    "parser_source": "soccerland",
                    "parser_version": self.VERSION
                }

                self.db.upsert_match(
                    match_data
                )

                added_count += 1

                logger.info(
                    "Added match | "
                    "R%s | %s vs %s | %s",
                    round_number,
                    home_team,
                    away_team,
                    (
                        match.get(
                            "score"
                        )
                        or "scheduled"
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Error loading match "
                    "%s vs %s: %s",
                    match.get("home"),
                    match.get("away"),
                    exc
                )

        logger.info(
            "Round %s loaded: %s matches",
            round_number,
            added_count
        )

        return added_count

    # =========================================================
    # ROUND ID
    # =========================================================

    def _get_round_id(
        self,
        round_number: int
    ) -> Optional[int]:
        """
        Получить round_id.
        """

        conn = self.db._get_connection()

        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                SELECT r.id
                FROM rounds r
                JOIN seasons s
                    ON r.season_id = s.id
                WHERE r.round_number = ?
                  AND s.league = ?
                  AND s.year = ?
                LIMIT 1
                """,
                (
                    int(round_number),
                    self.LEAGUE,
                    self.SEASON_YEAR
                )
            )

            row = cursor.fetchone()

            if not row:
                return None

            return row[0]

        finally:

            conn.close()

    # =========================================================
    # TEAM NAME
    # =========================================================

    def _get_team_name(
        self,
        team_id: int
    ) -> Optional[str]:

        conn = self.db._get_connection()

        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                SELECT name
                FROM teams
                WHERE id = ?
                LIMIT 1
                """,
                (team_id,)
            )

            row = cursor.fetchone()

            if not row:
                return None

            return row[0]

        finally:

            conn.close()

    # =========================================================
    # STANDINGS
    # =========================================================

    def get_standings(
        self
    ) -> List[Dict[str, Any]]:
        """
        Получение турнирной таблицы.

        Оставлено как отдельный метод,
        чтобы не ломать существующий pipeline.
        """

        try:

            response = self.session.get(
                self.BASE_URL,
                timeout=20
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            standings = []

            table = None

            for candidate in soup.find_all(
                "table"
            ):

                text = self._normalize_text(
                    candidate.get_text(
                        " ",
                        strip=True
                    )
                ).lower()

                if (
                    "команда" in text
                    and (
                        "игр" in text
                        or "очки" in text
                        or "место" in text
                    )
                ):
                    table = candidate
                    break

            if table is None:

                logger.warning(
                    "Standings table not found"
                )

                return []

            rows = table.find_all("tr")

            for row in rows:

                cells = row.find_all(
                    ["td", "th"]
                )

                if len(cells) < 8:
                    continue

                values = [
                    self._normalize_text(
                        cell.get_text(
                            " ",
                            strip=True
                        )
                    )
                    for cell in cells
                ]

                try:

                    place = (
                        int(values[0])
                        if values[0].isdigit()
                        else 0
                    )

                    team = values[1]

                    games = self._to_int(
                        values[2]
                    )

                    wins = self._to_int(
                        values[3]
                    )

                    draws = self._to_int(
                        values[4]
                    )

                    losses = self._to_int(
                        values[5]
                    )

                    goals_for = 0
                    goals_against = 0

                    goals_match = re.search(
                        r"(\d+)\s*[:\-]\s*(\d+)",
                        values[6]
                    )

                    if goals_match:

                        goals_for = int(
                            goals_match.group(1)
                        )

                        goals_against = int(
                            goals_match.group(2)
                        )

                    points = self._to_int(
                        values[7]
                    )

                    form = (
                        values[8]
                        if len(values) > 8
                        else ""
                    )

                    standings.append({
                        "place": place,
                        "team": team,
                        "games": games,
                        "wins": wins,
                        "draws": draws,
                        "losses": losses,
                        "goals_for": goals_for,
                        "goals_against": goals_against,
                        "goal_diff": (
                            goals_for
                            - goals_against
                        ),
                        "points": points,
                        "form": form
                    })

                except Exception as exc:

                    logger.debug(
                        "Standings row error: %s",
                        exc
                    )

            logger.info(
                "Parsed %s standings teams",
                len(standings)
            )

            return standings

        except Exception as exc:

            logger.exception(
                "Standings parsing error"
            )

            return []

    # =========================================================
    # INTEGER
    # =========================================================

    @staticmethod
    def _to_int(
        value: str
    ) -> int:

        match = re.search(
            r"-?\d+",
            value or ""
        )

        if not match:
            return 0

        return int(
            match.group(0)
        )

    # =========================================================
    # SAVE STANDINGS
    # =========================================================

    def save_standings_to_db(
        self,
        standings: List[Dict[str, Any]],
        round_number: int
    ) -> int:

        if not standings:
            return 0

        season_id = self._ensure_season()

        conn = self.db._get_connection()

        cursor = conn.cursor()

        saved_count = 0

        try:

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER,
                    season_id INTEGER,
                    round INTEGER,
                    place INTEGER,
                    games INTEGER,
                    wins INTEGER,
                    draws INTEGER,
                    losses INTEGER,
                    goals_for INTEGER,
                    goals_against INTEGER,
                    goal_diff INTEGER,
                    points INTEGER,
                    form TEXT,
                    updated_at TEXT,
                    FOREIGN KEY(team_id)
                        REFERENCES teams(id),
                    FOREIGN KEY(season_id)
                        REFERENCES seasons(id),
                    UNIQUE(
                        team_id,
                        season_id,
                        round
                    )
                )
                """
            )

            for item in standings:

                team_name = self._normalize_text(
                    item.get(
                        "team",
                        ""
                    )
                )

                if not team_name:
                    continue

                team_id = self._get_or_create_team(
                    team_name
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO standings (
                        team_id,
                        season_id,
                        round,
                        place,
                        games,
                        wins,
                        draws,
                        losses,
                        goals_for,
                        goals_against,
                        goal_diff,
                        points,
                        form,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        team_id,
                        season_id,
                        round_number,
                        item.get("place", 0),
                        item.get("games", 0),
                        item.get("wins", 0),
                        item.get("draws", 0),
                        item.get("losses", 0),
                        item.get("goals_for", 0),
                        item.get(
                            "goals_against",
                            0
                        ),
                        item.get(
                            "goal_diff",
                            0
                        ),
                        item.get("points", 0),
                        item.get("form", ""),
                        datetime.now().isoformat()
                    )
                )

                saved_count += 1

            conn.commit()

            logger.info(
                "Saved %s standings records",
                saved_count
            )

            return saved_count

        except Exception as exc:

            conn.rollback()

            logger.exception(
                "Error saving standings"
            )

            return 0

        finally:

            conn.close()

    # =========================================================
    # ANALYZE ROUND
    # =========================================================

    def analyze_and_update(
        self,
        round_number: int
    ) -> Dict[str, Any]:

        result = {
            "round": round_number,
            "matches_analyzed": 0,
            "teams_updated": [],
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }

        round_id = self._get_round_id(
            round_number
        )

        if not round_id:

            result["errors"].append(
                f"Round {round_number} not found"
            )

            return result

        matches = self.db.get_matches(
            round_id
        )

        if not matches:

            result["errors"].append(
                f"No matches found for round "
                f"{round_number}"
            )

            return result

        season_id = self._ensure_season()

        for match in matches:

            match_dict = dict(
                match
            )

            if (
                match_dict.get("status")
                != "finished"
            ):
                continue

            home_team_id = match_dict.get(
                "home_team_id"
            )

            away_team_id = match_dict.get(
                "away_team_id"
            )

            actual_home = match_dict.get(
                "actual_home"
            )

            actual_away = match_dict.get(
                "actual_away"
            )

            if (
                actual_home is None
                or actual_away is None
            ):
                continue

            # ---------------------------------------------
            # HOME
            # ---------------------------------------------

            try:

                self._update_team_after_match(
                    team_id=home_team_id,
                    goals_for=actual_home,
                    goals_against=actual_away,
                    is_home=True,
                    season_id=season_id
                )

                result[
                    "teams_updated"
                ].append(
                    home_team_id
                )

            except Exception as exc:

                result["errors"].append(
                    f"Home team "
                    f"{home_team_id}: {exc}"
                )

            # ---------------------------------------------
            # AWAY
            # ---------------------------------------------

            try:

                self._update_team_after_match(
                    team_id=away_team_id,
                    goals_for=actual_away,
                    goals_against=actual_home,
                    is_home=False,
                    season_id=season_id
                )

                result[
                    "teams_updated"
                ].append(
                    away_team_id
                )

            except Exception as exc:

                result["errors"].append(
                    f"Away team "
                    f"{away_team_id}: {exc}"
                )

            result[
                "matches_analyzed"
            ] += 1

        return result

    # =========================================================
    # UPDATE PASSPORT
    # =========================================================

    def _update_team_after_match(
        self,
        team_id: int,
        goals_for: int,
        goals_against: int,
        is_home: bool,
        season_id: int
    ):

        match_data = {
            "goals_for": goals_for,
            "goals_against": goals_against,
            "is_win": (
                goals_for > goals_against
            ),
            "is_draw": (
                goals_for == goals_against
            ),
            "xg_for": float(
                goals_for
            ),
            "xg_against": float(
                goals_against
            ),
            "home": is_home
        }

        self.passport_manager.update_after_match(
            team_id=team_id,
            season_id=season_id,
            match_data=match_data,
            opponent_rating=70.0,
            matches_count=1
        )

    # =========================================================
    # PREDICTION
    # =========================================================

    def predict_tour(
        self,
        round_number: int
    ) -> List[Dict[str, Any]]:

        predictions = []

        round_id = self._get_round_id(
            round_number
        )

        if not round_id:
            logger.warning(
                "Cannot predict round %s: "
                "round not found",
                round_number
            )
            return predictions

        matches = self.db.get_matches(
            round_id
        )

        for match in matches:

            match_dict = dict(
                match
            )

            if (
                match_dict.get("status")
                != "scheduled"
            ):
                continue

            home_team = self._get_team_name(
                match_dict.get(
                    "home_team_id"
                )
            )

            away_team = self._get_team_name(
                match_dict.get(
                    "away_team_id"
                )
            )

            if not home_team or not away_team:
                continue

            try:

                prediction = self.pm.predict(
                    home_team=home_team,
                    away_team=away_team,
                    league=self.LEAGUE,
                    season_id=match_dict.get(
                        "round_id"
                    )
                )

                if (
                    prediction.get(
                        "status"
                    )
                    != "error"
                ):

                    predictions.append({
                        "match_id": match_dict.get(
                            "id"
                        ),
                        "home_team": home_team,
                        "away_team": away_team,
                        "prediction": prediction
                    })

            except Exception as exc:

                logger.exception(
                    "Prediction error "
                    "%s vs %s",
                    home_team,
                    away_team
                )

        return predictions

    # =========================================================
    # FULL UPDATE
    # =========================================================

    def update_all(
        self,
        round_number: int
    ) -> Dict[str, Any]:
        """
        Полный цикл:

            standings
                ↓
            calendar
                ↓
            round
                ↓
            matches
                ↓
            predictions
        """

        result = {
            "timestamp": datetime.now().isoformat(),
            "round": round_number,
            "standings_saved": 0,
            "matches_loaded": 0,
            "predictions": [],
            "errors": []
        }

        logger.info(
            "=========================================="
        )

        logger.info(
            "FAJ FULL UPDATE | ROUND %s",
            round_number
        )

        logger.info(
            "=========================================="
        )

        try:

            # ---------------------------------------------
            # 1. Season
            # ---------------------------------------------

            self._ensure_season()

            # ---------------------------------------------
            # 2. Standings
            # ---------------------------------------------

            standings = self.get_standings()

            if standings:

                result[
                    "standings_saved"
                ] = self.save_standings_to_db(
                    standings,
                    round_number
                )

            # ---------------------------------------------
            # 3. Calendar
            # ---------------------------------------------

            matches = self.get_matches_by_tour(
                round_number
            )

            if not matches:

                result["errors"].append(
                    f"No matches found "
                    f"for round {round_number}"
                )

                return result

            # ---------------------------------------------
            # 4. Load matches
            # ---------------------------------------------

            result[
                "matches_loaded"
            ] = self.load_matches_to_db(
                matches,
                round_number
            )

            # ---------------------------------------------
            # 5. Predictions
            # ---------------------------------------------

            if result[
                "matches_loaded"
            ] > 0:

                result[
                    "predictions"
                ] = self.predict_tour(
                    round_number
                )

            return result

        except Exception as exc:

            logger.exception(
                "FAJ full update error"
            )

            result[
                "errors"
            ].append(
                str(exc)
            )

            return result

    # =========================================================
    # DIAGNOSTICS
    # =========================================================

    def diagnostics(
        self
    ) -> Dict[str, Any]:
        """
        Диагностика источника.

        Ничего не пишет в БД.
        """

        matches = self.get_all_matches()

        rounds = {}

        teams = set()

        finished = 0
        scheduled = 0

        for match in matches:

            round_number = match.get(
                "round"
            )

            rounds.setdefault(
                round_number,
                0
            )

            rounds[
                round_number
            ] += 1

            teams.add(
                match.get("home")
            )

            teams.add(
                match.get("away")
            )

            if (
                match.get("status")
                == "finished"
            ):
                finished += 1
            else:
                scheduled += 1

        return {
            "parser_version": self.VERSION,
            "source": self.CALENDAR_URL,
            "total_matches": len(matches),
            "total_rounds": len(rounds),
            "rounds": rounds,
            "teams": sorted(
                team
                for team in teams
                if team
            ),
            "team_count": len(teams),
            "finished": finished,
            "scheduled": scheduled,
            "expected_matches": (
                self.MAX_ROUNDS
                * self.MATCHES_PER_ROUND
            ),
            "expected_teams": self.EXPECTED_TEAMS,
            "status": (
                "READY"
                if (
                    len(matches)
                    > 0
                    and len(teams)
                    >= self.EXPECTED_TEAMS
                )
                else "WARNING"
            )
        }


# =============================================================
# SELF TEST
# =============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        )
    )

    print()
    print("=" * 70)
    print(
        "FAJ SOCCERLAND PARSER "
        "v12.1.1"
    )
    print("=" * 70)

    parser = SoccerlandParser()

    # =========================================================
    # 1. ALL MATCHES
    # =========================================================

    print()
    print("1. GET ALL MATCHES")
    print("-" * 70)

    matches = parser.get_all_matches()

    print(
        f"Found: {len(matches)} matches"
    )

    # =========================================================
    # 2. DIAGNOSTICS
    # =========================================================

    print()
    print("2. DIAGNOSTICS")
    print("-" * 70)

    diagnostics = parser.diagnostics()

    print(
        f"Status: "
        f"{diagnostics['status']}"
    )

    print(
        f"Rounds: "
        f"{diagnostics['total_rounds']}"
    )

    print(
        f"Teams: "
        f"{diagnostics['team_count']}"
    )

    print(
        f"Finished: "
        f"{diagnostics['finished']}"
    )

    print(
        f"Scheduled: "
        f"{diagnostics['scheduled']}"
    )

    print()
    print("MATCHES BY ROUND")

    for round_number, count in sorted(
        diagnostics["rounds"].items()
    ):

        print(
            f"  Round {round_number}: "
            f"{count} matches"
        )

    # =========================================================
    # 3. ROUND 1
    # =========================================================

    print()
    print("3. ROUND 1")
    print("-" * 70)

    round_1 = parser.get_matches_by_tour(1)

    for match in round_1:

        score = (
            match["score"]
            or "– : –"
        )

        print(
            f"  {match['date']} "
            f"{match['time']} | "
            f"{match['home']} | "
            f"{score} | "
            f"{match['away']}"
        )

    # =========================================================
    # 4. ROUND 4
    # =========================================================

    print()
    print("4. ROUND 4")
    print("-" * 70)

    round_4 = parser.get_matches_by_tour(4)

    print(
        f"Found: {len(round_4)}"
    )

    for match in round_4:

        score = (
            match["score"]
            or "– : –"
        )

        print(
            f"  {match['date']} "
            f"{match['time']} | "
            f"{match['home']} | "
            f"{score} | "
            f"{match['away']}"
        )

    # =========================================================
    # FINAL
    # =========================================================

    print()
    print("=" * 70)
    print(
        "SOCCERLAND PARSER "
        "v12.1.1 READY"
    )
    print("=" * 70)

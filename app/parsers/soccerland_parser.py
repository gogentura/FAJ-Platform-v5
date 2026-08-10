#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================
FAJ Platform v12.1
Soccerland Parser v12.3 — НАДЁЖНЫЙ ПАРСЕР
=====================================================
Источник:
    https://soccerland.ru/russia/premier-liga/2026-2027/calendar
Назначение:
    - загрузка календаря РПЛ 2026/27
    - определение тура непосредственно со страницы
    - определение хозяев/гостей
    - определение счёта
    - загрузка матчей в SQLite
    - автоматическое создание season / round
    - получение матчей конкретного тура
    - анализ завершённых матчей
ВАЖНО:
    - Тур НЕ определяется по позиции матча.
    - Источник сам содержит:
        Тур 1
        матч
        матч
        ...
        Тур 2
        матч
        ...
    - Поэтому parser сохраняет реальный round_number.
    - Парсер НЕ использует split('\\n') и НЕ полагается на
      фиксированное количество матчей.
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
    VERSION = "12.3"
    CALENDAR_URL = (
        "https://soccerland.ru/"
        "russia/premier-liga/"
        "2026-2027/calendar"
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
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        self.session.headers.update(self.headers)
        logger.info("SoccerlandParser v%s initialized", self.VERSION)

    # =========================================================
    # HTTP
    # =========================================================
    def _get_calendar_html(self) -> str:
        """Получение HTML календаря Soccerland."""
        response = self.session.get(
            self.CALENDAR_URL,
            timeout=20
        )
        response.raise_for_status()
        if not response.text:
            raise RuntimeError(
                "soccerland.ru returned empty response"
            )
        logger.info(
            "Soccerland HTTP %s | %s bytes",
            response.status_code,
            len(response.text)
        )
        return response.text

    # =========================================================
    # НОРМАЛИЗАЦИЯ
    # =========================================================
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Нормализация текста Soccerland."""
        if not text:
            return ""
        text = (
            text
            .replace("\xa0", " ")
            .replace("\u2009", " ")
            .replace("\u202f", " ")
        )
        text = re.sub(
            r"\s+",
            " ",
            text
        )
        return text.strip()

    # =========================================================
    # ТУР
    # =========================================================
    @staticmethod
    def _extract_round_number(text: str) -> Optional[int]:
        """Извлечение номера тура."""
        if not text:
            return None
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
        if 1 <= round_number <= 30:
            return round_number
        return None

    # =========================================================
    # СЧЁТ
    # =========================================================
    @staticmethod
    def _parse_score(
        score_text: str
    ) -> Dict[str, Any]:
        score_text = (
            SoccerlandParser
            ._normalize_text(score_text)
        )
        # Нормализуем разные тире
        normalized = (
            score_text
            .replace("−", "-")
            .replace("–", "-")
            .replace("—", "-")
        )
        # ---------------------------------------------------------
        # Завершённый матч
        # ---------------------------------------------------------
        match = re.search(
            r"(\d+)\s*:\s*(\d+)",
            normalized
        )
        if match:
            home_goals = int(
                match.group(1)
            )
            away_goals = int(
                match.group(2)
            )
            return {
                "score": (
                    f"{home_goals}:{away_goals}"
                ),
                "actual_home": home_goals,
                "actual_away": away_goals,
                "status": "finished"
            }
        # ---------------------------------------------------------
        # Будущий матч
        # ---------------------------------------------------------
        return {
            "score": "",
            "actual_home": None,
            "actual_away": None,
            "status": "scheduled"
        }

    # =========================================================
    # ОСНОВНОЙ ПАРСИНГ
    # =========================================================
    def get_all_matches(
        self
    ) -> List[Dict[str, Any]]:
        """
        Надёжный парсер календаря Soccerland.
        НЕ использует:
            split('\\n')
            фиксированное количество матчей
            позицию матча в списке
        Тур определяется непосредственно
        по заголовку "Тур N".
        """
        try:
            html = self._get_calendar_html()
            soup = BeautifulSoup(
                html,
                "html.parser"
            )
            # -----------------------------------------------------
            # ВАЖНО:
            #
            # Получаем весь текст одним потоком.
            # separator=" " не позволяет BeautifulSoup
            # склеивать слова из соседних HTML-узлов.
            # -----------------------------------------------------
            page_text = soup.get_text(
                " ",
                strip=True
            )
            page_text = self._normalize_text(
                page_text
            )
            logger.info(
                "Soccerland text length: %s",
                len(page_text)
            )
            # -----------------------------------------------------
            # Ищем все заголовки Тур N
            # -----------------------------------------------------
            round_matches = list(
                re.finditer(
                    r"\bТур\s+(\d{1,2})\b",
                    page_text,
                    flags=re.IGNORECASE
                )
            )
            logger.info(
                "Detected %s round headers",
                len(round_matches)
            )
            if not round_matches:
                logger.warning(
                    "No round headers found on Soccerland"
                )
                return []
            matches = []
            # -----------------------------------------------------
            # Для каждого тура выделяем его участок текста
            # -----------------------------------------------------
            for index, round_match in enumerate(
                round_matches
            ):
                round_number = int(
                    round_match.group(1)
                )
                if not (
                    1 <= round_number <= 30
                ):
                    continue
                start = round_match.end()
                if index + 1 < len(
                    round_matches
                ):
                    end = round_matches[
                        index + 1
                    ].start()
                else:
                    # До конца календаря.
                    # Дальше статистика, но regex
                    # матчей туда не попадёт.
                    end = len(page_text)
                round_text = page_text[
                    start:end
                ]
                # -------------------------------------------------
                # Матч:
                #
                # DD.MM HH:MM |
                # HOME |
                # SCORE |
                # AWAY
                #
                # Score:
                # 2 : 1
                # или
                # – : –
                # -------------------------------------------------
                match_pattern = re.compile(
                    r"""
                    (\d{2}\.\d{2})          # дата
                    \s+
                    (\d{2}:\d{2})           # время
                    \s*\|\s*
                    ([^|]+?)                # хозяева
                    \s*\|\s*
                    (
                        \d+\s*:\s*\d+
                        |
                        [-–—−]+\s*:\s*[-–—−]+
                    )                       # счёт
                    \s*\|\s*
                    (.*?)
                    (?=
                        \s+\d{2}\.\d{2}\s+\d{2}:\d{2}
                        \s*\|
                        |
                        $
                    )
                    """,
                    flags=re.VERBOSE
                )
                round_count = 0
                for match in match_pattern.finditer(
                    round_text
                ):
                    date_str = (
                        match.group(1)
                        .strip()
                    )
                    time_str = (
                        match.group(2)
                        .strip()
                    )
                    home = self._normalize_text(
                        match.group(3)
                    )
                    score_text = self._normalize_text(
                        match.group(4)
                    )
                    away = self._normalize_text(
                        match.group(5)
                    )
                    # -------------------------------------------------
                    # Защита от мусора
                    # -------------------------------------------------
                    if not home or not away:
                        continue
                    if home == away:
                        continue
                    if len(home) < 2:
                        continue
                    if len(away) < 2:
                        continue
                    # -------------------------------------------------
                    # Парсим счёт
                    # -------------------------------------------------
                    score_data = self._parse_score(
                        score_text
                    )
                    # -------------------------------------------------
                    # Год
                    #
                    # Июль-декабрь 2026
                    # Январь-май 2027
                    # -------------------------------------------------
                    day, month = map(
                        int,
                        date_str.split(".")
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
                    match_data = {
                        "round": round_number,
                        "date": iso_date,
                        "time": time_str,
                        "home": home,
                        "away": away,
                        "score": score_data[
                            "score"
                        ],
                        "status": score_data[
                            "status"
                        ],
                        "actual_home": score_data[
                            "actual_home"
                        ],
                        "actual_away": score_data[
                            "actual_away"
                        ],
                        "source": "soccerland",
                        "parser_version":
                            self.VERSION
                    }
                    matches.append(
                        match_data
                    )
                    round_count += 1
                logger.info(
                    "Round %s | parsed %s matches",
                    round_number,
                    round_count
                )
            # -----------------------------------------------------
            # Удаляем дубли
            # -----------------------------------------------------
            unique_matches = []
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
                unique_matches.append(
                    match
                )
            # -----------------------------------------------------
            # Сортировка
            # -----------------------------------------------------
            unique_matches.sort(
                key=lambda x: (
                    x.get("round", 0),
                    x.get("date", ""),
                    x.get("time", "")
                )
            )
            logger.info(
                "=========================================="
            )
            logger.info(
                "SOCCERLAND PARSER RESULT"
            )
            logger.info(
                "Rounds detected: %s",
                len(
                    set(
                        m["round"]
                        for m in unique_matches
                    )
                )
            )
            logger.info(
                "Matches detected: %s",
                len(unique_matches)
            )
            logger.info(
                "=========================================="
            )
            return unique_matches
        except Exception as exc:
            logger.exception(
                "Soccerland parser error: %s",
                exc
            )
            return []

    # =========================================================
    # МАТЧИ ТУРА
    # =========================================================
    def get_matches_by_tour(
        self,
        tour_number: int
    ) -> List[Dict[str, Any]]:
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
                "Invalid round: %s",
                tour_number
            )
            return []
        all_matches = (
            self.get_all_matches()
        )
        tour_matches = [
            match
            for match in all_matches
            if match.get("round")
            == tour_number
        ]
        logger.info(
            "ROUND %s | %s matches",
            tour_number,
            len(tour_matches)
        )
        return tour_matches

    # =========================================================
    # ДИАГНОСТИКА
    # =========================================================
    def diagnostics(
        self
    ) -> Dict[str, Any]:
        matches = (
            self.get_all_matches()
        )
        rounds = {}
        teams = set()
        finished = 0
        scheduled = 0
        for match in matches:
            round_number = match.get(
                "round"
            )
            rounds[
                round_number
            ] = rounds.get(
                round_number,
                0
            ) + 1
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
        # -----------------------------------------------------
        # Ожидаем:
        #
        # 30 туров
        # 8 матчей в туре
        # 16 команд
        # 240 матчей
        # -----------------------------------------------------
        total_rounds = len(
            rounds
        )
        total_matches = len(
            matches
        )
        expected_matches = (
            self.MAX_ROUNDS
            *
            self.MATCHES_PER_ROUND
        )
        valid_rounds = all(
            count == self.MATCHES_PER_ROUND
            for count in rounds.values()
        )
        ready = (
            total_matches
            == expected_matches
            and
            total_rounds
            == self.MAX_ROUNDS
            and
            len(teams)
            >= self.EXPECTED_TEAMS
            and
            valid_rounds
        )
        return {
            "parser_version":
                self.VERSION,
            "source":
                self.CALENDAR_URL,
            "total_matches":
                total_matches,
            "total_rounds":
                total_rounds,
            "rounds":
                rounds,
            "team_count":
                len(teams),
            "finished":
                finished,
            "scheduled":
                scheduled,
            "expected_matches":
                expected_matches,
            "expected_rounds":
                self.MAX_ROUNDS,
            "expected_teams":
                self.EXPECTED_TEAMS,
            "status":
                "READY"
                if ready
                else "WARNING"
        }

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
            # 2. Calendar
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
            # 3. Load matches
            # ---------------------------------------------
            result[
                "matches_loaded"
            ] = self.load_matches_to_db(
                matches,
                round_number
            )
            # ---------------------------------------------
            # 4. Predictions
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
    # SELF TEST
    # =========================================================
    def diagnostics(
        self
    ) -> Dict[str, Any]:
        matches = (
            self.get_all_matches()
        )
        rounds = {}
        teams = set()
        finished = 0
        scheduled = 0
        for match in matches:
            round_number = match.get(
                "round"
            )
            rounds[
                round_number
            ] = rounds.get(
                round_number,
                0
            ) + 1
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
        # -----------------------------------------------------
        # Ожидаем:
        #
        # 30 туров
        # 8 матчей в туре
        # 16 команд
        # 240 матчей
        # -----------------------------------------------------
        total_rounds = len(
            rounds
        )
        total_matches = len(
            matches
        )
        expected_matches = (
            self.MAX_ROUNDS
            *
            self.MATCHES_PER_ROUND
        )
        valid_rounds = all(
            count == self.MATCHES_PER_ROUND
            for count in rounds.values()
        )
        ready = (
            total_matches
            == expected_matches
            and
            total_rounds
            == self.MAX_ROUNDS
            and
            len(teams)
            >= self.EXPECTED_TEAMS
            and
            valid_rounds
        )
        return {
            "parser_version":
                self.VERSION,
            "source":
                self.CALENDAR_URL,
            "total_matches":
                total_matches,
            "total_rounds":
                total_rounds,
            "rounds":
                rounds,
            "team_count":
                len(teams),
            "finished":
                finished,
            "scheduled":
                scheduled,
            "expected_matches":
                expected_matches,
            "expected_rounds":
                self.MAX_ROUNDS,
            "expected_teams":
                self.EXPECTED_TEAMS,
            "status":
                "READY"
                if ready
                else "WARNING"
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
        "v12.3"
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
    # 3. ROUND 4
    # =========================================================
    print()
    print("3. ROUND 4")
    print("-" * 70)
    round_4 = parser.get_matches_by_tour(4)
    print(
        f"Found: {len(round_4)}"
    )
    for match in round_4:
        score = (
            match.get("score")
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
        "v12.3 READY"
    )
    print("=" * 70)

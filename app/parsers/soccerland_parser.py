#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================
FAJ Platform v12.1
Soccerland Parser v12.6 — ТЕКСТОВЫЙ ПОИСК + ДИАГНОСТИКА
=====================================================
Источник:
    https://soccerland.ru/russia/premier-liga/2026-2027/calendar
Назначение:
    - загрузка календаря РПЛ 2026/27
    - извлечение матчей через текстовый поиск
    - ДИАГНОСТИКА: debug_calendar()
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
    Парсер календаря РПЛ с soccerland.ru.
    Использует текстовый поиск по странице.
    """
    VERSION = "12.6"
    CALENDAR_URL = "https://soccerland.ru/russia/premier-liga/2026-2027/calendar"
    LEAGUE = "RPL"
    SEASON_YEAR = "2026-27"
    EXPECTED_TEAMS = 16
    MATCHES_PER_ROUND = 8
    MAX_ROUNDS = 30

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self.pm = get_prediction_manager()
        self.passport_manager = get_passport_manager()
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        self.session.headers.update(self.headers)
        logger.info("SoccerlandParser v%s initialized (TEXT SEARCH)", self.VERSION)

    # =========================================================
    # ЗАГРУЗКА
    # =========================================================
    def _get_calendar_text(self) -> str:
        """Получение текста календаря без HTML-тегов"""
        response = self.session.get(self.CALENDAR_URL, timeout=20)
        response.raise_for_status()
        if not response.text:
            raise RuntimeError("soccerland.ru returned empty response")
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Удаляем скрипты и стили
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Получаем текст
        text = soup.get_text(separator=" ", strip=True)
        return text

    # =========================================================
    # НОРМАЛИЗАЦИЯ
    # =========================================================
    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\xa0", " ").replace("\u2009", " ").replace("\u202f", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # =========================================================
    # ПАРСИНГ
    # =========================================================
    def get_all_matches(self) -> List[Dict[str, Any]]:
        """
        Парсинг календаря через текстовый поиск.
        Ищет паттерны: "ДД.ММ ЧЧ:ММ | Команда | Счёт | Команда"
        """
        try:
            text = self._get_calendar_text()
            text = self._normalize_text(text)
            
            logger.info("Text length: %s", len(text))
            
            # Ищем все заголовки "Тур N"
            round_matches = list(re.finditer(r"Тур\s+(\d{1,2})", text, re.IGNORECASE))
            logger.info("Found %s round headers", len(round_matches))
            
            if not round_matches:
                logger.warning("No round headers found")
                return []
            
            all_matches = []
            
            for idx, rm in enumerate(round_matches):
                round_num = int(rm.group(1))
                if not (1 <= round_num <= 30):
                    continue
                
                # Определяем границы текста для этого тура
                start = rm.end()
                end = round_matches[idx + 1].start() if idx + 1 < len(round_matches) else len(text)
                round_text = text[start:end]
                
                # Ищем матчи в этом блоке
                # Паттерн: дата время | команда | счёт | команда
                match_pattern = re.compile(
                    r"(\d{2}\.\d{2})\s+(\d{2}:\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)(?=\s+\d{2}\.\d{2}|$)"
                )
                
                matches_in_round = 0
                for m in match_pattern.finditer(round_text):
                    date_str = m.group(1).strip()
                    time_str = m.group(2).strip()
                    home = self._normalize_text(m.group(3))
                    score_text = self._normalize_text(m.group(4))
                    away = self._normalize_text(m.group(5))
                    
                    if not home or not away:
                        continue
                    if len(home) < 2 or len(away) < 2:
                        continue
                    
                    # Парсим счёт
                    score_data = self._parse_score(score_text)
                    
                    # Дата
                    day, month = map(int, date_str.split('.'))
                    year = 2026 if month >= 7 else 2027
                    iso_date = f"{year:04d}-{month:02d}-{day:02d}"
                    
                    all_matches.append({
                        "round": round_num,
                        "date": iso_date,
                        "time": time_str,
                        "home": home,
                        "away": away,
                        "score": score_data["score"],
                        "status": score_data["status"],
                        "actual_home": score_data["actual_home"],
                        "actual_away": score_data["actual_away"],
                    })
                    matches_in_round += 1
                
                logger.info("Round %s: %s matches", round_num, matches_in_round)
            
            # Удаляем дубли
            unique = []
            seen = set()
            for m in all_matches:
                key = (m["round"], m["date"], m["time"], m["home"], m["away"])
                if key not in seen:
                    seen.add(key)
                    unique.append(m)
            
            unique.sort(key=lambda x: (x["round"], x["date"], x["time"]))
            
            logger.info("TOTAL: %s unique matches", len(unique))
            return unique
            
        except Exception as e:
            logger.exception("Parser error")
            return []

    # =========================================================
    # ПАРСИНГ СЧЁТА
    # =========================================================
    @staticmethod
    def _parse_score(score_text: str) -> Dict[str, Any]:
        if not score_text:
            return {"score": "", "actual_home": None, "actual_away": None, "status": "scheduled"}
        
        score_text = score_text.replace("−", "-").replace("–", "-").replace("—", "-")
        match = re.search(r"(\d+)\s*:\s*(\d+)", score_text)
        if match:
            return {
                "score": f"{match.group(1)}:{match.group(2)}",
                "actual_home": int(match.group(1)),
                "actual_away": int(match.group(2)),
                "status": "finished"
            }
        return {"score": "", "actual_home": None, "actual_away": None, "status": "scheduled"}

    # =========================================================
    # МАТЧИ ТУРА
    # =========================================================
    def get_matches_by_tour(self, tour_number: int) -> List[Dict[str, Any]]:
        try:
            tour_number = int(tour_number)
        except (TypeError, ValueError):
            return []
        if not (1 <= tour_number <= self.MAX_ROUNDS):
            return []
        
        all_matches = self.get_all_matches()
        tour_matches = [m for m in all_matches if m.get("round") == tour_number]
        logger.info("ROUND %s: %s matches", tour_number, len(tour_matches))
        return tour_matches

    # =========================================================
    # ДИАГНОСТИКА
    # =========================================================
    def diagnostics(self) -> Dict[str, Any]:
        matches = self.get_all_matches()
        rounds = {}
        teams = set()
        finished = 0
        scheduled = 0
        
        for m in matches:
            r = m.get("round")
            rounds[r] = rounds.get(r, 0) + 1
            teams.add(m.get("home"))
            teams.add(m.get("away"))
            if m.get("status") == "finished":
                finished += 1
            else:
                scheduled += 1
        
        ready = len(matches) >= 200 and len(rounds) >= 20 and len(teams) >= 16
        
        return {
            "parser_version": self.VERSION,
            "source": self.CALENDAR_URL,
            "total_matches": len(matches),
            "total_rounds": len(rounds),
            "rounds": rounds,
            "team_count": len(teams),
            "finished": finished,
            "scheduled": scheduled,
            "expected_matches": 240,
            "expected_rounds": 30,
            "expected_teams": 16,
            "status": "READY" if ready else "WARNING"
        }

    # =========================================================
    # ДИАГНОСТИЧЕСКАЯ ЗАГРУЗКА (НОВЫЙ МЕТОД)
    # =========================================================
    def debug_calendar(self) -> Dict[str, Any]:
        """Диагностическая загрузка календаря"""
        response = self.session.get(
            self.CALENDAR_URL,
            timeout=20
        )
        
        logger.info("=" * 70)
        logger.info("SOCCERLAND DEBUG")
        logger.info("=" * 70)
        logger.info("HTTP STATUS: %s", response.status_code)
        logger.info("FINAL URL: %s", response.url)
        logger.info("CONTENT TYPE: %s", response.headers.get("content-type"))
        logger.info("HTML LENGTH: %s", len(response.text))
        
        # Первые 5000 символов HTML
        logger.info("========== HTML START ==========")
        logger.info(response.text[:5000])
        logger.info("========== HTML END ==========")
        
        soup = BeautifulSoup(response.text, "html.parser")
        logger.info("TITLE: %s", soup.title.get_text(strip=True) if soup.title else "NO TITLE")
        
        # Ссылки на страницы матчей
        match_links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = self._normalize_text(a.get_text(" ", strip=True))
            if "/match/" in href:
                match_links.append((text, href))
        
        logger.info("MATCH LINKS FOUND: %s", len(match_links))
        for item in match_links[:20]:
            logger.info("MATCH LINK: %s", item)
        
        # Текст страницы
        page_text = soup.get_text(" ", strip=True)
        page_text = self._normalize_text(page_text)
        
        logger.info("========== PAGE TEXT START ==========")
        logger.info(page_text[:10000])
        logger.info("========== PAGE TEXT END ==========")
        
        # Ищем JSON в HTML
        json_matches = re.findall(r'\{[^{}]*"matches"[^{}]*\}', response.text)
        logger.info("JSON MATCHES FOUND: %s", len(json_matches))
        if json_matches:
            logger.info("FIRST JSON: %s", json_matches[0][:500])
        
        return {
            "status_code": response.status_code,
            "url": str(response.url),
            "content_type": response.headers.get("content-type"),
            "html_length": len(response.text),
            "match_links": len(match_links),
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "text_length": len(page_text),
            "json_found": len(json_matches) > 0,
        }

    # =========================================================
    # РАБОТА С БД
    # =========================================================
    def _get_or_create_team(self, name: str) -> int:
        name = self._normalize_text(name)
        if not name:
            raise ValueError("Team name cannot be empty")
        
        team_id = self.db.get_team_id(name, self.LEAGUE)
        if team_id:
            return team_id
        
        team_id = self.db.add_team(name=name, league=self.LEAGUE, country="Russia", team_type="club")
        if not team_id:
            raise RuntimeError(f"Failed to create team: {name}")
        
        season_id = self._ensure_season()
        default_passport = {
            "attack": 50, "defense": 50, "control": 50,
            "goalkeeper": 50, "form": 50, "fitness": 50,
            "morale": 50, "home_advantage": 1.12, "source": "parser"
        }
        try:
            self.passport_manager.create_passport(
                team_id=team_id, season_id=season_id,
                data=default_passport, source="parser_auto"
            )
        except Exception as e:
            logger.warning("Could not create default passport for %s: %s", name, e)
        
        logger.info("Created team: %s (ID: %s)", name, team_id)
        return team_id

    def _ensure_season(self) -> int:
        season_id = self.db.get_season_id(self.LEAGUE, self.SEASON_YEAR)
        if season_id:
            return season_id
        season_id = self.db.create_season(
            name=f"{self.LEAGUE} {self.SEASON_YEAR}",
            league=self.LEAGUE, year=self.SEASON_YEAR, competition_type="league"
        )
        if not season_id:
            raise RuntimeError(f"Failed to create season {self.LEAGUE} {self.SEASON_YEAR}")
        return season_id

    def _ensure_round(self, season_id: int, round_number: int) -> int:
        round_number = int(round_number)
        existing = self._get_round_id(round_number)
        if existing:
            return existing
        round_id = self.db.create_round(season_id, round_number)
        if not round_id:
            existing = self._get_round_id(round_number)
            if existing:
                return existing
            raise RuntimeError(f"Round {round_number} could not be created/found")
        return round_id

    def _get_round_id(self, round_number: int) -> Optional[int]:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.id FROM rounds r
                JOIN seasons s ON r.season_id = s.id
                WHERE r.round_number = ? AND s.league = ? AND s.year = ?
                LIMIT 1
            """, (round_number, self.LEAGUE, self.SEASON_YEAR))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _get_team_name(self, team_id: int) -> Optional[str]:
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    # =========================================================
    # ЗАГРУЗКА В БД
    # =========================================================
    def load_matches_to_db(self, matches: List[Dict], round_number: int) -> int:
        if not matches:
            return 0
        
        season_id = self._ensure_season()
        round_id = self._ensure_round(season_id, round_number)
        added_count = 0
        
        for match in matches:
            try:
                home_team = self._normalize_text(match.get("home", ""))
                away_team = self._normalize_text(match.get("away", ""))
                if not home_team or not away_team:
                    continue
                
                home_id = self._get_or_create_team(home_team)
                away_id = self._get_or_create_team(away_team)
                
                actual_home = match.get("actual_home")
                actual_away = match.get("actual_away")
                status = match.get("status", "scheduled")
                
                raw_uuid = f"{self.LEAGUE}|{self.SEASON_YEAR}|{round_number}|{match.get('date', '')}|{match.get('time', '')}|{home_team}|{away_team}"
                match_uuid = hashlib.md5(raw_uuid.encode()).hexdigest()[:16]
                
                existing = self.db.get_match_by_uuid(match_uuid)
                if existing:
                    continue
                
                match_data = {
                    "round_id": round_id,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "match_uuid": match_uuid,
                    "date": match.get("date", ""),
                    "competition": self.LEAGUE,
                    "status": status,
                    "actual_home": actual_home,
                    "actual_away": actual_away,
                    "parser_source": "soccerland",
                    "parser_version": self.VERSION
                }
                self.db.upsert_match(match_data)
                added_count += 1
                
            except Exception as e:
                logger.exception("Error loading match %s vs %s", match.get("home"), match.get("away"))
        
        return added_count

    # =========================================================
    # АНАЛИЗ
    # =========================================================
    def analyze_and_update(self, round_number: int) -> Dict[str, Any]:
        result = {
            "round": round_number,
            "matches_analyzed": 0,
            "teams_updated": [],
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }
        
        round_id = self._get_round_id(round_number)
        if not round_id:
            result["errors"].append(f"Round {round_number} not found")
            return result
        
        matches = self.db.get_matches(round_id)
        if not matches:
            result["errors"].append(f"No matches found for round {round_number}")
            return result
        
        season_id = self._ensure_season()
        for match in matches:
            match_dict = dict(match)
            if match_dict.get("status") != "finished":
                continue
            
            home_id = match_dict.get("home_team_id")
            away_id = match_dict.get("away_team_id")
            actual_home = match_dict.get("actual_home")
            actual_away = match_dict.get("actual_away")
            
            if actual_home is None or actual_away is None:
                continue
            
            try:
                self._update_team_after_match(
                    team_id=home_id, goals_for=actual_home, goals_against=actual_away,
                    is_home=True, season_id=season_id
                )
                result["teams_updated"].append(home_id)
            except Exception as e:
                result["errors"].append(f"Home team {home_id}: {e}")
            
            try:
                self._update_team_after_match(
                    team_id=away_id, goals_for=actual_away, goals_against=actual_home,
                    is_home=False, season_id=season_id
                )
                result["teams_updated"].append(away_id)
            except Exception as e:
                result["errors"].append(f"Away team {away_id}: {e}")
            
            result["matches_analyzed"] += 1
        
        return result

    def _update_team_after_match(self, team_id: int, goals_for: int, goals_against: int, is_home: bool, season_id: int):
        match_data = {
            "goals_for": goals_for,
            "goals_against": goals_against,
            "is_win": goals_for > goals_against,
            "is_draw": goals_for == goals_against,
            "xg_for": float(goals_for),
            "xg_against": float(goals_against),
            "home": is_home
        }
        self.passport_manager.update_after_match(
            team_id=team_id, season_id=season_id, match_data=match_data,
            opponent_rating=70.0, matches_count=1
        )

    # =========================================================
    # ПРОГНОЗ
    # =========================================================
    def predict_tour(self, round_number: int) -> List[Dict[str, Any]]:
        predictions = []
        round_id = self._get_round_id(round_number)
        if not round_id:
            return predictions
        
        matches = self.db.get_matches(round_id)
        for match in matches:
            match_dict = dict(match)
            if match_dict.get("status") != "scheduled":
                continue
            
            home_team = self._get_team_name(match_dict.get("home_team_id"))
            away_team = self._get_team_name(match_dict.get("away_team_id"))
            if not home_team or not away_team:
                continue
            
            try:
                prediction = self.pm.predict(
                    home_team=home_team, away_team=away_team,
                    league=self.LEAGUE, season_id=match_dict.get("round_id")
                )
                if prediction.get("status") != "error":
                    predictions.append({
                        "match_id": match_dict.get("id"),
                        "home_team": home_team,
                        "away_team": away_team,
                        "prediction": prediction
                    })
            except Exception as e:
                logger.exception("Prediction error %s vs %s", home_team, away_team)
        
        return predictions

    # =========================================================
    # ПОЛНЫЙ ЦИКЛ
    # =========================================================
    def update_all(self, round_number: int) -> Dict[str, Any]:
        result = {
            "timestamp": datetime.now().isoformat(),
            "round": round_number,
            "standings_saved": 0,
            "matches_loaded": 0,
            "predictions": [],
            "errors": []
        }
        
        try:
            self._ensure_season()
            matches = self.get_matches_by_tour(round_number)
            if not matches:
                result["errors"].append(f"No matches found for round {round_number}")
                return result
            
            result["matches_loaded"] = self.load_matches_to_db(matches, round_number)
            
            if result["matches_loaded"] > 0:
                result["predictions"] = self.predict_tour(round_number)
            
            return result
        except Exception as e:
            logger.exception("FAJ full update error")
            result["errors"].append(str(e))
            return result


# =============================================================
# SELF TEST
# =============================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    parser = SoccerlandParser()
    print("\n" + "=" * 70)
    print("SOCCERLAND DEBUG")
    print("=" * 70)
    result = parser.debug_calendar()
    print("\n" + "=" * 70)
    print("RESULT:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print("=" * 70)

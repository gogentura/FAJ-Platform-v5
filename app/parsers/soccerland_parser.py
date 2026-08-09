#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.1 - Парсер soccerland.ru + championat.com
Интеграция с БД и Prediction Manager

РОЛЬ:
    1. Парсинг расписания с championat.com
    2. Парсинг результатов с soccerland.ru
    3. Загрузка данных в БД (без дублей)
    4. Обновление паспортов команд после матчей
    5. Автоматический прогноз на предстоящие матчи

ИСПОЛЬЗОВАНИЕ:
    from app.parsers.soccerland_parser import SoccerlandParser
    
    parser = SoccerlandParser()
    
    # Загрузить расписание тура
    matches = parser.get_upcoming_matches()
    parser.load_matches_to_db(matches, round_number=4)
    
    # Проанализировать сыгранный тур
    parser.analyze_and_update(round_number=3)
    
    # Сделать прогноз на тур
    predictions = parser.predict_tour(round_number=4)
"""

import requests
from bs4 import BeautifulSoup
import re
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.database import FAJDatabase
from app.core.prediction_manager import get_prediction_manager
from app.passports.passport_manager import get_passport_manager

logger = logging.getLogger(__name__)


class SoccerlandParser:
    """
    Парсер soccerland.ru + championat.com
    С интеграцией в FAJ Platform
    """

    VERSION = "12.1"

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self.pm = get_prediction_manager()
        self.passport_manager = get_passport_manager()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.base_url = "https://soccerland.ru/russia/premier-liga/2026-2027"
        self.calendar_url = "https://www.championat.com/football/_russiapl/tournament/7096/calendar/"

        # Кэш для избежания дублей
        self._loaded_matches = set()

        # Параметры сезона
        self.league = "RPL"
        self.season_year = "2026-27"

        logger.info("✅ SoccerlandParser v%s initialized with DB integration", self.VERSION)

    # =========================================================
    # 1. ПОЛУЧИТЬ ИЛИ СОЗДАТЬ КОМАНДУ В БД
    # =========================================================

    def _get_or_create_team(self, name: str) -> int:
        """
        Получить ID команды или создать новую
        """
        # Убираем лишние пробелы и нормализуем название
        name = name.strip()
        if not name:
            raise ValueError("Team name cannot be empty")

        # Проверяем в БД
        team_id = self.db.get_team_id(name, self.league)
        if team_id:
            return team_id

        # Создаём новую команду
        team_id = self.db.add_team(
            name=name,
            league=self.league,
            country="Russia",
            team_type="club"
        )

        # Получаем season_id
        season_id = self.db.get_season_id(self.league, self.season_year)
        if not season_id:
            season_id = self.db.create_season(
                name=f"{self.league} {self.season_year}",
                league=self.league,
                year=self.season_year,
                competition_type="league"
            )

        # Создаём дефолтный паспорт для новой команды
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

        self.passport_manager.create_passport(
            team_id=team_id,
            season_id=season_id,
            data=default_passport,
            source="parser_auto"
        )

        logger.info("✅ Created new team: %s (ID: %s)", name, team_id)
        return team_id

    # =========================================================
    # 2. ЗАГРУЗКА МАТЧЕЙ В БД (БЕЗ ДУБЛЕЙ)
    # =========================================================

    def load_matches_to_db(self, matches: List[Dict], round_number: int) -> int:
        """
        Загрузка матчей в БД с защитой от дублей

        Args:
            matches: список матчей с полями home, away, date, score
            round_number: номер тура

        Returns:
            количество добавленных матчей
        """
        added_count = 0

        # Получаем season_id
        season_id = self.db.get_season_id(self.league, self.season_year)
        if not season_id:
            season_id = self.db.create_season(
                name=f"{self.league} {self.season_year}",
                league=self.league,
                year=self.season_year
            )

        # Получаем или создаём round_id
        round_id = self.db.create_round(season_id, round_number)

        for match in matches:
            home_team = match.get("home", "").strip()
            away_team = match.get("away", "").strip()
            date = match.get("date", "")
            score = match.get("score", "")
            status = match.get("status", "scheduled")

            if not home_team or not away_team:
                logger.warning("Skipping match with empty team names")
                continue

            try:
                # Получаем ID команд
                home_id = self._get_or_create_team(home_team)
                away_id = self._get_or_create_team(away_team)

                # Генерируем UUID матча
                match_uuid = hashlib.md5(
                    f"{home_team}_{away_team}_{round_number}_{date}_{self.season_year}".encode()
                ).hexdigest()[:12]

                # Проверяем, есть ли уже такой матч
                existing = self.db.get_match_by_uuid(match_uuid)
                if existing:
                    logger.debug("⏭️ Match already exists: %s vs %s", home_team, away_team)
                    continue

                # Парсим счёт
                actual_home = None
                actual_away = None
                if score and ":" in score:
                    try:
                        parts = score.split(":")
                        actual_home = int(parts[0].strip())
                        actual_away = int(parts[1].strip())
                        status = "finished"
                    except (ValueError, IndexError):
                        pass

                # Сохраняем матч
                match_data = {
                    "round_id": round_id,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "match_uuid": match_uuid,
                    "date": date,
                    "competition": self.league,
                    "status": status,
                    "actual_home": actual_home,
                    "actual_away": actual_away,
                    "parser_source": "soccerland",
                    "parser_version": self.VERSION
                }

                self.db.upsert_match(match_data)
                added_count += 1
                logger.info("✅ Added match: %s vs %s (round %s)", home_team, away_team, round_number)

            except Exception as e:
                logger.error("❌ Error adding match %s vs %s: %s", home_team, away_team, e)

        logger.info("📊 Loaded %s matches for round %s", added_count, round_number)
        return added_count

    # =========================================================
    # 3. АНАЛИЗ СЫГРАННЫХ МАТЧЕЙ И ОБНОВЛЕНИЕ ПАСПОРТОВ
    # =========================================================

    def analyze_and_update(self, round_number: int) -> Dict[str, Any]:
        """
        Анализ сыгранных матчей тура и обновление паспортов

        Args:
            round_number: номер тура

        Returns:
            Dict с результатами анализа
        """
        results = {
            "round": round_number,
            "matches_analyzed": 0,
            "teams_updated": [],
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }

        # Получаем матчи тура из БД
        round_id = self._get_round_id(round_number)
        if not round_id:
            results["errors"].append(f"Round {round_number} not found")
            return results

        matches = self.db.get_matches(round_id)

        if not matches:
            results["errors"].append(f"No matches found for round {round_number}")
            return results

        for match in matches:
            match_dict = dict(match)

            # Только завершённые матчи
            if match_dict.get("status") != "finished":
                continue

            home_team_id = match_dict.get("home_team_id")
            away_team_id = match_dict.get("away_team_id")
            actual_home = match_dict.get("actual_home")
            actual_away = match_dict.get("actual_away")

            if actual_home is None or actual_away is None:
                continue

            # Обновляем паспорт хозяев
            try:
                self._update_team_after_match(
                    team_id=home_team_id,
                    goals_for=actual_home,
                    goals_against=actual_away,
                    is_home=True
                )
                results["teams_updated"].append(home_team_id)
            except Exception as e:
                results["errors"].append(f"Home team {home_team_id}: {e}")

            # Обновляем паспорт гостей
            try:
                self._update_team_after_match(
                    team_id=away_team_id,
                    goals_for=actual_away,
                    goals_against=actual_home,
                    is_home=False
                )
                results["teams_updated"].append(away_team_id)
            except Exception as e:
                results["errors"].append(f"Away team {away_team_id}: {e}")

            results["matches_analyzed"] += 1

        logger.info("📊 Analyzed %s matches in round %s", results["matches_analyzed"], round_number)
        return results

    def _update_team_after_match(
        self,
        team_id: int,
        goals_for: int,
        goals_against: int,
        is_home: bool
    ):
        """
        Обновление паспорта команды после матча
        """
        # Получаем season_id
        season_id = self.db.get_season_id(self.league, self.season_year)
        if not season_id:
            raise ValueError(f"Season {self.season_year} not found")

        # Подготавливаем данные для обновления
        match_data = {
            "goals_for": goals_for,
            "goals_against": goals_against,
            "is_win": goals_for > goals_against,
            "is_draw": goals_for == goals_against,
            "xg_for": float(goals_for),  # Временное решение, позже будет xG
            "xg_against": float(goals_against),
            "home": is_home
        }

        # Обновляем паспорт
        self.passport_manager.update_after_match(
            team_id=team_id,
            season_id=season_id,
            match_data=match_data,
            opponent_rating=70.0,  # Временное значение
            matches_count=1
        )

        logger.debug("Updated passport for team %s after match", team_id)

    # =========================================================
    # 4. ПРОГНОЗ НА ТУР
    # =========================================================

    def predict_tour(self, round_number: int) -> List[Dict[str, Any]]:
        """
        Прогноз всех матчей тура

        Args:
            round_number: номер тура

        Returns:
            List[Dict] с прогнозами
        """
        predictions = []

        # Получаем матчи тура
        round_id = self._get_round_id(round_number)
        if not round_id:
            logger.error("Round %s not found", round_number)
            return predictions

        matches = self.db.get_matches(round_id)

        if not matches:
            logger.warning("No matches found for round %s", round_number)
            return predictions

        for match in matches:
            match_dict = dict(match)

            # Только предстоящие матчи
            if match_dict.get("status") != "scheduled":
                continue

            # Получаем названия команд
            home_team = self._get_team_name(match_dict.get("home_team_id"))
            away_team = self._get_team_name(match_dict.get("away_team_id"))

            if not home_team or not away_team:
                continue

            # Делаем прогноз
            try:
                prediction = self.pm.predict(
                    home_team=home_team,
                    away_team=away_team,
                    league=self.league,
                    season_id=match_dict.get("round_id")
                )

                if prediction.get("status") != "error":
                    predictions.append({
                        "match_id": match_dict.get("id"),
                        "home_team": home_team,
                        "away_team": away_team,
                        "prediction": prediction
                    })
                    logger.info("✅ Prediction for %s vs %s", home_team, away_team)
                else:
                    logger.warning("⚠️ Prediction error for %s vs %s: %s",
                                 home_team, away_team, prediction.get("message"))

            except Exception as e:
                logger.error("❌ Prediction error for %s vs %s: %s", home_team, away_team, e)

        logger.info("📊 Made %s predictions for round %s", len(predictions), round_number)
        return predictions

    # =========================================================
    # 5. ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================

    def _get_round_id(self, round_number: int) -> Optional[int]:
        """Получить ID тура по номеру"""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.id
                FROM rounds r
                JOIN seasons s ON r.season_id = s.id
                WHERE r.round_number = ?
                AND s.league = ?
                AND s.year = ?
            """, (round_number, self.league, self.season_year))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _get_team_name(self, team_id: int) -> Optional[str]:
        """Получить название команды по ID"""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _extract_teams_from_text(self, text: str) -> tuple:
        """Извлечение названий команд из текста"""
        # Ищем названия команд (слова с заглавной буквы)
        teams = re.findall(r'[А-Я][а-я]+(?:\s[А-Я][а-я]+)?', text)
        if len(teams) >= 2:
            return teams[0], teams[1]
        return None, None

    # =========================================================
    # 6. ПАРСИНГ КАЛЕНДАРЯ (championat.com)
    # =========================================================

    def get_upcoming_matches(self) -> List[Dict[str, Any]]:
        """
        Парсинг календаря с championat.com

        Returns:
            List[Dict] с полями: home, away, date, tour
        """
        try:
            response = requests.get(self.calendar_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            upcoming = []
            current_tour = None

            # Ищем таблицу с матчами
            table = None
            for t in soup.find_all('table'):
                if 'Тур' in t.text or 'Дата' in t.text:
                    table = t
                    break

            if not table:
                logger.warning("Table not found on championat.com")
                return []

            rows = table.find_all('tr')

            for row in rows:
                cols = row.find_all('td')

                if not cols or len(cols) < 3:
                    continue

                # Проверяем, не является ли строка заголовком тура
                if len(cols) == 1:
                    tour_text = cols[0].text.strip()
                    if 'Тур' in tour_text:
                        current_tour = tour_text
                    continue

                try:
                    # Дата/время
                    date_time = cols[1].text.strip() if len(cols) > 1 else ""

                    # Счёт
                    score_text = cols[2].text.strip() if len(cols) > 2 else ""

                    # Извлекаем команды из текста строки
                    match_text = row.text.strip()
                    home_team, away_team = self._extract_teams_from_text(match_text)

                    if home_team and away_team:
                        # Определяем статус
                        is_finished = ":" in score_text and score_text != "– : –"
                        status = "finished" if is_finished else "scheduled"

                        upcoming.append({
                            "home": home_team,
                            "away": away_team,
                            "date": date_time,
                            "tour": current_tour,
                            "score": score_text if is_finished else "",
                            "status": status
                        })

                except Exception as e:
                    logger.debug("Error parsing row: %s", e)
                    continue

            logger.info("📊 Parsed %s upcoming matches from championat.com", len(upcoming))
            return upcoming

        except Exception as e:
            logger.error("❌ Error parsing championat.com: %s", e)
            return []

    # =========================================================
    # 7. ПАРСИНГ РЕЗУЛЬТАТОВ (soccerland.ru)
    # =========================================================

    def get_matches_with_goals(self) -> List[Dict[str, Any]]:
        """
        Парсинг матчей с голами с soccerland.ru

        Returns:
            List[Dict] с полями: home, away, score, goals, status
        """
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            matches = []
            match_blocks = soup.find_all('div', class_=re.compile(r'match|game|fixture|result'))

            for block in match_blocks:
                try:
                    home_elem = block.find('span', class_=re.compile(r'home|team1'))
                    away_elem = block.find('span', class_=re.compile(r'away|team2'))

                    if not home_elem or not away_elem:
                        continue

                    home = home_elem.text.strip()
                    away = away_elem.text.strip()

                    # Счёт
                    score_elem = block.find('span', class_=re.compile(r'score|result'))
                    score = score_elem.text.strip() if score_elem else "– : –"

                    # Голы
                    goals = []
                    goal_items = block.find_all('div', class_=re.compile(r'goal|event'))
                    for goal in goal_items:
                        try:
                            player_elem = goal.find('span', class_=re.compile(r'player'))
                            minute_elem = goal.find('span', class_=re.compile(r'minute|time'))
                            team_elem = goal.find('span', class_=re.compile(r'team'))

                            if player_elem:
                                goals.append({
                                    "player": player_elem.text.strip() if player_elem else "",
                                    "minute": minute_elem.text.strip() if minute_elem else "",
                                    "team": team_elem.text.strip() if team_elem else ""
                                })
                        except:
                            continue

                    is_finished = ":" in score and score != "– : –"
                    status = "finished" if is_finished else "scheduled"

                    matches.append({
                        "home": home,
                        "away": away,
                        "score": score if is_finished else "",
                        "goals": goals,
                        "status": status
                    })

                except Exception as e:
                    logger.debug("Error parsing match block: %s", e)
                    continue

            logger.info("📊 Parsed %s matches from soccerland.ru", len(matches))
            return matches

        except Exception as e:
            logger.error("❌ Error parsing soccerland.ru: %s", e)
            return []

    # =========================================================
    # 8. ПОЛНОЕ ОБНОВЛЕНИЕ
    # =========================================================

    def update_all(self, round_number: int) -> Dict[str, Any]:
        """
        Полное обновление: парсинг + загрузка в БД + прогноз

        Args:
            round_number: номер тура для загрузки

        Returns:
            Dict с результатами всех операций
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "round": round_number,
            "matches_loaded": 0,
            "predictions": [],
            "errors": []
        }

        logger.info("🚀 Starting full update for round %s", round_number)

        # 1. Получаем данные с championat.com
        try:
            upcoming = self.get_upcoming_matches()
            if isinstance(upcoming, list) and upcoming:
                loaded = self.load_matches_to_db(upcoming, round_number)
                results["matches_loaded"] = loaded
                logger.info("✅ Loaded %s matches to DB", loaded)
            else:
                results["errors"].append("No matches found on championat.com")
        except Exception as e:
            results["errors"].append(f"Error loading matches: {e}")

        # 2. Делаем прогноз на тур (если есть матчи)
        if results["matches_loaded"] > 0:
            try:
                predictions = self.predict_tour(round_number)
                results["predictions"] = predictions
                logger.info("✅ Made %s predictions", len(predictions))
            except Exception as e:
                results["errors"].append(f"Error making predictions: {e}")

        return results

    # =========================================================
    # 9. ФАСТ-ТРЕК: ПРОГНОЗ ТУРА ЗА 1 ШАГ
    # =========================================================

    def fast_forecast(self, round_number: int) -> Dict[str, Any]:
        """
        Быстрый прогноз тура:
        1. Парсинг календаря
        2. Загрузка в БД
        3. Прогноз всех матчей

        Args:
            round_number: номер тура

        Returns:
            Dict с прогнозами
        """
        return self.update_all(round_number)


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("⚽ SOCCERLAND PARSER v12.1 — SELF TEST")
    print("=" * 70)

    parser = SoccerlandParser()

    # Тест: парсинг календаря
    print("\n📋 Testing: get_upcoming_matches()")
    upcoming = parser.get_upcoming_matches()
    print(f"  Found {len(upcoming)} matches")

    if upcoming:
        for match in upcoming[:3]:
            print(f"  {match.get('home')} vs {match.get('away')} | {match.get('date')}")

    # Тест: загрузка в БД
    print("\n📋 Testing: load_matches_to_db()")
    if upcoming:
        loaded = parser.load_matches_to_db(upcoming[:3], round_number=99)
        print(f"  Loaded {loaded} matches to DB")

    print("\n" + "=" * 70)
    print("✅ SoccerlandParser v12.1 ready")
    print("=" * 70)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.1 - Парсер soccerland.ru
Сбор данных: календарь матчей + турнирная таблица
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
    Парсер soccerland.ru
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
        self.calendar_url = "https://soccerland.ru/russia/premier-liga/2026-2027/calendar"

        self.league = "RPL"
        self.season_year = "2026-27"

        logger.info("✅ SoccerlandParser v%s initialized", self.VERSION)

    # =========================================================
    # 1. ПОЛУЧИТЬ ИЛИ СОЗДАТЬ КОМАНДУ В БД
    # =========================================================

    def _get_or_create_team(self, name: str) -> int:
        """Получить ID команды или создать новую"""
        name = name.strip()
        if not name:
            raise ValueError("Team name cannot be empty")

        # Убираем сокращения типа "М" для поиска
        search_name = name
        if name.endswith(" М"):
            search_name = name[:-2]

        team_id = self.db.get_team_id(search_name, self.league)
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

        # Создаём дефолтный паспорт
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
    # 2. ПАРСИНГ ТУРНИРНОЙ ТАБЛИЦЫ
    # =========================================================

    def get_standings(self) -> List[Dict[str, Any]]:
        """
        Парсинг турнирной таблицы с soccerland.ru

        Returns:
            List[Dict] с полями:
                place, team, games, wins, draws, losses,
                goals_for, goals_against, goal_diff, points, form
        """
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            standings = []

            # Ищем таблицу
            table = None
            for t in soup.find_all('table'):
                text = t.text.lower()
                if 'команда' in text or 'место' in text or 'игры' in text:
                    table = t
                    break

            if not table:
                logger.warning("Table not found on soccerland.ru")
                return []

            rows = table.find_all('tr')

            for row in rows[1:]:  # Пропускаем заголовок
                cols = row.find_all('td')
                if len(cols) >= 8:
                    try:
                        place_text = cols[0].text.strip()
                        place = int(place_text) if place_text.isdigit() else 0

                        team = cols[1].text.strip()

                        games = int(cols[2].text.strip()) if cols[2].text.strip().isdigit() else 0
                        wins = int(cols[3].text.strip()) if cols[3].text.strip().isdigit() else 0
                        draws = int(cols[4].text.strip()) if cols[4].text.strip().isdigit() else 0
                        losses = int(cols[5].text.strip()) if cols[5].text.strip().isdigit() else 0

                        # Голы (например "15:8")
                        goals_text = cols[6].text.strip()
                        goals_for = 0
                        goals_against = 0
                        if ':' in goals_text:
                            parts = goals_text.split(':')
                            goals_for = int(parts[0].strip()) if parts[0].strip().isdigit() else 0
                            goals_against = int(parts[1].strip()) if parts[1].strip().isdigit() else 0

                        points = int(cols[7].text.strip()) if cols[7].text.strip().isdigit() else 0

                        # Форма (последние 5 матчей) — может быть в 8-й колонке
                        form = cols[8].text.strip() if len(cols) > 8 else ""

                        standings.append({
                            "place": place,
                            "team": team,
                            "games": games,
                            "wins": wins,
                            "draws": draws,
                            "losses": losses,
                            "goals_for": goals_for,
                            "goals_against": goals_against,
                            "goal_diff": goals_for - goals_against,
                            "points": points,
                            "form": form
                        })

                    except Exception as e:
                        logger.debug(f"Error parsing row: {e}")
                        continue

            logger.info("📊 Parsed %s teams from standings", len(standings))
            return standings

        except Exception as e:
            logger.error(f"❌ Error parsing standings: {e}")
            return []

    # =========================================================
    # 3. СОХРАНЕНИЕ ТАБЛИЦЫ В БД
    # =========================================================

    def save_standings_to_db(self, standings: List[Dict], round_number: int) -> int:
        """
        Сохранение турнирной таблицы в БД

        Args:
            standings: список с данными таблицы
            round_number: номер тура

        Returns:
            количество сохранённых записей
        """
        saved_count = 0

        season_id = self.db.get_season_id(self.league, self.season_year)
        if not season_id:
            season_id = self.db.create_season(
                name=f"{self.league} {self.season_year}",
                league=self.league,
                year=self.season_year
            )

        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:
            # Создаём таблицу standings, если её нет
            cursor.execute("""
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
                    FOREIGN KEY(team_id) REFERENCES teams(id),
                    FOREIGN KEY(season_id) REFERENCES seasons(id),
                    UNIQUE(team_id, season_id, round)
                )
            """)

            for item in standings:
                team_name = item.get('team', '')
                if not team_name:
                    continue

                team_id = self._get_or_create_team(team_name)

                cursor.execute("""
                    INSERT OR REPLACE INTO standings (
                        team_id, season_id, round,
                        place, games, wins, draws, losses,
                        goals_for, goals_against, goal_diff, points, form,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    team_id,
                    season_id,
                    round_number,
                    item.get('place', 0),
                    item.get('games', 0),
                    item.get('wins', 0),
                    item.get('draws', 0),
                    item.get('losses', 0),
                    item.get('goals_for', 0),
                    item.get('goals_against', 0),
                    item.get('goal_diff', 0),
                    item.get('points', 0),
                    item.get('form', ''),
                    datetime.now().isoformat()
                ))

                saved_count += 1

            conn.commit()
            logger.info("✅ Saved %s standings records", saved_count)

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error saving standings: {e}")
        finally:
            conn.close()

        return saved_count

    # =========================================================
    # 4. ПАРСИНГ МАТЧЕЙ С КАЛЕНДАРЯ
    # =========================================================

    def get_all_matches(self) -> List[Dict[str, Any]]:
        """
        Парсинг всех матчей с календаря soccerland.ru

        Returns:
            List[Dict] с полями: home, away, score, status
        """
        try:
            response = requests.get(self.calendar_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            matches = []

            # Находим все строки с матчами
            all_text = soup.get_text()
            lines = all_text.split('\n')

            for line in lines:
                line = line.strip()
                # Ищем строки с матчами: "Команда А | счёт | Команда Б"
                if ' | ' in line and (' - ' not in line and '  ' not in line):
                    if len(line) < 10:
                        continue

                    parts = line.split(' | ')
                    if len(parts) >= 3:
                        home_team = parts[0].strip()
                        score = parts[1].strip()
                        away_team = parts[2].strip()

                        if not home_team or not away_team:
                            continue

                        # Пропускаем строки с цифрами вместо команд
                        if re.match(r'^\d+$', home_team) or re.match(r'^\d+$', away_team):
                            continue

                        # Определяем статус
                        is_finished = ':' in score and '–' not in score
                        status = "finished" if is_finished else "scheduled"

                        matches.append({
                            "home": home_team,
                            "away": away_team,
                            "score": score if is_finished else "",
                            "status": status
                        })

            logger.info("📊 Parsed %s matches from soccerland.ru", len(matches))
            return matches

        except Exception as e:
            logger.error("❌ Error parsing soccerland.ru: %s", e)
            return []

    def get_matches_by_tour(self, tour_number: int) -> List[Dict[str, Any]]:
        """
        Получение матчей конкретного тура

        Args:
            tour_number: номер тура

        Returns:
            List[Dict] с матчами тура
        """
        all_matches = self.get_all_matches()

        # В РПЛ 8 матчей в туре (16 команд)
        matches_per_tour = 8
        start_idx = (tour_number - 1) * matches_per_tour
        end_idx = start_idx + matches_per_tour

        tour_matches = all_matches[start_idx:end_idx]

        logger.info("📊 Found %s matches for tour %s", len(tour_matches), tour_number)
        return tour_matches

    # =========================================================
    # 5. ЗАГРУЗКА МАТЧЕЙ В БД
    # =========================================================

    def load_matches_to_db(self, matches: List[Dict], round_number: int) -> int:
        """Загрузка матчей в БД с защитой от дублей"""
        added_count = 0

        season_id = self.db.get_season_id(self.league, self.season_year)
        if not season_id:
            season_id = self.db.create_season(
                name=f"{self.league} {self.season_year}",
                league=self.league,
                year=self.season_year
            )

        round_id = self.db.create_round(season_id, round_number)

        for match in matches:
            home_team = match.get("home", "").strip()
            away_team = match.get("away", "").strip()
            score = match.get("score", "")
            status = match.get("status", "scheduled")

            if not home_team or not away_team:
                continue

            try:
                home_id = self._get_or_create_team(home_team)
                away_id = self._get_or_create_team(away_team)

                match_uuid = hashlib.md5(
                    f"{home_team}_{away_team}_{round_number}_{self.season_year}".encode()
                ).hexdigest()[:12]

                existing = self.db.get_match_by_uuid(match_uuid)
                if existing:
                    logger.debug("⏭️ Match already exists: %s vs %s", home_team, away_team)
                    continue

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

                match_data = {
                    "round_id": round_id,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "match_uuid": match_uuid,
                    "date": "",
                    "competition": self.league,
                    "status": status,
                    "actual_home": actual_home,
                    "actual_away": actual_away,
                    "parser_source": "soccerland",
                    "parser_version": self.VERSION
                }

                self.db.upsert_match(match_data)
                added_count += 1
                logger.info("✅ Added match: %s vs %s", home_team, away_team)

            except Exception as e:
                logger.error("❌ Error adding match %s vs %s: %s", home_team, away_team, e)

        return added_count

    # =========================================================
    # 6. АНАЛИЗ И ОБНОВЛЕНИЕ ПАСПОРТОВ
    # =========================================================

    def analyze_and_update(self, round_number: int) -> Dict[str, Any]:
        """Анализ сыгранных матчей тура и обновление паспортов"""
        results = {
            "round": round_number,
            "matches_analyzed": 0,
            "teams_updated": [],
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }

        round_id = self._get_round_id(round_number)
        if not round_id:
            results["errors"].append(f"Round {round_number} not found")
            return results

        matches = self.db.get_matches(round_id)

        for match in matches:
            match_dict = dict(match)

            if match_dict.get("status") != "finished":
                continue

            home_team_id = match_dict.get("home_team_id")
            away_team_id = match_dict.get("away_team_id")
            actual_home = match_dict.get("actual_home")
            actual_away = match_dict.get("actual_away")

            if actual_home is None or actual_away is None:
                continue

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

        return results

    def _update_team_after_match(self, team_id: int, goals_for: int, goals_against: int, is_home: bool):
        """Обновление паспорта команды после матча"""
        season_id = self.db.get_season_id(self.league, self.season_year)
        if not season_id:
            raise ValueError(f"Season {self.season_year} not found")

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
            team_id=team_id,
            season_id=season_id,
            match_data=match_data,
            opponent_rating=70.0,
            matches_count=1
        )

    # =========================================================
    # 7. ПРОГНОЗ НА ТУР
    # =========================================================

    def predict_tour(self, round_number: int) -> List[Dict[str, Any]]:
        """Прогноз всех матчей тура"""
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

            except Exception as e:
                logger.error("❌ Prediction error for %s vs %s: %s", home_team, away_team, e)

        return predictions

    # =========================================================
    # 8. ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================

    def _get_round_id(self, round_number: int) -> Optional[int]:
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
        conn = self.db._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    # =========================================================
    # 9. ПОЛНОЕ ОБНОВЛЕНИЕ
    # =========================================================

    def update_all(self, round_number: int) -> Dict[str, Any]:
        """
        Полное обновление: таблица + матчи + прогноз

        Args:
            round_number: номер тура

        Returns:
            Dict с результатами
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "round": round_number,
            "standings_saved": 0,
            "matches_loaded": 0,
            "predictions": [],
            "errors": []
        }

        logger.info("🚀 Starting full update for round %s", round_number)

        try:
            # 1. Парсим и сохраняем таблицу
            standings = self.get_standings()
            if standings:
                saved = self.save_standings_to_db(standings, round_number)
                results["standings_saved"] = saved
                logger.info("✅ Saved %s standings", saved)
            else:
                results["errors"].append("No standings data")

            # 2. Парсим и загружаем матчи тура
            matches = self.get_matches_by_tour(round_number)
            if matches:
                loaded = self.load_matches_to_db(matches, round_number)
                results["matches_loaded"] = loaded
                logger.info("✅ Loaded %s matches", loaded)
            else:
                results["errors"].append(f"No matches found for tour {round_number}")

            # 3. Делаем прогноз
            if results["matches_loaded"] > 0:
                predictions = self.predict_tour(round_number)
                results["predictions"] = predictions
                logger.info("✅ Made %s predictions", len(predictions))

        except Exception as e:
            results["errors"].append(f"Error: {e}")
            logger.error(f"❌ Update error: {e}")

        return results


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("⚽ SOCCERLAND PARSER v12.1 — SELF TEST")
    print("=" * 70)

    parser = SoccerlandParser()

    # 1. Тест: турнирная таблица
    print("\n📋 1. Testing: get_standings()")
    standings = parser.get_standings()
    print(f"  Found {len(standings)} teams")

    if standings:
        print("\n  Top 5 teams:")
        for team in standings[:5]:
            print(f"  {team['place']}. {team['team']} — {team['points']} pts, {team['goals_for']}:{team['goals_against']}")

    # 2. Тест: матчи 3 тура
    print("\n📋 2. Testing: get_matches_by_tour(3)")
    tour_matches = parser.get_matches_by_tour(3)
    print(f"  Found {len(tour_matches)} matches for tour 3")

    if tour_matches:
        for match in tour_matches:
            status_icon = "✅" if match['status'] == 'finished' else "⏳"
            score_display = match['score'] if match['score'] else "– : –"
            print(f"  {status_icon} {match['home']} | {score_display} | {match['away']}")

    print("\n" + "=" * 70)
    print("✅ SoccerlandParser v12.1 ready")
    print("=" * 70)

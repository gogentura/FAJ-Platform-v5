#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Standings Manager — пересчёт турнирной таблицы из фактических результатов.
Принципы:
    - Никаких DELETE.
    - Только UPSERT (INSERT OR REPLACE или проверка + UPDATE).
    - Снимок каждого тура (standings сохраняется для каждого раунда).
    - Пересчёт выполняется от 1 до указанного тура (или до последнего, где есть результаты).
    - Места рассчитываются автоматически.
    - Повторный запуск безопасен.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.database import FAJDatabase

logger = logging.getLogger(__name__)


class StandingsManager:
    """Менеджер турнирной таблицы."""

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()

    # ============================================================
    # ПЕРЕСЧЁТ ТАБЛИЦЫ
    # ============================================================

    def recalc_standings(self, season_id: int, round_number: Optional[int] = None) -> Dict[str, Any]:
        """
        Пересчитывает турнирную таблицу для сезона на основе match_results.
        Если round_number указан, пересчитывает только до этого тура (включительно).
        Если не указан, определяет максимальный тур с результатами.

        Для каждого тура от 1 до max_round сохраняется снимок standings.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # ------------------------------------------------------------
        # 1. Определяем максимальный тур, для которого есть результаты
        # ------------------------------------------------------------
        if round_number is None:
            cursor.execute("""
                SELECT MAX(r.round_number)
                FROM match_results mr
                JOIN matches m ON m.id = mr.match_id
                JOIN rounds r ON r.id = m.round_id
                WHERE r.season_id = ?
            """, (season_id,))
            row = cursor.fetchone()
            max_round = row[0] if row and row[0] is not None else 0
        else:
            max_round = int(round_number)

        if max_round == 0:
            conn.close()
            return {
                "success": True,
                "message": "Нет результатов для расчёта таблицы",
                "round": 0,
                "teams": 0,
                "standings": []
            }

        # ------------------------------------------------------------
        # 2. Пересчитываем для каждого тура от 1 до max_round
        # ------------------------------------------------------------
        for current_round in range(1, max_round + 1):
            # Получаем все результаты для матчей до current_round включительно
            cursor.execute("""
                SELECT
                    mr.match_id,
                    mr.home_goals,
                    mr.away_goals,
                    m.home_team_id,
                    m.away_team_id,
                    r.round_number
                FROM match_results mr
                JOIN matches m ON m.id = mr.match_id
                JOIN rounds r ON r.id = m.round_id
                WHERE r.season_id = ? AND r.round_number <= ?
            """, (season_id, current_round))
            rows = cursor.fetchall()

            if not rows:
                # Если для этого тура нет результатов, пропускаем
                continue

            # ------------------------------------------------------------
            # 3. Собираем статистику по командам
            # ------------------------------------------------------------
            stats = {}
            for row in rows:
                home_id = row['home_team_id']
                away_id = row['away_team_id']
                home_goals = row['home_goals']
                away_goals = row['away_goals']

                for team_id in (home_id, away_id):
                    if team_id not in stats:
                        stats[team_id] = {
                            'games': 0,
                            'wins': 0,
                            'draws': 0,
                            'losses': 0,
                            'goals_for': 0,
                            'goals_against': 0
                        }

                # Хозяева
                stats[home_id]['games'] += 1
                stats[home_id]['goals_for'] += home_goals
                stats[home_id]['goals_against'] += away_goals
                if home_goals > away_goals:
                    stats[home_id]['wins'] += 1
                elif home_goals == away_goals:
                    stats[home_id]['draws'] += 1
                else:
                    stats[home_id]['losses'] += 1

                # Гости
                stats[away_id]['games'] += 1
                stats[away_id]['goals_for'] += away_goals
                stats[away_id]['goals_against'] += home_goals
                if away_goals > home_goals:
                    stats[away_id]['wins'] += 1
                elif away_goals == home_goals:
                    stats[away_id]['draws'] += 1
                else:
                    stats[away_id]['losses'] += 1

            # ------------------------------------------------------------
            # 4. Вычисляем очки и разницу
            # ------------------------------------------------------------
            standings = []
            for team_id, s in stats.items():
                points = s['wins'] * 3 + s['draws'] * 1
                goal_diff = s['goals_for'] - s['goals_against']
                standings.append({
                    'team_id': team_id,
                    'games': s['games'],
                    'wins': s['wins'],
                    'draws': s['draws'],
                    'losses': s['losses'],
                    'goals_for': s['goals_for'],
                    'goals_against': s['goals_against'],
                    'goal_diff': goal_diff,
                    'points': points,
                })

            # ------------------------------------------------------------
            # 5. Сортировка
            # ------------------------------------------------------------
            standings.sort(key=lambda x: (-x['points'], -x['goal_diff'], -x['goals_for']))

            # ------------------------------------------------------------
            # 6. Добавляем место
            # ------------------------------------------------------------
            for idx, item in enumerate(standings, start=1):
                item['place'] = idx

            # ------------------------------------------------------------
            # 7. Сохраняем снимок для current_round (UPSERT)
            # ------------------------------------------------------------
            now = datetime.now().isoformat()
            for item in standings:
                # Проверяем, существует ли уже запись для этой команды, сезона и тура
                cursor.execute("""
                    SELECT id FROM standings
                    WHERE team_id = ? AND season_id = ? AND round = ?
                """, (item['team_id'], season_id, current_round))
                existing = cursor.fetchone()

                if existing:
                    # Обновляем
                    cursor.execute("""
                        UPDATE standings SET
                            place = ?,
                            games = ?,
                            wins = ?,
                            draws = ?,
                            losses = ?,
                            goals_for = ?,
                            goals_against = ?,
                            goal_diff = ?,
                            points = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        item['place'],
                        item['games'],
                        item['wins'],
                        item['draws'],
                        item['losses'],
                        item['goals_for'],
                        item['goals_against'],
                        item['goal_diff'],
                        item['points'],
                        now,
                        existing['id']
                    ))
                else:
                    # Вставляем новую запись
                    cursor.execute("""
                        INSERT INTO standings (
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
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        item['team_id'],
                        season_id,
                        current_round,
                        item['place'],
                        item['games'],
                        item['wins'],
                        item['draws'],
                        item['losses'],
                        item['goals_for'],
                        item['goals_against'],
                        item['goal_diff'],
                        item['points'],
                        now
                    ))

        conn.commit()
        conn.close()

        # Получаем финальную таблицу для max_round
        final_standings = self.get_standings(season_id, max_round)

        return {
            "success": True,
            "round": max_round,
            "teams": len(final_standings),
            "standings": final_standings
        }

    # ============================================================
    # ПОЛУЧЕНИЕ ТАБЛИЦЫ
    # ============================================================

    def get_standings(self, season_id: int, round_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Возвращает текущую таблицу для указанного сезона и тура.
        Если round_number не указан, возвращает последний сохранённый снимок.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if round_number is None:
            # Берём максимальный тур, для которого есть записи в standings
            cursor.execute("""
                SELECT MAX(round) AS max_round
                FROM standings
                WHERE season_id = ?
            """, (season_id,))
            row = cursor.fetchone()
            if not row or row['max_round'] is None:
                conn.close()
                return []
            round_number = row['max_round']

        cursor.execute("""
            SELECT
                s.team_id,
                t.name AS team_name,
                s.place,
                s.games,
                s.wins,
                s.draws,
                s.losses,
                s.goals_for,
                s.goals_against,
                s.goal_diff,
                s.points,
                s.updated_at
            FROM standings s
            JOIN teams t ON t.id = s.team_id
            WHERE s.season_id = ? AND s.round = ?
            ORDER BY s.place
        """, (season_id, round_number))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ============================================================
    # ОБНОВЛЕНИЕ ПОСЛЕ ДОБАВЛЕНИЯ РЕЗУЛЬТАТА
    # ============================================================

    def update_after_result(self, match_id: int) -> Dict[str, Any]:
        """
        Вызывается после сохранения/изменения результата матча.
        Определяет сезон и тур матча, пересчитывает таблицу до этого тура.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.season_id, r.round_number
            FROM matches m
            JOIN rounds r ON r.id = m.round_id
            WHERE m.id = ?
        """, (match_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                "success": False,
                "error": "Матч не найден"
            }

        season_id = row['season_id']
        round_number = row['round_number']

        # Пересчитываем таблицу до этого тура (включая его)
        return self.recalc_standings(season_id, round_number)

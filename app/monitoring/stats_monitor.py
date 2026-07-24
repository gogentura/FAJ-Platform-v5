# =====================================================
# FAJ Platform v6.2
# app/monitoring/stats_monitor.py
#
# Match Statistics Monitor
# =====================================================

import logging

from app.database import get_connection

logger = logging.getLogger(__name__)


class StatisticsMonitor:

    def __init__(self):
        self.conn = get_connection()

    # =================================================
    # Матчи без статистики
    # =================================================

    def get_matches_without_stats(self):

        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT
                f.id,
                f.home_team,
                f.away_team,
                f.match_date,
                f.home_score,
                f.away_score

            FROM fixtures f

            LEFT JOIN match_statistics s
                ON s.fixture_id = f.id

            WHERE
                f.status='finished'
                AND s.fixture_id IS NULL

            ORDER BY f.match_date;
            """
        )

        rows = cur.fetchall()

        matches = []

        for row in rows:

            matches.append({

                "fixture_id": row[0],

                "home_team": row[1],

                "away_team": row[2],

                "match_date": row[3],

                "home_score": row[4],

                "away_score": row[5]

            })

        return matches

    # =================================================
    # Получение статистики
    # Пока заглушка
    # =================================================

    def load_statistics(self, fixture):

        return {

            "fixture_id": fixture["fixture_id"],

            "home_xg": None,
            "away_xg": None,

            "home_shots": None,
            "away_shots": None,

            "home_shots_on_target": None,
            "away_shots_on_target": None,

            "home_possession": None,
            "away_possession": None,

            "home_corners": None,
            "away_corners": None,

            "home_yellow": None,
            "away_yellow": None,

            "home_red": None,
            "away_red": None

        }

    # =================================================
    # Сохранение
    # =================================================

    def save_statistics(self, stats):

        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO match_statistics (

                fixture_id,

                home_xg,
                away_xg,

                home_shots,
                away_shots,

                home_shots_on_target,
                away_shots_on_target,

                home_possession,
                away_possession,

                home_corners,
                away_corners,

                home_yellow,
                away_yellow,

                home_red,
                away_red

            )

            VALUES (

                %(fixture_id)s,

                %(home_xg)s,
                %(away_xg)s,

                %(home_shots)s,
                %(away_shots)s,

                %(home_shots_on_target)s,
                %(away_shots_on_target)s,

                %(home_possession)s,
                %(away_possession)s,

                %(home_corners)s,
                %(away_corners)s,

                %(home_yellow)s,
                %(away_yellow)s,

                %(home_red)s,
                %(away_red)s

            )

            ON CONFLICT (fixture_id)

            DO NOTHING;
            """,

            stats

        )

        self.conn.commit()

    # =================================================
    # Главный цикл
    # =================================================

    def update(self):

        matches = self.get_matches_without_stats()

        updated = 0

        errors = []

        for fixture in matches:

            try:

                stats = self.load_statistics(fixture)

                self.save_statistics(stats)

                updated += 1

            except Exception as e:

                logger.exception(e)

                errors.append(str(e))

        return {

            "updated": updated,

            "errors": errors

        }


def sync_statistics():

    monitor = StatisticsMonitor()

    return monitor.update()

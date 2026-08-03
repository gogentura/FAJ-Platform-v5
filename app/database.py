#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11.5

Database Engine

SQLite storage:
- seasons
- rounds
- matches
- faj memory

No JSON dependency
"""

import sqlite3
import os
from datetime import datetime


# =====================================================
# PATH
# =====================================================

DATA_DIR = "data"

DB_FILE = os.path.join(
    DATA_DIR,
    "faj.db"
)


# =====================================================
# CONNECTION
# =====================================================

def get_connection():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =====================================================
# INIT DATABASE
# =====================================================

def init_database():

    conn = get_connection()

    cursor = conn.cursor()


    # ===============================
    # SEASONS
    # ===============================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS seasons (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            league TEXT NOT NULL,

            year TEXT,

            created TEXT

        )
        """
    )


    # ===============================
    # ROUNDS
    # ===============================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rounds (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            season_id INTEGER,

            round_number INTEGER,

            status TEXT DEFAULT 'scheduled',

            created TEXT,

            FOREIGN KEY(season_id)
            REFERENCES seasons(id)

        )
        """
    )


    # ===============================
    # MATCHES
    # ===============================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            round_id INTEGER,

            home TEXT,

            away TEXT,


            faj_prediction TEXT,

            expert_prediction TEXT,


            actual_score TEXT,


            xg_home REAL,

            xg_away REAL,


            status TEXT DEFAULT 'scheduled',


            created TEXT,


            FOREIGN KEY(round_id)
            REFERENCES rounds(id)

        )
        """
    )


    # ===============================
    # MEMORY
    # ===============================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS faj_memory (

            id INTEGER PRIMARY KEY AUTOINCREMENT,


            competition TEXT,


            match TEXT,


            prediction TEXT,


            actual TEXT,


            error_type TEXT,


            created TEXT


        )
        """
    )


    conn.commit()

    conn.close()



# =====================================================
# DATABASE CLASS
# =====================================================

class FAJDatabase:


    def __init__(self):

        init_database()



    # =================================
    # STATUS
    # =================================

    def get_status(self):

        conn = get_connection()

        cursor = conn.cursor()


        result = {}


        for table in [
            "seasons",
            "rounds",
            "matches",
            "faj_memory"
        ]:

            cursor.execute(
                f"SELECT COUNT(*) FROM {table}"
            )

            result[table] = cursor.fetchone()[0]


        conn.close()


        return {

            "database":
                "SQLite",

            "file":
                DB_FILE,

            "status":
                "ACTIVE",

            "tables":
                result

        }



    # =================================
    # SEASONS
    # =================================

    def create_season(
            self,
            name,
            league,
            year
    ):

        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO seasons
            (
            name,
            league,
            year,
            created
            )

            VALUES (?,?,?,?)
            """,

            (
                name,
                league,
                year,
                datetime.now().isoformat()
            )
        )


        conn.commit()

        season_id = cursor.lastrowid

        conn.close()


        return season_id



    def get_seasons(self):

        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT *
            FROM seasons
            ORDER BY id DESC
            """
        )


        data = cursor.fetchall()

        conn.close()


        return data



    # =================================
    # ROUNDS
    # =================================

    def create_round(
            self,
            season_id,
            number
    ):

        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO rounds
            (
            season_id,
            round_number,
            created
            )

            VALUES (?,?,?)
            """,

            (
                season_id,
                number,
                datetime.now().isoformat()
            )
        )


        conn.commit()

        round_id = cursor.lastrowid

        conn.close()


        return round_id



    # =================================
    # MATCHES
    # =================================

    def add_match(
            self,
            round_id,
            home,
            away,
            faj_prediction="",
            expert_prediction="",
            xg_home=None,
            xg_away=None
    ):

        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO matches

            (
            round_id,
            home,
            away,
            faj_prediction,
            expert_prediction,
            xg_home,
            xg_away,
            created
            )

            VALUES (?,?,?,?,?,?,?,?)
            """,

            (
                round_id,
                home,
                away,
                faj_prediction,
                expert_prediction,
                xg_home,
                xg_away,
                datetime.now().isoformat()
            )

        )


        conn.commit()

        match_id = cursor.lastrowid

        conn.close()


        return match_id



    def update_result(
            self,
            match_id,
            score
    ):

        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            UPDATE matches

            SET

            actual_score=?,

            status='finished'

            WHERE id=?

            """,

            (
                score,
                match_id
            )
        )


        conn.commit()

        conn.close()



    # =================================
    # MEMORY
    # =================================

    def add_memory(
            self,
            competition,
            match,
            prediction,
            actual,
            error_type=""
    ):

        conn = get_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO faj_memory

            (
            competition,
            match,
            prediction,
            actual,
            error_type,
            created
            )

            VALUES (?,?,?,?,?,?)
            """,

            (
                competition,
                match,
                prediction,
                actual,
                error_type,
                datetime.now().isoformat()
            )
        )


        conn.commit()

        conn.close()



# =====================================================
# AUTO INIT
# =====================================================

init_database()

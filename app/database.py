#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11
Database Core

SQLite Storage Engine

Tables:
- tours
- matches
- memory
- teams
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
# INITIALIZE DATABASE
# =====================================================

def init_database():

    conn = get_connection()

    cursor = conn.cursor()


    # -------------------------
    # TOURS
    # -------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tours (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            league TEXT,
            season TEXT,
            round INTEGER,

            status TEXT DEFAULT 'active',

            created TEXT

        )
        """
    )


    # -------------------------
    # MATCHES
    # -------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            tour_id INTEGER,

            home TEXT,
            away TEXT,

            faj_prediction TEXT,
            expert_prediction TEXT,

            actual TEXT,

            xg_home REAL,
            xg_away REAL,

            home_win REAL,
            draw REAL,
            away_win REAL,

            confidence REAL,

            status TEXT DEFAULT 'scheduled',

            created TEXT,

            FOREIGN KEY(tour_id)
            REFERENCES tours(id)

        )
        """
    )


    # -------------------------
    # MEMORY BRAIN
    # -------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match_id INTEGER,

            prediction TEXT,

            actual TEXT,

            error_type TEXT,

            lesson TEXT,

            created TEXT

        )
        """
    )


    # -------------------------
    # TEAM PASSPORTS
    # -------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            league TEXT,

            team TEXT UNIQUE,

            attack REAL DEFAULT 70,

            defense REAL DEFAULT 70,

            form REAL DEFAULT 70,

            coach TEXT,

            squad_strength REAL DEFAULT 70,

            updated TEXT

        )
        """
    )


    conn.commit()

    conn.close()



# =====================================================
# TOUR API
# =====================================================

def create_tour(
        league,
        season,
        round_number
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        INSERT INTO tours
        (
            league,
            season,
            round,
            created
        )

        VALUES
        (?, ?, ?, ?)

        """,
        (
            league,
            season,
            round_number,
            datetime.now().isoformat()
        )
    )


    tour_id = cursor.lastrowid


    conn.commit()

    conn.close()


    return tour_id



def get_tours():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *
        FROM tours
        ORDER BY id DESC
        """
    )


    data = cursor.fetchall()


    conn.close()


    return data



# =====================================================
# MATCH API
# =====================================================


def add_match(
        tour_id,
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
            tour_id,
            home,
            away,
            faj_prediction,
            expert_prediction,
            xg_home,
            xg_away,
            created
        )

        VALUES
        (?, ?, ?, ?, ?, ?, ?, ?)

        """,
        (
            tour_id,
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

    conn.close()



def get_matches(
        tour_id
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *

        FROM matches

        WHERE tour_id = ?

        ORDER BY id

        """,
        (
            tour_id,
        )
    )


    matches = cursor.fetchall()


    conn.close()


    return matches



def update_result(
        match_id,
        actual
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        UPDATE matches

        SET

        actual = ?,
        status = 'finished'

        WHERE id = ?

        """,
        (
            actual,
            match_id
        )
    )


    conn.commit()

    conn.close()



# =====================================================
# MEMORY
# =====================================================


def add_memory(
        match_id,
        prediction,
        actual,
        error_type="",
        lesson=""
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        INSERT INTO memory
        (
            match_id,
            prediction,
            actual,
            error_type,
            lesson,
            created
        )

        VALUES
        (?, ?, ?, ?, ?, ?)

        """,
        (
            match_id,
            prediction,
            actual,
            error_type,
            lesson,
            datetime.now().isoformat()
        )
    )


    conn.commit()

    conn.close()



def get_memory():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *

        FROM memory

        ORDER BY id DESC

        """
    )


    data = cursor.fetchall()


    conn.close()


    return data



# =====================================================
# AUTO START
# =====================================================

init_database()


if __name__ == "__main__":

    print(
        "FAJ Database v11 initialized"
    )

    print(
        DB_FILE
    )

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11
Database Layer

Локальная база FAJ SQLite

Хранит:
- сезоны
- туры
- матчи
- прогнозы FAJ
- экспертные прогнозы
- результаты
- память Brain
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
# INITIALIZATION
# =====================================================

def init_database():

    conn = get_connection()

    cursor = conn.cursor()


    # -------------------------
    # ТУРЫ
    # -------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tours (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT UNIQUE,

            league TEXT,

            season TEXT,

            round_number INTEGER,

            status TEXT DEFAULT 'active',

            created TEXT

        )
        """
    )


    # -------------------------
    # МАТЧИ
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

            status TEXT DEFAULT 'scheduled',

            memory_saved INTEGER DEFAULT 0,

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
        CREATE TABLE IF NOT EXISTS faj_memory (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            match TEXT,

            faj_prediction TEXT,

            expert_prediction TEXT,

            actual TEXT,

            created TEXT

        )
        """
    )


    # -------------------------
    # PASSPORTS
    # -------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS passports (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            team TEXT UNIQUE,

            attack REAL DEFAULT 70,

            defense REAL DEFAULT 70,

            form REAL DEFAULT 70,

            updated TEXT

        )
        """
    )


    conn.commit()

    conn.close()



# =====================================================
# TOURS
# =====================================================

def create_tour(
        name,
        league="RPL",
        season="2026/27",
        round_number=1
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        INSERT OR IGNORE INTO tours

        (
        name,
        league,
        season,
        round_number,
        created
        )

        VALUES (?,?,?,?,?)
        """,

        (
            name,
            league,
            season,
            round_number,
            datetime.now().isoformat()
        )

    )


    conn.commit()

    conn.close()



def get_tours():

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *
        FROM tours
        ORDER BY id
        """
    )


    data = cursor.fetchall()


    conn.close()


    return [
        dict(row)
        for row in data
    ]



# =====================================================
# MATCHES
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
        xg_away
        )

        VALUES (?,?,?,?,?,?,?)

        """,

        (
            tour_id,
            home,
            away,
            faj_prediction,
            expert_prediction,
            xg_home,
            xg_away
        )

    )


    conn.commit()

    conn.close()



def get_matches(tour_id):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT *
        FROM matches

        WHERE tour_id=?

        """,
        (tour_id,)
    )


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]



def update_result(
        match_id,
        actual
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        UPDATE matches

        SET actual=?,
        status='finished'

        WHERE id=?

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
        match,
        faj_prediction,
        expert_prediction,
        actual
):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        INSERT INTO faj_memory

        (
        match,
        faj_prediction,
        expert_prediction,
        actual,
        created
        )

        VALUES (?,?,?,?,?)

        """,

        (
            match,
            faj_prediction,
            expert_prediction,
            actual,
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
        FROM faj_memory
        ORDER BY id DESC
        """
    )


    rows = cursor.fetchall()

    conn.close()


    return [
        dict(row)
        for row in rows
    ]



# =====================================================
# COMPATIBILITY CLASS
# Для старых страниц FAJ
# =====================================================

class FAJDatabase:


    def __init__(self):

        init_database()



    def get_connection(self):

        return get_connection()



    def get_tours(self):

        return get_tours()



    def get_memory(self):

        return get_memory()



    def create_tour(
            self,
            name,
            league="RPL",
            season="2026/27",
            round_number=1
    ):

        return create_tour(
            name,
            league,
            season,
            round_number
        )



# =====================================================
# AUTO INIT
# =====================================================

init_database()



if __name__ == "__main__":

    print(
        "FAJ Database initialized"
    )

    print(
        DB_FILE
    )

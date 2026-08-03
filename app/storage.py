#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11.5

Storage Manager

Управление файлами FAJ:
- проверка базы
- резервные копии
- информация о хранилище
"""

import os
import shutil
from datetime import datetime


# =====================================================
# PATHS
# =====================================================

DATA_DIR = "data"

DB_FILE = os.path.join(
    DATA_DIR,
    "faj.db"
)

BACKUP_DIR = os.path.join(
    DATA_DIR,
    "backup"
)


# =====================================================
# STORAGE CHECK
# =====================================================

def check_storage():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    return {

        "data_directory":
            os.path.exists(DATA_DIR),

        "database":
            os.path.exists(DB_FILE),

        "database_file":
            DB_FILE

    }


# =====================================================
# DATABASE SIZE
# =====================================================

def get_database_size():

    if not os.path.exists(DB_FILE):
        return "0 KB"

    size = os.path.getsize(
        DB_FILE
    )

    if size < 1024:
        return f"{size} bytes"

    if size < 1024*1024:
        return f"{round(size/1024,2)} KB"

    return f"{round(size/(1024*1024),2)} MB"



# =====================================================
# BACKUP
# =====================================================

def create_backup():

    if not os.path.exists(DB_FILE):
        return {

            "status":
                "error",

            "message":
                "Database not found"

        }


    os.makedirs(
        BACKUP_DIR,
        exist_ok=True
    )


    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    backup_file = os.path.join(
        BACKUP_DIR,
        f"faj_backup_{timestamp}.db"
    )


    shutil.copy2(
        DB_FILE,
        backup_file
    )


    return {

        "status":
            "success",

        "file":
            backup_file

    }



# =====================================================
# LIST BACKUPS
# =====================================================

def get_backups():

    if not os.path.exists(
        BACKUP_DIR
    ):
        return []


    files = []

    for file in os.listdir(
        BACKUP_DIR
    ):

        if file.endswith(
            ".db"
        ):

            files.append(
                file
            )


    return sorted(
        files,
        reverse=True
    )



# =====================================================
# STORAGE REPORT
# =====================================================

def storage_report():

    status = check_storage()

    return {

        "storage":
            "ACTIVE",

        "database":
            status["database"],

        "file":
            DB_FILE,

        "size":
            get_database_size(),

        "backups":
            len(
                get_backups()
            )

    }

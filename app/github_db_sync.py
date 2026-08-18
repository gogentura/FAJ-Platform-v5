#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import os
from pathlib import Path
import requests
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "faj.db"


def _get_secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _github_config():
    token = _get_secret("GITHUB_TOKEN")
    repo = _get_secret("GITHUB_REPO")
    branch = _get_secret("GITHUB_BRANCH", "main")
    if not token or not repo:
        raise RuntimeError(
            "Не настроены GITHUB_TOKEN и GITHUB_REPO в Streamlit Secrets."
        )
    return token, repo, branch


def load_database_from_github():
    """
    Восстанавливает data/faj.db из GitHub.
    ВАЖНО:
    Если локальной базы нет — скачивает её из GitHub.
    Если локальная база уже существует — НЕ перезаписывает её.
    """
    # Если база уже существует локально, ничего не скачиваем.
    if DB_PATH.exists():
        return {
            "success": True,
            "loaded": False,
            "reason": "local_database_exists",
            "path": str(DB_PATH),
        }

    token, repo, branch = _github_config()

    url = f"https://api.github.com/repos/{repo}/contents/data/faj.db"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    response = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)

    # В GitHub базы ещё нет. Это нормально для самого первого запуска.
    if response.status_code == 404:
        return {
            "success": True,
            "loaded": False,
            "reason": "github_database_not_found",
            "path": str(DB_PATH),
        }

    response.raise_for_status()
    result = response.json()
    encoded_content = result.get("content", "")

    if not encoded_content:
        raise RuntimeError("GitHub вернул faj.db без содержимого.")

    # GitHub иногда возвращает переносы строк внутри base64.
    encoded_content = encoded_content.replace("\n", "")
    data = base64.b64decode(encoded_content)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_bytes(data)

    return {
        "success": True,
        "loaded": True,
        "reason": "github_database_restored",
        "path": str(DB_PATH),
        "size": len(data),
    }


def _checkpoint_database():
    """
    Перед загрузкой SQLite-файла в GitHub
    переносит изменения из WAL в основной файл.
    """
    if not DB_PATH.exists():
        return

    import sqlite3
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def save_database_to_github():
    """
    Загружает текущий data/faj.db в GitHub.
    Если базы нет — это ошибка.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"База данных не найдена: {DB_PATH}")

    # Очень важно для SQLite + WAL: сначала переносим изменения в основной faj.db.
    _checkpoint_database()

    token, repo, branch = _github_config()

    data = DB_PATH.read_bytes()
    content = base64.b64encode(data).decode("ascii")

    url = f"https://api.github.com/repos/{repo}/contents/data/faj.db"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    # Получаем SHA существующего файла.
    response = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)

    sha = None
    if response.status_code == 200:
        sha = response.json().get("sha")
    elif response.status_code != 404:
        response.raise_for_status()

    payload = {
        "message": "Update FAJ SQLite database",
        "content": content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    return {
        "success": True,
        "path": "data/faj.db",
        "size": len(data),
        "sha": response.json()["content"]["sha"],
    }

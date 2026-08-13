#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import hashlib
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


def save_database_to_github():
    """
    Загружает текущий data/faj.db в GitHub.
    Ничего не делает, если файла нет.
    """

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"База данных не найдена: {DB_PATH}"
        )

    token, repo, branch = _github_config()

    data = DB_PATH.read_bytes()

    content = base64.b64encode(data).decode("ascii")

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/data/faj.db"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    # Получаем SHA существующего файла, если он уже есть
    response = requests.get(
        url,
        headers=headers,
        params={"ref": branch},
        timeout=30,
    )

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

    response = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    return {
        "success": True,
        "path": "data/faj.db",
        "size": len(data),
        "sha": response.json()["content"]["sha"],
    }

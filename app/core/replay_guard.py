#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Replay Guard — глобальный защитник от утечки будущих данных

РАБОТАЕТ:
1. Читает состояние replay из data/replay/replay_state.json
2. Блокирует доступ к результатам матчей, если replay активен
3. Используется Prediction Manager перед прогнозом
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReplayGuard:
    """
    Replay Guard — единая точка контроля для Historical Replay
    """

    _instance = None
    _state_file = Path("data/replay/replay_state.json")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ReplayGuard, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self._state = self._load_state()

    def _load_state(self) -> Dict:
        """Загружает состояние из файла"""
        if not self._state_file.exists():
            return {"locked": False, "tour": None, "timestamp": None}
        try:
            with open(self._state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"locked": False, "tour": None, "timestamp": None}

    def _save_state(self):
        """Сохраняет состояние в файл"""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения состояния ReplayGuard: {e}")

    def lock(self, tour: int) -> bool:
        """Активирует блокировку"""
        self._state = {
            "locked": True,
            "tour": tour,
            "timestamp": datetime.now().isoformat()
        }
        self._save_state()
        logger.info(f"🔒 ReplayGuard: блокировка активирована для тура {tour}")
        return True

    def unlock(self):
        """Снимает блокировку"""
        self._state = {"locked": False, "tour": None, "timestamp": None}
        self._save_state()
        logger.info("🔓 ReplayGuard: блокировка снята")

    def is_locked(self) -> bool:
        """Проверяет, активна ли блокировка"""
        self._state = self._load_state()
        return self._state.get("locked", False)

    def get_current_tour(self) -> Optional[int]:
        """Возвращает текущий тур, если блокировка активна"""
        self._state = self._load_state()
        return self._state.get("tour") if self._state.get("locked") else None

    def check_access_to_match(self, match_data: Dict) -> bool:
        """
        Проверяет, можно ли получить доступ к данным матча
        
        Returns:
            True — доступ разрешён
            False — доступ запрещён (есть риск утечки будущего)
        """
        if not self.is_locked():
            return True
        
        # Если матч имеет статус FINISHED — блокируем
        if match_data.get('status') == 'FINISHED':
            logger.warning(f"⚠️ ReplayGuard: доступ к FINISHED матчу заблокирован")
            return False
        
        # Если матч имеет результаты — блокируем
        if match_data.get('home_goals') is not None and match_data.get('away_goals') is not None:
            logger.warning(f"⚠️ ReplayGuard: доступ к матчу с результатами заблокирован")
            return False
        
        return True


_replay_guard = None


def get_replay_guard() -> ReplayGuard:
    """Синглтон для ReplayGuard"""
    global _replay_guard
    if _replay_guard is None:
        _replay_guard = ReplayGuard()
    return _replay_guard

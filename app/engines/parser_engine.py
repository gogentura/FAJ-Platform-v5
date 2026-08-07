#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Parser Engine — оркестратор парсинга данных
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from app.database import FAJDatabase
from app.engines.source_adapters.base_adapter import BaseAdapter
from app.engines.source_adapters.soccerland_adapter import SoccerlandAdapter

logger = logging.getLogger(__name__)


class ParserEngine:
    """
    Parser Engine — оркестратор парсинга данных
    
    РОЛЬ:
        1. Запускать адаптеры
        2. Получать данные
        3. Сохранять через Database API
    """

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self._adapters = {}
        self._register_adapter(SoccerlandAdapter())
        
        # Контроль источников
        self.sources = {
            "manual": True,
            "soccerland": True
        }

    def _register_adapter(self, adapter: BaseAdapter):
        """Регистрирует адаптер"""
        source = adapter.get_source_name()
        self._adapters[source] = adapter
        logger.info(f"✅ Зарегистрирован адаптер: {source}")

    def get_adapters(self) -> List[str]:
        """Возвращает список доступных адаптеров"""
        return list(self._adapters.keys())

    def _has_upsert_match(self) -> bool:
        """Проверяет, есть ли метод upsert_match в БД"""
        return hasattr(self.db, "upsert_match")

    # ============================================================
    # ИМПОРТ МАТЧЕЙ ВРУЧНУЮ (MANUAL MODE)
    # ============================================================

    def import_matches(self, matches: List[Dict]) -> Dict:
        """
        Ручной импорт матчей (для historical replay)
        
        Args:
            matches: список словарей с данными матчей
            
        Returns:
            Dict с результатами импорта
        """
        if not self.sources.get("manual", True):
            logger.info("ℹ️ Ручной импорт отключён")
            return {"status": "disabled", "total": 0, "saved": 0, "errors": 0}

        results = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total": len(matches),
            "saved": 0,
            "errors": 0,
            "details": []
        }

        if not self._has_upsert_match():
            logger.error("❌ Database не поддерживает upsert_match")
            results["status"] = "error"
            results["errors"] = len(matches)
            return results

        for match in matches:
            try:
                match_id = self.db.upsert_match(match)
                if match_id:
                    results["saved"] += 1
                else:
                    results["errors"] += 1
            except Exception as e:
                results["errors"] += 1
                logger.error(f"❌ Ошибка импорта матча: {e}")

        logger.info(f"✅ Импортировано {results['saved']} из {results['total']} матчей")
        return results

    # ============================================================
    # ПАРСИНГ ИЗ ИСТОЧНИКОВ
    # ============================================================

    def update_fixtures(self, league: str = "РПЛ", source: Optional[str] = None) -> Dict:
        """Обновление календаря матчей"""
        if not self.sources.get("soccerland", True):
            logger.info("ℹ️ Soccerland парсинг отключён")
            return {"status": "disabled", "total": 0, "saved": 0, "errors": 0}

        results = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total": 0,
            "saved": 0,
            "errors": 0,
            "details": []
        }

        if not self._has_upsert_match():
            logger.error("❌ Database не поддерживает upsert_match")
            results["status"] = "error"
            return results

        sources = [source] if source else self._adapters.keys()

        for source_name in sources:
            if source_name not in self._adapters:
                results["errors"] += 1
                results["details"].append({"source": source_name, "error": "Adapter not found"})
                continue

            adapter = self._adapters[source_name]
            logger.info(f"🔄 Загрузка календаря из {source_name}...")

            try:
                fixtures = adapter.get_fixtures(league)
                
                for fixture in fixtures:
                    results["total"] += 1
                    try:
                        match_id = self.db.upsert_match(fixture)
                        if match_id:
                            results["saved"] += 1
                    except Exception as e:
                        results["errors"] += 1
                        logger.error(f"❌ Ошибка сохранения матча: {e}")

                results["details"].append({
                    "source": source_name,
                    "total": len(fixtures),
                    "saved": results["saved"]
                })
                logger.info(f"✅ Из {source_name} загружено {len(fixtures)} матчей")

            except Exception as e:
                results["errors"] += 1
                results["details"].append({"source": source_name, "error": str(e)})
                logger.error(f"❌ Ошибка загрузки из {source_name}: {e}")

        return results

    def update_matches(self, league: str = "РПЛ", source: Optional[str] = None) -> Dict:
        """Обновление результатов матчей (сыгранные матчи)"""
        if not self.sources.get("soccerland", True):
            logger.info("ℹ️ Soccerland парсинг отключён")
            return {"status": "disabled", "total": 0, "saved": 0, "errors": 0}

        results = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total": 0,
            "saved": 0,
            "errors": 0,
            "details": []
        }

        if not self._has_upsert_match():
            logger.error("❌ Database не поддерживает upsert_match")
            results["status"] = "error"
            return results

        sources = [source] if source else self._adapters.keys()

        for source_name in sources:
            if source_name not in self._adapters:
                results["errors"] += 1
                results["details"].append({"source": source_name, "error": "Adapter not found"})
                continue

            adapter = self._adapters[source_name]
            logger.info(f"🔄 Загрузка матчей из {source_name}...")

            try:
                matches = adapter.get_matches(league)
                
                for match in matches:
                    results["total"] += 1
                    try:
                        match_id = self.db.upsert_match(match)
                        if match_id:
                            results["saved"] += 1
                    except Exception as e:
                        results["errors"] += 1
                        logger.error(f"❌ Ошибка сохранения матча: {e}")

                results["details"].append({
                    "source": source_name,
                    "total": len(matches),
                    "saved": results["saved"]
                })
                logger.info(f"✅ Из {source_name} загружено {len(matches)} матчей")

            except Exception as e:
                results["errors"] += 1
                results["details"].append({"source": source_name, "error": str(e)})
                logger.error(f"❌ Ошибка загрузки из {source_name}: {e}")

        return results

    def update_all(self, league: str = "РПЛ") -> Dict:
        """Полное обновление данных (календарь + матчи)"""
        results = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "fixtures": self.update_fixtures(league),
            "matches": self.update_matches(league),
            "total_saved": 0
        }
        
        results["total_saved"] = (
            results["fixtures"].get("saved", 0) +
            results["matches"].get("saved", 0)
        )
        
        return results


if __name__ == "__main__":
    engine = ParserEngine()
    print("🔧 Доступные адаптеры:", engine.get_adapters())
    print("📌 Источники:", engine.sources)
    
    # Тест ручного импорта
    test_matches = [
        {
            "home_team": "Зенит",
            "away_team": "Ростов",
            "home_goals": 2,
            "away_goals": 1,
            "round": 1,
            "status": "FINISHED"
        }
    ]
    print("\n📡 Тест ручного импорта...")
    result = engine.import_matches(test_matches)
    print(f"   ✅ Сохранено: {result['saved']} из {result['total']}")

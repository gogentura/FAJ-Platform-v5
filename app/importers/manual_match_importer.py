#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Manual Match Importer — ручной импорт матчей из JSON
Для исторической реконструкции туров
"""

import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

from app.database import FAJDatabase
from app.engines.source_adapters.soccerland_adapter import SoccerlandAdapter

logger = logging.getLogger(__name__)


class ManualMatchImporter:
    """
    Импорт матчей из JSON для исторического replay
    """

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self.adapter = SoccerlandAdapter()
        self.data_dir = Path("data")

    def import_from_json(self, file_path: str) -> Dict:
        """
        Импорт матчей из JSON файла
        
        Args:
            file_path: путь к JSON файлу
            
        Returns:
            Dict с результатами импорта
        """
        results = {
            "status": "success",
            "total": 0,
            "saved": 0,
            "errors": 0,
            "details": []
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            matches = data.get('matches', [])
            if not matches:
                results["status"] = "error"
                results["details"].append({"error": "No matches found in JSON"})
                return results

            # Подготавливаем матчи
            prepared = []
            for match in matches:
                if not match.get('home_team') or not match.get('away_team'):
                    results["errors"] += 1
                    continue

                validated = self.adapter.validate_match(match)
                if validated:
                    prepared.append(validated)
                    results["total"] += 1
                else:
                    results["errors"] += 1

            # Сохраняем
            for match in prepared:
                try:
                    match_id = self.db.upsert_match(match)
                    if match_id:
                        results["saved"] += 1
                    else:
                        results["errors"] += 1
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"❌ Ошибка сохранения матча: {e}")

            logger.info(f"✅ Импортировано {results['saved']} из {results['total']} матчей")

        except FileNotFoundError:
            results["status"] = "error"
            results["details"].append({"error": f"File not found: {file_path}"})
        except json.JSONDecodeError as e:
            results["status"] = "error"
            results["details"].append({"error": f"Invalid JSON: {e}"})
        except Exception as e:
            results["status"] = "error"
            results["details"].append({"error": str(e)})

        return results

    def import_tour(self, tour: int, matches: List[Dict]) -> Dict:
        """
        Импорт одного тура
        
        Args:
            tour: номер тура
            matches: список матчей тура
            
        Returns:
            Dict с результатами импорта
        """
        for match in matches:
            match['round'] = tour
            if 'status' not in match:
                match['status'] = 'FINISHED' if match.get('home_goals') is not None else 'SCHEDULED'

        return self.import_matches(matches)

    def import_matches(self, matches: List[Dict]) -> Dict:
        """Импорт списка матчей"""
        results = {
            "status": "success",
            "total": len(matches),
            "saved": 0,
            "errors": 0,
            "details": []
        }

        for match in matches:
            validated = self.adapter.validate_match(match)
            if validated:
                try:
                    match_id = self.db.upsert_match(validated)
                    if match_id:
                        results["saved"] += 1
                    else:
                        results["errors"] += 1
                except Exception as e:
                    results["errors"] += 1
                    logger.error(f"❌ Ошибка сохранения матча: {e}")
            else:
                results["errors"] += 1

        logger.info(f"✅ Импортировано {results['saved']} из {results['total']} матчей")
        return results


if __name__ == "__main__":
    importer = ManualMatchImporter()
    
    test_matches = [
        {
            "home_team": "Зенит",
            "away_team": "Ростов",
            "home_goals": 2,
            "away_goals": 1,
            "round": 1,
            "status": "FINISHED"
        },
        {
            "home_team": "Спартак",
            "away_team": "Динамо Москва",
            "home_goals": 1,
            "away_goals": 1,
            "round": 1,
            "status": "FINISHED"
        }
    ]
    
    print("📡 Тест ручного импорта...")
    result = importer.import_matches(test_matches)
    print(f"   ✅ Сохранено: {result['saved']} из {result['total']}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Sync Engine — Единый модуль синхронизации
Паспорта команд вшиты в код (НЕ JSON!)
Работает ТОЛЬКО через FAJDatabase
"""

from app.database import FAJDatabase
from datetime import datetime
import os
import shutil


# ============================================================
# КОНФИГУРАЦИЯ ЛИГ (только нужные)
# ============================================================

LEAGUE_CONFIG = {
    "РПЛ": {
        "teams": 16,
        "rounds": 30,
        "country": "Россия",
        "format": "double_round_robin"
    },
    "АПЛ": {
        "teams": 20,
        "rounds": 38,
        "country": "Англия",
        "format": "double_round_robin"
    },
    "Ла Лига": {
        "teams": 20,
        "rounds": 38,
        "country": "Испания",
        "format": "double_round_robin"
    },
    "Лига чемпионов": {
        "teams": 36,
        "rounds": 8,
        "country": "Европа",
        "format": "swiss_system",
        "playoff_start": 9,
        "direct_qualification": 8
    }
}


# ============================================================
# ПАСПОРТА РПЛ 2026/27 (ВШИТЫ В КОД)
# ============================================================

RPL_PASSPORTS_2026 = {
    "Зенит": {
        "rating": 91,
        "class": "Чемпионский претендент",
        "style": "Контроль + позиционная атака",
        "dna": "Команда, которая выигрывает классом",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 92, "defense": 91, "control": 94,
            "efficiency": 90, "mentality": 92, "tempo": 76, "press": 88
        },
        "strengths": ["качество состава", "индивидуальное мастерство", "контроль мяча", "глубина скамейки", "давление после потери"],
        "weaknesses": ["зависимость от лидеров", "иногда медленный переход назад"]
    },
    "Спартак": {
        "rating": 86,
        "class": "Большая команда",
        "style": "Атакующий футбол, вертикальные атаки",
        "dna": "Большая команда с высоким потолком и высокой дисперсией",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 88, "defense": 82, "control": 86,
            "efficiency": 85, "mentality": 87, "tempo": 84, "press": 82
        },
        "strengths": ["индивидуальность игроков", "эмоции", "домашний фактор"],
        "weaknesses": ["нестабильность", "оборонительные ошибки"]
    },
    "ЦСКА": {
        "rating": 85,
        "class": "Команда результата",
        "style": "Организация + переходы",
        "dna": "Команда результата",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 84, "defense": 88, "control": 84,
            "efficiency": 86, "mentality": 90, "tempo": 76, "press": 84
        },
        "strengths": ["дисциплина", "структура", "характер"],
        "weaknesses": ["создание моментов против низкого блока"]
    },
    "Динамо Москва": {
        "rating": 84,
        "class": "Команда темпа",
        "style": "Высокий темп, давление",
        "dna": "Команда темпа",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 87, "defense": 81, "control": 86,
            "efficiency": 83, "mentality": 84, "tempo": 88, "press": 86
        },
        "strengths": ["скорость", "фланги", "интенсивность"],
        "weaknesses": ["пространство за линией обороны"]
    },
    "Локомотив": {
        "rating": 83,
        "class": "Команда развития",
        "style": "Молодость + вертикальный футбол",
        "dna": "Команда развития",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 86, "defense": 80, "control": 83,
            "efficiency": 84, "mentality": 80, "tempo": 86, "press": 82
        },
        "strengths": ["скорость", "переходы", "энергия"],
        "weaknesses": ["опыт"]
    },
    "Краснодар": {
        "rating": 86,
        "class": "Самая системная команда",
        "style": "Владение + позиционный футбол",
        "dna": "Самая системная команда России",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 86, "defense": 87, "control": 90,
            "efficiency": 87, "mentality": 86, "tempo": 76, "press": 84
        },
        "strengths": ["структура", "организация", "стабильность"],
        "weaknesses": ["иногда нехватка агрессии"]
    },
    "Ростов": {
        "rating": 78,
        "class": "Команда-сюрприз",
        "style": "Организация + борьба",
        "dna": "Команда, которая усложняет жизнь фаворитам",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 77, "defense": 79, "control": 74,
            "efficiency": 78, "mentality": 86, "tempo": 70, "press": 76
        },
        "strengths": ["характер", "домашние матчи"],
        "weaknesses": ["качество состава"]
    },
    "Ахмат": {
        "rating": 77,
        "class": "Сложный соперник",
        "style": "Физический футбол",
        "dna": "Сложный соперник",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 75, "defense": 80, "control": 70,
            "efficiency": 74, "mentality": 82, "tempo": 72, "press": 78,
            "physical": 84
        },
        "strengths": ["единоборства", "мощность"],
        "weaknesses": ["созидание"]
    },
    "Рубин": {
        "rating": 76,
        "class": "Рациональная команда",
        "style": "Организация + дисциплина",
        "dna": "Рациональная команда",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 74, "defense": 81, "control": 76,
            "efficiency": 78, "mentality": 84, "tempo": 70, "press": 74
        },
        "strengths": ["организация", "дисциплина"],
        "weaknesses": ["креативность"]
    },
    "Крылья Советов": {
        "rating": 74,
        "class": "Команда скорости",
        "style": "Скорость + молодость",
        "dna": "Команда с энергией",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 78, "defense": 72, "control": 72,
            "efficiency": 74, "mentality": 76, "tempo": 84, "press": 78
        },
        "strengths": ["переходы", "энергия"],
        "weaknesses": ["стабильность"]
    },
    "Факел": {
        "rating": 70,
        "class": "Оборонительная команда",
        "style": "Оборонительная модель",
        "dna": "Борьба + дисциплина",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 64, "defense": 76, "control": 66,
            "efficiency": 68, "mentality": 78, "tempo": 64, "press": 72
        },
        "strengths": ["борьба", "дисциплина"],
        "weaknesses": ["атака"]
    },
    "Оренбург": {
        "rating": 72,
        "class": "Атакующий новичок",
        "style": "Открытый футбол",
        "dna": "Смелость + атака",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 78, "defense": 66, "control": 72,
            "efficiency": 70, "mentality": 74, "tempo": 82, "press": 76
        },
        "strengths": ["атака", "смелость"],
        "weaknesses": ["оборона"]
    },
    "Балтика": {
        "rating": 73,
        "class": "Организованная команда",
        "style": "Организация + физика",
        "dna": "Структура + дисциплина",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 70, "defense": 78, "control": 72,
            "efficiency": 72, "mentality": 80, "tempo": 68, "press": 74
        },
        "strengths": ["структура", "дисциплина"],
        "weaknesses": ["атака"]
    },
    "Акрон": {
        "rating": 68,
        "class": "Новичок с энергией",
        "style": "Энергия новичка",
        "dna": "Мотивация + борьба",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 66, "defense": 70, "control": 64,
            "efficiency": 66, "mentality": 76, "tempo": 74, "press": 72
        },
        "strengths": ["мотивация"],
        "weaknesses": ["глубина состава"]
    },
    "Динамо Махачкала": {
        "rating": 71,
        "class": "Оборонительная команда",
        "style": "Оборона + характер",
        "dna": "Организация + борьба",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 66, "defense": 78, "control": 68,
            "efficiency": 70, "mentality": 82, "tempo": 64, "press": 72
        },
        "strengths": ["организация"],
        "weaknesses": ["атака"]
    },
    "Родина": {
        "rating": 67,
        "class": "Команда развития",
        "style": "Развитие молодых игроков",
        "dna": "Потенциал + молодость",
        "version": "RPL_2026.07",
        "source": "FAJ Expert Layer",
        "indices": {
            "attack": 64, "defense": 68, "control": 66,
            "efficiency": 64, "mentality": 70, "tempo": 76, "press": 70
        },
        "strengths": ["потенциал"],
        "weaknesses": ["опыт РПЛ"]
    }
}


LEAGUE_DNA = {
    "mean_xg": 1.35,
    "home_advantage": 0.12,
    "avg_tempo": 72,
    "avg_goals_min": 2.35,
    "avg_goals_max": 2.55,
    "derby_factor": 1.08,
    "newcomer_motivation": 1.05,
    "first_rounds_bonus": 5
}


class SyncEngine:
    """Единый движок синхронизации для FAJ v11.2"""

    def __init__(self):
        self.db = FAJDatabase()
        self.passports = RPL_PASSPORTS_2026
        self.league_dna = LEAGUE_DNA
        self.league = "РПЛ"
        self.config = LEAGUE_CONFIG

    # ============================================================
    # 1. РЕЗЕРВНОЕ КОПИРОВАНИЕ
    # ============================================================

    def _backup_database(self):
        """Создаёт резервную копию БД перед синхронизацией"""
        from app.database import DB_FILE
        
        if not os.path.exists(DB_FILE):
            return None
        
        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        backup_file = os.path.join(backup_dir, f"faj_{timestamp}.db")
        
        shutil.copy2(DB_FILE, backup_file)
        return backup_file

    # ============================================================
    # 2. СТАТУС
    # ============================================================

    def get_status(self, league="РПЛ"):
        """Получает статус синхронизации"""
        full_status = self.db.get_status()
        tables = full_status.get("tables", {})
        
        teams = self.db.get_teams(league=league)
        matches = self.db.get_matches()
        
        return {
            "league": league,
            "teams": len(teams) if teams else 0,
            "matches": len(matches) if matches else 0,
            "finished": sum(1 for m in matches if m['status'] == 'finished') if matches else 0,
            "gold_dataset": tables.get("gold_dataset", 0),
            "learning_records": tables.get("learning_records", 0)
        }

    # ============================================================
    # 3. ПОЛУЧЕНИЕ/СОЗДАНИЕ СЕЗОНА (с защитой от дублей)
    # ============================================================

    def _get_or_create_season(self, league="РПЛ", year="2026/27"):
        """Получает существующий сезон или создаёт новый"""
        seasons = self.db.get_seasons()
        
        for s in seasons:
            if s['league'] == league and s['year'] == year:
                return s['id']
        
        season_id = self.db.create_season(
            name=f"{league} {year}",
            league=league,
            year=year
        )
        
        # Используем конфиг для количества туров
        rounds_count = self.config.get(league, {}).get("rounds", 30)
        for i in range(1, rounds_count + 1):
            self.db.create_round(season_id, i)
        
        return season_id

    # ============================================================
    # 4. КОМАНДЫ + ПАСПОРТА
    # ============================================================

    def sync_teams(self, league="РПЛ"):
        """Загружает команды и их паспорта в SQLite"""
        
        # Резервная копия
        backup_file = self._backup_database()
        
        teams = list(self.passports.keys())
        
        created = 0
        updated = 0
        
        for name in teams:
            existing_id = self.db.get_team_id(name, league)
            if existing_id:
                updated += 1
            else:
                team_id = self.db.add_team(name, league=league, country="Россия")
                if team_id:
                    created += 1
        
        season_id = self._get_or_create_season(league)
        
        passport_count = self.sync_passports(league)
        
        # Используем метод database.py для сохранения мета-информации
        meta_count = self._save_passport_meta(season_id)
        
        return {
            "status": "success",
            "created": created,
            "updated": updated,
            "total": len(teams),
            "passports": passport_count.get("updated", 0),
            "meta": meta_count,
            "season_id": season_id,
            "backup": backup_file
        }

    # ============================================================
    # 5. ПАСПОРТА (ИЗ ВШИТЫХ ДАННЫХ)
    # ============================================================

    def sync_passports(self, league="РПЛ"):
        """Загружает паспорта из вшитых данных в SQLite"""
        
        season_id = self._get_or_create_season(league)
        teams = self.db.get_teams(league=league)
        updated = 0
        
        for team in teams:
            passport = self.passports.get(team['name'])
            if passport:
                indices = passport.get("indices", {})
                
                self.db.update_base(
                    team['id'],
                    season_id,
                    attack=indices.get("attack", 50),
                    defense=indices.get("defense", 50),
                    control=indices.get("control", 50),
                    press=indices.get("press", 50),
                    tempo=indices.get("tempo", 50),
                    transition=indices.get("transition", 50),
                    finishing=indices.get("efficiency", 50),
                    squad_quality=passport.get("rating", 50)
                )
                updated += 1
        
        return {
            "status": "success",
            "updated": updated,
            "total": len(teams)
        }

    # ============================================================
    # 6. МЕТА-ИНФОРМАЦИЯ ПАСПОРТОВ (через database.py)
    # ============================================================

    def _save_passport_meta(self, season_id):
        """Сохраняет мета-информацию паспортов через FAJDatabase"""
        
        teams = self.db.get_teams(league="РПЛ")
        count = 0
        
        for team in teams:
            passport = self.passports.get(team['name'])
            if passport:
                self.db.save_passport_meta(
                    team_id=team['id'],
                    season_id=season_id,
                    passport_data={
                        "style": passport.get("style", ""),
                        "dna": passport.get("dna", ""),
                        "strengths": passport.get("strengths", []),
                        "weaknesses": passport.get("weaknesses", []),
                        "class": passport.get("class", ""),
                        "version": passport.get("version", "1.0"),
                        "source": passport.get("source", "FAJ Expert Layer")
                    }
                )
                count += 1
        
        return count

    # ============================================================
    # 7. МАТЧИ (ЗАГЛУШКА ДО ПАРСЕРА)
    # ============================================================

    def sync_matches(self, league="РПЛ"):
        """Загружает матчи (заглушка до парсера)"""
        return {
            "status": "pending",
            "loaded": 0,
            "message": "Ожидание парсера РПЛ"
        }

    # ============================================================
    # 8. РЕЗУЛЬТАТЫ (ЗАГЛУШКА)
    # ============================================================

    def sync_results(self, league="РПЛ"):
        """Загружает результаты (заглушка)"""
        return {
            "status": "pending",
            "updated": 0,
            "message": "Ожидание парсера РПЛ"
        }

    # ============================================================
    # 9. GOLD DATASET
    # ============================================================

    def build_gold_dataset(self):
        """Строит Gold Dataset из завершённых матчей"""
        
        matches = self.db.get_matches()
        finished = [m for m in matches if m['status'] == 'finished']
        
        count = 0
        for m in finished:
            gold = self.db.get_gold_by_match(m['id'])
            
            if gold and not gold['actual_score']:
                self.db.update_gold_actual(gold['id'], {
                    'actual_score': f"{m['actual_home']}:{m['actual_away']}",
                    'actual_home_goals': m['actual_home'],
                    'actual_away_goals': m['actual_away']
                })
                count += 1
            elif not gold:
                home = self.db.get_team(m['home_team_id'])
                away = self.db.get_team(m['away_team_id'])
                
                if home and away:
                    self.db.add_to_gold({
                        'match_id': m['id'],
                        'home_team': home['name'],
                        'away_team': away['name'],
                        'match_date': m.get('date', ''),
                        'model_version': 'v11.2',
                        'faj_score': f"{m['actual_home']}:{m['actual_away']}",
                        'actual_score': f"{m['actual_home']}:{m['actual_away']}",
                        'actual_home_goals': m['actual_home'],
                        'actual_away_goals': m['actual_away'],
                        'status': 'completed'
                    })
                    count += 1

        return {
            "status": "success",
            "loaded": count
        }

    # ============================================================
    # 10. AUDIT
    # ============================================================

    def run_audit(self):
        """Запускает аудит"""
        try:
            from app.audit_engine import audit_all_pending
            results = audit_all_pending()
            return {
                "status": "success",
                "processed": len(results) if results else 0
            }
        except ImportError:
            return {
                "status": "error",
                "message": "audit_engine.py не найден"
            }

    # ============================================================
    # 11. LEARNING
    # ============================================================

    def run_learning(self):
        """Запускает обучение"""
        try:
            from app.learning_engine import get_learning_report
            report = get_learning_report()
            return {
                "status": "success" if report['status'] != 'no_errors' else "empty",
                "report": report
            }
        except ImportError:
            return {
                "status": "error",
                "message": "learning_engine.py не найден"
            }


if __name__ == "__main__":
    sync = SyncEngine()
    
    print("🏆 Тест SyncEngine")
    print("=" * 40)
    
    status = sync.get_status()
    print(f"Команды: {status['teams']}")
    print(f"Матчи: {status['matches']}")
    print(f"Gold Dataset: {status['gold_dataset']}")
    print(f"Learning Records: {status['learning_records']}")
    
    print("\n🔄 Загрузка команд РПЛ 2026/27 с паспортами...")
    result = sync.sync_teams()
    print(f"✅ Создано: {result['created']}")
    print(f"✅ Обновлено: {result['updated']}")
    print(f"✅ Всего: {result['total']}")
    print(f"✅ Паспортов: {result['passports']}")
    print(f"✅ Мета-информации: {result['meta']}")
    if result.get('backup'):
        print(f"✅ Резервная копия: {result['backup']}")

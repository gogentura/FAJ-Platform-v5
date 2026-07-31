#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
FAJ Core

Главный управляющий модуль платформы.
Интеграция с Learning DB и новой системой прогнозирования.

Pipeline:
Match
 ↓
Passport Engine (Learning DB)
 ↓
Prediction Engine (FAJPrediction)
 ↓
xG Engine
 ↓
Poisson
 ↓
Expert Layer
 ↓
Learning DB (Memory)
 ↓
Journal (Comparison Log)
"""

from datetime import datetime
from app.learning_db import LearningDB
from app.prediction import FAJPrediction


class FAJCore:
    """Главное ядро платформы FAJ"""

    def __init__(self):
        self.version = "10.0"
        self.learning_db = LearningDB()
        self.prediction_engine = FAJPrediction()

    # =====================================
    # MATCH PREDICTION API
    # =====================================

    def predict_match(self, home: str, away: str) -> dict:
        """
        Прогноз матча с сохранением в Learning DB

        Args:
            home: Название домашней команды
            away: Название гостевой команды

        Returns:
            dict: Результат прогноза с статусом и данными
        """
        try:
            result = self.prediction_engine.predict_match(home, away)

            if "error" in result:
                return {
                    "status": "error",
                    "message": result["error"]
                }

            # Добавляем метаданные
            result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            result["version"] = self.version

            # Сохраняем в Learning DB (для истории)
            self.learning_db.add_learning_record({
                "type": "prediction",
                "home": home,
                "away": away,
                "result": result,
                "version": self.version
            })

            return {
                "status": "success",
                "data": result
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    # =====================================
    # COMPARE WITH ACTUAL
    # =====================================

    def compare_with_actual(self, match: str, actual_result: str) -> dict:
        """
        Сравнение прогноза с фактическим результатом

        Args:
            match: Название матча (например, "Зенит-Спартак")
            actual_result: Фактический счет (например, "2:1")

        Returns:
            dict: Результат сравнения
        """
        # Ищем прогноз в памяти
        for record in self.learning_db.memory:
            if record.get("type") == "prediction":
                data = record.get("result", {})
                if f"{data.get('home')}-{data.get('away')}" == match:
                    faj_pred = data.get("top_scores", [{}])[0].get("score", "—")
                    break
        else:
            return {
                "status": "error",
                "message": f"Прогноз для матча {match} не найден"
            }

        # Сравниваем
        comparison = self.learning_db.compare_prediction(
            match=match,
            faj_pred=faj_pred,
            expert_pred="—",  # Пока нет экспертного ввода
            actual=actual_result
        )

        return {
            "status": "success",
            "data": comparison
        }

    # =====================================
    # ROUND PROCESSING
    # =====================================

    def process_round(self, round_number: int, results: list) -> dict:
        """
        Обработка тура: сравнение прогнозов с фактами

        Args:
            round_number: Номер тура
            results: Список матчей с результатами

        Returns:
            dict: Статистика обработки
        """
        errors = 0
        comparisons = []

        for match in results:
            home = match.get("home")
            away = match.get("away")
            actual = match.get("actual")

            if not home or not away or not actual:
                continue

            # Находим прогноз FAJ для этого матча
            faj_pred = "—"
            for record in self.learning_db.memory:
                if record.get("type") == "prediction":
                    data = record.get("result", {})
                    if data.get("home") == home and data.get("away") == away:
                        faj_pred = data.get("top_scores", [{}])[0].get("score", "—")
                        break

            # Сравниваем
            if faj_pred != actual:
                errors += 1

            comparison = self.learning_db.compare_prediction(
                match=f"{home}-{away}",
                faj_pred=faj_pred,
                expert_pred=match.get("expert", "—"),
                actual=actual
            )
            comparisons.append(comparison)

        # Обновляем веса, если есть ошибки
        if errors > 0:
            current_weights = self.learning_db.get_current_weights()
            # Простая корректировка: увеличиваем вес атаки и защиты
            new_weights = current_weights.copy()
            new_weights["attack"] = min(current_weights.get("attack", 0.18) + 0.01, 0.25)
            new_weights["defense"] = min(current_weights.get("defense", 0.18) + 0.01, 0.25)

            self.learning_db.update_weights(
                new_weights,
                f"Корректировка после тура {round_number} (ошибок: {errors})"
            )

        return {
            "round": round_number,
            "total_matches": len(results),
            "errors": errors,
            "accuracy": round((len(results) - errors) / len(results) * 100, 1) if results else 0,
            "comparisons": comparisons
        }

    # =====================================
    # TEAM MANAGEMENT
    # =====================================

    def get_team_passport(self, team_name: str) -> dict:
        """Получить паспорт команды"""
        return self.learning_db.get_team_passport(team_name)

    def get_all_teams(self) -> list:
        """Получить список всех команд"""
        return self.learning_db.get_all_teams()

    def update_team_passport(self, team_name: str, data: dict) -> None:
        """Обновить паспорт команды"""
        self.learning_db.update_team_passport(team_name, data)

    # =====================================
    # STATUS API
    # =====================================

    def status(self) -> dict:
        """Получить статус системы"""
        stats = self.learning_db.get_learning_stats()

        return {
            "version": self.version,
            "teams": stats.get("teams_count", 0),
            "passports": stats.get("teams_count", 0),
            "memory": stats.get("total_records", 0),
            "weights_updates": stats.get("weights_updates", 0),
            "comparisons": stats.get("comparisons", 0),
            "last_update": stats.get("last_update", "—"),
            "model_events": 0,
            "team_events": 0,
            "system_events": 1
        }

    # =====================================
    # EXPLANATION LAYER
    # =====================================

    def generate_explanation(self, result: dict) -> list:
        """Генерация объяснения прогноза"""
        reasons = []

        xg = result.get("xg", {})
        probability = result.get("probability", {})

        if xg.get("home_xg", 0) > xg.get("away_xg", 0):
            reasons.append("🏠 Преимущество атаки хозяев")
        else:
            reasons.append("✈️ Гостевая атака выглядит сильнее")

        if probability.get("P1", 0) > probability.get("P2", 0):
            reasons.append("📈 FAJ склоняется к победе хозяев")
        elif probability.get("P2", 0) > probability.get("P1", 0):
            reasons.append("📈 FAJ склоняется к победе гостей")
        else:
            reasons.append("⚖️ Матч имеет высокий риск ничьей")

        confidence = result.get("confidence", 0)
        if confidence > 70:
            reasons.append(f"🎯 Высокая уверенность модели ({confidence}%)")
        elif confidence > 50:
            reasons.append(f"📊 Средняя уверенность модели ({confidence}%)")
        else:
            reasons.append(f"⚠️ Низкая уверенность модели ({confidence}%)")

        return reasons

    # =====================================
    # TERMINAL
    # =====================================

    def print_status(self) -> None:
        """Вывод статуса в терминал"""
        data = self.status()

        print()
        print("========== FAJ CORE v10 ==========")
        for k, v in data.items():
            print(f"{k}: {v}")
        print("=================================")


if __name__ == "__main__":
    core = FAJCore()
    core.print_status()

    # Тестовый прогноз
    print("\n🔮 Тестовый прогноз Зенит vs Спартак:")
    result = core.predict_match("Зенит", "Спартак")
    if result["status"] == "success":
        data = result["data"]
        print(f"  xG: {data['xg']['home_xg']} - {data['xg']['away_xg']}")
        print(f"  Вероятности: П1 {data['probability']['P1']}% | X {data['probability']['X']}% | П2 {data['probability']['P2']}%")
        print(f"  Уверенность: {data['confidence']}%")
        print(f"  Лучшая ставка: {data['best_bet']}")

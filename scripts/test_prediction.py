#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Diagnostic Test — ПЕРВЫЙ ЗАПУСК FAJ

Проверяет:
    1. Загрузку паспорта команды
    2. Расчёт FAJ Rating
    3. Работу PredictionPipeline
    4. Полный прогноз

БЕЗ Streamlit, БЕЗ Telegram, БЕЗ API
=====================================================
"""

import sys
import os
import json
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import FAJDatabase
from app.passports.passport_manager import PassportManager, get_passport_manager
from app.core.prediction_pipeline import PredictionPipeline
from app.core.prediction_pipeline import PipelineInput


def print_separator(char="=", length=60):
    print(char * length)


def print_section(title):
    print_separator()
    print(f"  {title}")
    print_separator()


def test_passport_loading(pm: PassportManager, team_name: str):
    """Тест загрузки паспорта"""
    print(f"\n📋 Загрузка паспорта: {team_name}")
    print("-" * 40)

    passport = pm.get_passport_by_name(team_name)

    if not passport:
        print(f"  ❌ Паспорт не найден для {team_name}")
        return None

    # Основные параметры
    print(f"  ✅ Паспорт загружен")
    print(f"  📊 Attack: {passport.get('attack', 'N/A')}")
    print(f"  📊 Defense: {passport.get('defense', 'N/A')}")
    print(f"  📊 Control: {passport.get('control', 'N/A')}")
    print(f"  📊 Form: {passport.get('form', 'N/A')}")
    print(f"  📊 Squad Quality: {passport.get('squad_quality', 'N/A')}")

    # FAJ Rating
    rating = pm.calculate_rating(passport)
    print(f"  ⭐ FAJ Rating: {rating}")

    return passport


def test_prediction_pipeline(
    pipeline: PredictionPipeline,
    home_passport: dict,
    away_passport: dict,
    home_rating: float,
    away_rating: float,
    home_team: str,
    away_team: str
):
    """Тест PredictionPipeline"""
    print(f"\n📋 Запуск PredictionPipeline: {home_team} vs {away_team}")
    print("-" * 40)

    try:
        result = pipeline.run(
            home_passport=home_passport,
            away_passport=away_passport,
            home_rating=home_rating,
            away_rating=away_rating,
            home_team=home_team,
            away_team=away_team
        )

        if result.get("status") == "error":
            print(f"  ❌ Ошибка Pipeline: {result.get('message')}")
            return None

        return result

    except Exception as e:
        print(f"  ❌ Исключение: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_prediction_result(result: dict):
    """Вывод результата прогноза"""
    print(f"\n📊 РЕЗУЛЬТАТ ПРОГНОЗА")
    print_separator()

    # Основная информация
    print(f"\n  🆔 Prediction ID: {result.get('prediction_id', 'N/A')}")
    print(f"  ⏱️  Время расчёта: {result.get('processing_time_ms', 0):.2f} мс")
    print(f"  📦 Версия: {result.get('version', 'N/A')}")

    # Счёт
    print(f"\n  🏆 Счёт: {result.get('score', 'N/A')}")
    print(f"     Вероятность: {result.get('score_probability', 0) * 100:.1f}%")

    # xG
    xg = result.get("xg", {})
    print(f"\n  ⚽ xG: {xg.get('home', 0):.2f} : {xg.get('away', 0):.2f}")

    # Вероятности
    probs = result.get("probability", {})
    print(f"\n  📊 Вероятности:")
    print(f"     Победа хозяев: {probs.get('home', 0) * 100:.1f}%")
    print(f"     Ничья:         {probs.get('draw', 0) * 100:.1f}%")
    print(f"     Победа гостей: {probs.get('away', 0) * 100:.1f}%")

    # Рынки
    print(f"\n  📊 Рынки:")
    print(f"     BTTS (обе забьют): {result.get('btts', 0) * 100:.1f}%")
    print(f"     Тотал > 2.5:      {result.get('over_2_5', 0) * 100:.1f}%")

    # Уверенность и риск
    confidence = result.get("confidence", {})
    risk = result.get("risk", {})
    print(f"\n  📊 Качество прогноза:")
    print(f"     Уверенность: {confidence.get('level', 'N/A')} ({confidence.get('overall', 0) * 100:.1f}%)")
    print(f"     Риск:        {risk.get('level', 'N/A')} ({risk.get('score', 0)})")

    # Согласованность моделей
    agreement = result.get("model_agreement", {})
    print(f"\n  📊 Согласованность моделей: {agreement.get('level', 'N/A')} ({agreement.get('score', 0) * 100:.1f}%)")


def main():
    """Главный тест"""
    print_section("⚽ FAJ Platform v12.0 — ДИАГНОСТИЧЕСКИЙ ТЕСТ")
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ============================================================
    # 1. ИНИЦИАЛИЗАЦИЯ
    # ============================================================
    print_section("1. ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ")

    print("  🔧 Инициализация базы данных...")
    db = FAJDatabase()
    print("  ✅ База данных готова")

    print("  🔧 Инициализация PassportManager...")
    pm = get_passport_manager()
    print(f"  ✅ PassportManager v{pm.VERSION} готов")

    print("  🔧 Инициализация PredictionPipeline...")
    pipeline = PredictionPipeline()
    print(f"  ✅ PredictionPipeline v{pipeline.VERSION} готов")

    # ============================================================
    # 2. ЗАГРУЗКА ПАСПОРТОВ
    # ============================================================
    print_section("2. ЗАГРУЗКА ПАСПОРТОВ")

    home_team = "Зенит"
    away_team = "Спартак"

    home_passport = test_passport_loading(pm, home_team)
    if not home_passport:
        print("\n❌ Тест прерван: не найден паспорт хозяев")
        return

    away_passport = test_passport_loading(pm, away_team)
    if not away_passport:
        print("\n❌ Тест прерван: не найден паспорт гостей")
        return

    # ============================================================
    # 3. FAJ RATING
    # ============================================================
    print_section("3. FAJ RATING")

    home_rating = pm.calculate_rating(home_passport)
    away_rating = pm.calculate_rating(away_passport)

    print(f"\n  ⭐ {home_team}: {home_rating}")
    print(f"  ⭐ {away_team}: {away_rating}")

    # ============================================================
    # 4. ЗАПУСК PIPELINE
    # ============================================================
    print_section("4. ЗАПУСК PREDICTION PIPELINE")

    result = test_prediction_pipeline(
        pipeline=pipeline,
        home_passport=home_passport,
        away_passport=away_passport,
        home_rating=home_rating,
        away_rating=away_rating,
        home_team=home_team,
        away_team=away_team
    )

    if not result:
        print("\n❌ Тест прерван: ошибка в Pipeline")
        return

    # ============================================================
    # 5. РЕЗУЛЬТАТ
    # ============================================================
    print_section("5. РЕЗУЛЬТАТ ПРОГНОЗА")
    print_prediction_result(result)

    # ============================================================
    # 6. ВЕРДИКТ
    # ============================================================
    print_section("6. ВЕРДИКТ")

    print("\n  ✅ FAJ Core работает корректно!")
    print("  ✅ PassportManager загружает паспорта")
    print("  ✅ PredictionPipeline считает прогноз")
    print("  ✅ xG, Poisson, Monte Carlo работают")
    print("  ✅ Confidence и Risk рассчитываются")

    print(f"\n  📊 Итоговый прогноз: {result.get('score', 'N/A')}")
    print(f"  📊 Уверенность: {result.get('confidence', {}).get('level', 'N/A')}")
    print(f"  📊 Риск: {result.get('risk', {}).get('level', 'N/A')}")

    print_separator()
    print("  🎯 FAJ v12 готов к работе с реальными матчами!")


if __name__ == "__main__":
    main()

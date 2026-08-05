#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Test Prediction (ГЛАВНЫЙ)

Проверяет полную цепочку:
    PredictionManager → PassportManager → Pipeline → Database

Включая крайние случаи:
    - несуществующие команды
    - одинаковые команды
    - пустые имена
    - None
    - пробелы
=====================================================
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.prediction.prediction_manager import get_prediction_manager
from app.database import FAJDatabase
from app.config import config


def check_result_structure(prediction: dict) -> bool:
    """Проверка структуры результата (обязательные + желательные)"""
    required = ["score", "xg", "probability", "confidence", "risk"]
    optional = ["prediction_id", "score_probability", "btts", "over_2_5", "model_agreement", "version", "processing_time_ms"]

    for key in required:
        if key not in prediction:
            print(f"  ❌ Отсутствует обязательное поле: {key}")
            return False

    for key in optional:
        if key not in prediction:
            print(f"  ⚠️ Отсутствует желательное поле: {key}")

    return True


def test_prediction(
    home_team: str,
    away_team: str,
    league: str = "RPL",
    verbose: bool = False,
    expect_error: bool = False
) -> bool:
    pm = get_prediction_manager()
    db = FAJDatabase()

    display_home = home_team if home_team is not None else "None"
    display_away = away_team if away_team is not None else "None"
    print(f"\n📋 Прогноз: {display_home} vs {display_away} ({league})")
    print("-" * 40)

    start_time = time.time()

    try:
        result = pm.predict(
            home_team=home_team,
            away_team=away_team,
            league=league
        )
    except Exception as e:
        if expect_error:
            print(f"  ✅ Ожидаемая ошибка: {e}")
            return True
        else:
            print(f"  ❌ Неожиданное исключение: {e}")
            return False

    elapsed_ms = (time.time() - start_time) * 1000

    if expect_error:
        if result.get("status") == "error":
            print(f"  ✅ Ожидаемая ошибка: {result.get('message')}")
            return True
        else:
            print(f"  ❌ Ожидалась ошибка, но прогноз выполнен")
            return False

    if result.get("status") == "error":
        print(f"  ❌ Ошибка: {result.get('message')}")
        return False

    prediction = result.get("prediction", {})
    if not prediction:
        prediction = result

    # 1. Структура
    if not check_result_structure(prediction):
        return False

    # 2. Проверки
    score = prediction.get("score", "")
    if not score:
        print("  ❌ Счёт не должен быть пустым")
        return False

    xg = prediction.get("xg", {})
    home_xg = xg.get("home", 0)
    away_xg = xg.get("away", 0)

    if not (0.1 <= home_xg <= 4.0):
        print(f"  ❌ xG хозяев вне допустимого диапазона: {home_xg}")
        return False

    if not (0.1 <= away_xg <= 4.0):
        print(f"  ❌ xG гостей вне допустимого диапазона: {away_xg}")
        return False

    probs = prediction.get("probability", {})
    home_prob = probs.get("home", 0)
    draw_prob = probs.get("draw", 0)
    away_prob = probs.get("away", 0)

    total = home_prob + draw_prob + away_prob
    if not (0.99 <= total <= 1.01):
        print(f"  ❌ Сумма вероятностей должна быть 1.0, получено {total:.3f}")
        return False

    confidence = prediction.get("confidence", {})
    overall = confidence.get("overall", 0)
    if not (0 <= overall <= 1):
        print(f"  ❌ Уверенность вне допустимого диапазона: {overall}")
        return False

    btts = prediction.get("btts", 0)
    if not (0 <= btts <= 1):
        print(f"  ❌ BTTS вне допустимого диапазона: {btts}")
        return False

    over_2_5 = prediction.get("over_2_5", 0)
    if not (0 <= over_2_5 <= 1):
        print(f"  ❌ Over 2.5 вне допустимого диапазона: {over_2_5}")
        return False

    agreement = prediction.get("model_agreement", {})
    agreement_score = agreement.get("score", 0)
    if not (0 <= agreement_score <= 1):
        print(f"  ❌ Model Agreement вне допустимого диапазона: {agreement_score}")
        return False

    print("  ✅ Прогноз получен")

    if verbose:
        print(f"\n  📊 Результат:")
        print(f"     Счёт: {score}")
        print(f"     xG: {home_xg:.2f} : {away_xg:.2f}")
        print(f"     П1: {home_prob*100:.1f}%")
        print(f"     X:  {draw_prob*100:.1f}%")
        print(f"     П2: {away_prob*100:.1f}%")
        print(f"     Уверенность: {confidence.get('level', 'N/A')} ({overall*100:.1f}%)")
        print(f"     Время: {elapsed_ms:.0f} мс")

    # Время: <500 отлично, 500-3000 предупреждение, >3000 ошибка
    if elapsed_ms > 3000:
        print(f"  ❌ Время расчёта: {elapsed_ms:.0f} мс (превышен лимит 3000 мс)")
        return False
    elif elapsed_ms > 500:
        print(f"  ⚠️ Время расчёта: {elapsed_ms:.0f} мс (медленно)")

    # Проверка сохранения в БД (только если включено)
    if config.SAVE_TO_GOLD_DATASET:
        prediction_id = prediction.get("prediction_id", "")
        if prediction_id:
            try:
                exists = db.prediction_exists(prediction_id)
                if exists:
                    print("  ✅ Прогноз сохранён в БД")
                else:
                    print("  ⚠️ Прогноз не найден в БД")
            except Exception as e:
                print(f"  ⚠️ Ошибка проверки БД: {e}")
    else:
        print("  ℹ️ Сохранение прогнозов отключено (SAVE_TO_GOLD_DATASET=False)")

    return True


def test_edge_cases(prediction_manager) -> bool:
    """Тест крайних случаев"""
    print("\n📋 Тест крайних случаев")
    print("-" * 40)

    cases = [
        ("НесуществующаяКоманда", "Спартак", True, "несуществующая команда"),
        ("Зенит", "Зенит", True, "одинаковые команды"),
        ("", "Спартак", True, "пустое имя"),
        ("Зенит", "", True, "пустое имя"),
        ("", "", True, "пустые имена"),
        ("   ", "Спартак", True, "пробелы"),
        ("Зенит", "   ", True, "пробелы"),
        (None, "Спартак", True, "None"),
        ("Зенит", None, True, "None"),
    ]

    all_ok = True
    for home, away, expect_error, desc in cases:
        print(f"\n  📋 {desc}: '{home}' vs '{away}'")
        ok = test_prediction(home, away, expect_error=expect_error)
        if ok:
            print(f"    ✅ OK")
        else:
            print(f"    ❌ FAIL")
            all_ok = False

    return all_ok


def main():
    print("\n" + "=" * 60)
    print("⚽ FAJ Platform v12.0 — TEST PREDICTION (ГЛАВНЫЙ)")
    print("=" * 60)

    pm = get_prediction_manager()

    # 1. Обычные тесты
    test_cases = [
        ("Зенит", "Спартак"),
        ("ЦСКА", "Краснодар"),
        ("Динамо", "Ростов")
    ]

    results = []
    for home, away in test_cases:
        ok = test_prediction(home, away, verbose=True)
        results.append((f"{home} vs {away}", ok))

    # 2. Крайние случаи
    edge_ok = test_edge_cases(pm)

    print("\n" + "-" * 40)
    print("📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")

    passed = sum(1 for _, ok in results if ok)

    for name, ok in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")

    icon = "✅" if edge_ok else "❌"
    print(f"  {icon} Крайние случаи")

    print(f"\n  Успешно: {passed}/{len(results)} (обычные) + {'✅' if edge_ok else '❌'} (крайние)")

    if passed == len(results) and edge_ok:
        print("\n  🎯 FAJ v12 готов к работе с реальными матчами!")
    else:
        print("\n  ⚠️ Есть проблемы, требуется проверка")

    print("=" * 60)


if __name__ == "__main__":
    main()

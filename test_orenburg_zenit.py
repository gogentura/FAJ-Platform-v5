#!/usr/bin/env python3

import logging

from app.replay.historical_replay import HistoricalReplay


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


replay = HistoricalReplay()

result = replay.run_tour(2)

print("\n" + "=" * 70)
print("ОТЧЁТ: ОРЕНБУРГ vs ЗЕНИТ")
print("=" * 70)

found = False

for comp in result.get("comparison", []):

    if (
        comp.get("home_team") == "Оренбург"
        and comp.get("away_team") == "Зенит"
    ):

        found = True

        print(f"Прогноз:       {comp.get('predicted_score')}")
        print(f"Факт:          {comp.get('actual_score')}")
        print(
            f"Исход:         "
            f"{'✅' if comp.get('result_correct') else '❌'}"
        )
        print(
            f"Точный счёт:   "
            f"{'✅' if comp.get('score_correct') else '❌'}"
        )
        print(
            f"xG:            "
            f"{comp.get('xg_home_pred')} : "
            f"{comp.get('xg_away_pred')}"
        )
        print(
            f"Уверенность:   "
            f"{comp.get('confidence', 0) * 100:.1f}%"
        )
        print(f"Risk:           {comp.get('risk')}")
        print("=" * 70)


if not found:
    print("❌ Оренбург vs Зенит не найден в результате Replay")

print("\nСТАТУС REPLAY:")
print(result.get("status"))
print(f"Матчей: {result.get('total_matches')}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.brain.brain_manager import FAJBrainManager


print("=" * 50)
print("FAJ Brain Test")
print("=" * 50)


brain = FAJBrainManager()


# сохраняем тестовый прогноз

prediction = {

    "xg_home": 1.65,
    "xg_away": 0.95,

    "home_win": 55.5,
    "draw": 25.0,
    "away_win": 19.5,

    "top_scores": [
        {
            "score": "2:1",
            "prob": 18.5
        }
    ]

}


result = brain.save_prediction(
    "Спартак-ЦСКА",
    prediction
)


print("\nПрогноз сохранён:")
print(result)



# добавляем результат

result = brain.add_result(
    "Спартак-ЦСКА",
    "2:1"
)


print("\nРезультат добавлен:")
print(result)



# смотрим статус мозга

print("\nСтатус мозга:")

print(
    brain.get_status()
)

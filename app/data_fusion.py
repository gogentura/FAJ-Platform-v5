"""
Data Fusion Layer — приводит данные из разных API к единому формату
с указанием источника каждого поля.
"""

def normalize_team_data(raw_data: dict, source: str) -> dict:
    if source == "api-football":
        return _normalize_from_api_football(raw_data)
    elif source == "football-data":
        return _normalize_from_football_data(raw_data)
    else:
        raise ValueError(f"Неизвестный источник: {source}")

def _normalize_from_api_football(data: dict) -> dict:
    return {
        "team": data.get("team", ""),
        "league": data.get("league", ""),
        "matches": data.get("matches", []),
        "historical_xg": {
            "value": data.get("avg_xg", 0.0),
            "source": "api-football"
        },
        "predicted_xg": {
            "value": data.get("avg_xg", 0.0),  # пока такой же, позже будем пересчитывать
            "source": "faj"
        },
        "avg_goals": {
            "value": data.get("avg_goals", 0.0),
            "source": "api-football"
        },
        "avg_goals_conceded": {
            "value": data.get("avg_goals_conceded", 0.0),
            "source": "api-football"
        },
        "avg_possession": {
            "value": data.get("avg_possession", 50.0),
            "source": "api-football"
        },
        "form": data.get("form_index", 70)
    }

def _normalize_from_football_data(data: dict) -> dict:
    # Здесь НЕТ реального xG — оставляем только FAJ Predicted
    return {
        "team": data.get("team", ""),
        "league": data.get("league", ""),
        "matches": data.get("matches", []),
        "historical_xg": {
            "value": None,
            "source": None
        },
        "predicted_xg": {
            "value": data.get("faj_xg", 1.3),  # рассчитывается FAJ
            "source": "faj"
        },
        "avg_goals": {
            "value": data.get("avg_goals", 0.0),
            "source": "football-data"
        },
        "avg_goals_conceded": {
            "value": data.get("avg_goals_conceded", 0.0),
            "source": "football-data"
        },
        "avg_possession": {
            "value": data.get("avg_possession", 50.0),
            "source": "football-data"
        },
        "form": data.get("form_index", 70)
    }

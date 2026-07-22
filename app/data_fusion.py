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
    # Возвращаем структуру с вложенными объектами
    return {
        "team": data.get("team", ""),
        "league": data.get("league", ""),
        "matches": data.get("matches", []),
        "xg": {
            "historical": {
                "value": data.get("avg_xg", 0.0),
                "source": "api-football"
            },
            "predicted": {
                "value": None,  # будет рассчитано во время прогноза
                "source": None
            }
        },
        "goals": {
            "scored": {
                "value": data.get("avg_goals", 0.0),
                "source": "api-football"
            },
            "conceded": {
                "value": data.get("avg_goals_conceded", 0.0),
                "source": "api-football"
            }
        },
        "possession": {
            "value": data.get("avg_possession", 50.0),
            "source": "api-football"
        },
        "form": data.get("form_index", 70)
    }

def _normalize_from_football_data(data: dict) -> dict:
    # Нет реального xG, исторический xG = None, predicted рассчитает FAJ
    return {
        "team": data.get("team", ""),
        "league": data.get("league", ""),
        "matches": data.get("matches", []),
        "xg": {
            "historical": {
                "value": None,
                "source": None
            },
            "predicted": {
                "value": None,
                "source": None
            }
        },
        "goals": {
            "scored": {
                "value": data.get("avg_goals", 0.0),
                "source": "football-data"
            },
            "conceded": {
                "value": data.get("avg_goals_conceded", 0.0),
                "source": "football-data"
            }
        },
        "possession": {
            "value": data.get("avg_possession", 50.0),
            "source": "football-data"
        },
        "form": data.get("form_index", 70)
    }

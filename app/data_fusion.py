"""
FAJ Data Fusion Layer
FAJ Platform v5.1
"""


def normalize_team_data(raw_data: dict, source: str):

    return {

        "avg_goals": raw_data.get(
            "avg_goals",
            {
                "value": 1.5,
                "source": source
            }
        ),

        "avg_goals_conceded": raw_data.get(
            "avg_goals_conceded",
            {
                "value": 1.0,
                "source": source
            }
        ),

        "avg_possession": raw_data.get(
            "avg_possession",
            {
                "value": 50,
                "source": source
            }
        ),

        "historical_xg": raw_data.get(
            "historical_xg",
            {
                "value": 1.4,
                "source": source
            }
        ),

        "form": {
            "value": 0.5,
            "source": "faj"
        }
    }

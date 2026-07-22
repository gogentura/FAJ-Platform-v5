"""
FAJ Data Fusion Layer
FAJ Platform v5.1
Compatibility adapter
"""


def normalize_team_data(raw_data: dict, source: str):

    # xG
    if "historical_xg" in raw_data:
        xg_value = raw_data["historical_xg"].get(
            "value",
            1.4
        )
    else:
        xg_value = 1.4


    # Goals
    avg_goals = raw_data.get(
        "avg_goals",
        {
            "value": 1.5,
            "source": source
        }
    )

    avg_conceded = raw_data.get(
        "avg_goals_conceded",
        {
            "value": 1.0,
            "source": source
        }
    )


    possession = raw_data.get(
        "avg_possession",
        {
            "value": 50,
            "source": source
        }
    )


    return {

        # Старый формат FAJ
        "xg": {
            "value": xg_value,
            "source": source
        },


        # Новый формат
        "historical_xg": {
            "value": xg_value,
            "source": source
        },


        "avg_goals": avg_goals,


        "avg_goals_conceded": avg_conceded,


        "avg_possession": possession,


        "form": {
            "value": 0.5,
            "source": "faj"
        },


        "team_strength": {
            "value": 70,
            "source": "faj"
        }
    }

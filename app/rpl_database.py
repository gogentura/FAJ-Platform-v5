from app.passport_manager import save_passport


RPL_TEAMS = {

    "Зенит": {
        "attack": 88,
        "defense": 79,
        "form_index": 84,
        "historical_xg_value": 1.8
    },

    "Краснодар": {
        "attack": 80,
        "defense": 77,
        "form_index": 79,
        "historical_xg_value": 1.55
    },

    "Локомотив": {
        "attack": 81,
        "defense": 78,
        "form_index": 87,
        "historical_xg_value": 1.6
    },

    "Динамо": {
        "attack": 80,
        "defense": 78,
        "form_index": 81,
        "historical_xg_value": 1.5
    },

    "Спартак": {
        "attack": 80,
        "defense": 76,
        "form_index": 76,
        "historical_xg_value": 1.45
    },

    "ЦСКА": {
        "attack": 78,
        "defense": 80,
        "form_index": 79,
        "historical_xg_value": 1.4
    }

}


def load_rpl_database():

    for team, data in RPL_TEAMS.items():

        save_passport(
            team,
            {
                "league": "РПЛ",
                **data
            }
        )


    return True

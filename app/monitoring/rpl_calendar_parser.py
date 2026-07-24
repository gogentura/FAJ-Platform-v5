# =====================================================
# FAJ Platform v6.1
# app/monitoring/rpl_calendar_parser.py
#
# RPL Calendar Parser
# Source: Sport-Express / PremierLiga
# =====================================================


import re
from datetime import datetime

from bs4 import BeautifulSoup

from app.monitoring.sources.sportexpress import (
    SportExpressSource
)



# =====================================================
# CONFIG
# =====================================================


RPL_CALENDAR_URL = (

    "https://www.sport-express.ru/"
    "football/L/russia/premier/"
    "2026-2027/calendar/tours/"

)



SEASON = "2026/27"

LEAGUE = "RPL"




# =====================================================
# RPL TEAMS FILTER
# =====================================================


RPL_TEAMS = {

    "Зенит",
    "Ростов",
    "Спартак",
    "Динамо М",
    "ЦСКА",
    "Краснодар",
    "Локомотив",
    "Ахмат",
    "Рубин",
    "Крылья Советов",
    "Балтика",
    "Акрон",
    "Оренбург",
    "Факел",
    "Динамо Мх",
    "Родина"

}




# =====================================================
# CLEAN TEXT
# =====================================================


def clean_text(text):


    if not text:

        return ""



    text = text.strip()


    text = re.sub(
        r"\s+",
        " ",
        text
    )


    return text




# =====================================================
# CHECK TEAM
# =====================================================


def is_rpl_team(name):


    name = clean_text(name)


    return name in RPL_TEAMS




# =====================================================
# PARSE DATE
# =====================================================


def parse_date(value):


    if not value:

        return ""



    value = clean_text(value)



    formats = [

        "%d.%m.%Y",

        "%Y-%m-%d"

    ]



    for fmt in formats:


        try:


            return datetime.strptime(
                value,
                fmt
            ).strftime(
                "%Y-%m-%d"
            )


        except:


            pass



    return value




# =====================================================
# MAIN PARSER
# =====================================================


def parse_rpl_calendar():


    source = SportExpressSource()



    html = source.get_page(

        RPL_CALENDAR_URL

    )



    if not html:


        return []




    soup = BeautifulSoup(

        html,

        "html.parser"

    )



    fixtures = []



    current_round = 0



    # ищем текстовые блоки

    items = soup.find_all(

        [
            "div",
            "tr",
            "li"
        ]

    )




    for item in items:



        text = clean_text(

            item.get_text(
                " ",
                strip=True
            )

        )



        if not text:


            continue




        # -------------------------
        # тур
        # -------------------------


        round_match = re.search(

            r"(\d+)\s*тур",

            text,
            re.IGNORECASE

        )



        if round_match:


            current_round = int(

                round_match.group(1)

            )



        # -------------------------
        # команды
        # -------------------------


        found = []



        for team in RPL_TEAMS:


            if team in text:


                found.append(team)




        if len(found) != 2:


            continue



        home = found[0]

        away = found[1]



        # защита от дублей

        exists = False



        for f in fixtures:


            if (

                f["home_team"] == home

                and

                f["away_team"] == away

            ):


                exists = True



        if exists:


            continue




        fixtures.append(

            {

                "league":
                    LEAGUE,


                "season":
                    SEASON,


                "round":
                    current_round,


                "match_date":
                    "",


                "home_team":
                    home,


                "away_team":
                    away,


                "status":
                    "scheduled"

            }

        )




    return fixtures




# =====================================================
# TEST
# =====================================================


if __name__ == "__main__":


    data = parse_rpl_calendar()



    print(

        f"FOUND: {len(data)} fixtures"

    )



    for match in data:


        print(

            match["home_team"],

            "-",

            match["away_team"]

        )

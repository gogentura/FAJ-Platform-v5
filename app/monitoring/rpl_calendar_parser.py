# =====================================================
# FAJ Platform v6.1
# app/monitoring/rpl_calendar_parser.py
# RPL Calendar Parser
# Source: Championat
# =====================================================


import requests

from bs4 import BeautifulSoup


# =====================================================
# CONFIG
# =====================================================


CHAMPIONAT_RPL_URL = (
    "https://www.championat.com/football/"
    "_russiapl/tournament/7096/calendar/"
)


RPL_TEAMS = {

    "Зенит",
    "Спартак",
    "ЦСКА",
    "Динамо М",
    "Локомотив",
    "Краснодар",
    "Ростов",
    "Ахмат",
    "Рубин",
    "Крылья Советов",
    "Факел",
    "Оренбург",
    "Балтика",
    "Акрон",
    "Динамо Мх",
    "Родина"

}



# =====================================================
# LOAD PAGE
# =====================================================


def load_page():

    headers = {

        "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64)"
        )

    }


    response = requests.get(

        CHAMPIONAT_RPL_URL,

        headers=headers,

        timeout=20

    )


    response.raise_for_status()


    return response.text




# =====================================================
# NORMALIZE TEAM
# =====================================================


def normalize_team(name):

    if not name:

        return ""


    name = (

        name
        .replace("\n", " ")
        .replace("\xa0", " ")
        .strip()

    )


    aliases = {


        "Динамо М": "Динамо М",

        "Динамо Москва": "Динамо М",


        "Динамо Махачкала":
        "Динамо Мх",


        "Пари НН":
        "Родина"

    }


    return aliases.get(
        name,
        name
    )




# =====================================================
# CHECK RPL TEAM
# =====================================================


def is_rpl_team(team):

    return team in RPL_TEAMS




# =====================================================
# PARSE DATE
# =====================================================


def extract_date(text):

    if not text:

        return ""


    return text.strip()




# =====================================================
# PARSE CALENDAR
# =====================================================


def parse_rpl_calendar():


    html = load_page()


    soup = BeautifulSoup(

        html,

        "html.parser"

    )



    fixtures = []



    # ищем строки календаря

    rows = soup.find_all(

        "tr"

    )



    current_round = 0



    for row in rows:


        text = row.get_text(

            " ",

            strip=True

        )



        if not text:

            continue



        # ---------------------------------------------
        # тур
        # ---------------------------------------------


        if "тур" in text.lower():


            try:

                number = (
                    text.lower()
                    .split("тур")[0]
                    .strip()
                )


                current_round = int(number)


            except:


                continue




        # ---------------------------------------------
        # команды
        # ---------------------------------------------


        cells = row.find_all(

            "td"

        )


        if len(cells) < 2:

            continue



        teams = []


        for cell in cells:


            value = normalize_team(

                cell.get_text(

                    " ",

                    strip=True

                )

            )


            if value:

                teams.append(value)



        if len(teams) < 2:

            continue



        home = teams[0]

        away = teams[1]



        # ---------------------------------------------
        # фильтр мусора
        # ---------------------------------------------


        if not is_rpl_team(home):

            continue


        if not is_rpl_team(away):

            continue



        # дата

        match_date = ""

        for cell in cells:


            value = cell.get_text(

                " ",

                strip=True

            )


            if "2026" in value:

                match_date = extract_date(

                    value

                )

                break




        fixtures.append(

            {

                "league":
                "RPL",


                "season":
                "2026/27",


                "round":
                current_round,


                "date":
                match_date,


                "home":
                home,


                "away":
                away

            }

        )



    return fixtures




# =====================================================
# PUBLIC FUNCTION
# =====================================================


def get_rpl_fixtures():


    fixtures = parse_rpl_calendar()



    # защита от дублей

    unique = []

    exists = set()



    for item in fixtures:


        key = (

            item["round"],

            item["home"],

            item["away"]

        )


        if key not in exists:


            exists.add(key)

            unique.append(item)



    return unique

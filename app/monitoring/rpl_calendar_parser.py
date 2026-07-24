# =====================================================
# FAJ Platform v6.1
# app/monitoring/rpl_calendar_parser.py
#
# RPL Official Calendar Parser
# Source: premierliga.ru
# =====================================================


import re
import requests

from bs4 import BeautifulSoup



# =====================================================
# SOURCE
# =====================================================


RPL_CALENDAR_URL = (

    "https://premierliga.ru/matches/"
    "?tournament=724"
    "&stage=2962"
    "&month=0"
    "&club=0"
    "&match=all"

)



# =====================================================
# RPL TEAMS
# =====================================================


RPL_TEAMS = {

    "Зенит",

    "Акрон",

    "Спартак",

    "Динамо",

    "Динамо М",

    "Динамо Мх",

    "ЦСКА",

    "Краснодар",

    "Локомотив",

    "Ахмат",

    "Ростов",

    "Рубин",

    "Крылья Советов",

    "Балтика",

    "Оренбург",

    "Факел",

    "Родина"

}



# =====================================================
# HTTP
# =====================================================


def get_html():


    headers = {

        "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64)"
        ),

        "Accept-Language":
        "ru-RU"

    }



    response = requests.get(

        RPL_CALENDAR_URL,

        headers=headers,

        timeout=30

    )



    response.raise_for_status()


    return response.text




# =====================================================
# NORMALIZE
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


        "Динамо Москва":

        "Динамо М",



        "Динамо Махачкала":

        "Динамо Мх"


    }



    return aliases.get(

        name,

        name

    )




# =====================================================
# TEAM CHECK
# =====================================================


def is_rpl_team(team):

    return team in RPL_TEAMS




# =====================================================
# DATE PARSER
# =====================================================


def extract_date(text):


    if not text:

        return ""



    match = re.search(

        r"\d{2}\.\d{2}\.\d{4}",

        text

    )



    if match:

        return match.group(0)



    return text.strip()




# =====================================================
# ROUND PARSER
# =====================================================


def extract_round(text):


    if not text:

        return 1



    match = re.search(

        r"(\d+)\s*тур",

        text.lower()

    )



    if match:

        return int(

            match.group(1)

        )



    return 1




# =====================================================
# PARSER
# =====================================================


def parse_rpl_calendar():


    html = get_html()



    soup = BeautifulSoup(

        html,

        "html.parser"

    )



    fixtures = []



    current_round = 1



    rows = soup.find_all(

        ["tr", "div"]

    )



    for row in rows:



        text = row.get_text(

            " ",

            strip=True

        )



        if not text:

            continue




        # тур


        if "тур" in text.lower():


            current_round = extract_round(

                text

            )




        teams = []



        for team in RPL_TEAMS:


            if team in text:

                teams.append(team)




        if len(teams) < 2:

            continue




        home = teams[0]

        away = teams[1]



        home = normalize_team(

            home

        )


        away = normalize_team(

            away

        )




        if not is_rpl_team(home):

            continue



        if not is_rpl_team(away):

            continue




        match_date = extract_date(

            text

        )




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



                "match_date":

                match_date,



                "home":

                home,



                "away":

                away,



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
# PUBLIC
# =====================================================


def get_rpl_fixtures():



    fixtures = parse_rpl_calendar()



    result = []

    used = set()



    for fixture in fixtures:



        key = (

            fixture["round"],

            fixture["home_team"],

            fixture["away_team"]

        )



        if key in used:

            continue



        used.add(key)



        result.append(

            fixture

        )



    return result

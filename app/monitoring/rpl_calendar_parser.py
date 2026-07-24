# =====================================================
# FAJ Platform v6.1
# RPL Calendar Parser
# Championat.com
# =====================================================


import re
import requests

from bs4 import BeautifulSoup



URL = (
    "https://www.championat.com/football/"
    "_russiapl/tournament/7096/calendar/"
)



RPL_TEAMS = {

    "Акрон",
    "Зенит",
    "Спартак",
    "Динамо М",
    "ЦСКА",
    "Краснодар",
    "Локомотив",
    "Ахмат",
    "Рубин",
    "Крылья Советов",
    "Балтика",
    "Оренбург",
    "Факел",
    "Динамо Мх",
    "Ростов",
    "Родина"

}



def normalize(text):

    if not text:
        return ""

    text = (
        text
        .replace("\n", " ")
        .replace("\xa0", " ")
        .strip()
    )

    return text




def get_html():

    headers = {

        "User-Agent":
        "Mozilla/5.0"

    }


    r = requests.get(

        URL,

        headers=headers,

        timeout=30

    )


    r.raise_for_status()

    return r.text




def extract_round(text):

    match = re.search(
        r"(\d+)\s*тур",
        text.lower()
    )

    if match:

        return int(
            match.group(1)
        )

    return 1




def parse_rpl_calendar():


    html = get_html()


    soup = BeautifulSoup(

        html,

        "html.parser"

    )


    text = soup.get_text(

        "\n",

        strip=True

    )


    fixtures = []


    current_round = 1



    lines = [

        normalize(x)

        for x in text.split("\n")

        if normalize(x)

    ]



    for i,line in enumerate(lines):


        if "тур" in line.lower():

            current_round = extract_round(
                line
            )



        if line not in RPL_TEAMS:

            continue



        if i + 1 >= len(lines):

            continue



        next_line = lines[i+1]



        if next_line not in RPL_TEAMS:

            continue



        home = line

        away = next_line



        fixtures.append(

            {

                "league":
                "RPL",


                "season":
                "2026/27",


                "round":
                current_round,


                "date":
                "",


                "home":
                home,


                "away":
                away

            }

        )



    return fixtures




def get_rpl_fixtures():

    fixtures = parse_rpl_calendar()


    unique = []

    used = set()



    for f in fixtures:


        key = (

            f["home"],

            f["away"]

        )


        if key not in used:

            used.add(key)

            unique.append(f)



    return unique

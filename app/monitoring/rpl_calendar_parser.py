# =====================================================
# FAJ Platform v6.1
# RPL Calendar Parser
# Источник: Championship / Sport sites
# Назначение: обновление fixtures
# =====================================================


import re
import requests
from bs4 import BeautifulSoup



# =====================================================
# CONFIG
# =====================================================


RPL_URL = (
    "https://www.championat.com/football/"
    "_russiapl/tournament/7096/calendar/"
)


HEADERS = {

    "User-Agent":
    (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64)"
    )

}



# =====================================================
# TEAM NORMALIZATION
# =====================================================


TEAM_ALIASES = {


    "Динамо Махачкала":
        "Динамо Мх",


    "Динамо Москва":
        "Динамо М",


    "Крылья Советов":
        "Крылья Советов",


    "Зенит":
        "Зенит",


    "Спартак Москва":
        "Спартак",


    "ЦСКА":
        "ЦСКА"

}



def normalize_team(name):

    if not name:
        return ""


    name = (
        name
        .strip()
        .replace("\n", "")
    )


    return TEAM_ALIASES.get(
        name,
        name
    )



# =====================================================
# PARSE DATE
# =====================================================


def extract_date(text):

    if not text:
        return ""


    pattern = (
        r"\d{2}\.\d{2}\.\d{4}"
    )


    match = re.search(
        pattern,
        text
    )


    if match:

        day, month, year = (
            match.group(0)
            .split(".")
        )


        return (
            f"{year}-{month}-{day}"
        )


    return ""



# =====================================================
# LOAD HTML
# =====================================================


def get_page():

    response = requests.get(

        RPL_URL,

        headers=HEADERS,

        timeout=20

    )


    response.raise_for_status()


    return response.text



# =====================================================
# MAIN PARSER
# =====================================================


def parse_rpl_calendar():


    html = get_page()


    soup = BeautifulSoup(
        html,
        "html.parser"
    )



    fixtures = []



    # ищем строки календаря

    rows = soup.find_all(
        [
            "tr",
            "div"
        ]
    )



    current_round = 0



    for row in rows:


        text = row.get_text(
            " ",
            strip=True
        )



        if not text:

            continue



        # определяем тур


        round_match = re.search(

            r"(\d+)\s*тур",

            text.lower()

        )


        if round_match:


            current_round = int(

                round_match.group(1)

            )



        # ищем пары команд


        if "—" not in text:

            continue



        parts = text.split(
            "—"
        )



        if len(parts) != 2:

            continue



        home = normalize_team(
            parts[0]
        )


        away = normalize_team(
            parts[1]
        )



        if (

            len(home) < 2

            or

            len(away) < 2

        ):

            continue



        fixture = {


            "league":

            "RPL",



            "season":

            "2026/27",



            "round":

            current_round,



            "date":

            extract_date(text),



            "home":

            home,



            "away":

            away

        }



        fixtures.append(
            fixture
        )



    return clean_fixtures(
        fixtures
    )



# =====================================================
# CLEAN DUPLICATES
# =====================================================


def clean_fixtures(fixtures):


    result = []


    seen = set()



    for item in fixtures:


        key = (

            item["round"],

            item["home"],

            item["away"]

        )



        if key in seen:

            continue



        seen.add(key)


        result.append(
            item
        )



    return result



# =====================================================
# GET TOUR
# =====================================================


def get_rpl_round(
    round_number
):


    fixtures = parse_rpl_calendar()


    return [

        f

        for f in fixtures

        if f["round"] == round_number

    ]



# =====================================================
# TEST
# =====================================================


if __name__ == "__main__":


    matches = parse_rpl_calendar()



    for match in matches:


        print(

            match

        )

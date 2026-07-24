# =====================================================
# FAJ Platform v6.0
# Passport Analysis Manager
# Team Passport Analytics Layer
# =====================================================


from app.database import get_db




# =====================================================
# GET TEAM PASSPORT
# =====================================================


def get_passport(team_name):


    conn = get_db()


    try:


        row = conn.execute(

            """

            SELECT *

            FROM passports

            WHERE team = ?

            """,

            (
                team_name,
            )

        ).fetchone()



        if row:

            return dict(row)



        return None



    finally:


        conn.close()




# =====================================================
# SAFE VALUE
# =====================================================


def safe_value(
    passport,
    field,
    default=70
):


    value = passport.get(
        field
    )



    if value is None:

        return default



    try:

        return round(
            float(value),
            1
        )


    except:


        return default




# =====================================================
# BUILD TEAM ANALYSIS
# =====================================================


def build_team_analysis(
    team_name
):


    passport = get_passport(
        team_name
    )



    if not passport:


        return {


            "team":

            team_name,


            "found":

            False


        }




    return {


        "team":

        team_name,


        "found":

        True,



        "attack":

        safe_value(
            passport,
            "attack"
        ),



        "defense":

        safe_value(
            passport,
            "defense"
        ),



        "control":

        safe_value(
            passport,
            "control"
        ),



        "efficiency":

        safe_value(
            passport,
            "efficiency"
        ),



        "mentality":

        safe_value(
            passport,
            "mentality"
        ),



        "form":

        safe_value(
            passport,
            "form_index"
        ),



        "home_rating":

        safe_value(
            passport,
            "home_rating"
        ),



        "away_rating":

        safe_value(
            passport,
            "away_rating"
        ),



        "fitness":

        safe_value(
            passport,
            "fitness"
        ),



        "injury":

        safe_value(
            passport,
            "injury_index",
            0
        ),



        "fatigue":

        safe_value(
            passport,
            "fatigue_index",
            0
        )

    }




# =====================================================
# COMPARE TWO TEAMS
# =====================================================


def compare_teams(
    home_team,
    away_team
):


    home = build_team_analysis(
        home_team
    )


    away = build_team_analysis(
        away_team
    )



    if not home["found"] or not away["found"]:


        return {


            "error":

            "Паспорт команды не найден"


        }




    comparison = {


        "attack_difference":

        round(
            home["attack"]
            -
            away["attack"],
            1
        ),



        "defense_difference":

        round(
            home["defense"]
            -
            away["defense"],
            1
        ),



        "form_difference":

        round(
            home["form"]
            -
            away["form"],
            1
        ),



        "control_difference":

        round(
            home["control"]
            -
            away["control"],
            1
        )

    }



    return {


        "home":

        home,


        "away":

        away,


        "comparison":

        comparison

    }




# =====================================================
# FORMAT FOR TELEGRAM
# =====================================================


def format_passport_block(
    home_team,
    away_team
):


    data = compare_teams(

        home_team,

        away_team

    )



    if "error" in data:


        return (

            "📚 Паспорт данных недоступен"

        )



    home = data["home"]

    away = data["away"]



    return f"""

📚 Анализ команд


🏠 {home_team}

⚔️ Атака: {home['attack']}
🛡 Защита: {home['defense']}
🎮 Контроль: {home['control']}
📈 Форма: {home['form']}


🚩 {away_team}

⚔️ Атака: {away['attack']}
🛡 Защита: {away['defense']}
🎮 Контроль: {away['control']}
📈 Форма: {away['form']}

"""

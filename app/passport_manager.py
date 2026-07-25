# =====================================================
# FAJ Platform v6.3
# app/passport_manager.py
#
# TEAM PASSPORT MANAGER
# PostgreSQL
# =====================================================


from app.database import get_db


# =====================================================
# ALIASES
# =====================================================

ALIASES = {

    "Зенит": "Зенит",
    "Зенит СПб": "Зенит",

    "Краснодар": "Краснодар",

    "Локомотив": "Локомотив",

    "Динамо": "Динамо М",
    "Динамо Москва": "Динамо М",

    "Спартак": "Спартак",

    "ЦСКА": "ЦСКА",

    "Ахмат": "Ахмат",

    "Рубин": "Рубин",

    "Ростов": "Ростов",

    "Балтика": "Балтика",

    "Акрон": "Акрон",

    "Оренбург": "Оренбург",

    "Факел": "Факел",

    "Крылья": "Крылья Советов",

    "Динамо Мх": "Динамо Мх",

    "Родина": "Родина"

}



# =====================================================
# GET TEAM BY ALIAS
# =====================================================

def get_team_by_alias(name):

    return ALIASES.get(
        name,
        name
    )



# =====================================================
# SAVE PASSPORT
# =====================================================

def save_passport(
    team,
    passport
):

    conn = get_db()


    cur = conn.cursor()


    real_team = get_team_by_alias(team)


    cur.execute(

    """

    INSERT INTO team_passports
    (

        league,

        season,

        team,


        attack,

        defense,

        control,


        efficiency,

        mentality,

        discipline,

        fitness,

        predictability,


        xg_for,

        xg_against,


        form,


        injury_index,

        fatigue_index,

        transfer_index


    )


    VALUES

    (

        %s,%s,%s,

        %s,%s,%s,

        %s,%s,%s,%s,%s,

        %s,%s,

        %s,

        %s,%s,%s

    )


    ON CONFLICT

    (

        league,

        season,

        team

    )


    DO UPDATE SET


        attack = EXCLUDED.attack,

        defense = EXCLUDED.defense,

        control = EXCLUDED.control,

        efficiency = EXCLUDED.efficiency,

        mentality = EXCLUDED.mentality,

        discipline = EXCLUDED.discipline,

        fitness = EXCLUDED.fitness,

        predictability = EXCLUDED.predictability,

        xg_for = EXCLUDED.xg_for,

        xg_against = EXCLUDED.xg_against,

        form = EXCLUDED.form,

        injury_index = EXCLUDED.injury_index,

        fatigue_index = EXCLUDED.fatigue_index,

        transfer_index = EXCLUDED.transfer_index,

        updated = NOW()

    """,


    (

        passport.get(
            "league",
            "RPL"
        ),

        passport.get(
            "season",
            "2026/27"
        ),

        real_team,


        passport.get(
            "attack",
            70
        ),

        passport.get(
            "defense",
            70
        ),

        passport.get(
            "control",
            70
        ),


        passport.get(
            "efficiency",
            70
        ),

        passport.get(
            "mentality",
            70
        ),

        passport.get(
            "discipline",
            70
        ),

        passport.get(
            "fitness",
            70
        ),

        passport.get(
            "predictability",
            70
        ),


        passport.get(
            "xg_for",
            1.3
        ),

        passport.get(
            "xg_against",
            1.3
        ),


        passport.get(
            "form",
            70
        ),


        passport.get(
            "injury_index",
            0
        ),

        passport.get(
            "fatigue_index",
            0
        ),

        passport.get(
            "transfer_index",
            0
        )

    )


    )


    conn.commit()

    conn.close()



# =====================================================
# INIT ALIASES
# =====================================================

def init_default_aliases():

    return True

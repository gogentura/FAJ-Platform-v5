from aiogram import types
import traceback

from app.utils.formatter import format_prediction
from app.utils.explainer import explain_prediction
from app.database import get_db
from app.handlers.keyboard import get_main_keyboard


# =====================================================
# LOAD PASSPORT
# =====================================================

def load_passport(team):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM passports
        WHERE team = ?
        """,
        (team,)
    ).fetchone()

    conn.close()

    return dict(row) if row else None



# =====================================================
# PREDICT HANDLER
# =====================================================

async def handle_predict(
    message: types.Message,
    core,
    journal
):

    text = (message.text or "").strip()



    # ===============================
    # IGNORE MENU BUTTONS
    # ===============================

    ignore_buttons = [

        "📈 Прогноз",

        "📋 Последние прогнозы",

        "⚽ Статус",

        "📁 Паспорта",

        "🔄 Загрузить паспорта",

        "/start"

    ]


    if text in ignore_buttons:

        return



    # ===============================
    # REMOVE PREFIX
    # ===============================

    if text.lower().startswith("прогноз "):

        text = text[9:].strip()



    parts = text.split()



    # ===============================
    # CHECK MATCH FORMAT
    # ===============================

    if len(parts) < 2:

        return



    home = parts[0]

    away = parts[1]


    league = "RPL"



    if len(parts) >= 3:

        lg = parts[2].upper()

        if lg in [

            "RPL",
            "EPL",
            "UCL",
            "LALIGA",
            "SERIEA",
            "BUNDESLIGA",
            "LIGUE1"

        ]:

            league = lg



    await message.answer(

        f"⏳ Анализирую матч\n\n"
        f"{home} — {away}",

        reply_markup=get_main_keyboard()

    )



    try:


        # ===============================
        # CORE
        # ===============================

        result = core.predict_match(

            home,

            away,

            league

        )



        if "error" in result:

            raise Exception(

                result["error"]

            )



        if "xg" not in result:

            raise Exception(

                "FAJ Core не вернул xG"

            )



        # ===============================
        # XG
        # ===============================

        xg = result["xg"].get(

            "predicted",

            {}

        )


        xg_home = float(

            xg.get(

                "home",

                0

            )

        )


        xg_away = float(

            xg.get(

                "away",

                0

            )

        )



        # ===============================
        # PASSPORTS
        # ===============================

        home_pass = load_passport(home) or {}

        away_pass = load_passport(away) or {}



        factors = explain_prediction(

            home_pass,

            away_pass,

            xg_home,

            xg_away,

            league

        )



        # ===============================
        # FORMAT MESSAGE
        # ===============================

        answer = format_prediction(

            home,

            away,

            league,

            {
                "home": xg_home,

                "away": xg_away

            },

            result["decision"],

            result.get(

                "top_scores",

                []

            ),

            result.get(

                "btts",

                0

            ),

            result.get(

                "over25",

                0

            ),

            factors

        )



        # ===============================
        # JOURNAL
        # ===============================

        journal.save(

            match=f"{home} — {away}",


            prediction={


                "winner":

                result["decision"].get(

                    "winner_name",

                    ""

                ),


                "winner_probability":

                float(

                    result["decision"].get(

                        "winner_probability",

                        0

                    )

                ),


                "xg_home":

                xg_home,


                "xg_away":

                xg_away,


                "expected_score":

                result["decision"].get(

                    "expected_score",

                    ""

                ),


                "confidence":

                float(

                    result["decision"].get(

                        "confidence",

                        0

                    )

                ),


                "top_scores":

                result.get(

                    "top_scores",

                    []

                ),


                "btts":

                float(

                    result.get(

                        "btts",

                        0

                    )

                ),


                "over25":

                float(

                    result.get(

                        "over25",

                        0

                    )

                )

            }

        )



        await message.answer(

            answer,

            parse_mode="Markdown",

            reply_markup=get_main_keyboard()

        )



    except Exception as e:


        print(

            traceback.format_exc()

        )


        await message.answer(

            "❌ Ошибка модели\n\n"

            f"{type(e).__name__}\n\n"

            f"{str(e)}",

            reply_markup=get_main_keyboard()

        )

# =====================================================
# FAJ Platform v6.3
# app/debug_prediction.py
#
# Prediction structure debugger
# =====================================================


import json
import logging


from aiogram import types


logger = logging.getLogger(__name__)



async def cmd_debug_prediction(

    message: types.Message,

    core

):


    text = message.text.replace(
        "/debug_prediction",
        ""
    ).strip()


    if not text:

        await message.answer(

            "Пример:\n\n"
            "/debug_prediction Акрон Зенит"

        )

        return



    parts = text.split()


    home = parts[0]

    away = " ".join(
        parts[1:]
    )


    try:


        result = core.predict_match(

            home,

            away,

            "RPL"

        )



        debug = {


            "TYPE":

                str(type(result)),


            "RESULT":

                result,


            "DECISION":

                result.get(
                    "decision"
                )
                if isinstance(result,dict)
                else None,


            "XG":

                result.get(
                    "xg"
                )
                if isinstance(result,dict)
                else None,


            "SIMULATION":

                result.get(
                    "simulation"
                )
                if isinstance(result,dict)
                else None

        }



        await message.answer(

            "🧪 FAJ DEBUG\n\n"
            +
            json.dumps(

                debug,

                ensure_ascii=False,

                indent=2

            )[:4000]

        )



    except Exception as e:


        await message.answer(

            f"❌ DEBUG ERROR\n\n"
            f"{type(e).__name__}\n"
            f"{str(e)}"

        )

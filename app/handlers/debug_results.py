# =====================================================
# FAJ Platform v6.6
# Debug Results Handler
# =====================================================


from aiogram.types import Message


from app.monitoring.sources.soccer365 import (
    Soccer365Source
)



async def cmd_debug_results(
    message: Message
):


    try:


        source = Soccer365Source()



        results = source.parse_results()



        text = """

🧪 FAJ RESULTS DEBUG


Источник:
Soccer365


Найдено результатов:

{}


""".format(

            len(results)

        )



        if results:


            for r in results[:20]:


                text += f"""

⚽ {r.get('home_team')}
-
{r.get('away_team')}

🎯 {r.get('home_score')}
:
{r.get('away_score')}

"""


        else:


            text += """

❌ Результаты не найдены.


Возможные причины:

• Soccer365 изменил HTML
• нужен другой URL результатов
• матчи находятся в другом разделе

"""



        await message.answer(

            text

        )


    except Exception as e:


        await message.answer(

            f"""

❌ DEBUG RESULTS ERROR


{type(e).__name__}


{e}

"""

        )

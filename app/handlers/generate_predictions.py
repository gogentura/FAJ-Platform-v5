# =====================================================
# FAJ Platform v6.9.2
# app/handlers/generate_predictions.py
#
# Generate Tour Predictions
# =====================================================

import logging

from aiogram.types import Message

from app.managers.prediction_manager import (
    save_predictions_batch,
    get_predictions
)

from app.services.tour_predictor import (
    TourPredictor
)

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# CLEAR OLD PREDICTIONS
# =====================================================

def clear_predictions():

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM predictions
            """
        )

        conn.commit()
        conn.close()

        logger.info(
            "Old predictions cleared"
        )

        return True

    except Exception as e:

        logger.error(
            "Clear predictions error: %s",
            e,
            exc_info=True
        )

        return False



# =====================================================
# GENERATE TOUR
# =====================================================

async def cmd_generate_predictions(
    message: Message
):

    try:

        await message.answer(
            """
🚀 FAJ генерация прогноза тура...

🧠 Engine v6.9.2
🎲 Monte Carlo 10000
"""
        )


        # 1. очищаем старый тур

        clear_predictions()



        # 2. создаём predictor

        predictor = TourPredictor()



        # 3. получаем прогнозы

        result = predictor.generate_tour()



        if not result:


            await message.answer(
                """
❌ FAJ не получил прогнозы.

Проверьте календарь матчей.
"""
            )

            return



        fixtures = result.get(
            "fixtures",
            []
        )


        predictions = result.get(
            "predictions",
            []
        )



        if not fixtures or not predictions:


            await message.answer(
                """
❌ Пустой результат прогнозирования.
"""
            )

            return



        # 4. сохраняем

        saved = save_predictions_batch(
            fixtures,
            predictions
        )



        logger.info(
            "Saved predictions: %s",
            saved
        )



        # 5. ответ

        await message.answer(

f"""
✅ FAJ прогнозы тура созданы

⚽ Матчей:
{len(predictions)}

💾 Сохранено:
{saved}

🤖 FAJ Engine v6.9.2

Открыть:

🤖 FAJ прогнозы
"""

        )



    except Exception as e:


        logger.exception(
            "Generate predictions error"
        )


        await message.answer(

f"""
❌ FAJ ПРОГНОЗ ERROR

{type(e).__name__}

{str(e)}

"""
        )

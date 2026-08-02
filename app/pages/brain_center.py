#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center

Центр управления мозгом FAJ:
- память
- обучение
- анализ ошибок
- корректировки модели
"""

import streamlit as st
import json
import os

from app.brain.memory_brain import FAJMemoryBrain
from app.brain.learning_brain import FAJLearningBrain
from app.brain.correction_brain import FAJCorrectionBrain


DATA_DIR = "data"


def render():

    st.markdown("# 🧠 FAJ Brain Center v10.0")

    st.info(
        """
        Здесь работает обучающий слой FAJ:
        
        Memory Brain → хранит прогнозы и результаты

        Learning Brain → ищет ошибки

        Correction Brain → предлагает изменения модели
        """
    )


    # =====================================
    # ИНИЦИАЛИЗАЦИЯ
    # =====================================

    memory = FAJMemoryBrain()
    learning = FAJLearningBrain()
    correction = FAJCorrectionBrain()



    # =====================================
    # СТАТУС
    # =====================================

    st.markdown("## 📊 Статус мозга")


    stats = memory.get_statistics()


    col1, col2, col3 = st.columns(3)


    with col1:
        st.metric(
            "Прогнозов в памяти",
            stats["total_predictions"]
        )


    with col2:
        st.metric(
            "Завершённых матчей",
            stats["finished_matches"]
        )


    with col3:
        st.metric(
            "Точность",
            f'{stats["accuracy"]}%'
        )



    st.divider()



    # =====================================
    # СОЗДАНИЕ ТЕСТОВОЙ ПАМЯТИ
    # =====================================

    st.markdown("## 🧠 Память FAJ")


    if st.button(
        "➕ Создать тестовый прогноз",
        use_container_width=True
    ):


        prediction = {

            "top_scores":[
                {
                    "score":"2:1",
                    "prob":35
                }
            ],

            "xg_home":1.8,

            "xg_away":1.1

        }


        memory.save_prediction(
            "Спартак-ЦСКА",
            prediction
        )


        st.success(
            "Прогноз сохранён. Создан faj_memory.json"
        )



    memory_file = os.path.join(
        DATA_DIR,
        "faj_memory.json"
    )


    if os.path.exists(memory_file):

        st.success(
            "✅ faj_memory.json существует"
        )

    else:

        st.warning(
            "Память пока пустая"
        )



    st.divider()



    # =====================================
    # АНАЛИЗ
    # =====================================

    st.markdown(
        "## 🔍 Анализ ошибок"
    )


    if st.button(
        "Провести анализ ошибок",
        use_container_width=True
    ):


        result = learning.analyze_history()


        st.json(result)



    st.divider()



    # =====================================
    # КОРРЕКТИРОВКА
    # =====================================

    st.markdown(
        "## ⚙️ Корректировка модели"
    )


    if st.button(
        "Создать рекомендации FAJ",
        use_container_width=True
    ):


        result = correction.create_correction()


        st.success(
            "Корректировка создана"
        )


        st.json(result)



    st.divider()



    # =====================================
    # ИСТОРИЯ
    # =====================================

    st.markdown(
        "## 📚 История корректировок"
    )


    history = correction.get_history()


    if history:

        st.json(history)

    else:

        st.info(
            "История корректировок пока пустая"
        )



if __name__ == "__main__":

    render()

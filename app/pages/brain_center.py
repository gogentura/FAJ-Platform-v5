#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center
Панель управления искусственным интеллектом FAJ
"""

import streamlit as st
import json
import os
from datetime import datetime


DATA_DIR = "data"


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)

    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def render():

    st.markdown("# 🧠 FAJ Brain Center")

    st.info(
        """
        Центральная панель мозга FAJ.

        Здесь будут:
        - память модели
        - обучение на результатах
        - корректировка ошибок
        - анализ качества прогнозов
        """
    )


    # ==============================
    # СТАТУС МОЗГА
    # ==============================

    st.markdown("## 📊 Статус системы")


    try:

        from app.brain.memory_brain import FAJMemoryBrain
        from app.brain.learning_brain import FAJLearningBrain
        from app.brain.correction_brain import FAJCorrectionBrain


        memory = FAJMemoryBrain()
        learning = FAJLearningBrain()
        correction = FAJCorrectionBrain()


        col1, col2, col3 = st.columns(3)


        with col1:
            status = memory.get_status()

            st.metric(
                "Память",
                status.get("records", 0)
            )


        with col2:

            status = learning.get_status()

            st.metric(
                "Обучение",
                status.get("cycles", 0)
            )


        with col3:

            status = correction.get_status()

            st.metric(
                "Коррекции",
                status.get("corrections", 0)
            )


    except Exception as e:

        st.error(
            f"Ошибка подключения Brain: {e}"
        )



    st.divider()


    # ==============================
    # ПАМЯТЬ
    # ==============================

    st.markdown("## 🗃 Память FAJ")


    memory_file = load_json(
        "brain_memory.json"
    )


    if memory_file:

        st.json(memory_file)

    else:

        st.warning(
            "Память пока пустая"
        )



    st.divider()



    # ==============================
    # ОБУЧЕНИЕ
    # ==============================

    st.markdown("## 🔄 Обучение модели")


    if st.button(
        "Запустить цикл обучения",
        use_container_width=True
    ):

        try:

            from app.brain.learning_brain import FAJLearningBrain

            brain = FAJLearningBrain()

            result = brain.learn()

            st.success(
                "Цикл обучения завершён"
            )

            st.json(result)


        except Exception as e:

            st.error(
                str(e)
            )



    st.divider()



    # ==============================
    # КОРРЕКТИРОВКИ
    # ==============================


    st.markdown(
        "## 🔧 Коррекция прогнозов"
    )


    if st.button(
        "Анализ ошибок FAJ",
        use_container_width=True
    ):


        try:

            from app.brain.correction_brain import FAJCorrectionBrain


            brain = FAJCorrectionBrain()

            result = brain.analyze_errors()


            st.success(
                "Анализ завершён"
            )

            st.json(result)


        except Exception as e:

            st.error(
                str(e)
            )



    st.caption(
        f"FAJ Brain v10.0 | {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

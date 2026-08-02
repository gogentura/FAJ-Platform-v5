#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center

Центр управления мозгом FAJ:
- память
- обучение
- анализ ошибок
- корректировки
"""

import streamlit as st
import json
import os
from datetime import datetime


DATA_DIR = "data"



# =====================================================
# ЗАГРУЗКА JSON
# =====================================================

def load_json(filename):

    path = os.path.join(
        DATA_DIR,
        filename
    )

    if not os.path.exists(path):
        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return {}



# =====================================================
# ОСНОВНАЯ СТРАНИЦА
# =====================================================

def render():


    st.markdown(
        "# 🧠 FAJ Brain Center"
    )


    st.info(
        """
FAJ Brain v10.0

Модули:

🗃 Memory Brain  
📚 Learning Brain  
🔧 Correction Brain  

Мозг анализирует прогнозы,
результаты и ошибки модели.
"""
    )



    # =================================================
    # ПОДКЛЮЧЕНИЕ BRAIN
    # =================================================

    try:

        from app.brain.memory_brain import FAJMemoryBrain
        from app.brain.learning_brain import FAJLearningBrain
        from app.brain.correction_brain import FAJCorrectionBrain


        memory = FAJMemoryBrain()
        learning = FAJLearningBrain()
        correction = FAJCorrectionBrain()


    except Exception as e:

        st.error(
            f"Ошибка загрузки Brain: {e}"
        )

        return



    # =================================================
    # СТАТУС
    # =================================================

    st.markdown(
        "## 📊 Статус мозга"
    )


    col1, col2, col3 = st.columns(3)


    memory_status = memory.get_status()
    learning_status = learning.get_status()
    correction_status = correction.get_status()



    with col1:

        st.metric(
            "🗃 Память",
            memory_status.get(
                "records",
                memory_status.get(
                    "memory_count",
                    0
                )
            )
        )



    with col2:

        st.metric(
            "📚 Циклы обучения",
            learning_status.get(
                "cycles",
                learning_status.get(
                    "learning_cycles",
                    0
                )
            )
        )



    with col3:

        st.metric(
            "🔧 Коррекции",
            correction_status.get(
                "corrections_count",
                0
            )
        )



    st.divider()



    # =================================================
    # ПАМЯТЬ
    # =================================================

    st.markdown(
        "## 🗃 Память FAJ"
    )


    memory_data = load_json(
        "brain_memory.json"
    )


    if memory_data:

        st.json(
            memory_data
        )

    else:

        st.warning(
            "Память пока пустая"
        )



    st.divider()



    # =================================================
    # ОБУЧЕНИЕ
    # =================================================

    st.markdown(
        "## 📚 Обучение модели"
    )


    if st.button(
        "▶ Запустить обучение",
        use_container_width=True
    ):


        try:

            result = learning.learn()


            st.success(
                "Обучение завершено"
            )


            st.json(
                result
            )


        except Exception as e:

            st.error(
                f"Ошибка обучения: {e}"
            )



    st.divider()



    # =================================================
    # КОРРЕКЦИИ
    # =================================================

    st.markdown(
        "## 🔧 Анализ ошибок"
    )


    if st.button(
        "🔍 Найти ошибки FAJ",
        use_container_width=True
    ):


        try:

            result = correction.analyze_errors()


            st.success(
                "Анализ завершён"
            )


            st.json(
                result
            )


        except Exception as e:

            st.error(
                f"Ошибка анализа: {e}"
            )



    st.divider()



    # =================================================
    # ИСТОРИЯ КОРРЕКЦИЙ
    # =================================================

    st.markdown(
        "## 📜 История корректировок"
    )


    history = correction.get_history()


    if history:

        st.dataframe(
            history,
            use_container_width=True
        )

    else:

        st.info(
            "Корректировок пока нет"
        )



    st.caption(
        f"FAJ Brain v10.0 | {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

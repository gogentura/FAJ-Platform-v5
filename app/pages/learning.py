#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Learning Center

Центр обучения FAJ:
- память прогнозов
- анализ ошибок
- поиск закономерностей
- рекомендации модели
"""

import streamlit as st

from app.brain.memory_brain import FAJMemoryBrain
from app.brain.learning_brain import FAJLearningBrain
from app.brain.correction_brain import FAJCorrectionBrain



def render():

    st.markdown("## 🧠 Самообучение FAJ")

    st.divider()


    # ===============================
    # ИНИЦИАЛИЗАЦИЯ МОЗГА
    # ===============================

    memory = FAJMemoryBrain()
    learning = FAJLearningBrain()
    correction = FAJCorrectionBrain()



    # ===============================
    # СТАТУС ПАМЯТИ
    # ===============================

    st.markdown("### 📚 Память FAJ")


    stats = memory.get_statistics()


    col1, col2, col3 = st.columns(3)


    with col1:
        st.metric(
            "Всего прогнозов",
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



    # ===============================
    # АНАЛИЗ ОБУЧЕНИЯ
    # ===============================

    st.markdown("### 📊 Анализ истории")


    if st.button(
        "🔍 Запустить анализ ошибок",
        use_container_width=True
    ):


        result = learning.analyze_history()


        st.success(
            "Анализ завершён"
        )


        st.json(result)



    st.divider()



    # ===============================
    # ПОИСК ПАТТЕРНОВ
    # ===============================

    st.markdown("### 🔎 Поиск слабых мест модели")


    if st.button(
        "🧠 Найти ошибки FAJ",
        use_container_width=True
    ):


        patterns = learning.find_patterns()


        if patterns:

            st.warning(
                "Найдены проблемы:"
            )

            st.json(patterns)

        else:

            st.success(
                "Ошибок пока недостаточно для анализа"
            )



    st.divider()



    # ===============================
    # КОРРЕКТИРОВКА
    # ===============================

    st.markdown("### ⚙️ Корректировка модели")


    if st.button(
        "⚙️ Создать корректировку",
        use_container_width=True
    ):


        result = correction.create_correction()


        st.success(
            "Корректировка создана"
        )

        st.json(result)



    st.divider()



    # ===============================
    # ИСТОРИЯ
    # ===============================

    st.markdown(
        "### 📜 История корректировок"
    )


    history = correction.get_history()


    if history:

        st.json(history)

    else:

        st.info(
            "Корректировок пока нет"
        )

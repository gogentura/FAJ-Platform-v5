#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center

Центр памяти и обучения FAJ
"""

import streamlit as st
import json
import os
import pandas as pd


from app.brain.memory_brain import FAJMemoryBrain
from app.brain.learning_brain import FAJLearningBrain
from app.brain.correction_brain import FAJCorrectionBrain



DATA_DIR = "data"



def render():

    st.markdown("# 🧠 FAJ Brain Center")
    st.caption(
        "Память • обучение • анализ ошибок • корректировка модели"
    )


    memory = FAJMemoryBrain()
    learning = FAJLearningBrain()
    correction = FAJCorrectionBrain()



    # =====================================================
    # СТАТУС МОЗГА
    # =====================================================

    st.markdown("## 🧠 Статус мозга")


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



    # =====================================================
    # ПАМЯТЬ FAJ
    # =====================================================

    st.markdown("## 📂 Память FAJ")


    if st.button(
        "📂 Показать память",
        use_container_width=True
    ):

        records = memory.get_memory()


        if records:

            df = pd.DataFrame(records)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "Память пока пустая"
            )



    st.divider()



    # =====================================================
    # АНАЛИЗ ОБУЧЕНИЯ
    # =====================================================

    st.markdown("## 📊 Обучение")


    if st.button(
        "🔍 Анализ ошибок",
        use_container_width=True
    ):


        result = learning.analyze_history()


        st.json(result)



    st.divider()



    # =====================================================
    # КОРРЕКТИРОВКА
    # =====================================================

    st.markdown("## ⚙️ Корректировка модели")


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



    # =====================================================
    # ИСТОРИЯ
    # =====================================================

    st.markdown("## 📚 История корректировок")


    history = correction.get_history()


    if history:

        st.json(history)


    else:

        st.info(
            "Истории корректировок пока нет"
        )



    st.divider()



    # =====================================================
    # ФАЙЛ ПАМЯТИ
    # =====================================================

    st.markdown("## 💾 Файлы мозга")


    memory_file = os.path.join(
        DATA_DIR,
        "faj_memory.json"
    )


    if os.path.exists(memory_file):

        st.success(
            "✅ faj_memory.json существует"
        )


        size = os.path.getsize(memory_file)


        st.write(
            f"Размер файла: {size} байт"
        )


    else:

        st.warning(
            "faj_memory.json ещё не создан"
        )

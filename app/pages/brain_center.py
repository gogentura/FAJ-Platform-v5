#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center

Центр памяти и обучения FAJ
"""

import streamlit as st
import pandas as pd


from app.brain.memory_brain import FAJMemoryBrain
from app.brain.learning_brain import FAJLearningBrain
from app.brain.correction_brain import FAJCorrectionBrain



def render():

    st.markdown("## 🧠 FAJ Brain Center")

    st.caption(
        "Память, обучение и корректировка модели"
    )


    # =====================================================
    # ИНИЦИАЛИЗАЦИЯ
    # =====================================================

    memory = FAJMemoryBrain()

    learning = FAJLearningBrain()

    correction = FAJCorrectionBrain()



    # =====================================================
    # СТАТУС МОЗГА
    # =====================================================

    st.markdown("### 🧠 Статус мозга")


    stats = memory.get_statistics()


    col1, col2, col3 = st.columns(3)


    with col1:
        st.metric(
            "📚 Всего прогнозов",
            stats["total_predictions"]
        )


    with col2:
        st.metric(
            "✅ Завершённых матчей",
            stats["finished_matches"]
        )


    with col3:
        st.metric(
            "🎯 Точность",
            f'{stats["accuracy"]}%'
        )



    st.divider()



    # =====================================================
    # ПАМЯТЬ FAJ
    # =====================================================

    st.markdown("## 📚 Память FAJ")


    records = memory.get_memory()


    if records:

        rows = []


        for item in records:

            prediction = item.get(
                "prediction",
                {}
            )


            rows.append({

                "Дата":
                    item.get("date",""),

                "Матч":
                    item.get("match",""),

                "Статус":
                    item.get("status",""),

                "Прогноз":
                    prediction.get(
                        "top_scores",
                        [{}]
                    )[0].get(
                        "score",
                        "-"
                    )

            })


        df = pd.DataFrame(rows)


        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


    else:

        st.info(
            "Память FAJ пока пустая"
        )



    st.divider()



    # =====================================================
    # ОБУЧЕНИЕ
    # =====================================================

    st.markdown("## 🤖 Самообучение модели")


    learning_status = learning.get_status()


    col1, col2, col3 = st.columns(3)


    with col1:
        st.metric(
            "Записей в памяти",
            learning_status["samples"]
        )


    with col2:
        st.metric(
            "Точность",
            f'{learning_status["accuracy"]}%'
        )


    with col3:
        st.metric(
            "Готовность",
            "Да" if learning_status["learning_ready"] else "Нет"
        )



    if st.button(
        "🔍 Анализировать ошибки",
        use_container_width=True
    ):

        result = learning.analyze_history()

        st.success(
            "Анализ завершён"
        )

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
    # ИСТОРИЯ КОРРЕКТИРОВОК
    # =====================================================

    st.markdown(
        "## 📜 История корректировок"
    )


    history = correction.get_history()


    if history:

        st.json(history)

    else:

        st.info(
            "Корректировок пока нет"
        )

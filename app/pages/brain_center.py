#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center

Центр управления мозгом FAJ
"""

import streamlit as st
import pandas as pd


from app.brain.memory_brain import FAJMemoryBrain
from app.brain.learning_brain import FAJLearningBrain
from app.brain.correction_brain import FAJCorrectionBrain



def render():

    st.markdown(
        "# 🧠 FAJ Brain Center"
    )

    st.caption(
        "Память • Обучение • Корректировки модели"
    )


    # =====================================
    # ИНИЦИАЛИЗАЦИЯ
    # =====================================

    try:

        memory = FAJMemoryBrain()
        learning = FAJLearningBrain()
        correction = FAJCorrectionBrain()


    except Exception as e:

        st.error(
            f"Ошибка загрузки Brain: {e}"
        )

        return



    # =====================================
    # MEMORY
    # =====================================

    st.markdown(
        "## 🗃 Memory Brain"
    )


    memory_stats = memory.get_statistics()


    col1, col2, col3 = st.columns(3)


    with col1:
        st.metric(
            "Всего прогнозов",
            memory_stats["total_predictions"]
        )


    with col2:
        st.metric(
            "Завершено матчей",
            memory_stats["finished_matches"]
        )


    with col3:
        st.metric(
            "Точность",
            f"{memory_stats['accuracy']}%"
        )



    st.divider()



    # =====================================
    # LEARNING
    # =====================================


    st.markdown(
        "## 📚 Learning Brain"
    )


    learning_status = learning.get_status()


    col1, col2 = st.columns(2)


    with col1:

        st.metric(
            "Обучающих матчей",
            learning_status["samples"]
        )


    with col2:

        st.metric(
            "Accuracy",
            f"{learning_status['accuracy']}%"
        )



    patterns = learning.find_patterns()


    if patterns:

        st.warning(
            "Найдены слабые места модели"
        )

        for p in patterns:

            st.write(
                "⚠️",
                p["message"]
            )

    else:

        st.success(
            "Критических проблем не найдено"
        )



    st.divider()



    # =====================================
    # CORRECTION
    # =====================================


    st.markdown(
        "## 🔧 Correction Brain"
    )


    if st.button(
        "Провести анализ ошибок FAJ",
        use_container_width=True
    ):

        result = correction.create_correction()


        st.success(
            "Анализ выполнен"
        )


        st.json(
            result
        )



    history = correction.get_history()


    if history:


        st.markdown(
            "### История корректировок"
        )


        df = pd.DataFrame(history)

        st.dataframe(
            df,
            use_container_width=True
        )


    else:

        st.info(
            "Корректировок пока нет"
        )



    st.divider()



    # =====================================
    # ПАМЯТЬ МАТЧЕЙ
    # =====================================


    st.markdown(
        "## 📝 Последние записи памяти"
    )


    records = memory.get_memory()


    if records:


        show = []


        for item in records[-10:]:

            show.append({

                "Матч":
                    item.get("match"),

                "Статус":
                    item.get("status"),

                "Прогноз":
                    item.get("prediction",{}).get(
                        "top_scores",
                        "-"
                    ),

                "Результат":
                    item.get(
                        "actual_result",
                        "-"
                    )

            })


        st.dataframe(
            pd.DataFrame(show),
            use_container_width=True
        )


    else:

        st.info(
            "Память FAJ пока пустая"
        )



# Для Streamlit pages

if __name__ == "__main__":

    render()

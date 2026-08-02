#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Brain Center

Центр управления мозгом FAJ:
- память прогнозов
- обучение модели
- анализ ошибок
- рекомендации корректировки
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
        "Adaptive Football Intelligence — память, обучение и корректировка модели"
    )


    # =====================================================
    # ИНИЦИАЛИЗАЦИЯ МОЗГА
    # =====================================================

    memory = FAJMemoryBrain()

    learning = FAJLearningBrain()

    correction = FAJCorrectionBrain()



    # =====================================================
    # ОБЩАЯ СТАТИСТИКА
    # =====================================================

    st.markdown(
        "## 📊 Память FAJ"
    )


    stats = memory.get_statistics()


    col1, col2, col3, col4 = st.columns(4)


    with col1:
        st.metric(
            "Всего прогнозов",
            stats["total_predictions"]
        )


    with col2:
        st.metric(
            "Завершено матчей",
            stats["finished_matches"]
        )


    with col3:
        st.metric(
            "Точных прогнозов",
            stats["correct_predictions"]
        )


    with col4:
        st.metric(
            "Точность",
            f'{stats["accuracy"]}%'
        )



    st.divider()



    # =====================================================
    # АНАЛИЗ ОБУЧЕНИЯ
    # =====================================================

    st.markdown(
        "## 📚 Learning Brain"
    )


    learning_status = learning.get_status()


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "Обучение готово",
            "Да"
            if learning_status["learning_ready"]
            else "Нет"
        )


    with col2:

        st.metric(
            "Точность модели",
            f'{learning_status["accuracy"]}%'
        )


    with col3:

        st.metric(
            "Матчей для анализа",
            learning_status["samples"]
        )



    st.divider()



    # =====================================================
    # ПОИСК ПРОБЛЕМ
    # =====================================================

    st.markdown(
        "## 🔍 Анализ слабых мест"
    )


    patterns = learning.find_patterns()


    if patterns:


        for p in patterns:

            st.warning(
                f"""
                Тип: {p.get('type')}

                {p.get('message')}
                """
            )


    else:

        st.success(
            "Серьёзных проблем модели не обнаружено"
        )



    st.divider()



    # =====================================================
    # КОРРЕКТИРОВКИ
    # =====================================================

    st.markdown(
        "## ⚙️ Correction Brain"
    )


    correction_status = correction.get_status()


    st.write(
        f"Количество анализов корректировки: "
        f"{correction_status['corrections_count']}"
    )



    if st.button(
        "🧠 Запустить анализ ошибок FAJ",
        use_container_width=True
    ):

        result = correction.create_correction()


        st.success(
            "Анализ завершён"
        )


        st.json(
            result
        )



    st.divider()



    # =====================================================
    # ИСТОРИЯ ПАМЯТИ
    # =====================================================

    st.markdown(
        "## 📝 История прогнозов"
    )


    memory_data = memory.get_memory()


    if memory_data:


        rows = []


        for item in memory_data:


            rows.append({

                "Матч":
                    item.get("match"),


                "Статус":
                    item.get("status"),


                "Прогноз":
                    str(
                        item.get("prediction", {})
                        .get("top_scores", [])
                    ),


                "Результат":
                    item.get("actual_result")

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


    st.caption(
        "FAJ Brain v10.0 | Memory → Learning → Correction"
    )

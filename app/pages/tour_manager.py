#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v10.0
Tour Manager

Управление турами + связь с Memory Brain
"""

import streamlit as st
import pandas as pd
import json
import os


DATA_DIR = "data"


# =====================================================
# JSON
# =====================================================

def load_json(filename):

    path = os.path.join(DATA_DIR, filename)

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
        "### 🗓️ Управление турами FAJ"
    )


    from app.database import FAJDatabase

    db = FAJDatabase()


    # =================================================
    # СОСТОЯНИЕ БАЗЫ
    # =================================================

    st.markdown(
        "## 📋 Матчи в базе"
    )


    matches = db.get_matches(limit=1000)


    if matches:

        df = pd.DataFrame(matches)


        columns = [
            c for c in [
                "home_team_name",
                "away_team_name",
                "status",
                "home_goals",
                "away_goals"
            ]
            if c in df.columns
        ]


        st.dataframe(
            df[columns],
            width="stretch",
            hide_index=True
        )


        st.caption(
            f"Всего матчей: {len(matches)}"
        )

    else:

        st.info(
            "Матчей нет"
        )



    st.divider()



    # =================================================
    # ЗАГРУЗКА РЕЗУЛЬТАТОВ
    # =================================================

    st.markdown(
        "## 📊 Обновление результатов"
    )


    result_files = [

        f for f in os.listdir(DATA_DIR)

        if f.endswith("_results.json")

    ]


    if not result_files:

        st.warning(
            "Нет файлов результатов"
        )

        return



    selected = st.selectbox(
        "Выберите результаты",
        result_files
    )


    results = load_json(selected)



    if results:


        st.write(
            f"Найдено результатов: {len(results)}"
        )


        for match, data in results.items():

            st.write(
                match,
                "→",
                data.get(
                    "actual",
                    "-"
                )
            )



    # =================================================
    # ОБНОВЛЕНИЕ
    # =================================================

    if st.button(
        "📥 Обновить результаты и обучить FAJ",
        width="stretch"
    ):


        updated = 0
        memory_added = 0


        # подключаем память

        from app.brain.memory_brain import FAJMemoryBrain


        memory = FAJMemoryBrain()



        matches_db = db.get_matches(
            limit=1000
        )



        for match_name, data in results.items():


            actual = data.get(
                "actual",
                ""
            )


            if ":" not in actual:
                continue



            hg, ag = map(
                int,
                actual.split(":")
            )



            for m in matches_db:


                home = m.get(
                    "home_team_name"
                )

                away = m.get(
                    "away_team_name"
                )


                db_match = (
                    f"{home}-{away}"
                )


                if db_match == match_name:


                    # обновляем БД

                    try:

                        with db._get_connection() as conn:

                            cursor = conn.cursor()


                            cursor.execute(
                                """
                                UPDATE matches
                                SET home_goals=?,
                                    away_goals=?,
                                    status='FT'
                                WHERE id=?
                                """,
                                (
                                    hg,
                                    ag,
                                    m.get("id")
                                )
                            )


                            conn.commit()


                        updated += 1


                    except Exception:

                        pass



                    # добавляем результат в память

                    memory.add_result(
                        match_name,
                        actual
                    )


                    memory.analyze_prediction(
                        match_name
                    )


                    memory_added += 1



        st.success(
            f"""
            ✅ Обновлено матчей: {updated}

            🧠 Добавлено в память: {memory_added}
            """
        )



    st.divider()



    # =================================================
    # СТАТУС ПАМЯТИ
    # =================================================

    st.markdown(
        "## 🧠 Статус памяти FAJ"
    )


    from app.brain.memory_brain import FAJMemoryBrain


    brain = FAJMemoryBrain()


    stats = brain.get_statistics()


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "Прогнозов",
            stats["total_predictions"]
        )


    with col2:

        st.metric(
            "Завершённых",
            stats["finished_matches"]
        )


    with col3:

        st.metric(
            "Точность",
            f"{stats['accuracy']}%"
        )

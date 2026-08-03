#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.1.3
Tour Manager
- создание туров
- загрузка туров
- календарь матчей
- результаты
- память FAJ
"""
import streamlit as st
import json
import os
from datetime import datetime

DATA_DIR = "data"
TOURS_FILE = os.path.join(
    DATA_DIR,
    "tours.json"
)
MEMORY_FILE = os.path.join(
    DATA_DIR,
    "faj_memory.json"
)

# =====================================================
# JSON STORAGE
# =====================================================
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )
    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

# =====================================================
# TOURS
# =====================================================
def load_tours():
    return load_json(
        TOURS_FILE,
        {}
    )

def save_tours(data):
    save_json(
        TOURS_FILE,
        data
    )

# =====================================================
# MEMORY
# =====================================================
def load_memory():
    return load_json(
        MEMORY_FILE,
        []
    )

def save_memory(data):
    save_json(
        MEMORY_FILE,
        data
    )

def add_to_memory(match):
    memory = load_memory()
    memory.append({
        "date":
            datetime.now().isoformat(),
        "match":
            match.get(
                "match"
            ),
        "prediction":
            match.get(
                "faj_prediction"
            ),
        "actual":
            match.get(
                "actual"
            )
    })
    save_memory(
        memory
    )

# =====================================================
# TOUR CREATE
# =====================================================
def create_tour(name):
    tours = load_tours()
    tours[name] = {
        "created":
            datetime.now().isoformat(),
        "matches":[]
    }
    save_tours(
        tours
    )

# =====================================================
# ДОБАВЛЕНИЕ МАТЧА
# =====================================================
def add_match(
        tour_name,
        match_name,
        faj_prediction="",
        expert_prediction="",
        xg_home=None,
        xg_away=None
):
    tours = load_tours()
    if tour_name not in tours:
        return
    tours[tour_name]["matches"].append({
        "match":
            match_name,
        "faj_prediction":
            faj_prediction,
        "expert_prediction":
            expert_prediction,
        "actual":
            "",
        "xg_home":
            xg_home,
        "xg_away":
            xg_away,
        "status":
            "Ожидается"
    })
    save_tours(
        tours
    )

# =====================================================
# ИМПОРТ JSON ТУРА
# =====================================================
def import_tour(file):
    try:
        data = json.load(
            file
        )
    except:
        return None
    matches=[]
    for name, value in data.items():
        matches.append({
            "match":
                name,
            "faj_prediction":
                value.get(
                    "faj_prediction",
                    ""
                ),
            "expert_prediction":
                value.get(
                    "expert_prediction",
                    ""
                ),
            "actual":
                value.get(
                    "actual",
                    ""
                ),
            "xg_home":
                value.get(
                    "xg_home"
                ),
            "xg_away":
                value.get(
                    "xg_away"
                ),
            "status":
                "Ожидается"
        })
    return matches

# =====================================================
# СТАТИСТИКА
# =====================================================
def get_statistics(tour):
    total = len(
        tour.get(
            "matches",
            []
        )
    )
    finished = 0
    for m in tour.get(
        "matches",
        []
    ):
        if m.get(
            "actual"
        ):
            finished += 1
    return {
        "total":
            total,
        "finished":
            finished
    }

# =====================================================
# СОХРАНЕНИЕ РЕЗУЛЬТАТА
# =====================================================
def save_result(
        tour_name,
        index,
        result
):
    tours = load_tours()
    tours[tour_name]["matches"][index]["actual"] = result
    tours[tour_name]["matches"][index]["status"] = "Завершён"
    save_tours(
        tours
    )

# =====================================================
# ОТОБРАЖЕНИЕ МАТЧА
# =====================================================
def show_match(
        tour_name,
        index,
        match
):
    st.markdown(
        f"### ⚽ {match.get('match')}"
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(
            "🤖 FAJ"
        )
        st.info(
            match.get(
                "faj_prediction",
                "-"
            )
        )
    with col2:
        st.write(
            "👤 Эксперт"
        )
        st.warning(
            match.get(
                "expert_prediction",
                "-"
            )
        )
    with col3:
        st.write(
            "🏁 Результат"
        )
        if match.get(
            "actual"
        ):
            st.success(
                match["actual"]
            )
        else:
            st.write(
                "Не сыгран"
            )
    if match.get(
        "xg_home"
    ) is not None:
        c1,c2 = st.columns(2)
        with c1:
            st.metric(
                "xG хозяева",
                match.get(
                    "xg_home"
                )
            )
        with c2:
            st.metric(
                "xG гости",
                match.get(
                    "xg_away"
                )
            )
    if not match.get(
        "actual"
    ):
        result = st.text_input(
            "Ввести счёт",
            key=f"score_{tour_name}_{index}"
        )
        if st.button(
            "💾 Сохранить",
            key=f"save_{tour_name}_{index}"
        ):
            save_result(
                tour_name,
                index,
                result
            )
            st.success(
                "Результат сохранён"
            )
            st.rerun()
    else:
        if st.button(
            "🧠 Добавить в память FAJ",
            key=f"memory_{tour_name}_{index}"
        ):
            add_to_memory(
                match
            )
            st.success(
                "Добавлено в память"
            )
    st.divider()

# =====================================================
# ГЛАВНЫЙ ЭКРАН
# =====================================================
def render():
    st.title(
        "🗓️ Управление турами FAJ"
    )
    # создание файла автоматически
    tours = load_tours()
    # -------------------------------------------------
    # СОЗДАНИЕ ТУРА
    # -------------------------------------------------
    st.subheader(
        "➕ Создать новый тур"
    )
    name = st.text_input(
        "Название",
        "Тур 1"
    )
    if st.button(
        "Создать тур"
    ):
        create_tour(
            name
        )
        st.success(
            "Тур создан"
        )
        st.rerun()
    st.divider()
    # -------------------------------------------------
    # ИМПОРТ
    # -------------------------------------------------
    st.subheader(
        "📥 Загрузить тур"
    )
    uploaded = st.file_uploader(
        "JSON файл",
        type=[
            "json"
        ]
    )
    if uploaded:
        if st.button(
            "Импортировать тур"
        ):
            matches = import_tour(
                uploaded
            )
            tours = load_tours()
            tour_name = (
                f"Тур {len(tours)+1}"
            )
            tours[tour_name]={
                "created":
                    datetime.now().isoformat(),
                "matches":
                    matches
            }
            save_tours(
                tours
            )
            st.success(
                "Тур импортирован"
            )
            st.rerun()
    # -------------------------------------------------
    # СПИСОК ТУРОВ
    # -------------------------------------------------
    tours = load_tours()
    if not tours:
        st.info(
            "Туров пока нет"
        )
        return
    selected = st.selectbox(
        "Выберите тур",
        list(
            tours.keys()
        )
    )
    tour = tours[selected]
    st.divider()
    st.subheader(
        f"📋 {selected}"
    )
    stats = get_statistics(
        tour
    )
    c1,c2 = st.columns(2)
    with c1:
        st.metric(
            "Всего матчей",
            stats["total"]
        )
    with c2:
        st.metric(
            "Завершено",
            stats["finished"]
        )
    # -------------------------------------------------
    # МАТЧИ
    # -------------------------------------------------
    for index, match in enumerate(
        tour.get(
            "matches",
            []
        )
    ):
        show_match(
            selected,
            index,
            match
        )
    # -------------------------------------------------
    # АРХИВ
    # -------------------------------------------------
    st.divider()
    st.subheader(
        "📜 Архив туров"
    )
    archive=[]
    for name,item in tours.items():
        archive.append({
            "Тур":
                name,
            "Матчи":
                len(
                    item.get(
                        "matches",
                        []
                    )
                )
        })
    st.table(
        archive
    )
    # -------------------------------------------------
    # ПАМЯТЬ
    # -------------------------------------------------
    st.divider()
    st.subheader(
        "🧠 Память FAJ"
    )
    memory = load_memory()
    st.metric(
        "Записей",
        len(memory)
    )
    if memory:
        with st.expander(
            "Последние записи"
        ):
            st.json(
                memory[-5:]
            )

# =====================================================
# ЗАПУСК
# =====================================================
if __name__ == "__main__":
    render()

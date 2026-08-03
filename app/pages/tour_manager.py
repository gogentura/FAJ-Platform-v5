#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11
Season Center / Tour Manager
Центр управления сезонами:
- туры
- матчи
- прогнозы
- результаты
- память FAJ
- архив
"""
import streamlit as st
import json
import os
from datetime import datetime
from app.faj_core import FAJCore

# =====================================================
# PATHS
# =====================================================
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
# FAJ ENGINE CONNECTION
# =====================================================
def get_faj_core():
    return FAJCore()

# =====================================================
# GENERATE FAJ PREDICTION
# =====================================================
def generate_prediction(home, away):
    core = get_faj_core()
    result = core.predict_match(
        home,
        away
    )
    if result.get("status") != "success":
        return None
    data = result.get(
        "data",
        {}
    )
    return {
        "score":
            data.get(
                "top_scores",
                [{}]
            )[0].get(
                "score",
                ""
            ),
        "xg_home":
            data.get(
                "xg",
                {}
            ).get(
                "home_xg"
            ),
        "xg_away":
            data.get(
                "xg",
                {}
            ).get(
                "away_xg"
            ),
        "confidence":
            data.get(
                "confidence",
                0
            )
    }

# =====================================================
# STORAGE ENGINE
# =====================================================
def ensure_storage():
    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )
    if not os.path.exists(
        TOURS_FILE
    ):
        save_json(
            TOURS_FILE,
            {}
        )
    if not os.path.exists(
        MEMORY_FILE
    ):
        save_json(
            MEMORY_FILE,
            []
        )

def load_json(
        path,
        default
):
    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(
                file
            )
    except:
        return default

def save_json(
        path,
        data
):
    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

# =====================================================
# DATABASE
# =====================================================
def get_tours():
    ensure_storage()
    return load_json(
        TOURS_FILE,
        {}
    )

def save_tours(
        tours
):
    save_json(
        TOURS_FILE,
        tours
    )

def get_memory():
    ensure_storage()
    return load_json(
        MEMORY_FILE,
        []
    )

def save_memory(
        memory
):
    save_json(
        MEMORY_FILE,
        memory
    )

# =====================================================
# TOUR CREATOR
# =====================================================
def create_tour(
        name
):
    tours = get_tours()
    if name in tours:
        return False
    tours[name] = {
        "created":
            datetime.now().isoformat(),
        "status":
            "active",
        "matches":
            []
    }
    save_tours(
        tours
    )
    return True

# =====================================================
# MATCH OBJECT
# =====================================================
def create_match(
        name,
        faj_prediction="",
        expert_prediction="",
        xg_home=None,
        xg_away=None
):
    return {
        "match":
            name,
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
            "scheduled",
        "memory_saved":
            False
    }

# =====================================================
# ADD MATCH
# =====================================================
def add_match(
        tour_name,
        match
):
    tours = get_tours()
    if tour_name not in tours:
        return False
    tours[tour_name]["matches"].append(
        match
    )
    save_tours(
        tours
    )
    return True

# =====================================================
# IMPORT JSON TOUR
# =====================================================
def import_json_tour(
        uploaded
):
    try:
        data = json.load(
            uploaded
        )
    except:
        return []
    matches=[]
    for name, item in data.items():
        matches.append(
            create_match(
                name,
                item.get(
                    "faj_prediction",
                    ""
                ),
                item.get(
                    "expert_prediction",
                    ""
                ),
                item.get(
                    "xg_home"
                ),
                item.get(
                    "xg_away"
                )
            )
        )
    return matches

# =====================================================
# RESULT UPDATE
# =====================================================
def update_result(
        tour_name,
        index,
        score
):
    tours = get_tours()
    if tour_name not in tours:
        return False
    tours[tour_name]["matches"][index]["actual"] = score
    tours[tour_name]["matches"][index]["status"] = "finished"
    save_tours(
        tours
    )
    return True

# =====================================================
# MEMORY BRAIN
# =====================================================
def send_to_brain(
        match
):
    memory = get_memory()
    if match.get(
        "memory_saved"
    ):
        return
    memory.append({
        "date":
            datetime.now().isoformat(),
        "match":
            match.get(
                "match"
            ),
        "faj_prediction":
            match.get(
                "faj_prediction"
            ),
        "expert_prediction":
            match.get(
                "expert_prediction"
            ),
        "actual":
            match.get(
                "actual"
            )
    })
    match["memory_saved"] = True
    save_memory(
        memory
    )

# =====================================================
# TOUR STATISTICS
# =====================================================
def tour_stats(
        tour
):
    total = len(
        tour.get(
            "matches",
            []
        )
    )
    finished = 0
    correct = 0
    for match in tour.get(
        "matches",
        []
    ):
        if match.get(
            "actual"
        ):
            finished += 1
            if (
                match.get("faj_prediction")
                ==
                match.get("actual")
            ):
                correct += 1
    accuracy = 0
    if finished:
        accuracy = round(
            correct / finished * 100,
            1
        )
    return {
        "total":
            total,
        "finished":
            finished,
        "correct":
            correct,
        "accuracy":
            accuracy
    }

# =====================================================
# MATCH CARD
# =====================================================
def render_match(
        tour_name,
        index,
        match
):
    st.markdown(
        f"### ⚽ {match.get('match')}"
    )
    col1,col2,col3 = st.columns(3)
    with col1:
        st.caption(
            "🤖 FAJ прогноз"
        )
        st.info(
            match.get(
                "faj_prediction",
                "-"
            )
        )
    with col2:
        st.caption(
            "👤 Эксперт"
        )
        st.warning(
            match.get(
                "expert_prediction",
                "-"
            )
        )
    with col3:
        st.caption(
            "🏁 Факт"
        )
        if match.get(
            "actual"
        ):
            st.success(
                match.get(
                    "actual"
                )
            )
        else:
            st.write(
                "Ожидается"
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
    # Ввод результата
    if not match.get(
        "actual"
    ):
        score = st.text_input(
            "Введите счёт",
            key=f"score_{tour_name}_{index}",
            placeholder="2:1"
        )
        if st.button(
            "💾 Сохранить результат",
            key=f"save_{tour_name}_{index}"
        ):
            update_result(
                tour_name,
                index,
                score
            )
            st.success(
                "Результат сохранён"
            )
            st.cache_data.clear()
            st.rerun()
    else:
        if st.button(
            "🧠 Передать в Brain",
            key=f"brain_{tour_name}_{index}"
        ):
            send_to_brain(
                match
            )
            st.success(
                "Матч добавлен в память FAJ"
            )
    st.divider()

# =====================================================
# IMPORT BLOCK
# =====================================================
def import_block():
    st.subheader(
        "📥 Импорт тура"
    )
    uploaded = st.file_uploader(
        "Выберите JSON",
        type=["json"]
    )
    if uploaded:
        if st.button(
            "Импортировать"
        ):
            matches = import_json_tour(
                uploaded
            )
            tours = get_tours()
            name = f"Тур {len(tours)+1}"
            tours[name] = {
                "created":
                    datetime.now().isoformat(),
                "status":
                    "active",
                "matches":
                    matches
            }
            save_tours(
                tours
            )
            st.success(
                f"{name} создан"
            )
            st.rerun()

# =====================================================
# CREATE TOUR BLOCK
# =====================================================
def create_tour_block():
    st.subheader(
        "➕ Создать новый тур"
    )
    name = st.text_input(
        "Название тура",
        placeholder="Тур 1"
    )
    if st.button(
        "Создать тур",
        key="create_tour"
    ):
        if name:
            if create_tour(name):
                st.success(
                    "Тур создан"
                )
                st.rerun()
            else:
                st.warning(
                    "Такой тур уже существует"
                )

# =====================================================
# ARCHIVE
# =====================================================
def render_archive(
        tours
):
    st.subheader(
        "📜 Архив туров"
    )
    archive=[]
    for name,tour in tours.items():
        stat = tour_stats(
            tour
        )
        archive.append({
            "Тур":
                name,
            "Матчи":
                stat["total"],
            "Сыграно":
                stat["finished"],
            "Точность FAJ":
                f'{stat["accuracy"]}%'
        })
    if archive:
        st.table(
            archive
        )

# =====================================================
# MEMORY VIEW
# =====================================================
def render_memory():
    st.subheader(
        "🧠 Память FAJ"
    )
    memory = get_memory()
    col1,col2 = st.columns(2)
    with col1:
        st.metric(
            "Записей",
            len(memory)
        )
    with col2:
        st.metric(
            "Brain статус",
            "ACTIVE"
        )
    if memory:
        with st.expander(
            "Последние записи"
        ):
            st.json(
                memory[-10:]
            )

# =====================================================
# MAIN PAGE
# =====================================================
def render():
    ensure_storage()
    st.title(
        "🏟️ FAJ Season Center v11"
    )
    st.caption(
        "Управление турами, прогнозами и памятью FAJ"
    )
    # создание тура
    create_tour_block()
    st.divider()
    # импорт
    import_block()
    st.divider()
    tours = get_tours()
    if not tours:
        st.info(
            "Туров пока нет. Создайте первый тур."
        )
        render_memory()
        return
    # выбор тура
    selected = st.selectbox(
        "📅 Выберите тур",
        list(
            tours.keys()
        )
    )
    tour = tours[selected]
    st.divider()
    st.subheader(
        f"⚽ {selected}"
    )
    stats = tour_stats(
        tour
    )
    c1,c2,c3 = st.columns(3)
    with c1:
        st.metric(
            "Матчи",
            stats["total"]
        )
    with c2:
        st.metric(
            "Сыграно",
            stats["finished"]
        )
    with c3:
        st.metric(
            "Точность",
            f'{stats["accuracy"]}%'
        )
    st.divider()
    # матчи
    st.subheader(
        "📋 Матчи тура"
    )
    for index,match in enumerate(
        tour.get(
            "matches",
            []
        )
    ):
        render_match(
            selected,
            index,
            match
        )
    st.divider()
    render_archive(
        tours
    )
    st.divider()
    render_memory()

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    render()

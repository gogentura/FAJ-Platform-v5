#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.1
Tour Manager
Центр управления турами:
- календарь матчей
- прогнозы FAJ
- экспертные прогнозы
- фактические результаты
- анализ точности
- передача данных в Brain
"""
import streamlit as st
import json
import os
from datetime import datetime

# =====================================================
# ПУТИ ДАННЫХ
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
# ЗАГРУЗКА ДАННЫХ
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
# ТУРЫ
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
# ПАМЯТЬ FAJ
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

# =====================================================
# СОЗДАНИЕ ТУРА
# =====================================================
def create_tour():
    return {
        "created":
            datetime.now().isoformat(),
        "matches": []
    }

# =====================================================
# ДОБАВЛЕНИЕ МАТЧА
# =====================================================
def add_match(
        tour,
        match_name,
        faj_prediction="",
        expert_prediction=""
):
    match = {
        "match":
            match_name,
        "faj_prediction":
            faj_prediction,
        "expert_prediction":
            expert_prediction,
        "actual":
            "",
        "status":
            "Ожидается",
        "xg_home":
            None,
        "xg_away":
            None
    }
    tour["matches"].append(
        match
    )

# =====================================================
# ПРОВЕРКА РЕЗУЛЬТАТА
# =====================================================
def calculate_status(match):
    if match.get("actual"):
        return "Завершён"
    return "Ожидается"

# =====================================================
# СРАВНЕНИЕ
# =====================================================
def compare_score(
        prediction,
        actual
):
    if not prediction or not actual:
        return False
    return prediction == actual

# =====================================================
# ОТОБРАЖЕНИЕ ОДНОГО МАТЧА
# =====================================================
def show_match(match, index):
    status = calculate_status(match)
    match["status"] = status
    st.markdown(
        f"### ⚽ {match.get('match','')}"
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(
            "🤖 FAJ прогноз"
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
            "🏁 Факт"
        )
        if match.get("actual"):
            st.success(
                match["actual"]
            )
        else:
            st.write(
                "Ожидается"
            )
    # xG
    if match.get("xg_home"):
        c1, c2 = st.columns(2)
        with c1:
            st.metric(
                "xG хозяева",
                match["xg_home"]
            )
        with c2:
            st.metric(
                "xG гости",
                match["xg_away"]
            )
    # Анализ
    if match.get("actual"):
        st.write(
            "📊 Анализ"
        )
        if compare_score(
            match.get("faj_prediction"),
            match.get("actual")
        ):
            st.success(
                "FAJ угадал счёт ✅"
            )
        else:
            st.error(
                "FAJ ошибся ❌"
            )
    st.divider()

# =====================================================
# СОХРАНЕНИЕ РЕЗУЛЬТАТА
# =====================================================
def update_result(
        tours,
        tour_number,
        match_index,
        result
):
    tours[tour_number]["matches"][match_index]["actual"] = result
    tours[tour_number]["matches"][match_index]["status"] = "Завершён"
    save_tours(
        tours
    )

# =====================================================
# ДОБАВЛЕНИЕ В MEMORY BRAIN
# =====================================================
def send_to_memory(
        match
):
    memory = load_memory()
    record = {
        "id":
            len(memory)+1,
        "date":
            datetime.now().isoformat(),
        "match":
            match["match"],
        "prediction":
            {
            "faj_score":
                match.get(
                    "faj_prediction"
                )
            },
        "actual_result":
            match.get(
                "actual"
            ),
        "status":
            "finished"
    }
    memory.append(
        record
    )
    save_memory(
        memory
    )

# =====================================================
# СТАТИСТИКА ТУРА
# =====================================================
def tour_statistics(
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
    for match in tour["matches"]:
        if match.get("actual"):
            finished += 1
            if compare_score(
                match.get(
                    "faj_prediction"
                ),
                match.get(
                    "actual"
                )
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
# ГЛАВНАЯ СТРАНИЦА
# =====================================================
def render():
    st.title(
        "🗓️ Управление турами FAJ"
    )
    tours = load_tours()
    if not tours:
        st.info(
            "Туры пока не загружены"
        )
        st.write(
            "Создайте файл data/tours.json"
        )
        return
    
    tour_list = list(
        tours.keys()
    )
    selected_tour = st.selectbox(
        "Выберите тур",
        tour_list
    )
    tour = tours[selected_tour]
    
    st.subheader(
        f"⚽ {selected_tour}"
    )
    stats = tour_statistics(
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
            "Точность FAJ",
            f'{stats["accuracy"]}%'
        )
    
    # =====================================================
    # СПИСОК МАТЧЕЙ ТУРА
    # =====================================================
    st.subheader(
        "📋 Матчи тура"
    )
    for index, match in enumerate(
        tour.get("matches", [])
    ):
        show_match(
            match,
            index
        )
        # Ввод результата
        if not match.get("actual"):
            with st.expander(
                f"✍️ Внести результат: {match.get('match')}"
            ):
                result = st.text_input(
                    "Фактический счёт",
                    key=f"result_{selected_tour}_{index}",
                    placeholder="Например 2:1"
                )
                if st.button(
                    "💾 Сохранить результат",
                    key=f"save_{selected_tour}_{index}"
                ):
                    update_result(
                        tours,
                        selected_tour,
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
                key=f"memory_{selected_tour}_{index}"
            ):
                send_to_memory(
                    match
                )
                st.success(
                    "Добавлено в Memory Brain"
                )
    
    # =====================================================
    # СОХРАНЕНИЕ ТУРА
    # =====================================================
    save_tours(
        tours
    )
    st.divider()
    
    # =====================================================
    # ОБУЧЕНИЕ ПО ТУРУ
    # =====================================================
    st.subheader(
        "🧠 Обучение FAJ"
    )
    finished_matches = [
        m for m in tour["matches"]
        if m.get("actual")
    ]
    if finished_matches:
        st.write(
            f"Завершённых матчей: {len(finished_matches)}"
        )
        if st.button(
            "🔎 Анализировать ошибки тура"
        ):
            try:
                from app.brain.learning_brain import FAJLearningBrain
                brain = FAJLearningBrain()
                result = brain.analyze_history()
                st.json(
                    result
                )
            except Exception as e:
                st.error(
                    f"Ошибка Brain: {e}"
                )
    else:
        st.info(
            "После завершения матчей здесь появится анализ обучения"
        )
    
    # =====================================================
    # СОСТОЯНИЕ ПАМЯТИ
    # =====================================================
    st.divider()
    st.subheader(
        "🧠 Память FAJ"
    )
    memory = load_memory()
    st.metric(
        "Записей памяти",
        len(memory)
    )
    if memory:
        with st.expander(
            "📜 Последние записи"
        ):
            st.json(
                memory[-5:]
            )

# =====================================================
# ИМПОРТ ТУРА ИЗ JSON
# =====================================================
def import_tour_from_json(uploaded_file):
    try:
        data = json.load(
            uploaded_file
        )
    except Exception:
        return None
    tour = create_tour()
    for match_name, values in data.items():
        match = {
            "match":
                match_name,
            "faj_prediction":
                values.get(
                    "faj_prediction",
                    ""
                ),
            "expert_prediction":
                values.get(
                    "expert_prediction",
                    ""
                ),
            "actual":
                values.get(
                    "actual",
                    ""
                ),
            "status":
                "Ожидается",
            "xg_home":
                values.get(
                    "xg_home"
                ),
            "xg_away":
                values.get(
                    "xg_away"
                )
        }
        tour["matches"].append(
            match
        )
    return tour

# =====================================================
# СОЗДАНИЕ НОВОГО ТУРА
# =====================================================
def create_new_tour(
        tours,
        name,
        matches
):
    tours[name] = {
        "created":
            datetime.now().isoformat(),
        "matches":
            matches
    }
    save_tours(
        tours
    )

# =====================================================
# ФОРМИРОВАНИЕ АРХИВА
# =====================================================
def get_archive(tours):
    archive = []
    for name, tour in tours.items():
        stats = tour_statistics(
            tour
        )
        archive.append({
            "tour":
                name,
            "matches":
                stats["total"],
            "finished":
                stats["finished"],
            "accuracy":
                stats["accuracy"]
        })
    return archive

# =====================================================
# БЛОК ЗАГРУЗКИ В RENDER
# =====================================================
def render_import_block():
    st.sidebar.subheader(
        "📥 Загрузка тура"
    )
    uploaded = st.sidebar.file_uploader(
        "JSON файл тура",
        type=[
            "json"
        ]
    )
    if uploaded:
        if st.sidebar.button(
            "Импортировать тур"
        ):
            tour = import_tour_from_json(
                uploaded
            )
            if tour:
                tours = load_tours()
                number = (
                    f"Тур {len(tours)+1}"
                )
                tours[number] = tour
                save_tours(
                    tours
                )
                st.sidebar.success(
                    f"{number} создан"
                )
                st.rerun()
            else:
                st.sidebar.error(
                    "Ошибка файла"
                )

# =====================================================
# БЛОК АРХИВА
# =====================================================
def show_archive():
    st.subheader(
        "📜 Архив туров"
    )
    tours = load_tours()
    if not tours:
        st.info(
            "Архив пуст"
        )
        return
    archive = get_archive(
        tours
    )
    st.table(
        archive
    )

# =====================================================
# ФИНАЛЬНЫЙ БЛОК СТРАНИЦЫ
# =====================================================
def render_footer():
    st.divider()
    st.caption(
        "⚽ FAJ Platform 10.1 | Tour Manager | Brain Connected"
    )

# =====================================================
# ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ
# =====================================================
def reset_tours():
    save_tours({})

# =====================================================
# РАСШИРЕННЫЙ RENDER
# =====================================================
def render_page():
    render_import_block()
    render()
    st.divider()
    show_archive()
    render_footer()

# =====================================================
# ЭКСПОРТ ДЛЯ STREAMLIT
# =====================================================
def main():
    render_page()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.1
MAIN APPLICATION
FAJ Match Center — ЕДИНЫЙ ИНТЕРФЕЙС
Все действия на одной странице.
"""
import os
import sys
from datetime import datetime
import pandas as pd
import streamlit as st

# ============================================================
# PATH
# ============================================================
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ============================================================
# CONFIG
# ============================================================
try:
    from app.config import config
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.config: {e}")
    st.stop()

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title=f"FAJ Platform v{config.PLATFORM_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# DATABASE
# ============================================================
try:
    from app.database import get_connection, DB_FILE
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.database: {e}")
    st.stop()
DB_PATH = DB_FILE

# ============================================================
# PREDICTION MANAGER
# ============================================================
try:
    from app.core.prediction_manager import get_prediction_manager
except Exception:
    get_prediction_manager = None

# ============================================================
# BOOTSTRAP
# ============================================================
try:
    from app.bootstrap import bootstrap_faj
except Exception:
    bootstrap_faj = None

# ============================================================
# FAJ CYCLE
# ============================================================
try:
    from app.faj_cycle import FAJCycle
    FAJ_CYCLE_AVAILABLE = True
except Exception:
    FAJCycle = None
    FAJ_CYCLE_AVAILABLE = False

# ============================================================
# SESSION
# ============================================================
if "page" not in st.session_state:
    st.session_state.page = "home"
if "bootstrap_result" not in st.session_state:
    st.session_state.bootstrap_result = None
if "cycle_result" not in st.session_state:
    st.session_state.cycle_result = None
if "round_predictions" not in st.session_state:
    st.session_state.round_predictions = {}
if "calendar_fixed" not in st.session_state:
    st.session_state.calendar_fixed = False

# ============================================================
# NAVIGATION
# ============================================================
def navigate(page_name):
    st.session_state.page = page_name
    st.rerun()

# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db_connection():
    return get_connection()

def database_exists():
    return os.path.exists(DB_PATH)

# ============================================================
# BOOTSTRAP
# ============================================================
if st.session_state.bootstrap_result is None:
    if bootstrap_faj is not None:
        try:
            with st.spinner("🚀 Проверка FAJ..."):
                st.session_state.bootstrap_result = bootstrap_faj()
        except Exception as e:
            st.session_state.bootstrap_result = {
                "ready": False,
                "messages": [f"❌ Ошибка Bootstrap: {e}"]
            }
    else:
        st.session_state.bootstrap_result = {
            "ready": False,
            "messages": ["⚠️ bootstrap_faj недоступен."]
        }

# ============================================================
# БЕЗОПАСНЫЕ SQL-ХЕЛПЕРЫ
# ============================================================
def table_exists(table_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table_name,))
        result = cursor.fetchone()
        conn.close()
        return bool(result)
    except Exception:
        return False

# ============================================================
# СЕЗОН И ТУРЫ
# ============================================================
def get_active_season():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, league, name FROM seasons
            WHERE status = 'active' OR league = 'РПЛ'
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {"id": row[0], "league": row[1], "name": row[2]}
    except Exception:
        return None

def get_rounds(season_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, round_number FROM rounds WHERE season_id = ? ORDER BY round_number", (season_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{"id": row[0], "round_number": int(row[1])} for row in rows]
    except Exception:
        return []

def get_round_matches(round_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.date, m.status, th.name AS home_team, ta.name AS away_team,
                   m.is_played, mr.home_goals, mr.away_goals
            FROM matches m
            LEFT JOIN teams th ON m.home_team_id = th.id
            LEFT JOIN teams ta ON m.away_team_id = ta.id
            LEFT JOIN match_results mr ON mr.match_id = m.id
            WHERE m.round_id = ?
            ORDER BY m.date, m.id
        """, (round_id,))
        rows = cursor.fetchall()
        conn.close()
        return [{
            "id": row[0],
            "date": row[1],
            "status": row[2],
            "home_team": row[3],
            "away_team": row[4],
            "is_played": row[5] == 1 or row[5] is True,
            "home_goals": row[6],
            "away_goals": row[7],
        } for row in rows]
    except Exception as e:
        return []

# ============================================================
# СТАТИСТИКА БД
# ============================================================
def get_db_counts():
    result = {"teams": 0, "matches": 0, "predictions": 0}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams WHERE league = 'РПЛ'")
        row = cursor.fetchone()
        if row:
            result["teams"] = row[0] or 0
        season = get_active_season()
        if season:
            cursor.execute("""
                SELECT COUNT(*) FROM matches m JOIN rounds r ON m.round_id = r.id WHERE r.season_id = ?
            """, (season["id"],))
            row = cursor.fetchone()
            if row:
                result["matches"] = row[0] or 0
        if table_exists("predictions"):
            cursor.execute("SELECT COUNT(*) FROM predictions")
            row = cursor.fetchone()
            if row:
                result["predictions"] = row[0] or 0
        conn.close()
    except Exception:
        pass
    return result

# ============================================================
# ДИАГНОСТИКА КАЛЕНДАРЯ
# ============================================================
def get_calendar_status():
    CALENDAR = [
        (1, "ЦСКА", "Балтика"), (1, "Рубин", "Краснодар"),
        (1, "Спартак", "Родина"), (1, "Акрон", "Зенит"),
        (1, "Динамо Москва", "Крылья Советов"), (1, "Факел", "Динамо Махачкала"),
        (1, "Оренбург", "Ростов"), (1, "Локомотив", "Ахмат"),
        (2, "Ахмат", "Спартак"), (2, "Краснодар", "Факел"),
        (2, "Оренбург", "Зенит"), (2, "Балтика", "Динамо Москва"),
        (2, "Динамо Махачкала", "Локомотив"), (2, "ЦСКА", "Крылья Советов"),
        (2, "Акрон", "Рубин"), (2, "Родина", "Ростов"),
        (3, "Факел", "Ахмат"), (3, "Спартак", "Краснодар"),
        (3, "Рубин", "Оренбург"), (3, "Зенит", "Родина"),
        (3, "Динамо Москва", "Динамо Махачкала"), (3, "ЦСКА", "Ростов"),
        (3, "Локомотив", "Акрон"), (3, "Крылья Советов", "Балтика"),
        (4, "Родина", "Акрон"), (4, "Оренбург", "Локомотив"),
        (4, "Балтика", "Спартак"), (4, "Крылья Советов", "Динамо Махачкала"),
        (4, "Зенит", "Динамо Москва"), (4, "Краснодар", "Ахмат"),
        (4, "Ростов", "Рубин"), (4, "ЦСКА", "Факел"),
    ]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        season = get_active_season()
        if not season:
            conn.close()
            return {"error": "Сезон не найден"}
        cursor.execute("SELECT id, round_number FROM rounds WHERE season_id = ? AND round_number BETWEEN 1 AND 4", (season["id"],))
        rounds = {row[1]: row[0] for row in cursor.fetchall()}
        db_matches = {}
        for rn, rid in rounds.items():
            cursor.execute("""
                SELECT m.id, th.name AS home, ta.name AS away
                FROM matches m
                JOIN teams th ON th.id = m.home_team_id
                JOIN teams ta ON ta.id = m.away_team_id
                WHERE m.round_id = ?
            """, (rid,))
            for row in cursor.fetchall():
                db_matches[(rn, row[1], row[2])] = row[0]
        conn.close()

        wrong = []
        for r, h, a in CALENDAR:
            if (r, h, a) not in db_matches:
                # проверяем перевёрнутый вариант
                if (r, a, h) in db_matches:
                    wrong.append((r, h, a))
        return {"total": len(CALENDAR), "wrong": len(wrong), "fixed": len(CALENDAR) - len(wrong), "matches": wrong}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ИСПРАВЛЕНИЕ КАЛЕНДАРЯ (ТОЛЬКО КОМАНДЫ)
# ============================================================
def fix_calendar():
    CALENDAR = {
        (1, "ЦСКА", "Балтика"): ("ЦСКА", "Балтика"),
        (1, "Рубин", "Краснодар"): ("Рубин", "Краснодар"),
        (1, "Спартак", "Родина"): ("Спартак", "Родина"),
        (1, "Акрон", "Зенит"): ("Акрон", "Зенит"),
        (1, "Динамо Москва", "Крылья Советов"): ("Динамо Москва", "Крылья Советов"),
        (1, "Факел", "Динамо Махачкала"): ("Факел", "Динамо Махачкала"),
        (1, "Оренбург", "Ростов"): ("Оренбург", "Ростов"),
        (1, "Локомотив", "Ахмат"): ("Локомотив", "Ахмат"),
        (2, "Ахмат", "Спартак"): ("Ахмат", "Спартак"),
        (2, "Краснодар", "Факел"): ("Краснодар", "Факел"),
        (2, "Оренбург", "Зенит"): ("Оренбург", "Зенит"),
        (2, "Балтика", "Динамо Москва"): ("Балтика", "Динамо Москва"),
        (2, "Динамо Махачкала", "Локомотив"): ("Динамо Махачкала", "Локомотив"),
        (2, "ЦСКА", "Крылья Советов"): ("ЦСКА", "Крылья Советов"),
        (2, "Акрон", "Рубин"): ("Акрон", "Рубин"),
        (2, "Родина", "Ростов"): ("Родина", "Ростов"),
        (3, "Факел", "Ахмат"): ("Факел", "Ахмат"),
        (3, "Спартак", "Краснодар"): ("Спартак", "Краснодар"),
        (3, "Рубин", "Оренбург"): ("Рубин", "Оренбург"),
        (3, "Зенит", "Родина"): ("Зенит", "Родина"),
        (3, "Динамо Москва", "Динамо Махачкала"): ("Динамо Москва", "Динамо Махачкала"),
        (3, "ЦСКА", "Ростов"): ("ЦСКА", "Ростов"),
        (3, "Локомотив", "Акрон"): ("Локомотив", "Акрон"),
        (3, "Крылья Советов", "Балтика"): ("Крылья Советов", "Балтика"),
        (4, "Родина", "Акрон"): ("Родина", "Акрон"),
        (4, "Оренбург", "Локомотив"): ("Оренбург", "Локомотив"),
        (4, "Балтика", "Спартак"): ("Балтика", "Спартак"),
        (4, "Крылья Советов", "Динамо Махачкала"): ("Крылья Советов", "Динамо Махачкала"),
        (4, "Зенит", "Динамо Москва"): ("Зенит", "Динамо Москва"),
        (4, "Краснодар", "Ахмат"): ("Краснодар", "Ахмат"),
        (4, "Ростов", "Рубин"): ("Ростов", "Рубин"),
        (4, "ЦСКА", "Факел"): ("ЦСКА", "Факел"),
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        season = get_active_season()
        if not season:
            return {"error": "Сезон не найден"}
        cursor.execute("SELECT id, round_number FROM rounds WHERE season_id = ? AND round_number BETWEEN 1 AND 4", (season["id"],))
        rounds = {row[1]: row[0] for row in cursor.fetchall()}
        to_fix = []
        for rn, rid in rounds.items():
            cursor.execute("""
                SELECT m.id, th.name AS home, ta.name AS away
                FROM matches m
                JOIN teams th ON th.id = m.home_team_id
                JOIN teams ta ON ta.id = m.away_team_id
                WHERE m.round_id = ?
            """, (rid,))
            for row in cursor.fetchall():
                correct = CALENDAR.get((rn, row[1], row[2]))
                if correct is None:
                    correct = CALENDAR.get((rn, row[2], row[1]))
                    if correct is not None:
                        to_fix.append((row[0], correct[0], correct[1]))
        if not to_fix:
            return {"success": True, "fixed": 0, "message": "Ничего исправлять не нужно"}

        fixed = 0
        for match_id, home, away in to_fix:
            cursor.execute("SELECT id FROM teams WHERE name = ?", (home,))
            home_id = cursor.fetchone()
            cursor.execute("SELECT id FROM teams WHERE name = ?", (away,))
            away_id = cursor.fetchone()
            if home_id and away_id:
                cursor.execute("UPDATE matches SET home_team_id = ?, away_team_id = ? WHERE id = ?",
                               (home_id[0], away_id[0], match_id))
                fixed += 1
        conn.commit()
        conn.close()
        return {"success": True, "fixed": fixed}
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# ПРОГНОЗ
# ============================================================
def calculate_prediction(match):
    if get_prediction_manager is None:
        return {"error": "Prediction Manager недоступен."}
    try:
        manager = get_prediction_manager()
        result = manager.predict(home_team=match["home_team"], away_team=match["away_team"], league="РПЛ")
        if isinstance(result, dict) and (result.get("error") or result.get("status") == "error"):
            return {"error": result.get("message", "Ошибка расчёта")}
        return result
    except Exception as e:
        return {"error": str(e)}

def pct(value):
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "—"

def render_prediction(match, result):
    if not result:
        st.caption("⏳ Прогноз ещё не рассчитан")
        return
    if result.get("error"):
        st.error(result["error"])
        return
    if result.get("status") == "error":
        st.error(result.get("message", "Ошибка расчёта"))
        return

    xg = result.get("xg", {})
    confidence = result.get("confidence", {})
    risk = result.get("risk", {})
    prob = result.get("probability", {})

    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col1:
        st.metric("xG хозяев", f'{float(xg.get("home", 0)):.2f}')
    with col2:
        st.metric("FAJ прогноз", result.get("score", "—"))
    with col3:
        st.metric("xG гостей", f'{float(xg.get("away", 0)):.2f}')

    p1, px, p2 = st.columns(3)
    with p1:
        st.caption("П1")
        st.write(f"**{pct(prob.get('home', 0))}**")
    with px:
        st.caption("X")
        st.write(f"**{pct(prob.get('draw', 0))}**")
    with p2:
        st.caption("П2")
        st.write(f"**{pct(prob.get('away', 0))}**")

    c1, c2 = st.columns(2)
    with c1:
        st.caption("🧠 Confidence")
        st.write(f"**{pct(confidence.get('overall', 0))}** {confidence.get('level', '')}")
    with c2:
        st.caption("⚠️ Risk")
        st.write(f"**{risk.get('level', '—')}**")

def render_match_card(match, index):
    result = st.session_state.round_predictions.get(int(match["id"]))

    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"### ⚽ {match['home_team']}  —  {match['away_team']}")
            if match.get("date"):
                st.caption(f"📅 {match['date']}")
        with col2:
            if match.get("is_played"):
                st.caption("✅ Сыгран")
            elif result and not result.get("error") and result.get("status") != "error":
                st.success("FAJ ✓")
            else:
                st.caption("⏳ Ожидает")

        if match.get("is_played"):
            st.caption(f"📊 Результат: {match.get('home_goals', '?')} : {match.get('away_goals', '?')}")
        else:
            render_prediction(match, result)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔬 Детали", key=f"details_{match['id']}", use_container_width=True):
                st.session_state.lab_match_id = int(match["id"])
                navigate("match_analysis")
        with col2:
            if not match.get("is_played") and (not result or result.get("error") or result.get("status") == "error"):
                if st.button("🔮 Рассчитать", key=f"predict_{match['id']}", use_container_width=True):
                    with st.spinner(f"FAJ рассчитывает: {match['home_team']} — {match['away_team']}"):
                        prediction = calculate_prediction(match)
                    st.session_state.round_predictions[int(match["id"])] = prediction
                    st.rerun()

def calculate_round(matches):
    if not matches:
        return
    progress = st.progress(0, text="Подготовка прогнозов...")
    total = len(matches)
    for index, match in enumerate(matches, start=1):
        if match.get("is_played"):
            continue
        progress.progress(index / total, text=f"FAJ: {index}/{total} — {match['home_team']} — {match['away_team']}")
        result = calculate_prediction(match)
        st.session_state.round_predictions[int(match["id"])] = result
    progress.empty()

def run_faj_cycle():
    if not FAJ_CYCLE_AVAILABLE:
        return {"success": False, "message": "FAJ Cycle недоступен."}
    try:
        cycle = FAJCycle()
        if hasattr(cycle, "run"):
            result = cycle.run()
        elif hasattr(cycle, "run_cycle"):
            result = cycle.run_cycle()
        elif hasattr(cycle, "execute"):
            result = cycle.execute()
        else:
            return {"success": False, "message": "FAJCycle не имеет run/run_cycle/execute."}
        if isinstance(result, dict):
            return result
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("⚽ FAJ")
    st.caption(f"Platform v{config.PLATFORM_VERSION}")
    st.divider()
    st.caption("🏠 ОСНОВНОЕ")
    if st.button("🏠 Матч-центр", use_container_width=True):
        navigate("home")
    if st.button("🔮 Прогнозы", use_container_width=True):
        navigate("predictions")
    if st.button("📊 Аналитика", use_container_width=True):
        navigate("analytics")
    if st.button("📚 История", use_container_width=True):
        navigate("history")
    st.divider()
    st.caption("🧠 FAJ")
    if st.button("📋 Паспорта", use_container_width=True):
        navigate("passports")
    if st.button("🔬 Match Laboratory", use_container_width=True):
        navigate("match_analysis")
    st.divider()
    st.caption("⚙️ СИСТЕМА")
    if st.button("⚙️ Система", use_container_width=True):
        navigate("system")
    st.divider()
    if st.button("🔄 Обновить FAJ", type="primary", use_container_width=True):
        with st.spinner("🧠 FAJ выполняет цикл..."):
            st.session_state.cycle_result = run_faj_cycle()
        st.rerun()
    st.divider()
    counts = get_db_counts()
    st.caption("📊 СОСТОЯНИЕ")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Команды", counts["teams"])
    with c2:
        st.metric("Матчи", counts["matches"])
    if database_exists():
        st.caption("🟢 SQLite")
    else:
        st.caption("🔴 SQLite отсутствует")

# ============================================================
# HOME — ГЛАВНАЯ СТРАНИЦА
# ============================================================
if st.session_state.page == "home":
    season = get_active_season()
    if not season:
        st.error("❌ Активный сезон РПЛ не найден.")
        st.stop()

    rounds = get_rounds(season["id"])
    if not rounds:
        st.error("❌ В сезоне нет туров.")
        st.stop()

    round_map = {r["round_number"]: r["id"] for r in rounds}
    current_round = 5 if 5 in round_map else max(round_map.keys())
    round_id = round_map[current_round]
    matches = get_round_matches(round_id)

    # ============================================================
    # КАЛЕНДАРЬ — ДИАГНОСТИКА И ИСПРАВЛЕНИЕ
    # ============================================================
    calendar_status = get_calendar_status()
    if "error" not in calendar_status and calendar_status["wrong"] > 0:
        st.warning(f"⚠️ В календаре 1-4 туров {calendar_status['wrong']} матчей с перепутанными командами.")
        if st.button("🔧 Исправить календарь (только команды)", type="primary"):
            result = fix_calendar()
            if result.get("success"):
                st.success(f"✅ Исправлено {result.get('fixed', 0)} матчей!")
                st.session_state.calendar_fixed = True
                st.rerun()
            else:
                st.error(f"❌ Ошибка: {result.get('error')}")
        st.divider()
    elif "error" not in calendar_status:
        st.success("✅ Календарь первых 4 туров корректен.")

    # ============================================================
    # ЗАГОЛОВОК
    # ============================================================
    st.markdown("# ⚽ FAJ Match Center")
    st.caption(f"РПЛ · 2026/27 · {current_round}-й тур")

    # ============================================================
    # ВЕРХНЯЯ ПАНЕЛЬ
    # ============================================================
    counts = get_db_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🏟️ Команды", counts["teams"])
    with c2:
        st.metric("⚽ Матчи", counts["matches"])
    with c3:
        st.metric("🔮 Прогнозы", counts["predictions"])
    with c4:
        st.metric("📅 Тур", current_round)

    st.divider()

    # ============================================================
    # НАВИГАЦИЯ ПО ТУРАМ
    # ============================================================
    left, center, right = st.columns([1, 2, 1])
    with left:
        prev = current_round - 1
        if prev in round_map:
            if st.button("← Предыдущий", use_container_width=True):
                st.session_state.selected_round = prev
                st.rerun()
    with center:
        selected_round = st.selectbox(
            "Тур",
            sorted(round_map.keys()),
            index=sorted(round_map.keys()).index(st.session_state.get("selected_round", current_round)),
            label_visibility="collapsed"
        )
    with right:
        nxt = current_round + 1
        if nxt in round_map:
            if st.button("Следующий →", use_container_width=True):
                st.session_state.selected_round = nxt
                st.rerun()

    if selected_round != current_round:
        matches = get_round_matches(round_map[selected_round])

    st.markdown(f"## {selected_round}-й тур")
    st.caption(f"{len(matches)} матчей")

    # ============================================================
    # РАСЧЁТ ПРОГНОЗОВ
    # ============================================================
    upcoming = [m for m in matches if not m.get("is_played")]
    if upcoming and not all(int(m["id"]) in st.session_state.round_predictions for m in upcoming):
        if st.button(f"🔮 Рассчитать прогнозы тура ({len(upcoming)})", type="primary", use_container_width=True):
            calculate_round(matches)
            st.rerun()
    else:
        if not upcoming:
            st.success("🟢 Все матчи этого тура уже сыграны.")
        else:
            st.success("🟢 Все прогнозы этого тура рассчитаны.")

    st.divider()

    # ============================================================
    # МАТЧИ
    # ============================================================
    if not matches:
        st.info("В выбранном туре матчей нет.")
    else:
        for index, match in enumerate(matches):
            render_match_card(match, index)
            st.write("")

    # ============================================================
    # ПОСЛЕДНИЙ ЗАПУСК FAJ CYCLE
    # ============================================================
    if st.session_state.cycle_result:
        with st.expander("🔄 Последний запуск FAJ Cycle"):
            result = st.session_state.cycle_result
            if result.get("success"):
                st.success("FAJ Cycle завершён успешно.")
            else:
                st.warning("FAJ Cycle завершён с проблемой.")
            st.json(result)

# ============================================================
# ОСТАЛЬНЫЕ СТРАНИЦЫ
# ============================================================
elif st.session_state.page == "predictions":
    from app.pages.predictions import main
    main()

elif st.session_state.page == "match_analysis":
    st.title("🔬 Match Laboratory")
    try:
        from app.pages.match_analysis import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка Match Laboratory: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

elif st.session_state.page == "passports":
    st.title("📋 Паспорта команд")
    try:
        conn = get_db_connection()
        passport_df = pd.read_sql_query("""
            SELECT t.name AS team_name, tp.attack, tp.defense, tp.control,
                   tp.goalkeeper, tp.faj_rating
            FROM teams t
            LEFT JOIN team_passports tp ON t.id = tp.team_id
            WHERE t.league = 'РПЛ'
            ORDER BY t.name
        """, conn)
        conn.close()
        if passport_df.empty:
            st.info("Паспорта не найдены.")
        else:
            display_df = passport_df.rename(columns={
                "team_name": "Команда", "attack": "Атака", "defense": "Защита",
                "control": "Контроль", "goalkeeper": "Вратарь", "faj_rating": "FAJ Rating"
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"❌ Ошибка паспортов: {e}")

elif st.session_state.page == "analytics":
    st.title("📊 Аналитика")
    st.info("Аналитический слой FAJ.")
    counts = get_db_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Матчи", counts["matches"])
    with c2:
        st.metric("Прогнозы", counts["predictions"])
    with c3:
        st.metric("Команды", counts["teams"])

elif st.session_state.page == "history":
    st.title("📚 История FAJ")
    st.info("История прогнозов и фактических результатов.")
    counts = get_db_counts()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Матчи", counts["matches"])
    with c2:
        st.metric("Прогнозы", counts["predictions"])

elif st.session_state.page == "system":
    st.title("⚙️ Система")
    st.caption("Техническое состояние FAJ Platform")
    st.divider()
    counts = get_db_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Platform", f"v{config.PLATFORM_VERSION}")
    with c2:
        st.metric("Core", f"v{config.CORE_VERSION}")
    with c3:
        st.metric("Pipeline", f"v{config.PIPELINE_VERSION}")
    st.divider()
    st.subheader("💾 SQLite")
    if database_exists():
        st.success("🟢 SQLite доступна")
        try:
            size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
            st.metric("Размер БД", f"{size_mb:.2f} MB")
        except Exception:
            pass
    else:
        st.error("🔴 faj.db не найден")
    st.divider()
    st.subheader("🔍 Диагностика")
    summary_df = pd.DataFrame([
        {"Показатель": "Команды РПЛ", "Количество": counts["teams"]},
        {"Показатель": "Матчи активного сезона", "Количество": counts["matches"]},
        {"Показатель": "Прогнозы", "Количество": counts["predictions"]},
    ])
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption(
    f"⚽ FAJ Platform v{config.PLATFORM_VERSION} · "
    f"Core v{config.CORE_VERSION} · "
    f"Pipeline v{config.PIPELINE_VERSION} · "
    f"SQLite · "
    f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
)

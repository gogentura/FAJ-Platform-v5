#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
STREAMLIT MAIN APPLICATION
============================================================

ГЛАВНАЯ ТОЧКА ВХОДА FAJ.

Streamlit является ТОЛЬКО интерфейсом.

Архитектура:

    Streamlit
        │
        ├── Auto Bootstrap
        │
        ├── FAJ Cycle
        │      │
        │      ├── Results Loader
        │      ├── Learning Engine
        │      ├── Prediction Manager
        │      └── Persistence
        │
        ├── Match Laboratory
        ├── Passports
        ├── System Trace
        │
        └── System

ВАЖНЫЕ ПРИНЦИПЫ:

    - SQLite only
    - database.py НЕ изменяется Streamlit
    - Streamlit НЕ содержит схему БД
    - Streamlit НЕ содержит математическое ядро
    - Streamlit НЕ содержит обучение
    - Streamlit НЕ содержит загрузчики
    - Streamlit НЕ делает DELETE
    - Streamlit НЕ делает DROP
    - Streamlit НЕ очищает исторические данные
    - Bootstrap только проверяет/восстанавливает
      отсутствующие базовые данные
    - FAJ Cycle является будущим единым оркестратором

ТЕКУЩИЙ ЭТАП:

    faj_cycle.py подключается мягко.

    Если модуль ещё не создан:
        интерфейс продолжает работать.

    После создания faj_cycle.py:
        кнопка "🔄 Обновить FAJ" автоматически
        использует его.

============================================================
"""

import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

# ============================================================
# PATH
# ============================================================

ROOT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

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
# EXISTING CORE MODULES
# ============================================================

try:
    from app.database import get_connection, FAJDatabase
except Exception as e:
    st.error(f"❌ Не удалось загрузить app.database: {e}")
    st.stop()

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
# GITHUB SYNC
# ============================================================

try:
    from app.github_db_sync import save_database_to_github
except Exception:
    save_database_to_github = None

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
# DATA LOADER (автоматическая загрузка календаря и результатов)
# ============================================================

try:
    from data_loader import load_initial_data
except Exception:
    load_initial_data = None

# ============================================================
# DATABASE PATH
# ============================================================

try:
    from app.database import DB_FILE
    DB_PATH = DB_FILE
except Exception:
    DB_PATH = os.path.join(ROOT_DIR, "data", "faj.db")

# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "prediction_result" not in st.session_state:
    st.session_state.prediction_result = None

if "cycle_result" not in st.session_state:
    st.session_state.cycle_result = None

if "cycle_running" not in st.session_state:
    st.session_state.cycle_running = False

# ============================================================
# NAVIGATION
# ============================================================

def navigate(page_name, clear_prediction=False):
    st.session_state.page = page_name
    if clear_prediction:
        st.session_state.prediction_result = None
    st.rerun()

# ============================================================
# DATABASE READ-ONLY HELPERS
# ============================================================

def database_exists():
    try:
        return os.path.exists(DB_PATH)
    except Exception:
        return False

def get_db_connection():
    return get_connection()

def get_table_count(table_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0] or 0
    except Exception:
        pass
    return 0

def get_db_counts():
    result = {"tables": 0, "teams": 0, "matches": 0, "predictions": 0}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        row = cursor.fetchone()
        if row:
            result["tables"] = row[0] or 0
        for key, table in {"teams": "teams", "matches": "matches", "predictions": "predictions"}.items():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                row = cursor.fetchone()
                if row:
                    result[key] = row[0] or 0
            except Exception:
                result[key] = 0
        conn.close()
    except Exception:
        pass
    return result

def get_all_tables():
    tables = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        rows = cursor.fetchall()
        for row in rows:
            tables.append(row[0])
        conn.close()
    except Exception:
        pass
    return tables

def get_table_columns(table_name):
    columns = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        rows = cursor.fetchall()
        for row in rows:
            columns.append({
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": row[3],
                "default": row[4],
                "pk": row[5],
            })
        conn.close()
    except Exception:
        pass
    return columns

# ============================================================
# BOOTSTRAP
# ============================================================

if "bootstrap_result" not in st.session_state:
    if bootstrap_faj is not None:
        try:
            with st.spinner("🚀 Проверка FAJ..."):
                st.session_state.bootstrap_result = bootstrap_faj()
        except Exception as e:
            st.session_state.bootstrap_result = {
                "ready": False,
                "messages": [f"❌ Ошибка Bootstrap: {e}"],
            }
    else:
        st.session_state.bootstrap_result = {
            "ready": False,
            "messages": ["⚠️ bootstrap_faj недоступен."],
        }

bootstrap_result = st.session_state.bootstrap_result

# ============================================================
# ЗАГРУЗКА НАЧАЛЬНЫХ ДАННЫХ (календарь и результаты 1-4 туров)
# ============================================================
if load_initial_data is not None:
    try:
        load_initial_data()
    except Exception as e:
        st.warning(f"⚠️ Не удалось загрузить начальные данные: {e}")
else:
    st.warning("⚠️ data_loader.py не найден, начальные данные не загружены.")

# ============================================================
# FAJ CYCLE RUNNER
# ============================================================

def run_faj_cycle():
    if not FAJ_CYCLE_AVAILABLE:
        return {
            "success": False,
            "status": "not_available",
            "message": "faj_cycle.py пока не подключён.",
        }
    try:
        cycle = FAJCycle()
        if hasattr(cycle, "run"):
            result = cycle.run()
        elif hasattr(cycle, "run_cycle"):
            result = cycle.run_cycle()
        elif hasattr(cycle, "execute"):
            result = cycle.execute()
        else:
            return {
                "success": False,
                "status": "invalid",
                "message": "FAJCycle загружен, но у него нет метода run(), run_cycle() или execute().",
            }
        if isinstance(result, dict):
            return result
        return {
            "success": True,
            "status": "completed",
            "result": result,
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "message": str(e),
            "exception": e,
        }

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("⚽ FAJ")
    st.caption(f"Platform v{config.PLATFORM_VERSION}")
    st.divider()

    st.caption("🏠 ОСНОВНОЕ")
    if st.button("🏠 Матч-центр", use_container_width=True, key="nav_home"):
        navigate("home", clear_prediction=True)
    if st.button("📊 Аналитика", use_container_width=True, key="nav_analytics"):
        navigate("analytics")
    if st.button("🔮 Прогнозы", use_container_width=True, key="nav_predictions"):
        navigate("predictions")
    if st.button("📚 История", use_container_width=True, key="nav_history"):
        navigate("history")

    st.divider()
    st.caption("⚙️ СИСТЕМА")
    if st.button("⚙️ Система", use_container_width=True, key="nav_system"):
        navigate("system")
    if st.button("🔬 Match Laboratory", use_container_width=True, key="nav_match_lab"):
        navigate("match_analysis")
    if st.button("📋 Паспорта", use_container_width=True, key="nav_passports"):
        navigate("passports")
    if st.button("🧬 System Trace", use_container_width=True, key="nav_system_trace"):
        navigate("system_trace")

    st.divider()
    st.caption("🔄 FAJ CYCLE")
    if FAJ_CYCLE_AVAILABLE:
        if st.button("🔄 Обновить FAJ", use_container_width=True, type="primary", key="nav_cycle"):
            with st.spinner("🧠 FAJ выполняет полный цикл..."):
                cycle_result = run_faj_cycle()
            st.session_state.cycle_result = cycle_result
            st.session_state.page = "home"
            st.rerun()
    else:
        st.button("🔄 Обновить FAJ", use_container_width=True, disabled=True, key="nav_cycle_disabled")
        st.caption("FAJ Cycle пока не подключён.")

    st.divider()
    st.caption("💾 СОХРАНЕНИЕ")
    if st.button("💾 Сохранить БД в GitHub", use_container_width=True, key="nav_save_db"):
        try:
            if save_database_to_github is None:
                st.error("❌ github_db_sync недоступен.")
            else:
                with st.spinner("⏳ Сохранение faj.db..."):
                    result = save_database_to_github()
                st.success("✅ База данных сохранена.")
                if isinstance(result, dict):
                    if result.get("path"):
                        st.caption(f"Файл: {result['path']}")
                    if result.get("size"):
                        st.caption(f"Размер: {result['size'] // 1024} KB")
        except Exception as e:
            st.error(f"❌ Ошибка сохранения: {e}")

    st.divider()
    st.caption("📊 СОСТОЯНИЕ")
    counts = get_db_counts()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Команды", counts["teams"])
    with c2:
        st.metric("Матчи", counts["matches"])
    if database_exists():
        st.caption("🟢 SQLite доступна")
    else:
        st.caption("🔴 SQLite не найдена")

# ============================================================
# HOME / MATCH CENTER
# ============================================================

if st.session_state.page == "home":
    st.title("🏠 FAJ Match Center")
    st.caption(f"FAJ Platform v{config.PLATFORM_VERSION} · Core v{config.CORE_VERSION} · Pipeline v{config.PIPELINE_VERSION}")
    st.divider()

    st.subheader("🔄 FAJ Cycle")
    if FAJ_CYCLE_AVAILABLE:
        st.success("🟢 Оркестратор FAJ Cycle подключён.")
    else:
        st.warning("🟡 FAJ Cycle ещё не подключён.")
        st.caption("После создания app/faj_cycle.py кнопка «Обновить FAJ» станет активной.")

    cycle_result = st.session_state.cycle_result
    if cycle_result:
        st.divider()
        st.subheader("📋 Последний запуск FAJ Cycle")
        success = cycle_result.get("success", cycle_result.get("ready", False))
        if success:
            st.success("✅ Цикл завершён.")
        else:
            st.warning("⚠️ Цикл завершён с проблемой.")
        message = cycle_result.get("message")
        if message:
            st.info(str(message))
        with st.expander("🔬 Полная диагностика цикла"):
            st.json(cycle_result)

    st.divider()
    st.subheader("🚀 Состояние системы")
    if bootstrap_result.get("ready"):
        st.success("✅ Auto Bootstrap: система готова")
    else:
        st.warning("⚠️ Auto Bootstrap сообщает о проблеме")
        messages = bootstrap_result.get("messages", [])
        if messages:
            with st.expander("📋 Детали Bootstrap"):
                for message in messages:
                    st.text(str(message))

    st.divider()
    st.subheader("💾 Состояние данных")
    counts = get_db_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🏟️ Команды", counts["teams"])
    with c2:
        st.metric("⚽ Матчи", counts["matches"])
    with c3:
        st.metric("🔮 Прогнозы", counts["predictions"])
    with c4:
        st.metric("🗄️ Таблицы", counts["tables"])

    st.divider()
    st.subheader("🚀 Быстрые действия")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🔄 Обновить FAJ", use_container_width=True, type="primary", disabled=not FAJ_CYCLE_AVAILABLE, key="home_cycle"):
            with st.spinner("🧠 Выполняется FAJ Cycle..."):
                result = run_faj_cycle()
            st.session_state.cycle_result = result
            st.rerun()
    with c2:
        if st.button("🔮 Прогноз", use_container_width=True, key="home_prediction"):
            navigate("predictions")
    with c3:
        if st.button("📚 История", use_container_width=True, key="home_history"):
            navigate("history")
    with c4:
        if st.button("🔬 Match Lab", use_container_width=True, key="home_lab"):
            navigate("match_analysis")

# ============================================================
# PREDICTIONS
# ============================================================

elif st.session_state.page == "predictions":
    st.title("🔮 Прогнозы FAJ")
    st.caption("Prediction Manager → Prediction Pipeline → Models")
    st.divider()

    if get_prediction_manager is None:
        st.error("❌ Prediction Manager не удалось загрузить.")
        st.stop()

    try:
        conn = get_db_connection()
        teams_df = pd.read_sql_query("SELECT id, name FROM teams WHERE league = 'РПЛ' ORDER BY name", conn)
        conn.close()
    except Exception as e:
        teams_df = pd.DataFrame()
        st.error(f"❌ Ошибка чтения команд: {e}")

    if teams_df.empty:
        st.warning("⚠️ В БД пока нет команд РПЛ.")
    else:
        team_names = teams_df["name"].tolist()
        col1, col2 = st.columns(2)
        with col1:
            team1 = st.selectbox("🏠 Хозяева", team_names, key="prediction_home_team")
        with col2:
            team2 = st.selectbox("✈️ Гости", team_names, key="prediction_away_team")

        if st.button("🔮 РАССЧИТАТЬ ПРОГНОЗ", type="primary", use_container_width=True, key="calculate_prediction"):
            if team1 == team2:
                st.error("❌ Команды должны отличаться.")
                st.session_state.prediction_result = None
            else:
                with st.spinner("🧠 FAJ рассчитывает прогноз..."):
                    try:
                        manager = get_prediction_manager()
                        result = manager.predict(home_team=team1, away_team=team2, league="RPL")
                        st.session_state.prediction_result = result
                    except Exception as e:
                        st.session_state.prediction_result = None
                        st.error(f"❌ Ошибка Prediction Manager: {e}")
                        with st.expander("Техническая ошибка"):
                            st.exception(e)

        result = st.session_state.prediction_result
        if result:
            if result.get("status") == "error":
                st.error(result.get("message", "Prediction Engine вернул ошибку."))
            else:
                st.divider()
                home_team = result.get("home_team", team1)
                away_team = result.get("away_team", team2)
                st.subheader(f"⚽ {home_team} — {away_team}")
                xg = result.get("xg", {})
                probability = result.get("probability", {})

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("🏠 xG", f"{float(xg.get('home', 0) or 0):.2f}")
                with c2:
                    st.metric("🎯 Прогноз", result.get("score", "—"))
                    try:
                        score_probability = result.get("score_probability", 0) or 0
                        st.caption(f"Вероятность точного счёта: {float(score_probability):.1%}")
                    except Exception:
                        pass
                with c3:
                    st.metric("✈️ xG", f"{float(xg.get('away', 0) or 0):.2f}")

                st.subheader("📈 Вероятности исходов")
                prob_df = pd.DataFrame({
                    "Исход": ["Победа хозяев", "Ничья", "Победа гостей"],
                    "Вероятность": [probability.get("home", 0) or 0, probability.get("draw", 0) or 0, probability.get("away", 0) or 0],
                })
                st.bar_chart(prob_df.set_index("Исход"))

                extended = result.get("extended", {})
                if extended:
                    st.divider()
                    st.subheader("📋 Расширенные показатели")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("### ⚽ Обе забьют")
                        btts = extended.get("btts", {})
                        try:
                            st.metric("Да", f"{float(btts.get('yes', 0) or 0):.1%}")
                            st.metric("Нет", f"{float(btts.get('no', 0) or 0):.1%}")
                        except Exception:
                            st.write(btts)
                    with c2:
                        st.write("### 📊 Тоталы")
                        total = extended.get("total", {})
                        try:
                            st.metric("Тотал > 2.5", f"{float(total.get('over_2_5', 0) or 0):.1%}")
                            st.metric("Тотал > 3.5", f"{float(total.get('over_3_5', 0) or 0):.1%}")
                        except Exception:
                            st.write(total)

                with st.expander("📋 Полный результат"):
                    st.json(result)

# ============================================================
# MATCH LABORATORY
# ============================================================

elif st.session_state.page == "match_analysis":
    st.title("🔬 Match Laboratory")
    st.caption("Диагностика прогноза от Team Passport до Monte Carlo")
    try:
        from app.pages.match_analysis import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка Match Laboratory: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ============================================================
# PASSPORTS
# ============================================================

elif st.session_state.page == "passports":
    st.title("📋 Паспорта команд")
    st.caption("Team Passport · FAJ Rating · Team Intelligence")
    st.divider()
    try:
        conn = get_db_connection()
        passport_df = pd.read_sql_query("""
            SELECT
                t.name AS team_name,
                tp.attack,
                tp.defense,
                tp.control,
                tp.goalkeeper,
                tp.faj_rating
            FROM teams t
            LEFT JOIN team_passports tp ON t.id = tp.team_id
            WHERE t.league = 'РПЛ'
            ORDER BY t.name
        """, conn)
        conn.close()
        if passport_df.empty:
            st.warning("⚠️ Паспорта команд пока не найдены.")
        else:
            display_df = passport_df.rename(columns={
                "team_name": "Команда",
                "attack": "Атака",
                "defense": "Защита",
                "control": "Контроль",
                "goalkeeper": "Вратарь",
                "faj_rating": "FAJ Rating",
            })
            for column in ["Атака", "Защита", "Контроль", "Вратарь", "FAJ Rating"]:
                if column in display_df.columns:
                    display_df[column] = pd.to_numeric(display_df[column], errors="coerce").round(1)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"❌ Ошибка загрузки паспортов: {e}")

# ============================================================
# HISTORY
# ============================================================

elif st.session_state.page == "history":
    st.title("📚 История FAJ")
    st.caption("История прогнозов, фактических результатов и обучения")
    st.info("📌 Страница подготовлена под FAJ Cycle. Метрики будут подключены после проверки реальной структуры сохранённых результатов.")
    st.divider()
    counts = get_db_counts()
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Прогнозов в БД", counts["predictions"])
    with c2:
        st.metric("Матчей в БД", counts["matches"])
    st.caption("Никаких данных здесь не изменяется.")

# ============================================================
# ANALYTICS
# ============================================================

elif st.session_state.page == "analytics":
    st.title("📊 Аналитика")
    st.caption("FAJ Analytics · Model Intelligence")
    st.info("📌 Аналитический слой будет подключён после завершения FAJ Cycle и проверки learning_memory / model_parameters.")
    counts = get_db_counts()
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Матчи", counts["matches"])
    with c2:
        st.metric("Прогнозы", counts["predictions"])
    with c3:
        st.metric("Таблицы", counts["tables"])

# ============================================================
# SYSTEM TRACE
# ============================================================

elif st.session_state.page == "system_trace":
    st.title("🧬 System Trace")
    st.caption("Фактическая архитектура FAJ Platform")
    try:
        from app.pages.system_trace import main
        main()
    except Exception as e:
        st.error(f"❌ Ошибка System Trace: {e}")
        with st.expander("Техническая ошибка"):
            st.exception(e)

# ============================================================
# SYSTEM
# ============================================================

elif st.session_state.page == "system":
    st.title("⚙️ Система")
    st.caption("FAJ Platform · System Status")

    st.subheader("📌 Версии")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Platform", f"v{config.PLATFORM_VERSION}")
    with c2:
        st.metric("Core", f"v{config.CORE_VERSION}")
    with c3:
        st.metric("Pipeline", f"v{config.PIPELINE_VERSION}")

    st.divider()
    st.subheader("🔄 FAJ Cycle")
    if FAJ_CYCLE_AVAILABLE:
        st.success("🟢 FAJ Cycle доступен")
    else:
        st.warning("🟡 FAJ Cycle пока не установлен.")

    st.divider()
    st.subheader("💾 SQLite")
    if database_exists():
        st.success("🟢 База данных доступна")
        try:
            size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
            st.metric("Размер БД", f"{size_mb:.2f} MB")
        except Exception:
            pass
    else:
        st.error("🔴 faj.db не найден")

    st.divider()
    st.subheader("🔍 Диагностика")
    st.caption("Все проверки ниже выполняются только на чтение.")
    counts = get_db_counts()
    summary_df = pd.DataFrame([
        {"Показатель": "Таблицы", "Количество": counts["tables"]},
        {"Показатель": "Команды", "Количество": counts["teams"]},
        {"Показатель": "Матчи", "Количество": counts["matches"]},
        {"Показатель": "Прогнозы", "Количество": counts["predictions"]},
    ])
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with st.expander("🗄️ Таблицы SQLite"):
        tables = get_all_tables()
        if tables:
            table_rows = []
            for table in tables:
                table_rows.append({"Таблица": table, "Записей": get_table_count(table)})
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
        else:
            st.warning("Таблицы не обнаружены.")

    with st.expander("🩺 SQLite Integrity Check"):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            row = cursor.fetchone()
            conn.close()
            if row and row[0] == "ok":
                st.success("✅ SQLite integrity_check: OK")
            else:
                st.error(f"❌ Integrity check: {row}")
        except Exception as e:
            st.error(f"❌ Ошибка проверки: {e}")

    with st.expander("🔗 Foreign Key Check"):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_key_check")
            errors = cursor.fetchall()
            conn.close()
            if not errors:
                st.success("✅ Нарушений FOREIGN KEY не обнаружено.")
            else:
                st.error(f"❌ Нарушений: {len(errors)}")
                st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"❌ Ошибка FOREIGN KEY check: {e}")

    st.divider()
    st.caption(f"Текущее время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

# ============================================================
# UNKNOWN PAGE
# ============================================================

else:
    st.session_state.page = "home"
    st.rerun()

# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption(f"⚽ FAJ Platform v{config.PLATFORM_VERSION} · Core v{config.CORE_VERSION} · Pipeline v{config.PIPELINE_VERSION} · SQLite · {datetime.now().strftime('%d.%m.%Y %H:%M')}")

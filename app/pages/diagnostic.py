#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Диагностика FAJ Database
============================================================

Назначение:
    Техническая диагностика базы данных и ETC-инфраструктуры.

Принципы:
    - Только чтение (READ ONLY)
    - Не изменяет БД
    - Не создаёт данные
    - Использует FAJDatabase

============================================================
"""

import streamlit as st
import os
from datetime import datetime

from app.database import FAJDatabase, DB_FILE


# ============================================================
# HELPERS
# ============================================================

def table_exists(db: FAJDatabase, table_name: str) -> bool:
    """Проверяет существование таблицы."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        result = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return result
    except Exception:
        return False


def get_table_count(db: FAJDatabase, table_name: str) -> int:
    """Возвращает количество строк в таблице."""
    if not table_exists(db, table_name):
        return 0
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception:
        return 0


def get_table_columns(db: FAJDatabase, table_name: str) -> list:
    """Возвращает список колонок таблицы."""
    if not table_exists(db, table_name):
        return []
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [row[1] for row in rows]
    except Exception:
        return []


# ============================================================
# MAIN
# ============================================================

def main():
    st.title("🔧 Диагностика FAJ")

    st.caption(
        "Техническая диагностика базы данных и ETC-инфраструктуры"
    )

    st.divider()

    # --------------------------------------------------------
    # 1. DATABASE / SCHEMA
    # --------------------------------------------------------

    st.subheader("📁 1. База данных")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Путь",
            DB_FILE,
        )

    with col2:
        if os.path.exists(DB_FILE):
            size_mb = os.path.getsize(DB_FILE) / 1024 / 1024
            st.metric(
                "Размер",
                f"{size_mb:.2f} MB",
            )
        else:
            st.metric(
                "Размер",
                "❌",
            )

    with col3:
        if os.path.exists(DB_FILE):
            mtime = os.path.getmtime(DB_FILE)
            st.metric(
                "Изменён",
                datetime.fromtimestamp(mtime).strftime("%d.%m %H:%M"),
            )
        else:
            st.metric(
                "Изменён",
                "—",
            )

    st.divider()

    # ========================================================
    # 2. INITIALIZATION
    # ========================================================

    st.subheader("🚀 2. Инициализация")

    try:
        db = FAJDatabase()
        status = db.get_status()
        st.success(f"✅ Database initialized: {status['status']}")
        with st.expander("Детали"):
            st.json(status)
    except Exception as exc:
        st.error(f"❌ Ошибка инициализации: {exc}")

    st.divider()

    # ========================================================
    # 3. MATCH LIFECYCLE
    # ========================================================

    st.subheader("📋 3. Жизненный цикл матчей")

    try:

        db = FAJDatabase()

        # Считаем
        matches_count = get_table_count(db, "matches")
        predictions_count = get_table_count(db, "predictions")
        results_count = get_table_count(db, "match_results")
        validation_count = get_table_count(db, "prediction_validation")
        gold_count = get_table_count(db, "gold_dataset")

        # Полный lifecycle
        if table_exists(db, "predictions") and table_exists(db, "match_results"):
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT p.match_id)
                FROM predictions p
                JOIN match_results mr ON p.match_id = mr.match_id
            """)
            full_lifecycle = cursor.fetchone()[0]
            cursor.close()
            conn.close()
        else:
            full_lifecycle = 0

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            st.metric(
                "📋 Матчи",
                matches_count,
            )
        with col2:
            st.metric(
                "🧠 Прогнозы",
                predictions_count,
            )
        with col3:
            st.metric(
                "🏁 Результаты",
                results_count,
            )
        with col4:
            st.metric(
                "✅ Валидация",
                validation_count,
            )
        with col5:
            st.metric(
                "⭐ Gold",
                gold_count,
            )
        with col6:
            st.metric(
                "🔗 Full",
                full_lifecycle,
            )

        # Цепочка
        st.caption(
            f"Полный цикл (прогноз → результат): {full_lifecycle} матчей"
        )

        # Визуализация
        steps = [
            ("📋 Матчи", matches_count),
            ("🧠 Прогнозы", predictions_count),
            ("🏁 Результаты", results_count),
            ("✅ Валидация", validation_count),
            ("⭐ Gold", gold_count),
        ]

        step_cols = st.columns(len(steps))

        for idx, (label, count) in enumerate(steps):
            with step_cols[idx]:
                if count > 0:
                    st.success(f"{label}\n{count}")
                else:
                    st.warning(f"{label}\n{count}")

    except Exception as exc:
        st.warning(f"⚠️ Ошибка чтения lifecycle: {exc}")

    st.divider()

    # ========================================================
    # 4. RESULT xG
    # ========================================================

    st.subheader("🎯 4. Result xG")

    try:

        db = FAJDatabase()
        conn = db.get_connection()
        cursor = conn.cursor()

        # match_statistics.xg
        cursor.execute("""
            SELECT COUNT(*) FROM match_statistics WHERE xg IS NOT NULL
        """)
        stats_xg_count = cursor.fetchone()[0]

        # gold_dataset.actual_xg_home/away
        cursor.execute("""
            SELECT COUNT(*) FROM gold_dataset
            WHERE actual_xg_home IS NOT NULL AND actual_xg_away IS NOT NULL
        """)
        gold_xg_count = cursor.fetchone()[0]

        # prediction_validation.actual_home_xg/away_xg
        cursor.execute("""
            SELECT COUNT(*) FROM prediction_validation
            WHERE actual_home_xg IS NOT NULL AND actual_away_xg IS NOT NULL
        """)
        validation_xg_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        col1, col2, col3 = st.columns(3)

        with col1:
            icon = "✅" if stats_xg_count > 0 else "❌"
            st.metric(
                f"{icon} match_statistics.xg",
                stats_xg_count,
            )

        with col2:
            icon = "✅" if gold_xg_count > 0 else "❌"
            st.metric(
                f"{icon} gold_dataset.actual_xg",
                gold_xg_count,
            )

        with col3:
            icon = "✅" if validation_xg_count > 0 else "❌"
            st.metric(
                f"{icon} prediction_validation.xg",
                validation_xg_count,
            )

        if stats_xg_count > 0 or gold_xg_count > 0 or validation_xg_count > 0:
            st.success("✅ Result xG доступен в БД")
        else:
            st.warning("⚠️ Result xG не найден")

    except Exception as exc:
        st.warning(f"⚠️ Ошибка проверки xG: {exc}")

    st.divider()

    # ========================================================
    # 5. LEARNING MEMORY
    # ========================================================

    st.subheader("🧠 5. Learning Memory")

    try:

        db = FAJDatabase()
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM learning_memory
        """)
        lm_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT event_type, COUNT(*) as cnt
            FROM learning_memory
            GROUP BY event_type
            ORDER BY cnt DESC
        """)
        event_types = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) FROM learning_events
        """)
        le_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM learning_records
        """)
        lr_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "learning_memory",
                lm_count,
            )
        with col2:
            st.metric(
                "learning_events",
                le_count,
            )
        with col3:
            st.metric(
                "learning_records",
                lr_count,
            )

        if event_types:
            st.caption("Типы событий:")
            for et, cnt in event_types:
                st.text(f"  • {et}: {cnt}")

        if lm_count == 0:
            st.warning("⚠️ Learning Memory пуста")

    except Exception as exc:
        st.warning(f"⚠️ Ошибка чтения Learning Memory: {exc}")

    st.divider()

    # ========================================================
    # 6. MODEL HISTORY
    # ========================================================

    st.subheader("📊 6. Model History")

    try:

        db = FAJDatabase()
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) FROM model_parameters
        """)
        mp_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM parameter_history
        """)
        ph_count = cursor.fetchone()[0]

        # Версии модели в predictions
        cursor.execute("""
            SELECT model_version, COUNT(*) as cnt
            FROM predictions
            WHERE model_version IS NOT NULL
            GROUP BY model_version
            ORDER BY cnt DESC
        """)
        model_versions = cursor.fetchall()

        cursor.close()
        conn.close()

        col1, col2 = st.columns(2)

        with col1:
            icon = "✅" if mp_count > 0 else "❌"
            st.metric(
                f"{icon} model_parameters",
                mp_count,
            )

        with col2:
            icon = "✅" if ph_count > 0 else "❌"
            st.metric(
                f"{icon} parameter_history",
                ph_count,
            )

        if model_versions:
            st.caption("Версии модели в predictions:")
            for version, cnt in model_versions:
                st.text(f"  • {version}: {cnt}")

        if mp_count == 0:
            st.warning("⚠️ Model History отсутствует (нужно для Evolution Report)")

    except Exception as exc:
        st.warning(f"⚠️ Ошибка проверки Model History: {exc}")

    st.divider()

    # ========================================================
    # 7. EVOLUTION READINESS
    # ========================================================

    st.subheader("🚀 7. Evolution Readiness")

    try:

        db = FAJDatabase()

        # Проверяем всё
        items = []

        # Predictions
        pred_count = get_table_count(db, "predictions")
        items.append(("Прогнозы", pred_count > 0, pred_count))

        # Results
        res_count = get_table_count(db, "match_results")
        items.append(("Результаты", res_count > 0, res_count))

        # xG (хотя бы один источник)
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM match_statistics WHERE xg IS NOT NULL")
        stats_xg = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM gold_dataset WHERE actual_xg_home IS NOT NULL")
        gold_xg = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        has_xg = stats_xg > 0 or gold_xg > 0
        items.append(("Result xG", has_xg, stats_xg + gold_xg))

        # Learning Memory
        lm_count = get_table_count(db, "learning_memory")
        items.append(("Learning Memory", lm_count > 0, lm_count))

        # Model History
        mp_count = get_table_count(db, "model_parameters")
        ph_count = get_table_count(db, "parameter_history")
        has_model_history = mp_count > 0 or ph_count > 0
        items.append(("Model History", has_model_history, mp_count + ph_count))

        # Match Snapshots
        ms_count = get_table_count(db, "match_snapshots")
        items.append(("Match Snapshots", ms_count > 0, ms_count))

        # Full lifecycle
        if table_exists(db, "predictions") and table_exists(db, "match_results"):
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT p.match_id)
                FROM predictions p
                JOIN match_results mr ON p.match_id = mr.match_id
            """)
            full_lifecycle = cursor.fetchone()[0]
            cursor.close()
            conn.close()
        else:
            full_lifecycle = 0
        items.append(("Full Lifecycle", full_lifecycle > 0, full_lifecycle))

        ready = all(item[1] for item in items)

        # Отображаем
        for name, status, count in items:
            icon = "✅" if status else "❌"
            st.text(f"{icon} {name}: {count}")

        st.divider()

        if ready:
            st.success("✅ FAJ готова к Evolution Report!")
        else:
            missing = [name for name, status, _ in items if not status]
            st.warning(
                f"⚠️ Не хватает: {', '.join(missing)}\n\n"
                "Evolution Report пока нельзя построить полностью."
            )

    except Exception as exc:
        st.warning(f"⚠️ Ошибка проверки готовности: {exc}")

    st.divider()

    # ========================================================
    # 8. DATA DIRECTORY
    # ========================================================

    st.subheader("📁 8. Содержимое data/")

    try:
        data_dir = os.path.dirname(DB_FILE)
        if os.path.exists(data_dir):
            files = os.listdir(data_dir)
            st.write(f"Директория: {data_dir}")
            st.write(f"Файлы: {files}")
        else:
            st.warning(f"Директория {data_dir} не существует")
    except Exception as exc:
        st.error(f"❌ Ошибка: {exc}")

    st.divider()

    # ========================================================
    # КНОПКА ОБНОВЛЕНИЯ
    # ========================================================

    if st.button(
        "🔄 Обновить диагностику",
        use_container_width=True,
    ):
        st.rerun()

    st.caption(
        "Диагностика не изменяет базу данных. "
        "Все данные читаются через FAJDatabase."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

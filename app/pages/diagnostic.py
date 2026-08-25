#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Диагностика FAJ Database
============================================================

READ-ONLY.

НЕ:
    INSERT
    UPDATE
    DELETE
    ALTER
    DROP

Назначение:
    Техническая диагностика БД и ETC-инфраструктуры.

Особое внимание:
    - фактический xG
    - match_statistics
    - gold_dataset
    - prediction_validation
    - связь MATCH -> PREDICTION -> RESULT -> VALIDATION -> GOLD
    - Learning Memory
    - Model History
    - Match Snapshots
"""

import streamlit as st
import os
from datetime import datetime

from app.database import FAJDatabase, DB_FILE


# ============================================================
# HELPERS
# ============================================================

def table_exists(db: FAJDatabase, table_name: str) -> bool:
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        )

        result = cursor.fetchone() is not None

        cursor.close()
        conn.close()

        return result

    except Exception:
        return False


def get_table_count(db: FAJDatabase, table_name: str) -> int:

    if not table_exists(db, table_name):
        return 0

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        )

        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return count

    except Exception:
        return 0


def get_table_columns(db: FAJDatabase, table_name: str) -> list:

    if not table_exists(db, table_name):
        return []

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [row[1] for row in rows]

    except Exception:
        return []


def get_rows(
    db: FAJDatabase,
    sql: str,
    params=(),
):
    """
    READ-ONLY SELECT helper.
    """

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params)
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def safe_columns(
    db: FAJDatabase,
    table_name: str,
    candidates: list,
) -> list:

    columns = get_table_columns(db, table_name)

    return [
        column
        for column in candidates
        if column in columns
    ]


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🔧 Диагностика FAJ")

    st.caption(
        "READ-ONLY диагностика базы данных и ETC-инфраструктуры"
    )

    st.divider()

    # ========================================================
    # 1. DATABASE
    # ========================================================

    st.subheader("📁 1. База данных")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Путь",
            DB_FILE,
        )

    with col2:

        if os.path.exists(DB_FILE):

            size_mb = (
                os.path.getsize(DB_FILE)
                / 1024
                / 1024
            )

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
                datetime.fromtimestamp(
                    mtime
                ).strftime("%d.%m %H:%M"),
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

        st.success(
            f"✅ Database initialized: "
            f"{status['status']}"
        )

        with st.expander("Детали"):

            st.json(status)

    except Exception as exc:

        st.error(
            f"❌ Ошибка инициализации: {exc}"
        )

        return

    st.divider()

    # ========================================================
    # 3. MATCH LIFECYCLE
    # ========================================================

    st.subheader("📋 3. Жизненный цикл матчей")

    try:

        db = FAJDatabase()

        matches_count = get_table_count(
            db,
            "matches",
        )

        predictions_count = get_table_count(
            db,
            "predictions",
        )

        results_count = get_table_count(
            db,
            "match_results",
        )

        validation_count = get_table_count(
            db,
            "prediction_validation",
        )

        gold_count = get_table_count(
            db,
            "gold_dataset",
        )

        # ----------------------------------------------------
        # FULL LIFECYCLE
        # ----------------------------------------------------

        full_lifecycle = 0

        if (
            table_exists(db, "predictions")
            and table_exists(db, "match_results")
        ):

            rows = get_rows(
                db,
                """
                SELECT COUNT(DISTINCT p.match_id)
                FROM predictions p
                JOIN match_results mr
                  ON p.match_id = mr.match_id
                """,
            )

            if rows:
                full_lifecycle = rows[0][0]

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        cols = st.columns(6)

        with cols[0]:
            st.metric(
                "📋 Матчи",
                matches_count,
            )

        with cols[1]:
            st.metric(
                "🧠 Прогнозы",
                predictions_count,
            )

        with cols[2]:
            st.metric(
                "🏁 Результаты",
                results_count,
            )

        with cols[3]:
            st.metric(
                "✅ Валидация",
                validation_count,
            )

        with cols[4]:
            st.metric(
                "⭐ Gold",
                gold_count,
            )

        with cols[5]:
            st.metric(
                "🔗 Full",
                full_lifecycle,
            )

        st.caption(
            "Полный цикл = матч имеет прогноз и фактический результат."
        )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка lifecycle: {exc}"
        )

    st.divider()

    # ========================================================
    # 4. FACTUAL xG — ГЛАВНЫЙ БЛОК
    # ========================================================

    st.subheader(
        "🎯 4. ФАКТИЧЕСКИЙ xG — ГДЕ ОН ЛЕЖИТ"
    )

    st.info(
        "Этот раздел ничего не записывает в БД. "
        "Он показывает реальные источники фактического xG "
        "и связывает их с match_id."
    )

    try:

        db = FAJDatabase()

        xg_sources = [
            "match_statistics",
            "gold_dataset",
            "prediction_validation",
            "xg_memory",
        ]

        for table in xg_sources:

            exists = table_exists(
                db,
                table,
            )

            if not exists:

                st.error(
                    f"❌ {table}: таблица отсутствует"
                )

                continue

            count = get_table_count(
                db,
                table,
            )

            columns = get_table_columns(
                db,
                table,
            )

            with st.expander(
                f"📦 {table} — {count} строк"
            ):

                st.write(
                    "**Реальные колонки:**"
                )

                st.code(
                    ", ".join(columns)
                )

                # ------------------------------------------------
                # MATCH_STATISTICS
                # ------------------------------------------------

                if table == "match_statistics":

                    xg_columns = [
                        c
                        for c in columns
                        if "xg" in c.lower()
                    ]

                    st.write(
                        "**Колонки, связанные с xG:**"
                    )

                    if xg_columns:

                        st.success(
                            ", ".join(xg_columns)
                        )

                    else:

                        st.warning(
                            "xG-колонка не найдена."
                        )

                    select_columns = safe_columns(
                        db,
                        table,
                        [
                            "id",
                            "match_id",
                            "xg",
                            "home_xg",
                            "away_xg",
                            "home_team_id",
                            "away_team_id",
                            "created_at",
                        ],
                    )

                    if select_columns:

                        sql = (
                            "SELECT "
                            + ", ".join(
                                select_columns
                            )
                            + f" FROM {table} "
                            + "ORDER BY rowid DESC "
                            + "LIMIT 20"
                        )

                        rows = get_rows(
                            db,
                            sql,
                        )

                        if rows:

                            data = [
                                dict(row)
                                if hasattr(row, "keys")
                                else {
                                    select_columns[i]: row[i]
                                    for i in range(
                                        len(select_columns)
                                    )
                                }
                                for row in rows
                            ]

                            st.dataframe(
                                data,
                                use_container_width=True,
                            )

                        else:

                            st.warning(
                                "Записей нет."
                            )

                # ------------------------------------------------
                # GOLD DATASET
                # ------------------------------------------------

                elif table == "gold_dataset":

                    xg_columns = [
                        c
                        for c in columns
                        if "xg" in c.lower()
                    ]

                    st.write(
                        "**xG-колонки:**"
                    )

                    if xg_columns:
                        st.success(
                            ", ".join(xg_columns)
                        )
                    else:
                        st.warning(
                            "xG-колонки не найдены."
                        )

                    select_columns = safe_columns(
                        db,
                        table,
                        [
                            "id",
                            "match_id",
                            "actual_xg_home",
                            "actual_xg_away",
                            "actual_home_xg",
                            "actual_away_xg",
                            "created_at",
                        ],
                    )

                    if select_columns:

                        sql = (
                            "SELECT "
                            + ", ".join(
                                select_columns
                            )
                            + f" FROM {table} "
                            + "ORDER BY rowid DESC "
                            + "LIMIT 20"
                        )

                        rows = get_rows(
                            db,
                            sql,
                        )

                        if rows:

                            data = [
                                dict(row)
                                if hasattr(row, "keys")
                                else {
                                    select_columns[i]: row[i]
                                    for i in range(
                                        len(select_columns)
                                    )
                                }
                                for row in rows
                            ]

                            st.dataframe(
                                data,
                                use_container_width=True,
                            )

                # ------------------------------------------------
                # PREDICTION VALIDATION
                # ------------------------------------------------

                elif table == "prediction_validation":

                    xg_columns = [
                        c
                        for c in columns
                        if "xg" in c.lower()
                    ]

                    st.write(
                        "**xG-колонки:**"
                    )

                    if xg_columns:
                        st.success(
                            ", ".join(xg_columns)
                        )
                    else:
                        st.warning(
                            "xG-колонки не найдены."
                        )

                    select_columns = safe_columns(
                        db,
                        table,
                        [
                            "id",
                            "match_id",
                            "prediction_id",
                            "actual_home_xg",
                            "actual_away_xg",
                            "actual_xg_home",
                            "actual_xg_away",
                            "created_at",
                        ],
                    )

                    if select_columns:

                        sql = (
                            "SELECT "
                            + ", ".join(
                                select_columns
                            )
                            + f" FROM {table} "
                            + "ORDER BY rowid DESC "
                            + "LIMIT 20"
                        )

                        rows = get_rows(
                            db,
                            sql,
                        )

                        if rows:

                            data = [
                                dict(row)
                                if hasattr(row, "keys")
                                else {
                                    select_columns[i]: row[i]
                                    for i in range(
                                        len(select_columns)
                                    )
                                }
                                for row in rows
                            ]

                            st.dataframe(
                                data,
                                use_container_width=True,
                            )

                # ------------------------------------------------
                # XG MEMORY
                # ------------------------------------------------

                elif table == "xg_memory":

                    xg_columns = [
                        c
                        for c in columns
                        if "xg" in c.lower()
                    ]

                    st.write(
                        "**xG-колонки:**"
                    )

                    if xg_columns:
                        st.success(
                            ", ".join(xg_columns)
                        )
                    else:
                        st.caption(
                            "Специфические xG-колонки "
                            "по имени не обнаружены."
                        )

        # ====================================================
        # SUMMARY COUNTS
        # ====================================================

        st.markdown("### 📊 Количество фактического xG")

        stats_xg = 0
        gold_xg = 0
        validation_xg = 0

        if table_exists(
            db,
            "match_statistics",
        ):

            columns = get_table_columns(
                db,
                "match_statistics",
            )

            if "xg" in columns:

                rows = get_rows(
                    db,
                    """
                    SELECT COUNT(*)
                    FROM match_statistics
                    WHERE xg IS NOT NULL
                    """,
                )

                stats_xg = rows[0][0]

            elif (
                "home_xg" in columns
                and "away_xg" in columns
            ):

                rows = get_rows(
                    db,
                    """
                    SELECT COUNT(*)
                    FROM match_statistics
                    WHERE home_xg IS NOT NULL
                      AND away_xg IS NOT NULL
                    """,
                )

                stats_xg = rows[0][0]

        if table_exists(
            db,
            "gold_dataset",
        ):

            columns = get_table_columns(
                db,
                "gold_dataset",
            )

            if (
                "actual_xg_home" in columns
                and "actual_xg_away" in columns
            ):

                rows = get_rows(
                    db,
                    """
                    SELECT COUNT(*)
                    FROM gold_dataset
                    WHERE actual_xg_home IS NOT NULL
                      AND actual_xg_away IS NOT NULL
                    """,
                )

                gold_xg = rows[0][0]

        if table_exists(
            db,
            "prediction_validation",
        ):

            columns = get_table_columns(
                db,
                "prediction_validation",
            )

            if (
                "actual_home_xg" in columns
                and "actual_away_xg" in columns
            ):

                rows = get_rows(
                    db,
                    """
                    SELECT COUNT(*)
                    FROM prediction_validation
                    WHERE actual_home_xg IS NOT NULL
                      AND actual_away_xg IS NOT NULL
                    """,
                )

                validation_xg = rows[0][0]

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "match_statistics xG",
                stats_xg,
            )

        with c2:
            st.metric(
                "gold_dataset xG",
                gold_xg,
            )

        with c3:
            st.metric(
                "validation xG",
                validation_xg,
            )

    except Exception as exc:

        st.error(
            f"❌ Ошибка диагностики xG: {exc}"
        )

    st.divider()

    # ========================================================
    # 5. REAL MATCH -> RESULT -> xG
    # ========================================================

    st.subheader(
        "🔎 5. РЕАЛЬНЫЕ МАТЧИ: RESULT + FACTUAL xG"
    )

    try:

        db = FAJDatabase()

        if not table_exists(
            db,
            "match_results",
        ):

            st.error(
                "❌ match_results отсутствует"
            )

        elif not table_exists(
            db,
            "match_statistics",
        ):

            st.error(
                "❌ match_statistics отсутствует"
            )

        else:

            result_columns = get_table_columns(
                db,
                "match_results",
            )

            stats_columns = get_table_columns(
                db,
                "match_statistics",
            )

            if (
                "match_id" in result_columns
                and "match_id" in stats_columns
            ):

                # --------------------------------------------
                # САМЫЙ ВАЖНЫЙ ЗАПРОС
                # --------------------------------------------

                if (
                    "home_xg" in stats_columns
                    and "away_xg" in stats_columns
                ):

                    sql = """
                        SELECT
                            mr.match_id,
                            mr.home_goals,
                            mr.away_goals,
                            ms.home_xg,
                            ms.away_xg
                        FROM match_results mr
                        JOIN match_statistics ms
                          ON ms.match_id = mr.match_id
                        WHERE mr.home_goals IS NOT NULL
                          AND mr.away_goals IS NOT NULL
                          AND ms.home_xg IS NOT NULL
                          AND ms.away_xg IS NOT NULL
                        ORDER BY mr.match_id DESC
                        LIMIT 30
                    """

                elif "xg" in stats_columns:

                    sql = """
                        SELECT
                            mr.match_id,
                            mr.home_goals,
                            mr.away_goals,
                            ms.xg
                        FROM match_results mr
                        JOIN match_statistics ms
                          ON ms.match_id = mr.match_id
                        WHERE mr.home_goals IS NOT NULL
                          AND mr.away_goals IS NOT NULL
                          AND ms.xg IS NOT NULL
                        ORDER BY mr.match_id DESC
                        LIMIT 30
                    """

                else:

                    sql = None

                if sql:

                    rows = get_rows(
                        db,
                        sql,
                    )

                    if rows:

                        data = [
                            dict(row)
                            if hasattr(row, "keys")
                            else row
                            for row in rows
                        ]

                        st.success(
                            f"✅ Найдено связанных матчей: "
                            f"{len(data)}"
                        )

                        st.dataframe(
                            data,
                            use_container_width=True,
                        )

                    else:

                        st.warning(
                            "⚠️ Нет матчей, где одновременно "
                            "есть RESULT и фактический xG "
                            "в match_statistics."
                        )

                else:

                    st.warning(
                        "⚠️ В match_statistics не найдена "
                        "подходящая xG-колонка."
                    )

            else:

                st.warning(
                    "⚠️ Невозможно связать таблицы: "
                    "нет match_id."
                )

    except Exception as exc:

        st.error(
            f"❌ Ошибка проверки RESULT + xG: {exc}"
        )

    st.divider()

    # ========================================================
    # 6. LEARNING MEMORY
    # ========================================================

    st.subheader("🧠 6. Learning Memory")

    try:

        db = FAJDatabase()

        lm_count = get_table_count(
            db,
            "learning_memory",
        )

        le_count = get_table_count(
            db,
            "learning_events",
        )

        lr_count = get_table_count(
            db,
            "learning_records",
        )

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

        if table_exists(
            db,
            "learning_memory",
        ):

            columns = get_table_columns(
                db,
                "learning_memory",
            )

            if "event_type" in columns:

                rows = get_rows(
                    db,
                    """
                    SELECT
                        event_type,
                        COUNT(*) AS cnt
                    FROM learning_memory
                    GROUP BY event_type
                    ORDER BY cnt DESC
                    """,
                )

                if rows:

                    st.caption(
                        "Типы событий:"
                    )

                    for row in rows:

                        st.text(
                            f"• {row[0]}: {row[1]}"
                        )

        if (
            lm_count == 0
            and le_count == 0
            and lr_count == 0
        ):

            st.warning(
                "⚠️ Learning Memory пока пуста"
            )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка Learning Memory: {exc}"
        )

    st.divider()

    # ========================================================
    # 7. MODEL HISTORY
    # ========================================================

    st.subheader("📊 7. Model History")

    try:

        db = FAJDatabase()

        mp_count = get_table_count(
            db,
            "model_parameters",
        )

        ph_count = get_table_count(
            db,
            "parameter_history",
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "model_parameters",
                mp_count,
            )

        with col2:

            st.metric(
                "parameter_history",
                ph_count,
            )

        if table_exists(
            db,
            "predictions",
        ):

            columns = get_table_columns(
                db,
                "predictions",
            )

            if "model_version" in columns:

                rows = get_rows(
                    db,
                    """
                    SELECT
                        model_version,
                        COUNT(*) AS cnt
                    FROM predictions
                    WHERE model_version IS NOT NULL
                    GROUP BY model_version
                    ORDER BY cnt DESC
                    """,
                )

                if rows:

                    st.caption(
                        "Версии модели в predictions:"
                    )

                    for row in rows:

                        st.text(
                            f"• {row[0]}: {row[1]}"
                        )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка Model History: {exc}"
        )

    st.divider()

    # ========================================================
    # 8. MATCH SNAPSHOTS
    # ========================================================

    st.subheader("📸 8. Match Snapshots")

    try:

        db = FAJDatabase()

        snapshot_count = get_table_count(
            db,
            "match_snapshots",
        )

        st.metric(
            "match_snapshots",
            snapshot_count,
        )

        if snapshot_count > 0:

            st.success(
                "✅ Исторические snapshots существуют"
            )

        else:

            st.warning(
                "⚠️ Snapshots пока отсутствуют"
            )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка snapshots: {exc}"
        )

    st.divider()

    # ========================================================
    # 9. EVOLUTION READINESS
    # ========================================================

    st.subheader("🚀 9. Evolution Readiness")

    try:

        db = FAJDatabase()

        pred_count = get_table_count(
            db,
            "predictions",
        )

        res_count = get_table_count(
            db,
            "match_results",
        )

        lm_count = get_table_count(
            db,
            "learning_memory",
        )

        snapshot_count = get_table_count(
            db,
            "match_snapshots",
        )

        model_parameters = get_table_count(
            db,
            "model_parameters",
        )

        parameter_history = get_table_count(
            db,
            "parameter_history",
        )

        # --------------------------------------------
        # Full lifecycle
        # --------------------------------------------

        full_lifecycle = 0

        if (
            table_exists(db, "predictions")
            and table_exists(db, "match_results")
        ):

            rows = get_rows(
                db,
                """
                SELECT COUNT(DISTINCT p.match_id)
                FROM predictions p
                JOIN match_results mr
                  ON p.match_id = mr.match_id
                """,
            )

            if rows:
                full_lifecycle = rows[0][0]

        # --------------------------------------------
        # xG
        # --------------------------------------------

        has_xg = (
            stats_xg > 0
            or gold_xg > 0
            or validation_xg > 0
        )

        checks = [
            (
                "Прогнозы",
                pred_count > 0,
                pred_count,
            ),
            (
                "Фактические результаты",
                res_count > 0,
                res_count,
            ),
            (
                "Фактический xG",
                has_xg,
                stats_xg + gold_xg + validation_xg,
            ),
            (
                "Full Lifecycle",
                full_lifecycle > 0,
                full_lifecycle,
            ),
            (
                "Learning Memory",
                lm_count > 0,
                lm_count,
            ),
            (
                "Model History",
                (
                    model_parameters > 0
                    or parameter_history > 0
                ),
                model_parameters + parameter_history,
            ),
            (
                "Match Snapshots",
                snapshot_count > 0,
                snapshot_count,
            ),
        ]

        for name, ok, count in checks:

            icon = "✅" if ok else "❌"

            st.write(
                f"{icon} **{name}**: {count}"
            )

        st.divider()

        missing = [
            name
            for name, ok, _ in checks
            if not ok
        ]

        if not missing:

            st.success(
                "✅ Все диагностические компоненты присутствуют."
            )

        else:

            st.warning(
                "⚠️ Отсутствуют/пусты: "
                + ", ".join(missing)
            )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка Evolution Readiness: {exc}"
        )

    st.divider()

    # ========================================================
    # 10. DATA DIRECTORY
    # ========================================================

    st.subheader("📁 10. Содержимое data/")

    try:

        data_dir = os.path.dirname(
            DB_FILE
        )

        if os.path.exists(data_dir):

            files = os.listdir(
                data_dir
            )

            st.write(
                f"Директория: {data_dir}"
            )

            st.write(
                f"Файлы: {files}"
            )

        else:

            st.warning(
                f"Директория {data_dir} не существует"
            )

    except Exception as exc:

        st.error(
            f"❌ Ошибка: {exc}"
        )

    st.divider()

    # ========================================================
    # REFRESH
    # ========================================================

    if st.button(
        "🔄 Обновить диагностику",
        use_container_width=True,
    ):

        st.rerun()

    st.caption(
        "Диагностика работает только на чтение. "
        "База данных не изменяется."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
